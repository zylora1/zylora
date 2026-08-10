from __future__ import annotations

import ipaddress
import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.core.config import get_settings
from zylora_api.db.auth_models import User
from zylora_api.db.deployment_models import Deployment, DeploymentEvent, Domain
from zylora_api.db.models import OutboxEvent
from zylora_api.db.website_models import Website, WebsitePagePathChange, WebsiteVersion
from zylora_api.modules.analytics.service import AnalyticsService
from zylora_api.modules.commerce.service import SubscriptionService
from zylora_api.modules.notifications.service import NotificationService
from zylora_api.modules.publishing.artifacts import ArtifactBuilder
from zylora_api.modules.publishing.providers import DomainProvider, DomainProviderError
from zylora_api.modules.templates.service import problem

HOST_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
RESERVED_HOSTS = frozenset({"admin", "api", "app", "mail", "support", "www"})


def normalize_hostname(value: str) -> str:
    candidate = value.strip().rstrip(".")
    if not candidate or value != value.strip() or "/" in candidate:
        raise problem(422, "invalid_domain_hostname", "Enter a valid domain hostname.")
    try:
        normalized = candidate.encode("idna").decode("ascii").casefold()
        ipaddress.ip_address(normalized)
    except ValueError:
        pass
    else:
        raise problem(422, "invalid_domain_hostname", "An IP address cannot be used as a domain.")
    labels = normalized.split(".")
    if (
        len(labels) < 2
        or len(normalized) > 253
        or any(not HOST_LABEL.fullmatch(item) for item in labels)
    ):
        raise problem(422, "invalid_domain_hostname", "Enter a valid domain hostname.")
    return normalized


def _is_failed_provider_state(state: str) -> bool:
    return state in {"FAILED", "BLOCKED", "PENDING_BLOCKED", "TEST_BLOCKED"}


