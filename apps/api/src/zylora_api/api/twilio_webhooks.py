from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from twilio.request_validator import RequestValidator  # type: ignore[import-untyped]

from zylora_api.core.config import Settings, get_settings
from zylora_api.db.session import get_session
from zylora_api.modules.auth.http import get_crypto
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.notifications.whatsapp import WhatsAppNotificationService
from zylora_api.modules.templates.service import problem

logger = logging.getLogger("zylora.whatsapp.webhook")

router = APIRouter(prefix="/api/v1/webhooks/twilio", tags=["twilio-webhooks"])


@router.post("/whatsapp/status", status_code=status.HTTP_204_NO_CONTENT)
async def whatsapp_status(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    crypto: Annotated[AuthCrypto, Depends(get_crypto)],
    signature: Annotated[str | None, Header(alias="X-Twilio-Signature")] = None,
) -> Response:
    if (
        not settings.whatsapp_enabled
        or not settings.twilio_auth_token
        or not settings.twilio_status_callback_base_url
    ):
        raise problem(503, "whatsapp_webhook_unavailable", "Webhook is unavailable.")
    form = await request.form()
    parameters = {str(key): str(value) for key, value in form.multi_items()}
    callback_url = (
        settings.twilio_status_callback_base_url.rstrip("/")
        + "/api/v1/webhooks/twilio/whatsapp/status"
    )
    if request.url.query:
        callback_url += f"?{request.url.query}"
    if not signature or not RequestValidator(settings.twilio_auth_token).validate(
        callback_url, parameters, signature
    ):
        logger.warning(
            "twilio_webhook_invalid_signature",
            extra={
                "event_type": "whatsapp.webhook_invalid",
                "outcome": "rejected",
                "safe_error_code": "twilio_signature_invalid",
            },
        )
        raise problem(403, "twilio_signature_invalid", "Webhook signature is invalid.")
    message_sid = parameters.get("MessageSid", "")
    provider_status = parameters.get("MessageStatus", "")
    if not message_sid.startswith("SM") or not provider_status:
        raise problem(422, "twilio_callback_invalid", "Webhook payload is invalid.")
    await WhatsAppNotificationService(session, crypto, settings).apply_callback(
        message_sid=message_sid,
        provider_status=provider_status,
        parameters=parameters,
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
