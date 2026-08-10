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
        artifacts, "ArtifactBuilder", lambda received_storage: ("builder", received_storage)
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
