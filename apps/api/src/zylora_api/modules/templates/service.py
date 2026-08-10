from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from zylora_api.db.template_models import (
    Template,
    TemplateAsset,
    TemplateCategory,
    TemplateTag,
    TemplateTagAssignment,
    TemplateValidation,
    TemplateVersion,
)
from zylora_api.modules.auth.errors import AuthProblem
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.templates.document import REGISTRY_VERSION, SCHEMA_VERSION
from zylora_api.modules.templates.schemas import (
    TemplateCreateRequest,
    TemplateMetadataUpdateRequest,
)
from zylora_api.modules.templates.validation import (
    VALIDATOR_VERSION,
    document_checksum,
    validate_document,
)


def problem(status: int, code: str, detail: str) -> AuthProblem:
    return AuthProblem(status, code, "Template operation failed", detail)


class TemplateService:
    def __init__(self, session: AsyncSession, crypto: AuthCrypto) -> None:
        self.session = session
        self.crypto = crypto

    async def create(self, payload: TemplateCreateRequest, actor_id: UUID) -> Template:
        if await self.session.scalar(select(Template.id).where(Template.slug == payload.slug)):
            raise problem(409, "template_slug_exists", "A Template with this slug already exists.")
        category = await self.session.scalar(
            select(TemplateCategory).where(TemplateCategory.slug == payload.category_slug)
        )
        if category is None:
            category = TemplateCategory(
                slug=payload.category_slug,
                name=payload.category_name,
                description=payload.category_description,
            )
            self.session.add(category)
            await self.session.flush()
        template = Template(
            slug=payload.slug,
            name=payload.name,
            summary=payload.summary,
            category_id=category.id,
            featured_order=payload.featured_order,
            created_by=actor_id,
        )
        self.session.add(template)
        await self.session.flush()
        for tag_slug in sorted(set(payload.tags)):
            tag = await self.session.scalar(select(TemplateTag).where(TemplateTag.slug == tag_slug))
            if tag is None:
                tag = TemplateTag(slug=tag_slug, name=tag_slug.replace("-", " ").title())
                self.session.add(tag)
                await self.session.flush()
            self.session.add(TemplateTagAssignment(template_id=template.id, tag_id=tag.id))
        return template

    async def update_metadata(
        self, template_id: UUID, payload: TemplateMetadataUpdateRequest
    ) -> Template:
        template = await self._template(template_id)
        if payload.name is not None:
            template.name = payload.name
        if payload.summary is not None:
            template.summary = payload.summary
        if payload.featured_order is not None:
            template.featured_order = payload.featured_order
        if payload.category_slug is not None:
            category = await self.session.scalar(
                select(TemplateCategory).where(TemplateCategory.slug == payload.category_slug)
            )
            if category is None:
                if payload.category_name is None or payload.category_description is None:
                    raise problem(
                        422,
                        "category_metadata_required",
                        "A new Template category needs a name and description.",
                    )
                category = TemplateCategory(
                    slug=payload.category_slug,
                    name=payload.category_name,
                    description=payload.category_description,
                )
                self.session.add(category)
                await self.session.flush()
            template.category_id = category.id
        if payload.tags is not None:
            await self.session.execute(
                delete(TemplateTagAssignment).where(
                    TemplateTagAssignment.template_id == template.id
                )
            )
            for tag_slug in sorted(set(payload.tags)):
                tag = await self.session.scalar(
                    select(TemplateTag).where(TemplateTag.slug == tag_slug)
                )
                if tag is None:
                    tag = TemplateTag(slug=tag_slug, name=tag_slug.replace("-", " ").title())
                    self.session.add(tag)
                    await self.session.flush()
                self.session.add(TemplateTagAssignment(template_id=template.id, tag_id=tag.id))
        await self.session.flush()
        return template

    async def add_version(
        self, template_id: UUID, document: dict[str, Any], actor_id: UUID
    ) -> TemplateVersion:
        template = await self._template(template_id)
        current = (
            await self.session.scalar(
                select(func.max(TemplateVersion.version)).where(
                    TemplateVersion.template_id == template.id
                )
            )
            or 0
        )
        version = TemplateVersion(
            template_id=template.id,
            version=current + 1,
            document=document,
            checksum=document_checksum(document),
            schema_version=str(document.get("schema_version", "")),
            registry_version=str(document.get("registry_version", "")),
            created_by=actor_id,
        )
        self.session.add(version)
        await self.session.flush()
        return version

    async def validate(
        self, template_id: UUID, version_number: int, actor_id: UUID
    ) -> TemplateVersion:
        version = await self._version(template_id, version_number)
        if version.status not in {"DRAFT", "REJECTED", "VALIDATED"}:
            raise problem(
                409,
                "invalid_template_transition",
                "Only a Draft or rejected version can be validated.",
            )
        version.status = "VALIDATING"
        await self.session.flush()
        result = validate_document(version.document)
        if result.valid:
            asset_ids = [UUID(item["id"]) for item in version.document.get("assets", [])]
            if asset_ids:
                ready = set(
                    (
                        await self.session.scalars(
                            select(TemplateAsset.id).where(
                                TemplateAsset.id.in_(asset_ids), TemplateAsset.status == "READY"
                            )
                        )
                    ).all()
                )
                missing = set(asset_ids) - ready
                if missing:
                    result = type(result)(
                        False,
                        result.checksum,
                        (*result.errors, {"code": "asset_not_ready", "path": "assets"}),
                        result.warnings,
                        result.computed_requirements,
                    )
        report = result.summary()
        version.validation_summary = report
        version.validated_at = datetime.now(UTC)
        version.status = "VALIDATED" if result.valid else "REJECTED"
        self.session.add(
            TemplateValidation(
                template_version_id=version.id,
                checksum=result.checksum,
                validator_version=VALIDATOR_VERSION,
                outcome=version.status,
                report=report,
                created_by=actor_id,
            )
        )
        return version

    async def approve(self, template_id: UUID, version_number: int) -> TemplateVersion:
        version = await self._version(template_id, version_number)
        if version.status != "VALIDATED" or not self._validation_current(version):
            raise problem(
                409,
                "validation_stale",
                "A current successful validation is required before approval.",
            )
        version.status = "APPROVED"
        version.approved_at = datetime.now(UTC)
        return version

    async def publish(self, template_id: UUID, version_number: int) -> TemplateVersion:
        template = await self._template(template_id)
        version = await self._version(template_id, version_number)
        if version.status != "APPROVED" or not self._validation_current(version):
            raise problem(
                409,
                "version_not_approved",
                "An approved version with current validation is required.",
            )
        previous = (
            await self.session.scalar(
                select(TemplateVersion).where(
                    TemplateVersion.id == template.current_published_version_id
                )
            )
            if template.current_published_version_id
            else None
        )
        if previous:
            previous.status = "DEPRECATED"
        version.status = "PUBLISHED"
        version.published_at = datetime.now(UTC)
        template.current_published_version_id = version.id
        template.status = "ACTIVE"
        return version

    async def deprecate(self, template_id: UUID, version_number: int) -> TemplateVersion:
        template = await self._template(template_id)
        version = await self._version(template_id, version_number)
        if version.status != "PUBLISHED":
            raise problem(
                409, "invalid_template_transition", "Only a published version can be deprecated."
            )
        version.status = "DEPRECATED"
        if template.current_published_version_id == version.id:
            template.current_published_version_id = None
            template.status = "DEPRECATED"
        return version

    async def unpublish(self, template_id: UUID, version_number: int) -> TemplateVersion:
        template = await self._template(template_id)
        version = await self._version(template_id, version_number)
        if version.status != "PUBLISHED" or template.current_published_version_id != version.id:
            raise problem(
                409,
                "invalid_template_transition",
                "Only the current published version can be unpublished.",
            )
        version.status = "DEPRECATED"
        template.current_published_version_id = None
        template.status = "DRAFT"
        return version

    async def restore(self, template_id: UUID, version_number: int) -> TemplateVersion:
        template = await self._template(template_id)
        version = await self._version(template_id, version_number)
        if version.status != "DEPRECATED" or not self._validation_current(version):
            raise problem(
                409,
                "version_not_restorable",
                "A deprecated version with current successful validation is required to restore.",
            )
        previous = (
            await self.session.scalar(
                select(TemplateVersion).where(
                    TemplateVersion.id == template.current_published_version_id
                )
            )
            if template.current_published_version_id
            else None
        )
        if previous:
            previous.status = "DEPRECATED"
        version.status = "PUBLISHED"
        version.published_at = datetime.now(UTC)
        template.current_published_version_id = version.id
        template.status = "ACTIVE"
        return version

    def _validation_current(self, version: TemplateVersion) -> bool:
        report = version.validation_summary or {}
        return bool(
            report.get("valid")
            and report.get("checksum") == document_checksum(version.document)
            and report.get("validatorVersion") == VALIDATOR_VERSION
            and version.schema_version == SCHEMA_VERSION
            and version.registry_version == REGISTRY_VERSION
        )

    async def _template(self, template_id: UUID) -> Template:
        template = await self.session.get(Template, template_id)
        if not template:
            raise problem(404, "template_not_found", "Template not found.")
        return template

    async def _version(self, template_id: UUID, number: int) -> TemplateVersion:
        version = await self.session.scalar(
            select(TemplateVersion).where(
                TemplateVersion.template_id == template_id, TemplateVersion.version == number
            )
        )
        if not version:
            raise problem(404, "template_version_not_found", "Template version not found.")
        return version

    def encode_cursor(self, offset: int, fingerprint: str) -> str:
        body = json.dumps({"offset": offset, "fingerprint": fingerprint}, separators=(",", ":"))
        signature = (
            base64.urlsafe_b64encode(self.crypto.digest(body, purpose="template-cursor"))
            .decode()
            .rstrip("=")
        )
        return base64.urlsafe_b64encode(f"{body}.{signature}".encode()).decode().rstrip("=")

    def decode_cursor(self, cursor: str | None, fingerprint: str) -> int:
        if not cursor:
            return 0
        try:
            padded = cursor + "=" * (-len(cursor) % 4)
            body, signature = base64.urlsafe_b64decode(padded).decode().rsplit(".", 1)
            expected = (
                base64.urlsafe_b64encode(self.crypto.digest(body, purpose="template-cursor"))
                .decode()
                .rstrip("=")
            )
            data = json.loads(body)
            if (
                not self.crypto.constant_time_equal(signature.encode(), expected.encode())
                or data["fingerprint"] != fingerprint
                or not isinstance(data["offset"], int)
            ):
                raise ValueError
            return max(0, data["offset"])
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            raise problem(400, "invalid_cursor", "The catalogue cursor is invalid.") from None
