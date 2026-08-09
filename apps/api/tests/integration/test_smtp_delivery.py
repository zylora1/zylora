from __future__ import annotations

from uuid import uuid4

import pytest
from zylora_api.core.config import Settings
from zylora_api.modules.auth.delivery import SMTPEmailSender


@pytest.mark.integration
async def test_local_smtp_adapter_delivers_without_fake_success() -> None:
    settings = Settings(
        environment="test",
        storage_provider="memory",
        smtp_host="localhost",
        smtp_port=1025,
        smtp_start_tls=False,
        _env_file=None,
    )

    await SMTPEmailSender(settings).send_verification(
        email=f"smtp-{uuid4()}@example.com", code="123456"
    )
