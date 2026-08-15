from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest
from zylora_api.api import ai_builder
from zylora_api.app import create_app
from zylora_api.core.config import Settings
from zylora_api.db.auth_models import Session, User
from zylora_api.db.session import get_session
from zylora_api.modules.auth.http import RequestIdentity, get_crypto, get_user_identity
from zylora_api.modules.auth.security import AuthCrypto


class Database:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


def snapshot(*, state: str = "QUEUED", artifact: bool = False) -> SimpleNamespace:
    now = datetime(2026, 8, 13, tzinfo=UTC)
    owner_id = uuid4()
    project_id = uuid4()
    generation_id = uuid4()
    project = SimpleNamespace(
        id=project_id,
        owner_user_id=owner_id,
        status=state,
        created_at=now,
    )
    generation = SimpleNamespace(
        id=generation_id,
        state=state,
        version_number=1,
        retryable=state == "FAILED",
        error_category="PROVIDER_UNAVAILABLE" if state == "FAILED" else None,
        prompt_digest=b"d" * 32,
        queued_at=now,
        started_at=now if state != "QUEUED" else None,
        completed_at=now if state == "COMPLETED" else None,
        failed_at=now if state == "FAILED" else None,
        cancelled_at=now if state == "CANCELLED" else None,
        updated_at=now,
    )
    job = SimpleNamespace(
        id=uuid4(),
        attempt=1,
        max_attempts=4,
        safe_error_code=None,
    )
    artifact_model = (
        SimpleNamespace(
            generation_id=generation_id,
            object_key=f"ai-sites/{owner_id}/{project_id}/{generation_id}/{'a' * 64}.tar.gz",
            checksum_sha256="a" * 64,
            size_bytes=2048,
            content_type="application/gzip",
        )
        if artifact
        else None
    )
    return SimpleNamespace(
        project=project,
        generation=generation,
        job=job,
        artifact=artifact_model,
    )


def setup(
    monkeypatch: pytest.MonkeyPatch, *, enabled: bool = True, canary_allowed: bool = True
) -> tuple[object, Database, User, AuthCrypto]:
    now = datetime.now(UTC)
    crypto = AuthCrypto("ai-builder-route-test-secret-that-is-long-enough")
    user = User(
        id=uuid4(),
        account_type="USER",
        normalized_email="ai-owner@example.com",
        display_email="ai-owner@example.com",
        status="ACTIVE",
        verified_at=now,
    )
    session = Session(
        id=uuid4(),
        user_id=user.id,
        token_hash=b"s" * 32,
        csrf_hash=crypto.digest("ai-csrf", purpose="csrf:USER_WEB"),
        audience="USER_WEB",
        auth_epoch=1,
        expires_at=now + timedelta(hours=1),
    )
    database = Database()
    app = create_app()
    app.dependency_overrides[get_user_identity] = lambda: RequestIdentity(session, user, "token")
    app.dependency_overrides[get_session] = lambda: database
    app.dependency_overrides[get_crypto] = lambda: crypto
    app.dependency_overrides[ai_builder.get_settings] = lambda: Settings(
        _env_file=None,
        environment="test",
        storage_provider="memory",
        ai_builder_enabled=enabled,
        ai_builder_rollout_mode="canary",
        ai_builder_canary_user_ids=str(user.id if canary_allowed else uuid4()),
        ai_builder_url="https://builder.test",
        ai_builder_service_token="builder-service-token-long-enough-for-tests",
    )
    return app, database, user, crypto


