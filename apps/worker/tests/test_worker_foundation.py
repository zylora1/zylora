from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from zylora_api.core.config import Settings
from zylora_worker import tasks
from zylora_worker.celery_app import celery_app
from zylora_worker.config import WorkerSettings
from zylora_worker.tasks import worker_health


def test_worker_health_task_is_deterministic_in_eager_mode() -> None:
    celery_app.conf.task_always_eager = True
    result = worker_health.apply(args=("foundation-check",), throw=True)

    assert result.get() == {
        "service": "zylora-worker",
        "status": "alive",
        "version": "0.1.0",
        "request_id": "foundation-check",
    }


def test_worker_health_rejects_unbounded_request_id() -> None:
    with pytest.raises(ValueError, match="between 1 and 128"):
        worker_health("x" * 129)


def test_production_worker_rejects_local_transport() -> None:
    with pytest.raises(ValidationError, match="cannot use localhost"):
        WorkerSettings(_env_file=None, environment="production")


@pytest.mark.asyncio
async def test_publication_worker_uses_the_domain_service_and_commits_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Celery bridge must use the same transactional deployment service as the API."""

    import sqlalchemy.ext.asyncio as sqlalchemy_asyncio
    from zylora_api.core import config
    from zylora_api.db import session as db_session
    from zylora_api.modules.publishing import artifacts, providers, runtime, service

    event_id = uuid4()
    committed = False
    captured: dict[str, object] = {}

    class FakeSession:
        async def __aenter__(self) -> "FakeSession":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def commit(self) -> None:
            nonlocal committed
            committed = True

    class FakeDeploymentService:
        def __init__(self, session: FakeSession) -> None:
            captured["session"] = session

        async def process_outbox_event(
            self, received_id: UUID, provider: object, builder: object
        ) -> SimpleNamespace:
            captured["event_id"] = received_id
            captured["provider"] = provider
            captured["builder"] = builder
            return SimpleNamespace(state="PUBLISHED")

    worker_session = FakeSession()
    worker_settings = Settings(_env_file=None, environment="test", storage_provider="memory")
    provider = object()
    storage = object()
    monkeypatch.setattr(config, "get_settings", lambda: worker_settings)
    monkeypatch.setattr(db_session, "get_engine", lambda: object())
    monkeypatch.setattr(
        sqlalchemy_asyncio,
        "async_sessionmaker",
        lambda *_args, **_kwargs: lambda: worker_session,
    )
    monkeypatch.setattr(providers, "domain_provider_for", lambda _: provider)
    monkeypatch.setattr(runtime, "publication_storage_for", lambda _: storage)
    monkeypatch.setattr(
        artifacts,
        "ArtifactBuilder",
        lambda received_storage, **_kwargs: ("builder", received_storage),
    )
    monkeypatch.setattr(service, "DeploymentService", FakeDeploymentService)

    assert await tasks._process_publication_event(event_id) == "PUBLISHED"
    assert committed is True
    assert captured == {
        "session": worker_session,
        "event_id": event_id,
        "provider": provider,
        "builder": ("builder", storage),
    }


def test_publication_task_validates_uuid_before_running_the_async_bridge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[UUID] = []

    async def successful(event_id: UUID) -> str:
        called.append(event_id)
        return "PUBLISHED"

    monkeypatch.setattr(tasks, "_process_publication_event", successful)
    event_id = uuid4()
    assert tasks.process_publication_event(str(event_id)) == "PUBLISHED"
    assert called == [event_id]
    with pytest.raises(ValueError):
        tasks.process_publication_event("not-a-uuid")


def test_dispatcher_leases_then_enqueues_each_event_independently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_ids = [str(uuid4()), str(uuid4())]
    enqueued: list[str] = []

    async def claim(limit: int) -> list[str]:
        assert limit == 2
        return event_ids

    monkeypatch.setattr(tasks, "_claim_publication_events", claim)
    monkeypatch.setattr(tasks.process_publication_event, "delay", enqueued.append)

    assert tasks.dispatch_publication_events(2) == 2
    assert enqueued == event_ids
    with pytest.raises(ValueError, match="between 1 and 100"):
        tasks.dispatch_publication_events(0)


@pytest.mark.asyncio
async def test_export_worker_uses_the_private_storage_boundary_and_commits_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sqlalchemy.ext.asyncio as sqlalchemy_asyncio
    from zylora_api.core import config
    from zylora_api.db import session as db_session
    from zylora_api.modules.commerce import exports
    from zylora_api.modules.publishing import runtime

    event_id = uuid4()
    captured: dict[str, object] = {}

    class FakeSession:
        async def __aenter__(self) -> "FakeSession":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def commit(self) -> None:
            captured["committed"] = True

    class FakeExports:
        def __init__(self, session: FakeSession, storage: object) -> None:
            captured["session"] = session
            captured["storage"] = storage

        async def process_outbox_event(self, received_id: UUID) -> SimpleNamespace:
            captured["event_id"] = received_id
            return SimpleNamespace(state="PUBLISHED")

    worker_session = FakeSession()
    worker_settings = Settings(_env_file=None, environment="test", storage_provider="memory")
    storage = object()
    monkeypatch.setattr(config, "get_settings", lambda: worker_settings)
    monkeypatch.setattr(db_session, "get_engine", lambda: object())
    monkeypatch.setattr(
        sqlalchemy_asyncio,
        "async_sessionmaker",
        lambda *_args, **_kwargs: lambda: worker_session,
    )
    monkeypatch.setattr(runtime, "publication_storage_for", lambda _: storage)
    monkeypatch.setattr(exports, "ExportService", FakeExports)

    assert await tasks._process_export_event(event_id) == "PUBLISHED"
    assert captured == {
        "session": worker_session,
        "storage": storage,
        "event_id": event_id,
        "committed": True,
    }


def test_export_task_and_dispatcher_validate_and_enqueue_independently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[UUID] = []
    event_ids = [str(uuid4()), str(uuid4())]
    enqueued: list[str] = []

    async def successful(event_id: UUID) -> str:
        called.append(event_id)
        return "PUBLISHED"

    async def claim(limit: int) -> list[str]:
        assert limit == 2
        return event_ids

    monkeypatch.setattr(tasks, "_process_export_event", successful)
    first = uuid4()
    assert tasks.process_export_event(str(first)) == "PUBLISHED"
    assert called == [first]
    with pytest.raises(ValueError):
        tasks.process_export_event("not-a-uuid")
    monkeypatch.setattr(tasks, "_claim_export_events", claim)
    monkeypatch.setattr(tasks.process_export_event, "delay", enqueued.append)
    assert tasks.dispatch_export_events(2) == 2
    assert enqueued == event_ids
    with pytest.raises(ValueError, match="between 1 and 100"):
        tasks.dispatch_export_events(101)


@pytest.mark.asyncio
async def test_chatbot_worker_uses_the_isolated_index_service_and_commits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sqlalchemy.ext.asyncio as sqlalchemy_asyncio
    from zylora_api.core import config
    from zylora_api.db import session as db_session
    from zylora_api.modules.chatbot import indexing
    from zylora_api.modules.publishing import runtime

    event_id = uuid4()
    captured: dict[str, object] = {}

    class FakeSession:
        async def __aenter__(self) -> "FakeSession":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def commit(self) -> None:
            captured["committed"] = True

        async def scalar(self, _statement: object) -> str:
            return "chatbot.index_requested"

    class FakeIndexes:
        def __init__(self, session: FakeSession, storage: object, settings: Settings) -> None:
            captured.update({"session": session, "storage": storage, "settings": settings})

        async def process_outbox_event(self, received_id: UUID) -> SimpleNamespace:
            captured["event_id"] = received_id
            return SimpleNamespace(state="PUBLISHED")

    worker_session = FakeSession()
    worker_settings = Settings(_env_file=None, environment="test", storage_provider="memory")
    storage = object()
    monkeypatch.setattr(config, "get_settings", lambda: worker_settings)
    monkeypatch.setattr(db_session, "get_engine", lambda: object())
    monkeypatch.setattr(
        sqlalchemy_asyncio,
        "async_sessionmaker",
        lambda *_args, **_kwargs: lambda: worker_session,
    )
    monkeypatch.setattr(runtime, "publication_storage_for", lambda _: storage)
    monkeypatch.setattr(indexing, "KnowledgeIndexService", FakeIndexes)

    assert await tasks._process_chatbot_event(event_id) == "PUBLISHED"
    assert captured == {
        "session": worker_session,
        "storage": storage,
        "settings": worker_settings,
        "event_id": event_id,
        "committed": True,
    }


def test_chatbot_task_and_dispatcher_validate_and_enqueue_independently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[UUID] = []
    event_ids = [str(uuid4()), str(uuid4())]
    enqueued: list[str] = []

    async def successful(event_id: UUID) -> str:
        called.append(event_id)
        return "PUBLISHED"

    async def claim(limit: int) -> list[str]:
        assert limit == 2
        return event_ids

    monkeypatch.setattr(tasks, "_process_chatbot_event", successful)
    first = uuid4()
    assert tasks.process_chatbot_event(str(first)) == "PUBLISHED"
    assert called == [first]
    with pytest.raises(ValueError):
        tasks.process_chatbot_event("not-a-uuid")
    monkeypatch.setattr(tasks, "_claim_chatbot_events", claim)
    monkeypatch.setattr(tasks.process_chatbot_event, "delay", enqueued.append)
    assert tasks.dispatch_chatbot_events(2) == 2
    assert enqueued == event_ids
    with pytest.raises(ValueError, match="between 1 and 50"):
        tasks.dispatch_chatbot_events(51)


@pytest.mark.asyncio
async def test_transactional_email_worker_uses_durable_service_and_commits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sqlalchemy.ext.asyncio as sqlalchemy_asyncio
    from zylora_api.core import config
    from zylora_api.db import session as db_session
    from zylora_api.modules.auth import delivery
    from zylora_api.modules.notifications import email

    event_id = uuid4()
    captured: dict[str, object] = {}

    class FakeSession:
        async def __aenter__(self) -> "FakeSession":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def commit(self) -> None:
            captured["committed"] = True

    class FakeEmailService:
        def __init__(self, session: FakeSession, crypto: object) -> None:
            captured.update({"session": session, "crypto": crypto})

        async def process_outbox_event(
            self, received_id: UUID, provider: object
        ) -> SimpleNamespace:
            captured.update({"event_id": received_id, "provider": provider})
            return SimpleNamespace(state="PUBLISHED")

    worker_session = FakeSession()
    worker_settings = Settings(_env_file=None, environment="test", storage_provider="memory")
    provider = object()
    monkeypatch.setattr(config, "get_settings", lambda: worker_settings)
    monkeypatch.setattr(db_session, "get_engine", lambda: object())
    monkeypatch.setattr(
        sqlalchemy_asyncio,
        "async_sessionmaker",
        lambda *_args, **_kwargs: lambda: worker_session,
    )
    monkeypatch.setattr(delivery, "SMTPEmailSender", lambda _: provider)
    monkeypatch.setattr(email, "TransactionalEmailService", FakeEmailService)

    assert await tasks._process_transactional_email_event(event_id) == "PUBLISHED"
    assert captured["session"] is worker_session
    assert captured["event_id"] == event_id
    assert captured["provider"] is provider
    assert captured["committed"] is True


def test_transactional_email_task_and_dispatcher_validate_and_enqueue_independently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[UUID] = []
    event_ids = [str(uuid4()), str(uuid4())]
    enqueued: list[str] = []

    async def successful(event_id: UUID) -> str:
        called.append(event_id)
        return "PUBLISHED"

    async def claim(limit: int) -> list[str]:
        assert limit == 2
        return event_ids

    monkeypatch.setattr(tasks, "_process_transactional_email_event", successful)
    first = uuid4()
    assert tasks.process_transactional_email_event(str(first)) == "PUBLISHED"
    assert called == [first]
    with pytest.raises(ValueError):
        tasks.process_transactional_email_event("not-a-uuid")
    monkeypatch.setattr(tasks, "_claim_transactional_email_events", claim)
    monkeypatch.setattr(tasks.process_transactional_email_event, "delay", enqueued.append)
    assert tasks.dispatch_transactional_email_events(2) == 2
    assert enqueued == event_ids
    with pytest.raises(ValueError, match="between 1 and 100"):
        tasks.dispatch_transactional_email_events(101)


@pytest.mark.asyncio
async def test_analytics_worker_refreshes_through_canonical_service_and_commits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sqlalchemy.ext.asyncio as sqlalchemy_asyncio
    from zylora_api.db import session as db_session
    from zylora_api.modules.analytics import service

    captured: dict[str, object] = {}

    class FakeSession:
        async def __aenter__(self) -> "FakeSession":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def commit(self) -> None:
            captured["committed"] = True

    class FakeAnalyticsService:
        def __init__(self, session: FakeSession) -> None:
            captured["session"] = session

        async def refresh_recent(self, limit: int) -> int:
            captured["limit"] = limit
            return 3

    worker_session = FakeSession()
    monkeypatch.setattr(db_session, "get_engine", lambda: object())
    monkeypatch.setattr(
        sqlalchemy_asyncio,
        "async_sessionmaker",
        lambda *_args, **_kwargs: lambda: worker_session,
    )
    monkeypatch.setattr(service, "AnalyticsService", FakeAnalyticsService)

    assert await tasks._refresh_analytics(12) == 3
    assert captured == {"session": worker_session, "limit": 12, "committed": True}


def test_analytics_task_validates_its_batch_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    async def refresh(limit: int) -> int:
        assert limit == 5
        return 2

    monkeypatch.setattr(tasks, "_refresh_analytics", refresh)
    assert tasks.refresh_analytics(5) == 2
    with pytest.raises(ValueError, match="between 1 and 500"):
        tasks.refresh_analytics(0)


def test_ai_generation_dispatch_records_broker_acceptance_per_id_only_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_id = uuid4()
    job_id = uuid4()
    finished: list[tuple[UUID, str, bool]] = []
    enqueued: list[str] = []

    async def claim(limit: int) -> list[tuple[UUID, UUID, str]]:
        assert limit == 1
        return [(event_id, job_id, "lease-owner")]

    async def finish(received: UUID, owner: str, *, delivered: bool) -> None:
        finished.append((received, owner, delivered))

    monkeypatch.setattr(tasks, "_claim_ai_generation_events", claim)
    monkeypatch.setattr(tasks, "_finish_ai_generation_dispatch", finish)
    monkeypatch.setattr(tasks.execute_ai_generation, "delay", enqueued.append)

    assert tasks.dispatch_ai_generation_events(1) == 1
    assert enqueued == [str(job_id)]
    assert finished == [(event_id, "lease-owner", True)]
    with pytest.raises(ValueError, match="between 1 and 50"):
        tasks.dispatch_ai_generation_events(0)


def test_ai_generation_dispatch_releases_outbox_lease_when_broker_rejects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_id = uuid4()
    job_id = uuid4()
    finished: list[tuple[UUID, str, bool]] = []

    async def claim(_limit: int) -> list[tuple[UUID, UUID, str]]:
        return [(event_id, job_id, "lease-owner")]

    async def finish(received: UUID, owner: str, *, delivered: bool) -> None:
        finished.append((received, owner, delivered))

    def unavailable(_job_id: str) -> None:
        raise ConnectionError("broker unavailable")

    monkeypatch.setattr(tasks, "_claim_ai_generation_events", claim)
    monkeypatch.setattr(tasks, "_finish_ai_generation_dispatch", finish)
    monkeypatch.setattr(tasks.execute_ai_generation, "delay", unavailable)

    with pytest.raises(ConnectionError, match="broker unavailable"):
        tasks.dispatch_ai_generation_events(1)
    assert finished == [(event_id, "lease-owner", False)]


def test_ai_generation_recovery_enqueues_persisted_job_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_ids = [uuid4(), uuid4()]
    enqueued: list[str] = []

    async def recover(limit: int) -> list[UUID]:
        assert limit == 2
        return job_ids

    monkeypatch.setattr(tasks, "_recover_ai_generation_jobs", recover)
    monkeypatch.setattr(tasks.execute_ai_generation, "delay", enqueued.append)

    assert tasks.recover_ai_generation_jobs(2) == 2
    assert enqueued == [str(item) for item in job_ids]
    with pytest.raises(ValueError, match="between 1 and 500"):
        tasks.recover_ai_generation_jobs(0)


def test_ai_generation_task_rejects_invalid_job_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[UUID] = []

    async def execute(job_id: UUID, _worker_id: str) -> str:
        called.append(job_id)
        return "SKIPPED"

    monkeypatch.setattr(tasks, "_execute_ai_generation", execute)
    job_id = uuid4()
    assert tasks.execute_ai_generation(str(job_id)) == "SKIPPED"
    assert called == [job_id]
    with pytest.raises(ValueError):
        tasks.execute_ai_generation("not-a-uuid")


@pytest.mark.asyncio
async def test_ai_generation_worker_claims_builds_verifies_and_commits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sqlalchemy.ext.asyncio as sqlalchemy_asyncio
    from zylora_api.core import config
    from zylora_api.db import session as db_session
    from zylora_api.modules.ai_builder import artifacts, client, service
    from zylora_api.modules.publishing import runtime

    job_id = uuid4()
    generation_id = uuid4()
    project_id = uuid4()
    owner_id = uuid4()
    lease_token = uuid4()
    commits: list[str] = []
    captured: dict[str, object] = {}
    result = SimpleNamespace(
        generation_id=generation_id,
        artifact=SimpleNamespace(
            object_key=f"ai-sites/{owner_id}/{project_id}/{generation_id}/{'a' * 64}.tar.gz",
            checksum_sha256="a" * 64,
            size_bytes=2048,
            content_type="application/gzip",
        ),
        provider_name="test-provider",
        provider_model="test-model",
        stage_durations_ms={"generating": 12},
    )
    claim = SimpleNamespace(
        job_id=job_id,
        generation_id=generation_id,
        project_id=project_id,
        owner_user_id=owner_id,
        lease_token=lease_token,
        prompt="A private prompt that must not be logged.",
        attempt=1,
        correlation_id="ai-worker-correlation",
    )

    class FakeSession:
        async def __aenter__(self) -> "FakeSession":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def commit(self) -> None:
            commits.append("commit")

    class Service:
        def __init__(self, *_: object) -> None: ...

        async def claim(self, received: UUID, worker: str) -> SimpleNamespace:
            captured.update({"claimed": received, "worker": worker})
            return claim

        async def complete(
            self, received: UUID, token: UUID, received_result: object
        ) -> SimpleNamespace:
            captured.update({"completed": received, "token": token, "result": received_result})
            return SimpleNamespace()

    class Client:
        def __init__(self, *_: object) -> None: ...

        async def execute(self, **kwargs: object) -> object:
            captured["execute"] = kwargs
            return result

    class Verifier:
        def __init__(self, storage: object, _settings: object) -> None:
            captured["storage"] = storage

        def verify(self, artifact: object, **kwargs: object) -> None:
            captured.update({"verified": artifact, "verification_scope": kwargs})

    settings = Settings(
        _env_file=None,
        environment="test",
        storage_provider="memory",
        ai_builder_enabled=True,
        ai_builder_url="https://builder.test",
        ai_builder_service_token="builder-service-token-long-enough-for-tests",
    )
    storage = object()
    session = FakeSession()
    monkeypatch.setattr(config, "get_settings", lambda: settings)
    monkeypatch.setattr(db_session, "get_engine", lambda: object())
    monkeypatch.setattr(
        sqlalchemy_asyncio,
        "async_sessionmaker",
        lambda *_args, **_kwargs: lambda: session,
    )
    monkeypatch.setattr(service, "AiSiteProjectService", Service)
    monkeypatch.setattr(client, "AiBuilderClient", Client)
    monkeypatch.setattr(artifacts, "GenerationArtifactVerifier", Verifier)
    monkeypatch.setattr(runtime, "publication_storage_for", lambda _: storage)

    assert await tasks._execute_ai_generation(job_id, "worker-one") == "COMPLETED"
    assert captured["claimed"] == job_id
    assert captured["execute"] == {
        "generation_id": generation_id,
        "project_id": project_id,
        "owner_user_id": owner_id,
        "prompt": claim.prompt,
        "lease_token": lease_token,
    }
    assert captured["verification_scope"] == {
        "owner_user_id": owner_id,
        "project_id": project_id,
        "generation_id": generation_id,
    }
    assert captured["completed"] == job_id
    assert commits == ["commit", "commit"]


@pytest.mark.asyncio
async def test_ai_generation_worker_persists_classified_failure_and_skips_duplicate_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sqlalchemy.ext.asyncio as sqlalchemy_asyncio
    from zylora_api.core import config
    from zylora_api.db import session as db_session
    from zylora_api.modules.ai_builder import client, service

    job_id = uuid4()
    lease_token = uuid4()
    claim = SimpleNamespace(
        job_id=job_id,
        generation_id=uuid4(),
        project_id=uuid4(),
        owner_user_id=uuid4(),
        lease_token=lease_token,
        prompt="A private prompt that must not be logged.",
        attempt=1,
        correlation_id="ai-worker-failure",
    )
    claims: list[object] = [claim, None]
    failures: list[dict[str, object]] = []

    class FakeSession:
        async def __aenter__(self) -> "FakeSession":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def commit(self) -> None: ...

    class Service:
        def __init__(self, *_: object) -> None: ...

        async def claim(self, *_: object) -> object:
            return claims.pop(0)

        async def fail(self, *args: object, **kwargs: object) -> None:
            failures.append({"args": args, **kwargs})

    class Client:
        def __init__(self, *_: object) -> None: ...

        async def execute(self, **_kwargs: object) -> object:
            raise client.AiBuilderError("PROVIDER_RATE_LIMITED", retryable=True)

    settings = Settings(
        _env_file=None,
        environment="test",
        storage_provider="memory",
        ai_builder_enabled=True,
        ai_builder_url="https://builder.test",
        ai_builder_service_token="builder-service-token-long-enough-for-tests",
    )
    session = FakeSession()
    monkeypatch.setattr(config, "get_settings", lambda: settings)
    monkeypatch.setattr(db_session, "get_engine", lambda: object())
    monkeypatch.setattr(
        sqlalchemy_asyncio,
        "async_sessionmaker",
        lambda *_args, **_kwargs: lambda: session,
    )
    monkeypatch.setattr(service, "AiSiteProjectService", Service)
    monkeypatch.setattr(client, "AiBuilderClient", Client)

    assert await tasks._execute_ai_generation(job_id, "worker-two") == "RETRY_WAIT"
    assert failures == [
        {
            "args": (job_id, lease_token),
            "error_code": "PROVIDER_RATE_LIMITED",
            "retryable": True,
        }
    ]
    assert await tasks._execute_ai_generation(job_id, "worker-three") == "SKIPPED"


@pytest.mark.asyncio
async def test_ai_outbox_claim_and_finish_are_persisted_and_retry_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sqlalchemy.ext.asyncio as sqlalchemy_asyncio
    from zylora_api.db import session as db_session

    job_id = uuid4()
    valid = SimpleNamespace(
        id=uuid4(),
        payload={"job_id": str(job_id)},
        state="PENDING",
        lease_owner=None,
        leased_until=None,
        attempts=0,
        last_error_code=None,
        available_at=None,
        published_at=None,
    )
    invalid = SimpleNamespace(
        id=uuid4(),
        payload={"prompt": "must never dispatch"},
        state="PENDING",
        lease_owner=None,
        leased_until=None,
        attempts=0,
        last_error_code=None,
        available_at=None,
        published_at=None,
    )
    current_event = valid
    commits = 0

    class Scalars:
        def all(self) -> list[object]:
            return [valid, invalid]

    class FakeSession:
        async def __aenter__(self) -> "FakeSession":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def scalars(self, _statement: object) -> Scalars:
            return Scalars()

        async def scalar(self, _statement: object) -> object:
            return current_event

        async def commit(self) -> None:
            nonlocal commits
            commits += 1

    session = FakeSession()
    monkeypatch.setattr(db_session, "get_engine", lambda: object())
    monkeypatch.setattr(
        sqlalchemy_asyncio,
        "async_sessionmaker",
        lambda *_args, **_kwargs: lambda: session,
    )

    claimed = await tasks._claim_ai_generation_events(10)
    assert len(claimed) == 1
    event_id, claimed_job, owner = claimed[0]
    assert event_id == valid.id and claimed_job == job_id
    assert valid.lease_owner == owner
    assert valid.leased_until is not None
    assert invalid.state == "FAILED"
    assert invalid.last_error_code == "ai_generation_job_reference_invalid"

    await tasks._finish_ai_generation_dispatch(valid.id, owner, delivered=True)
    assert valid.state == "PUBLISHED"
    assert valid.published_at is not None
    assert valid.lease_owner is None and valid.leased_until is None

    valid.state = "PENDING"
    valid.lease_owner = owner
    await tasks._finish_ai_generation_dispatch(valid.id, owner, delivered=False)
    assert valid.attempts == 1
    assert valid.last_error_code == "ai_generation_broker_unavailable"
    assert valid.available_at is not None
    assert commits == 3


@pytest.mark.asyncio
async def test_ai_recovery_bridge_uses_canonical_persisted_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sqlalchemy.ext.asyncio as sqlalchemy_asyncio
    from zylora_api.core import config
    from zylora_api.db import session as db_session
    from zylora_api.modules.ai_builder import service

    recovered = [uuid4(), uuid4()]
    captured: dict[str, object] = {}

    class FakeSession:
        async def __aenter__(self) -> "FakeSession":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def commit(self) -> None:
            captured["committed"] = True

    class Service:
        def __init__(self, session: object, _crypto: object, settings: object) -> None:
            captured.update({"session": session, "settings": settings})

        async def recover_stale(self, limit: int) -> list[UUID]:
            captured["limit"] = limit
            return recovered

    settings = Settings(_env_file=None, environment="test", storage_provider="memory")
    session = FakeSession()
    monkeypatch.setattr(config, "get_settings", lambda: settings)
    monkeypatch.setattr(db_session, "get_engine", lambda: object())
    monkeypatch.setattr(
        sqlalchemy_asyncio,
        "async_sessionmaker",
        lambda *_args, **_kwargs: lambda: session,
    )
    monkeypatch.setattr(service, "AiSiteProjectService", Service)

    assert await tasks._recover_ai_generation_jobs(17) == recovered
    assert captured == {
        "session": session,
        "settings": settings,
        "limit": 17,
        "committed": True,
    }


def test_celery_transport_and_ai_time_limits_are_explicit_and_safe() -> None:
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.task_reject_on_worker_lost is True
    assert celery_app.conf.worker_prefetch_multiplier == 1
    assert celery_app.conf.broker_transport_options["visibility_timeout"] == 900
    assert celery_app.conf.worker_max_tasks_per_child == 50
    annotation = celery_app.conf.task_annotations["zylora.ai_builder.execute_generation"]
    assert annotation == {"soft_time_limit": 570, "time_limit": 600}


def test_worker_rejects_visibility_and_time_limit_misconfiguration() -> None:
    with pytest.raises(ValidationError, match="visibility timeout must exceed"):
        WorkerSettings(
            _env_file=None,
            celery_visibility_timeout_seconds=600,
            ai_generation_time_limit_seconds=600,
        )
    with pytest.raises(ValidationError, match="soft time limit must be shorter"):
        WorkerSettings(
            _env_file=None,
            ai_generation_soft_time_limit_seconds=600,
            ai_generation_time_limit_seconds=600,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("worker_concurrency", 0, "worker concurrency"),
        ("celery_visibility_timeout_seconds", 299, "visibility timeout must be between"),
        ("celery_soft_time_limit_seconds", 29, "Celery soft time limit"),
        ("ai_generation_soft_time_limit_seconds", 29, "AI generation soft time limit"),
        ("celery_prefetch_multiplier", 5, "prefetch multiplier"),
        ("celery_max_tasks_per_child", 0, "max tasks per child"),
    ],
)
def test_worker_operational_limits_fail_closed(field: str, value: int, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        WorkerSettings(_env_file=None, **{field: value})


def test_production_worker_requires_tls_for_remote_transport() -> None:
    with pytest.raises(ValidationError, match="must require TLS"):
        WorkerSettings(
            _env_file=None,
            environment="production",
            celery_broker_url="redis://broker.example.com/1",
            celery_result_backend="redis://broker.example.com/2",
        )


def test_staging_worker_requires_remote_tls_transport() -> None:
    with pytest.raises(ValidationError, match="staging/production worker transport"):
        WorkerSettings(_env_file=None, environment="staging")
    settings = WorkerSettings(
        _env_file=None,
        environment="staging",
        celery_broker_url="rediss://broker.staging.example/1",
        celery_result_backend="rediss://broker.staging.example/2",
    )
    assert settings.environment == "staging"
