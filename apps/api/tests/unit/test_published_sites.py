from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from zylora_api.api import published_sites
from zylora_api.core.config import Settings
from zylora_api.storage.memory import MemoryObjectStorage


class ScalarSession:
    def __init__(self, *values: object) -> None:
        self.values = list(values)
        self.get_values: list[object] = []

    async def scalar(self, _: object) -> object:
        return self.values.pop(0)

    async def get(self, _: object, __: object) -> object:
        return self.get_values.pop(0)


def request(host: str, path: str = "/") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "https",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [(b"host", host.encode())],
            "client": ("127.0.0.1", 1234),
            "server": (host, 443),
        }
    )


@pytest.mark.asyncio
async def test_published_health_uses_host_scoped_candidate_deployment() -> None:
    deployment = SimpleNamespace(id=uuid4())
    domain = SimpleNamespace(id=uuid4(), hostname="www.example.com", state="PROVISIONING")
    response = await published_sites.published_health(
        request("www.example.com"),
        ScalarSession(domain, deployment),  # type: ignore[arg-type]
    )
    assert response.status_code == 200
    assert response.headers["x-zylora-deployment"] == str(deployment.id)


@pytest.mark.asyncio
async def test_published_page_serves_only_active_immutable_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deployment_id = uuid4()
    domain = SimpleNamespace(id=uuid4(), website_id=uuid4(), hostname="www.example.com")
    website = SimpleNamespace(
        id=domain.website_id, status="PUBLISHED", active_deployment_id=deployment_id
    )
    deployment = SimpleNamespace(
        id=deployment_id,
        domain_id=domain.id,
        state="ACTIVE",
        artifact_key="deployments/current/manifest.json",
    )
    storage = MemoryObjectStorage()
    storage.put_bytes(
        deployment.artifact_key,
        json.dumps(
            {
                "files": {"/": "deployments/current/index.html"},
                "redirects": {"/old": "/"},
            }
        ).encode(),
        "application/json",
    )
    storage.put_bytes("deployments/current/index.html", b"<h1>Published</h1>", "text/html")
    monkeypatch.setattr(published_sites, "publication_storage_for", lambda _: storage)
    session = ScalarSession(domain, website)
    session.get_values.append(deployment)
    response = await published_sites.published_page(
        "",
        request("www.example.com"),
        session,
        Settings(_env_file=None, environment="test"),  # type: ignore[arg-type]
    )
    assert response.status_code == 200 and b"Published" in response.body
    assert response.headers["x-zylora-deployment"] == str(deployment_id)


@pytest.mark.asyncio
async def test_published_site_rejects_unknown_host() -> None:
    with pytest.raises(HTTPException, match="not found"):
        await published_sites.published_health(
            request("unknown.example.com"),
            ScalarSession(None),  # type: ignore[arg-type]
        )


def test_hostname_rejects_requests_without_a_hostname() -> None:
    no_host_request = Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "https",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [],
        }
    )
    with pytest.raises(HTTPException, match="not found"):
        published_sites._hostname(no_host_request)


@pytest.mark.asyncio
async def test_published_page_redirects_only_from_the_active_domain_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deployment_id = uuid4()
    domain = SimpleNamespace(id=uuid4(), website_id=uuid4(), hostname="www.example.com")
    website = SimpleNamespace(
        id=domain.website_id, status="PUBLISHED", active_deployment_id=deployment_id
    )
    deployment = SimpleNamespace(
        id=deployment_id,
        domain_id=domain.id,
        state="ACTIVE",
        artifact_key="deployments/current/manifest.json",
    )
    storage = MemoryObjectStorage()
    storage.put_bytes(
        deployment.artifact_key,
        json.dumps({"files": {}, "redirects": {"/legacy": "/about"}}).encode(),
        "application/json",
    )
    monkeypatch.setattr(published_sites, "publication_storage_for", lambda _: storage)
    session = ScalarSession(domain, website)
    session.get_values.append(deployment)

    response = await published_sites.published_page(
        "legacy",
        request("www.example.com", "/legacy"),
        session,  # type: ignore[arg-type]
        Settings(_env_file=None, environment="test"),  # type: ignore[arg-type]
    )
    assert response.status_code == 308 and response.headers["location"] == "/about"


@pytest.mark.asyncio
async def test_published_resolver_rejects_inactive_or_missing_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deployment_id = uuid4()
    domain = SimpleNamespace(id=uuid4(), website_id=uuid4(), hostname="www.example.com")
    website = SimpleNamespace(
        id=domain.website_id, status="PUBLISHED", active_deployment_id=deployment_id
    )
    inactive = SimpleNamespace(
        id=deployment_id,
        domain_id=domain.id,
        state="SUPERSEDED",
        artifact_key="deployments/current/manifest.json",
    )
    session = ScalarSession(domain, website)
    session.get_values.append(inactive)
    with pytest.raises(HTTPException, match="not found"):
        await published_sites.published_page(
            "", request("www.example.com"), session, Settings(_env_file=None, environment="test")
        )  # type: ignore[arg-type]

    active_without_artifact = SimpleNamespace(
        id=deployment_id, domain_id=domain.id, state="ACTIVE", artifact_key=None
    )
    session = ScalarSession(domain, website)
    session.get_values.append(active_without_artifact)
    with pytest.raises(HTTPException, match="artifact is unavailable"):
        await published_sites.published_page(
            "", request("www.example.com"), session, Settings(_env_file=None, environment="test")
        )  # type: ignore[arg-type]

    active = SimpleNamespace(
        id=deployment_id,
        domain_id=domain.id,
        state="ACTIVE",
        artifact_key="deployments/current/manifest.json",
    )
    monkeypatch.setattr(published_sites, "publication_storage_for", lambda _: MemoryObjectStorage())
    session = ScalarSession(domain, website)
    session.get_values.append(active)
    with pytest.raises(HTTPException, match="artifact is unavailable"):
        await published_sites.published_page(
            "", request("www.example.com"), session, Settings(_env_file=None, environment="test")
        )  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_published_health_rejects_domain_without_a_candidate_deployment() -> None:
    domain = SimpleNamespace(id=uuid4(), hostname="www.example.com", state="ACTIVE")
    with pytest.raises(HTTPException, match="not ready"):
        await published_sites.published_health(
            request("www.example.com"),
            ScalarSession(domain, None),  # type: ignore[arg-type]
        )
