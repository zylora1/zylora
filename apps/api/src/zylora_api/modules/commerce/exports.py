from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from io import BytesIO
from typing import Any, cast
from uuid import UUID
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.db.commerce_models import (
    ExportPrice,
    ExportPurchase,
    Payment,
    WebsiteExportArtifact,
)
from zylora_api.db.models import OutboxEvent
from zylora_api.db.website_models import Website, WebsiteVersion
from zylora_api.modules.commerce.export_schemas import (
    ExportPriceResponse,
    ExportPurchaseResponse,
)
from zylora_api.modules.commerce.schemas import MoneyResponse
from zylora_api.modules.commerce.service import region_for_country
from zylora_api.modules.publishing.artifacts import render_page
from zylora_api.modules.publishing.service import DeploymentService
from zylora_api.modules.templates.service import problem
from zylora_api.storage.base import ObjectStorage

EXPORT_ARTIFACT_TTL = timedelta(days=7)


def export_currency_for_country(country_code: str) -> str:
    return "INR" if region_for_country(country_code) == "INDIA" else "USD"


def price_response(price: ExportPrice) -> ExportPriceResponse:
    return ExportPriceResponse(
        id=price.id,
        currency=price.currency,
        amount_minor=price.amount_minor,
        active=price.active,
        version=price.version,
        effective_at=price.effective_at,
        created_at=price.created_at,
    )


def purchase_response(purchase: ExportPurchase) -> ExportPurchaseResponse:
    return ExportPurchaseResponse(
        id=purchase.id,
        website_id=purchase.website_id,
        website_version_id=purchase.website_version_id,
        status=purchase.state,
        price=MoneyResponse(amount_minor=purchase.amount_minor, currency=purchase.currency),
        created_at=purchase.created_at,
        paid_at=purchase.paid_at,
        ready_at=purchase.ready_at,
        expires_at=purchase.expires_at,
        failure_code=purchase.failure_code,
    )


class ExportPriceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def current(self, currency: str) -> ExportPrice | None:
        return cast(
            ExportPrice | None,
            await self.session.scalar(
                select(ExportPrice)
                .where(
                    ExportPrice.currency == currency,
                    ExportPrice.active.is_(True),
                    ExportPrice.effective_at <= datetime.now(UTC),
                )
                .order_by(ExportPrice.version.desc())
            ),
        )

    async def list_prices(self) -> list[ExportPrice]:
        return list(
            (
                await self.session.scalars(
                    select(ExportPrice).order_by(ExportPrice.currency, ExportPrice.version.desc())
                )
            ).all()
        )

    async def configure(
        self,
        *,
        currency: str,
        amount_minor: int,
        active: bool,
        configured_by_user_id: UUID,
    ) -> ExportPrice:
        if currency not in {"INR", "USD"} or amount_minor <= 0:
            raise problem(
                422,
                "invalid_export_price",
                "Export prices must use a positive supported amount.",
            )
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:currency, 0))"),
            {"currency": f"zylora-export-price:{currency}"},
        )
        current = await self.session.scalar(
            select(ExportPrice)
            .where(ExportPrice.currency == currency, ExportPrice.active.is_(True))
            .with_for_update()
        )
        latest = await self.session.scalar(
            select(func.max(ExportPrice.version)).where(ExportPrice.currency == currency)
        )
        if active and current:
            current.active = False
        price = ExportPrice(
            currency=currency,
            amount_minor=amount_minor,
            active=active,
            version=int(latest or 0) + 1,
            effective_at=datetime.now(UTC),
            configured_by_user_id=configured_by_user_id,
        )
        self.session.add(price)
        await self.session.flush()
        return price