async def test_ai_builder_routes_restore_submit_retry_cancel_and_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, database, user, _crypto = setup(monkeypatch)
    queued = snapshot()
    completed = snapshot(state="COMPLETED", artifact=True)
    failed = snapshot(state="FAILED")
    cancelled = snapshot(state="CANCELLED")
    calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    class Service:
        async def list_for_owner(self, owner: UUID) -> list[SimpleNamespace]:
            assert owner == user.id
            return [queued]

        async def get_for_owner(self, project: UUID, owner: UUID) -> SimpleNamespace:
            calls.append(("get", (project, owner), {}))
            return completed

        async def queue(self, **kwargs: object) -> SimpleNamespace:
            calls.append(("queue", (), kwargs))
            return queued

        async def retry(self, *args: object, **kwargs: object) -> SimpleNamespace:
            calls.append(("retry", args, kwargs))
            return failed

        async def cancel(self, *args: object, **kwargs: object) -> SimpleNamespace:
            calls.append(("cancel", args, kwargs))
            return cancelled

        async def artifact_for_owner(self, *args: object) -> SimpleNamespace:
            calls.append(("artifact", args, {}))
            return completed.artifact

    class Audit:
        def __init__(self, *_: object) -> None: ...

        def record(self, *args: object, **kwargs: object) -> None:
            calls.append(("audit", args, kwargs))

    class Storage:
        def presign_get(self, key: str, expires: int) -> str:
            assert key == completed.artifact.object_key
            assert expires == 300
            return "https://objects.test/signed"

    instance = Service()
    monkeypatch.setattr(ai_builder, "service", lambda *_: instance)
    monkeypatch.setattr(ai_builder, "AuditService", Audit)
    monkeypatch.setattr(ai_builder, "publication_storage_for", lambda _: Storage())
    headers = {
        "Origin": "http://localhost:3000",
        "X-CSRF-Token": "ai-csrf",
        "Idempotency-Key": "ai-route-idempotency-0001",
    }

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        client.cookies.set("zylora_user_csrf", "ai-csrf")
        listed = await client.get("/api/v1/ai-site-projects")
        detail = await client.get(f"/api/v1/ai-site-projects/{queued.project.id}")
        created = await client.post(
            "/api/v1/ai-site-projects",
            json={"prompt": "Build a professional local services website."},
            headers=headers,
        )
        retried = await client.post(
            f"/api/v1/ai-site-projects/{queued.project.id}/retry",
            json={},
            headers=headers,
        )
        cancelled_response = await client.post(
            f"/api/v1/ai-site-projects/{queued.project.id}/cancel",
            json={},
            headers={key: value for key, value in headers.items() if key != "Idempotency-Key"},
        )
        artifact = await client.get(
            f"/api/v1/ai-site-projects/{completed.project.id}/generations/{completed.generation.id}/artifact"
        )

    assert listed.status_code == detail.status_code == artifact.status_code == 200
    assert created.status_code == retried.status_code == 202
    assert cancelled_response.status_code == 200
    assert listed.json()["items"][0]["status"] == "QUEUED"
    assert detail.json()["preview_ready"] is True
    assert created.json()["can_cancel"] is True
    assert retried.json()["can_retry"] is True
    assert retried.json()["safe_error_message"].startswith("The generation provider")
    assert cancelled_response.json()["status"] == "CANCELLED"
    assert artifact.json()["download_url"] == "https://objects.test/signed"
    assert database.commits == 3
    queue_call = next(item for item in calls if item[0] == "queue")
    assert queue_call[2]["owner_user_id"] == user.id
    assert queue_call[2]["prompt"] == "Build a professional local services website."
    assert len([item for item in calls if item[0] == "audit"]) == 3


async def test_ai_builder_mutations_fail_closed_for_disabled_csrf_and_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, database, _user, _crypto = setup(monkeypatch, enabled=False)
    prompt = {"prompt": "Build a professional local services website."}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        client.cookies.set("zylora_user_csrf", "ai-csrf")
        disabled = await client.post(
            "/api/v1/ai-site-projects",
            json=prompt,
            headers={
                "Origin": "http://localhost:3000",
                "X-CSRF-Token": "ai-csrf",
                "Idempotency-Key": "ai-route-idempotency-0002",
            },
        )
        missing_csrf = await client.post(
            "/api/v1/ai-site-projects",
            json=prompt,
            headers={
                "Origin": "http://localhost:3000",
                "Idempotency-Key": "ai-route-idempotency-0003",
            },
        )
        forged_origin = await client.post(
            "/api/v1/ai-site-projects",
            json=prompt,
            headers={
                "Origin": "https://attacker.example",
                "X-CSRF-Token": "ai-csrf",
                "Idempotency-Key": "ai-route-idempotency-0004",
            },
        )

    assert disabled.status_code == 503
    assert disabled.json()["type"].endswith("ai_builder_unavailable")
    assert missing_csrf.status_code == forged_origin.status_code == 403
    assert database.commits == 0


async def test_ai_artifact_access_hides_storage_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    app, _database, _user, _crypto = setup(monkeypatch)
    completed = snapshot(state="COMPLETED", artifact=True)

    class Service:
        async def artifact_for_owner(self, *_: object) -> SimpleNamespace:
            return completed.artifact

    class Storage:
        def presign_get(self, _key: str, _expires: int) -> str:
            raise RuntimeError("private storage detail")

    monkeypatch.setattr(ai_builder, "service", lambda *_: Service())
    monkeypatch.setattr(ai_builder, "publication_storage_for", lambda _: Storage())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        result = await client.get(
            f"/api/v1/ai-site-projects/{completed.project.id}/generations/{completed.generation.id}/artifact"
        )

    assert result.status_code == 503
    assert "private storage detail" not in result.text
    assert result.json()["type"].endswith("ai_artifact_storage_unavailable")


async def test_ai_builder_canary_rejects_non_allowlisted_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, database, _user, _crypto = setup(monkeypatch, canary_allowed=False)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        client.cookies.set("zylora_user_csrf", "ai-csrf")
        result = await client.post(
            "/api/v1/ai-site-projects",
            json={"prompt": "Build a professional local services website."},
            headers={
                "Origin": "http://localhost:3000",
                "X-CSRF-Token": "ai-csrf",
                "Idempotency-Key": "ai-route-idempotency-canary",
            },
        )

    assert result.status_code == 503
    assert result.json()["type"].endswith("ai_builder_unavailable")
    assert database.commits == 0