class DomainService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_owner(self, website_id: UUID, owner_user_id: UUID) -> list[Domain]:
        return list(
            (
                await self.session.scalars(
                    select(Domain)
                    .where(Domain.website_id == website_id, Domain.owner_user_id == owner_user_id)
                    .order_by(Domain.created_at.desc())
                )
            ).all()
        )

    async def create_custom(
        self,
        website_id: UUID,
        owner_user_id: UUID,
        hostname: str,
        idempotency_key: str,
        provider: DomainProvider,
    ) -> Domain:
        website = await self.session.scalar(
            select(Website)
            .where(Website.id == website_id, Website.owner_user_id == owner_user_id)
            .with_for_update()
        )
        if not website:
            raise problem(404, "website_not_found", "Website not found.")
        user = await self.session.get(User, owner_user_id)
        if not user:
            raise problem(404, "user_not_found", "User not found.")
        effective = await SubscriptionService(self.session).effective(
            owner_user_id, user.billing_country_code
        )
        if effective.entitlements.get("custom_domain") is not True:
            raise problem(
                403,
                "custom_domain_not_entitled",
                "Your current plan does not include custom domains.",
            )
        normalized = normalize_hostname(hostname)
        settings = get_settings()
        if normalized == settings.published_site_base_domain or normalized.endswith(
            f".{settings.published_site_base_domain}"
        ):
            raise problem(409, "reserved_domain_hostname", "That hostname is reserved by Zylora.")
        existing = await self.session.scalar(select(Domain).where(Domain.hostname == normalized))
        if existing:
            if existing.website_id == website_id and existing.owner_user_id == owner_user_id:
                return existing
            raise problem(409, "domain_hostname_taken", "That domain is already reserved.")
        try:
            remote = await provider.create_custom(normalized, idempotency_key)
        except DomainProviderError as error:
            raise problem(503, error.code, error.safe_message) from error
        domain = Domain(
            website_id=website.id,
            owner_user_id=owner_user_id,
            type="CUSTOM",
            hostname=normalized,
            display_hostname=hostname.strip(),
            state="VERIFICATION_FAILED"
            if _is_failed_provider_state(remote.state)
            else "PENDING_DNS",
            verification_record_name=remote.verification_name,
            verification_record_type=remote.verification_type,
            verification_record_value=remote.verification_value,
            provider_hostname_id=remote.provider_id,
            provider_reference=remote.provider_id,
            tls_status=remote.tls_status,
            failure_code="cloudflare_verification_failed"
            if _is_failed_provider_state(remote.state)
            else None,
            safe_error="Cloudflare could not verify this domain."
            if _is_failed_provider_state(remote.state)
            else None,
        )
        self.session.add(domain)
        await self.session.flush()
        return domain

    async def verify_custom(
        self, domain_id: UUID, owner_user_id: UUID, provider: DomainProvider
    ) -> Domain:
        domain = await self.session.scalar(
            select(Domain)
            .where(
                Domain.id == domain_id,
                Domain.owner_user_id == owner_user_id,
                Domain.type == "CUSTOM",
            )
            .with_for_update()
        )
        if not domain:
            raise problem(404, "domain_not_found", "Custom domain not found.")
        if not domain.provider_hostname_id:
            raise problem(409, "domain_provider_state_invalid", "Domain verification is not ready.")
        try:
            remote = await provider.inspect(
                domain.provider_hostname_id, domain.hostname, domain.type
            )
        except DomainProviderError as error:
            raise problem(503, error.code, error.safe_message) from error
        domain.last_checked_at = datetime.now(UTC)
        domain.tls_status = remote.tls_status
        domain.version += 1
        if remote.state == "ACTIVE" and remote.tls_status == "ACTIVE":
            domain.state = "VERIFIED"
            domain.failure_code = None
            domain.safe_error = None
        elif _is_failed_provider_state(remote.state):
            domain.state = "VERIFICATION_FAILED"
            domain.failure_code = "cloudflare_verification_failed"
            domain.safe_error = (
                "Cloudflare could not verify this domain. Check the DNS record and retry."
            )
        else:
            domain.state = "PENDING_DNS"
        return domain

    async def reserve_for_publish(
        self,
        website: Website,
        domain_type: str,
        hostname: str | None,
    ) -> Domain:
        if domain_type == "CUSTOM":
            if not hostname:
                raise problem(
                    422, "custom_domain_hostname_required", "Enter a verified custom domain."
                )
            domain = await self.session.scalar(
                select(Domain)
                .where(
                    Domain.website_id == website.id,
                    Domain.owner_user_id == website.owner_user_id,
                    Domain.hostname == normalize_hostname(hostname),
                    Domain.type == "CUSTOM",
                )
                .with_for_update()
            )
            if not domain or domain.state != "VERIFIED":
                raise problem(
                    409,
                    "domain_verification_required",
                    "Verify the custom domain before publishing this Website.",
                )
            return domain
        if hostname is not None:
            raise problem(
                422,
                "zylora_subdomain_generated",
                "Zylora subdomains are assigned safely by Zylora.",
            )
        suffix = normalize_hostname(get_settings().published_site_base_domain)
        generated = f"w-{website.id.hex[:12]}.{suffix}"
        existing_domain: Domain | None = await self.session.scalar(
            select(Domain)
            .where(Domain.website_id == website.id, Domain.type == "ZYLORA_SUBDOMAIN")
            .with_for_update()
        )
        if existing_domain:
            return existing_domain
        domain = Domain(
            website_id=website.id,
            owner_user_id=website.owner_user_id,
            type="ZYLORA_SUBDOMAIN",
            hostname=generated,
            display_hostname=generated,
            state="RESERVED",
        )
        self.session.add(domain)
        await self.session.flush()
        return domain


class DeploymentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.domains = DomainService(session)

    async def queue_publish(
        self,
        website: Website,
        domain_type: str,
        hostname: str | None,
        idempotency_key: str,
        correlation_id: str,
    ) -> Deployment:
        existing = await self.session.scalar(
            select(Deployment).where(
                Deployment.website_id == website.id,
                Deployment.idempotency_key == idempotency_key,
            )
        )
        if existing:
            return existing
        if not website.current_version_id:
            raise problem(
                409, "website_revision_missing", "This Website has no valid revision to publish."
            )
        domain = await self.domains.reserve_for_publish(website, domain_type, hostname)
        deployment = Deployment(
            website_id=website.id,
            owner_user_id=website.owner_user_id,
            website_version_id=website.current_version_id,
            domain_id=domain.id,
            previous_deployment_id=website.active_deployment_id,
            operation="PUBLISH",
            state="QUEUED",
            idempotency_key=idempotency_key,
        )
        self.session.add(deployment)
        await self.session.flush()
        self._event(deployment, None, "QUEUED", "USER", str(website.owner_user_id), correlation_id)
        website.status = "PUBLISHING"
        website.live_owner_user_id = website.owner_user_id
        website.publication_domain_type = domain_type
        website.publish_request_idempotency_key = idempotency_key
        self.session.add(
            OutboxEvent(
                aggregate_type="DEPLOYMENT",
                aggregate_id=deployment.id,
                event_type="deployment.publish_requested",
                payload={"deployment_id": str(deployment.id)},
                correlation_id=correlation_id,
            )
        )
        return deployment

    async def cancel_pending_publish(
        self, website: Website, correlation_id: str
    ) -> Deployment | None:
        deployment = await self.session.scalar(
            select(Deployment)
            .where(
                Deployment.website_id == website.id,
                Deployment.state.in_(
                    ("QUEUED", "VALIDATING", "BUILDING", "PROVISIONING", "HEALTH_CHECKING")
                ),
            )
            .with_for_update()
        )
        if not deployment:
            return None
        self._transition(deployment, "CANCELLED", correlation_id)
        deployment.completed_at = datetime.now(UTC)
        return deployment

    async def queue_rollback(
        self,
        website_id: UUID,
        owner_user_id: UUID,
        target_deployment_id: UUID,
        idempotency_key: str,
        correlation_id: str,
    ) -> Deployment:
        website = await self.session.scalar(
            select(Website)
            .where(Website.id == website_id, Website.owner_user_id == owner_user_id)
            .with_for_update()
        )
        if not website or website.status != "PUBLISHED" or not website.active_deployment_id:
            raise problem(
                409, "rollback_not_available", "A live Website deployment is required to roll back."
            )
        target = await self.session.scalar(
            select(Deployment).where(
                Deployment.id == target_deployment_id,
                Deployment.website_id == website.id,
                Deployment.state.in_(("SUPERSEDED", "ACTIVE")),
            )
        )
        if not target:
            raise problem(404, "rollback_target_not_found", "That deployment cannot be restored.")
        current = await self.session.get(Deployment, website.active_deployment_id)
        domain = await self.session.get(Domain, current.domain_id if current else None)
        if not current or not domain or not domain.is_active:
            raise problem(
                409, "rollback_not_available", "The active deployment route is unavailable."
            )
        deployment = Deployment(
            website_id=website.id,
            owner_user_id=owner_user_id,
            website_version_id=target.website_version_id,
            domain_id=domain.id,
            previous_deployment_id=current.id,
            operation="ROLLBACK",
            state="QUEUED",
            idempotency_key=idempotency_key,
        )
        self.session.add(deployment)
        await self.session.flush()
        self._event(deployment, None, "QUEUED", "USER", str(owner_user_id), correlation_id)
        website.status = "PUBLISHING"
        website.publish_request_idempotency_key = idempotency_key
        self.session.add(
            OutboxEvent(
                aggregate_type="DEPLOYMENT",
                aggregate_id=deployment.id,
                event_type="deployment.rollback_requested",
                payload={"deployment_id": str(deployment.id)},
                correlation_id=correlation_id,
            )
        )
        return deployment

    def _event(
        self,
        deployment: Deployment,
        before: str | None,
        after: str,
        actor_type: str,
        actor_id: str | None,
        correlation_id: str,
        evidence: dict[str, object] | None = None,
    ) -> None:
        self.session.add(
            DeploymentEvent(
                deployment_id=deployment.id,
                from_state=before,
                to_state=after,
                actor_type=actor_type,
                actor_id=actor_id,
                correlation_id=correlation_id,
                evidence=evidence or {},
            )
        )

    def _transition(self, deployment: Deployment, after: str, correlation_id: str) -> None:
        before = deployment.state
        deployment.state = after
        self._event(deployment, before, after, "WORKER", None, correlation_id)

    @staticmethod
    def _snapshot_pages(version: WebsiteVersion) -> list[dict[str, object]]:
        raw_pages = [dict(item) for item in version.page_state if isinstance(item, dict)]
        by_id = {str(page["id"]): page for page in raw_pages if page.get("id")}

        def path_for(page: dict[str, object], visited: set[str] | None = None) -> str:
            if page.get("is_home") is True:
                return "/"
            current_id = str(page.get("id"))
            seen = visited or set()
            if current_id in seen:
                raise problem(
                    409, "page_hierarchy_cycle", "The published page hierarchy is invalid."
                )
            parent_id = page.get("parent_page_id")
            parent = by_id.get(str(parent_id)) if parent_id else None
            segment = str(page.get("slug") or "")
            if not segment:
                raise problem(
                    409, "published_page_slug_invalid", "The published page URL is invalid."
                )
            return (
                (path_for(parent, seen | {current_id}).rstrip("/") if parent else "")
                + "/"
                + segment
            )

        result: list[dict[str, object]] = []
        for page in raw_pages:
            raw_content = page.get("content")
            content: dict[str, object] = raw_content if isinstance(raw_content, dict) else {}
            result.append(
                {
                    **page,
                    "path": path_for(page),
                    "components": content.get("components", []),
                }
            )
        if len([page for page in result if page.get("is_home") is True]) != 1:
            raise problem(
                409,
                "published_home_page_invalid",
                "The published Website needs exactly one home page.",
            )
        return result

    async def _failure(
        self,
        deployment: Deployment,
        website: Website,
        domain: Domain,
        correlation_id: str,
        code: str,
        safe_message: str,
    ) -> Deployment:
        deployment.failure_code = code
        deployment.safe_error = safe_message
        deployment.completed_at = datetime.now(UTC)
        self._transition(deployment, "FAILED", correlation_id)
        previous = (
            await self.session.get(Deployment, deployment.previous_deployment_id)
            if deployment.previous_deployment_id
            else None
        )
        if previous and previous.state == "ACTIVE":
            website.status = "PUBLISHED"
            website.active_deployment_id = previous.id
            website.published_version_id = previous.website_version_id
            website.live_owner_user_id = website.owner_user_id
            domain.state = "ACTIVE"
            domain.is_active = True
        else:
            website.status = "FAILED"
            website.active_deployment_id = None
            website.live_owner_user_id = None
            website.publication_domain_type = None
            website.publish_request_idempotency_key = None
            domain.state = "PROVISIONING_FAILED"
            domain.is_active = False
        domain.failure_code = code
        domain.safe_error = safe_message
        domain.version += 1
        await NotificationService(self.session).create(
            recipient_user_id=website.owner_user_id,
            notification_type="WEBSITE_PUBLISH_FAILED",
            resource_type="deployment",
            resource_id=deployment.id,
            dedupe_key=f"deployment-failed:{deployment.id}",
            data={"website_id": str(website.id)},
        )
        return deployment

    async def process_publish(
        self,
        deployment_id: UUID,
        provider: DomainProvider,
        artifacts: ArtifactBuilder,
        correlation_id: str,
    ) -> Deployment:
        deployment = await self.session.scalar(
            select(Deployment).where(Deployment.id == deployment_id).with_for_update()
        )
        if not deployment:
            raise problem(404, "deployment_not_found", "Deployment not found.")
        if deployment.state in {"ACTIVE", "FAILED", "CANCELLED", "SUPERSEDED"}:
            return deployment
        website = await self.session.scalar(
            select(Website).where(Website.id == deployment.website_id).with_for_update()
        )
        domain = await self.session.scalar(
            select(Domain).where(Domain.id == deployment.domain_id).with_for_update()
        )
        version = await self.session.get(WebsiteVersion, deployment.website_version_id)
        if not website or not domain or not version:
            raise problem(409, "deployment_source_missing", "The deployment source is unavailable.")
        try:
            deployment.started_at = deployment.started_at or datetime.now(UTC)
            self._transition(deployment, "VALIDATING", correlation_id)
            pages = self._snapshot_pages(version)
            redirects = {
                item.old_path: item.new_path
                for item in (
                    await self.session.scalars(
                        select(WebsitePagePathChange).where(
                            WebsitePagePathChange.website_id == website.id
                        )
                    )
                ).all()
            }
            self._transition(deployment, "BUILDING", correlation_id)
            artifact = artifacts.build(deployment.id, pages, redirects)
            deployment.artifact_key = artifact.manifest_key
            deployment.artifact_checksum = artifact.checksum
            self._transition(deployment, "PROVISIONING", correlation_id)
            if domain.type == "ZYLORA_SUBDOMAIN":
                remote = (
                    await provider.inspect(
                        domain.provider_hostname_id, domain.hostname, domain.type
                    )
                    if domain.provider_hostname_id
                    else await provider.provision_subdomain(
                        domain.hostname, deployment.idempotency_key
                    )
                )
                domain.provider_hostname_id = remote.provider_id
                domain.provider_reference = remote.provider_id
            else:
                if domain.state != "VERIFIED" or not domain.provider_hostname_id:
                    raise DomainProviderError(
                        "domain_verification_required", "Verify the custom domain first."
                    )
                remote = await provider.inspect(
                    domain.provider_hostname_id, domain.hostname, domain.type
                )
                if remote.state != "ACTIVE" or remote.tls_status != "ACTIVE":
                    raise DomainProviderError(
                        "domain_verification_pending", "Cloudflare has not activated this domain."
                    )
            domain.state = "PROVISIONING"
            domain.tls_status = remote.tls_status
            domain.is_primary = True
            domain.version += 1
            self._transition(deployment, "HEALTH_CHECKING", correlation_id)
            if not await provider.health(domain.hostname, deployment.id):
                raise DomainProviderError(
                    "deployment_health_check_failed", "The new Website did not pass health checks."
                )
            deployment.health_checked_at = datetime.now(UTC)
            self._transition(deployment, "SWITCHING", correlation_id)
            previous = (
                await self.session.get(Deployment, deployment.previous_deployment_id)
                if deployment.previous_deployment_id
                else None
            )
            if previous and previous.state == "ACTIVE":
                self._transition(previous, "SUPERSEDED", correlation_id)
            self._transition(deployment, "ACTIVE", correlation_id)
            deployment.switched_at = datetime.now(UTC)
            deployment.completed_at = deployment.switched_at
            domain.state = "ACTIVE"
            domain.tls_status = "ACTIVE"
            domain.is_active = True
            domain.failure_code = None
            domain.safe_error = None
            domain.last_checked_at = deployment.health_checked_at
            domain.version += 1
            website.status = "PUBLISHED"
            website.active_deployment_id = deployment.id
            website.published_version_id = deployment.website_version_id
            website.live_owner_user_id = website.owner_user_id
            website.publication_domain_type = domain.type
            from zylora_api.modules.chatbot.indexing import KnowledgeIndexService

            await KnowledgeIndexService(
                self.session, artifacts.storage, get_settings()
            ).request_for_published_website(website, deployment.website_version_id, correlation_id)
            await AnalyticsService(self.session).record(
                website_id=website.id,
                owner_user_id=website.owner_user_id,
                event_type="WEBSITE_PUBLISHED",
                idempotency_key=f"website-published:{deployment.id}",
                properties={"operation": deployment.operation},
            )
            await NotificationService(self.session).create(
                recipient_user_id=website.owner_user_id,
                notification_type="WEBSITE_PUBLISHED",
                resource_type="deployment",
                resource_id=deployment.id,
                dedupe_key=f"deployment-published:{deployment.id}",
                data={"website_id": str(website.id)},
            )
            return deployment
        except DomainProviderError as error:
            return await self._failure(
                deployment, website, domain, correlation_id, error.code, error.safe_message
            )
        except Exception:
            return await self._failure(
                deployment,
                website,
                domain,
                correlation_id,
                "deployment_failed",
                "Zylora could not complete the deployment safely.",
            )

    async def process_unpublish(
        self,
        website_id: UUID,
        provider: DomainProvider,
        correlation_id: str,
    ) -> Website:
        website = await self.session.scalar(
            select(Website).where(Website.id == website_id).with_for_update()
        )
        if not website or website.status != "UNPUBLISHING" or not website.active_deployment_id:
            raise problem(409, "invalid_website_state", "Unpublish confirmation is not expected.")
        deployment = await self.session.get(Deployment, website.active_deployment_id)
        domain = await self.session.get(Domain, deployment.domain_id if deployment else None)
        if not deployment or not domain:
            raise problem(409, "deployment_source_missing", "The active deployment is unavailable.")
        domain.state = "DEACTIVATING"
        try:
            await provider.deactivate(domain.provider_hostname_id or "", domain.type)
        except DomainProviderError as error:
            domain.state = "ACTIVE"
            domain.failure_code = error.code
            domain.safe_error = error.safe_message
            website.status = "PUBLISHED"
            raise
        domain.state = "INACTIVE"
        domain.is_active = False
        domain.is_primary = False
        domain.version += 1
        self._event(deployment, deployment.state, "ROUTE_INACTIVE", "WORKER", None, correlation_id)
        website.status = "UNPUBLISHED"
        website.active_deployment_id = None
        website.live_owner_user_id = None
        website.publication_domain_type = None
        website.publish_request_idempotency_key = None
        return website

    async def process_outbox_event(
        self,
        event_id: UUID,
        provider: DomainProvider,
        artifacts: ArtifactBuilder,
    ) -> OutboxEvent:
        event = await self.session.scalar(
            select(OutboxEvent).where(OutboxEvent.id == event_id).with_for_update()
        )
        if not event:
            raise problem(404, "publication_event_not_found", "Publication event not found.")
        if event.state == "PUBLISHED":
            return event
        event.attempts += 1
        try:
            if event.event_type in {
                "deployment.publish_requested",
                "deployment.rollback_requested",
            }:
                await self.process_publish(
                    UUID(str(event.payload["deployment_id"])),
                    provider,
                    artifacts,
                    event.correlation_id,
                )
            elif event.event_type == "website.unpublish_requested":
                await self.process_unpublish(event.aggregate_id, provider, event.correlation_id)
                transfer_id = event.payload.get("transfer_id")
                if transfer_id:
                    from zylora_api.modules.commerce.ownership import OwnershipService

                    await OwnershipService(self.session).complete_after_unpublish(
                        UUID(str(transfer_id))
                    )
            else:
                raise problem(
                    409, "unsupported_publication_event", "Publication event is unsupported."
                )
            event.state = "PUBLISHED"
            event.published_at = datetime.now(UTC)
            event.last_error_code = None
        except DomainProviderError as error:
            event.state = "FAILED"
            event.last_error_code = error.code
            transfer_id = event.payload.get("transfer_id")
            if transfer_id:
                from zylora_api.modules.commerce.ownership import OwnershipService

                await OwnershipService(self.session).fail_after_unpublish(
                    UUID(str(transfer_id)), error.code
                )
        except Exception:
            event.state = "FAILED"
            event.last_error_code = "publication_processing_failed"
            transfer_id = event.payload.get("transfer_id")
            if transfer_id:
                from zylora_api.modules.commerce.ownership import OwnershipService

                await OwnershipService(self.session).fail_after_unpublish(
                    UUID(str(transfer_id)), "publication_processing_failed"
                )
        finally:
            event.lease_owner = None
            event.leased_until = None
        return event