class ExportService:
    def __init__(self, session: AsyncSession, storage: ObjectStorage | None = None) -> None:
        self.session = session
        self.storage = storage
        self.prices = ExportPriceService(session)

    async def create_purchase(
        self,
        website_id: UUID,
        owner_user_id: UUID,
        country_code: str,
        idempotency_key: str,
    ) -> ExportPurchase:
        existing = await self.session.scalar(
            select(ExportPurchase)
            .where(
                ExportPurchase.owner_user_id == owner_user_id,
                ExportPurchase.idempotency_key == idempotency_key,
            )
            .with_for_update()
        )
        if existing:
            if existing.website_id != website_id:
                raise problem(
                    409,
                    "idempotency_key_reused",
                    "This idempotency key was already used for another Website export.",
                )
            return existing
        website = await self.session.scalar(
            select(Website)
            .where(Website.id == website_id, Website.owner_user_id == owner_user_id)
            .with_for_update()
        )
        if not website:
            raise problem(404, "website_not_found", "Website not found.")
        if not website.current_version_id:
            raise problem(
                409,
                "website_revision_missing",
                "Save a valid Website revision before creating an export purchase.",
            )
        version = await self.session.scalar(
            select(WebsiteVersion).where(
                WebsiteVersion.id == website.current_version_id,
                WebsiteVersion.website_id == website.id,
            )
        )
        if not version:
            raise problem(409, "website_revision_missing", "Website revision needs review.")
        currency = export_currency_for_country(country_code)
        price = await self.prices.current(currency)
        if not price:
            raise problem(
                503,
                "export_price_unavailable",
                "Website ZIP export is not available for your billing region yet.",
            )
        purchase = ExportPurchase(
            website_id=website.id,
            owner_user_id=owner_user_id,
            website_version_id=version.id,
            website_version_checksum=version.checksum,
            export_price_id=price.id,
            price_version=price.version,
            amount_minor=price.amount_minor,
            currency=price.currency,
            state="CREATED",
            idempotency_key=idempotency_key,
        )
        self.session.add(purchase)
        await self.session.flush()
        return purchase

    async def get_for_owner(self, purchase_id: UUID, owner_user_id: UUID) -> ExportPurchase:
        purchase = await self.session.scalar(
            select(ExportPurchase)
            .join(Website, Website.id == ExportPurchase.website_id)
            .where(
                ExportPurchase.id == purchase_id,
                ExportPurchase.owner_user_id == owner_user_id,
                Website.owner_user_id == owner_user_id,
            )
        )
        if not purchase:
            raise problem(404, "website_export_not_found", "Website export not found.")
        return purchase

    async def checkout(
        self, purchase_id: UUID, owner_user_id: UUID
    ) -> tuple[ExportPurchase, Payment]:
        purchase = await self.session.scalar(
            select(ExportPurchase)
            .join(Website, Website.id == ExportPurchase.website_id)
            .where(
                ExportPurchase.id == purchase_id,
                ExportPurchase.owner_user_id == owner_user_id,
                Website.owner_user_id == owner_user_id,
            )
            .with_for_update()
        )
        if not purchase:
            raise problem(404, "website_export_not_found", "Website export not found.")
        payment = await self.session.scalar(
            select(Payment).where(Payment.export_purchase_id == purchase.id).with_for_update()
        )
        if payment:
            return purchase, payment
        if purchase.state != "CREATED":
            raise problem(
                409,
                "export_checkout_not_available",
                "This Website export cannot start a new checkout.",
            )
        payment = Payment(
            user_id=owner_user_id,
            export_purchase_id=purchase.id,
            purpose="EXPORT",
            state="CREATED",
            expected_amount_minor=purchase.amount_minor,
            expected_currency=purchase.currency,
            provider="UNSELECTED",
            idempotency_key=f"export:{purchase.id}",
        )
        purchase.state = "PAYMENT_PENDING"
        self.session.add(payment)
        await self.session.flush()
        return purchase, payment

    async def queue_generation(
        self, purchase_id: UUID, owner_user_id: UUID, correlation_id: str
    ) -> tuple[ExportPurchase, bool]:
        purchase = await self.session.scalar(
            select(ExportPurchase)
            .join(Website, Website.id == ExportPurchase.website_id)
            .where(
                ExportPurchase.id == purchase_id,
                ExportPurchase.owner_user_id == owner_user_id,
                Website.owner_user_id == owner_user_id,
            )
            .with_for_update()
        )
        if not purchase:
            raise problem(404, "website_export_not_found", "Website export not found.")
        if purchase.state in {"GENERATING", "READY"}:
            return purchase, False
        if purchase.state != "PAID":
            raise problem(
                409,
                "export_payment_required",
                "A verified payment is required before Website ZIP generation.",
            )
        purchase.state = "GENERATING"
        purchase.generation_requested_at = datetime.now(UTC)
        self.session.add(
            OutboxEvent(
                aggregate_type="EXPORT_PURCHASE",
                aggregate_id=purchase.id,
                event_type="export.generate_requested",
                payload={"purchase_id": str(purchase.id)},
                correlation_id=correlation_id,
            )
        )
        return purchase, True

    async def process_outbox_event(self, event_id: UUID) -> OutboxEvent:
        event = await self.session.scalar(
            select(OutboxEvent).where(OutboxEvent.id == event_id).with_for_update()
        )
        if not event:
            raise problem(404, "export_event_not_found", "Website export event not found.")
        if event.state == "PUBLISHED":
            return event
        event.attempts += 1
        try:
            if event.event_type != "export.generate_requested":
                raise problem(
                    409, "unsupported_export_event", "Website export event is unsupported."
                )
            await self.generate(UUID(str(event.payload["purchase_id"])))
            event.state = "PUBLISHED"
            event.published_at = datetime.now(UTC)
            event.last_error_code = None
        except Exception:
            event.state = "FAILED"
            event.last_error_code = "export_generation_failed"
            purchase_id = event.payload.get("purchase_id")
            if purchase_id:
                purchase = await self.session.scalar(
                    select(ExportPurchase)
                    .where(ExportPurchase.id == UUID(str(purchase_id)))
                    .with_for_update()
                )
                if purchase and purchase.state == "GENERATING":
                    purchase.state = "FAILED"
                    purchase.failure_code = "export_generation_failed"
                    purchase.safe_error = "Zylora could not generate this Website export safely."
        finally:
            event.lease_owner = None
            event.leased_until = None
        return event

    async def generate(self, purchase_id: UUID) -> WebsiteExportArtifact:
        if not self.storage:
            raise RuntimeError("Private object storage is not configured.")
        purchase = await self.session.scalar(
            select(ExportPurchase).where(ExportPurchase.id == purchase_id).with_for_update()
        )
        if not purchase:
            raise problem(404, "website_export_not_found", "Website export not found.")
        existing = await self.session.scalar(
            select(WebsiteExportArtifact)
            .where(WebsiteExportArtifact.purchase_id == purchase.id)
            .with_for_update()
        )
        now = datetime.now(UTC)
        if existing and existing.expires_at > now:
            purchase.state = "READY"
            purchase.ready_at = purchase.ready_at or now
            purchase.expires_at = existing.expires_at
            return existing
        if purchase.state not in {"GENERATING", "PAID"}:
            raise problem(
                409,
                "export_generation_not_expected",
                "Website export generation is not expected for this purchase.",
            )
        website = await self.session.scalar(
            select(Website)
            .where(
                Website.id == purchase.website_id,
                Website.owner_user_id == purchase.owner_user_id,
            )
            .with_for_update()
        )
        version = await self.session.scalar(
            select(WebsiteVersion).where(
                WebsiteVersion.id == purchase.website_version_id,
                WebsiteVersion.website_id == purchase.website_id,
                WebsiteVersion.checksum == purchase.website_version_checksum,
            )
        )
        if not website or not version:
            purchase.state = "FAILED"
            purchase.failure_code = "export_source_unavailable"
            purchase.safe_error = "The purchased Website revision is no longer available."
            raise problem(409, purchase.failure_code, purchase.safe_error)
        archive, manifest = self._build_archive(version)
        checksum = sha256(archive).hexdigest()
        object_key = f"website-exports/{purchase.id}/{checksum}.zip"
        metadata = self.storage.put_bytes(object_key, archive, "application/zip")
        expires_at = now + EXPORT_ARTIFACT_TTL
        artifact = existing or WebsiteExportArtifact(
            purchase_id=purchase.id,
            object_key=metadata.key,
            checksum_sha256=checksum,
            byte_size=metadata.size,
            manifest=manifest,
            expires_at=expires_at,
        )
        if existing:
            existing.object_key = metadata.key
            existing.checksum_sha256 = checksum
            existing.byte_size = metadata.size
            existing.manifest = manifest
            existing.expires_at = expires_at
            artifact = existing
        else:
            self.session.add(artifact)
        purchase.state = "READY"
        purchase.ready_at = now
        purchase.expires_at = expires_at
        purchase.failure_code = None
        purchase.safe_error = None
        return artifact

    async def artifact_for_download(
        self, purchase_id: UUID, owner_user_id: UUID
    ) -> WebsiteExportArtifact:
        purchase = await self.session.scalar(
            select(ExportPurchase)
            .join(Website, Website.id == ExportPurchase.website_id)
            .where(
                ExportPurchase.id == purchase_id,
                ExportPurchase.owner_user_id == owner_user_id,
                Website.owner_user_id == owner_user_id,
            )
            .with_for_update()
        )
        if not purchase:
            raise problem(404, "website_export_not_found", "Website export not found.")
        artifact = await self.session.scalar(
            select(WebsiteExportArtifact)
            .where(WebsiteExportArtifact.purchase_id == purchase.id)
            .with_for_update()
        )
        now = datetime.now(UTC)
        if purchase.state != "READY" or not artifact or artifact.expires_at <= now:
            if purchase.state == "READY":
                purchase.state = "EXPIRED"
            raise problem(
                409,
                "website_export_not_ready",
                "This Website export is not available for download.",
            )
        artifact.download_count += 1
        artifact.last_downloaded_at = now
        return artifact

    @staticmethod
    def _build_archive(version: WebsiteVersion) -> tuple[bytes, dict[str, Any]]:
        pages = DeploymentService._snapshot_pages(version)
        navigation = [
            (str(page.get("name") or page.get("label") or "Page"), str(page.get("path") or "/"))
            for page in pages
            if page.get("show_in_navigation") is True
        ]
        files: list[dict[str, str]] = []
        stream = BytesIO()
        with ZipFile(stream, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
            for page in sorted(pages, key=lambda item: str(item.get("path") or "/")):
                path = str(page.get("path") or "/")
                filename = "index.html" if path == "/" else f"{path.strip('/')}/index.html"
                ExportService._write_archive_file(
                    archive, filename, render_page(page, navigation, include_chatbot=False)
                )
                files.append({"path": path, "file": filename})
            manifest = {
                "schema": "ZYLORA_WEBSITE_EXPORT_V1",
                "website_version_checksum": version.checksum,
                "files": files,
            }
            ExportService._write_archive_file(
                archive,
                "manifest.json",
                json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode(),
            )
            ExportService._write_archive_file(
                archive,
                "README.txt",
                b"Zylora Website Export\n\nThis archive contains static Website files only.\n",
            )
        return stream.getvalue(), manifest

    @staticmethod
    def _write_archive_file(archive: ZipFile, filename: str, data: bytes) -> None:
        info = ZipInfo(filename, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        archive.writestr(info, data)
