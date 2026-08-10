from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import httpx
import pytest
from zylora_api.core.config import Settings
from zylora_api.modules.auth.errors import AuthProblem
from zylora_api.modules.publishing.artifacts import ArtifactBuilder, render_page
from zylora_api.modules.publishing.providers import (
    CloudflareDomainProvider,
    DisabledDomainProvider,
    DomainProviderError,
    MemoryDomainProvider,
    domain_provider_for,
)
from zylora_api.modules.publishing.runtime import (
    DisabledPublicationStorage,
    publication_storage_for,
)
from zylora_api.modules.publishing.service import DeploymentService, normalize_hostname
from zylora_api.storage.memory import MemoryObjectStorage


@pytest.mark.parametrize("value", ["", "  example.com", "127.0.0.1", "bad/path", "one"])
def test_normalize_hostname_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(AuthProblem):
        normalize_hostname(value)


def test_normalize_hostname_canonicalizes_idna_and_case() -> None:
    assert normalize_hostname("BÜCHER.example.") == "xn--bcher-kva.example"


def test_artifact_builder_uses_immutable_deployment_prefix_and_escaped_content() -> None:
    storage = MemoryObjectStorage()
    deployment_id = uuid4()
    built = ArtifactBuilder(storage).build(
        deployment_id,
        [
            {
                "path": "/",
                "name": "Home <unsafe>",
                "show_in_navigation": True,
                "seo": {"title": "<script>bad</script>", "description": "safe"},
                "components": [
                    {
                        "props": {"heading": "<img src=x>", "body": "Welcome"},
                        "children": [],
                    }
                ],
            },
            {
                "path": "/about",
                "name": "About",
                "show_in_navigation": True,
                "seo": {},
                "components": [],
            },
        ],
        {"/old-about": "/about"},
    )
    manifest = json.loads(storage.get_bytes(built.manifest_key))
    assert manifest["deployment_id"] == str(deployment_id)
    assert manifest["redirects"] == {"/old-about": "/about"}
    home = storage.get_bytes(manifest["files"]["/"]).decode()
    assert "&lt;script&gt;bad&lt;/script&gt;" in home
    assert "<script>bad</script>" not in home
    assert str(deployment_id) in built.manifest_key


@pytest.mark.asyncio
async def test_memory_provider_models_verification_health_and_disabled_fail_closed() -> None:
    provider = MemoryDomainProvider()
    pending = await provider.create_custom("www.example.com", "idempotency-key")
    assert pending.state == "PENDING_DNS" and pending.verification_value
    provider.mark_custom_active("www.example.com")
    verified = await provider.inspect(pending.provider_id, "www.example.com", "CUSTOM")
    assert verified.state == "ACTIVE" and verified.tls_status == "ACTIVE"
    deployment_id = uuid4()
    provider.healthy.add(("www.example.com", deployment_id))
    assert await provider.health("www.example.com", deployment_id)
    with pytest.raises(DomainProviderError, match="unavailable"):
        await DisabledDomainProvider().provision_subdomain("w.example.com", "idempotency-key")


class FakeCloudflareClient:
    def __init__(self, *, accepted: bool = True) -> None:
        self.accepted = accepted
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []
        self.deployment_id = uuid4()

    async def request(
        self, method: str, url: str, *, json: dict[str, Any] | None = None
    ) -> httpx.Response:
        self.calls.append((method, url, json))
        if not self.accepted:
            return httpx.Response(403, json={"success": False, "result": {}})
        if "custom_hostnames" in url and method == "POST":
            result: dict[str, Any] = {
                "id": "custom-1",
                "status": "pending",
                "ssl": {"status": "pending_validation"},
                "ownership_verification": {
                    "name": "_cf-custom-hostname.www.example.com",
                    "type": "TXT",
                    "value": "proof",
                },
            }
        elif "custom_hostnames" in url:
            result = {"id": "custom-1", "status": "active", "ssl": {"status": "active"}}
        else:
            result = {"id": "dns-1"}
        return httpx.Response(200, json={"success": True, "result": result})

    async def get(self, url: str) -> httpx.Response:
        self.calls.append(("GET", url, None))
        return httpx.Response(200, headers={"x-zylora-deployment": str(self.deployment_id)})


def cloudflare_settings() -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        domain_provider="cloudflare",
        cloudflare_api_token="server-only-token",
        cloudflare_zone_id="zone-id",
        cloudflare_published_origin="origin.example.com",
    )


@pytest.mark.asyncio
async def test_cloudflare_adapter_uses_server_side_custom_hostname_and_health_contracts() -> None:
    client = FakeCloudflareClient()
    provider = CloudflareDomainProvider(cloudflare_settings(), client=client)  # type: ignore[arg-type]
    pending = await provider.create_custom("www.example.com", "idempotency-key")
    assert pending.provider_id == "custom-1" and pending.verification_value == "proof"
    active = await provider.inspect(pending.provider_id, "www.example.com", "CUSTOM")
    assert active.state == "ACTIVE" and active.tls_status == "ACTIVE"
    subdomain = await provider.provision_subdomain("w.example.com", "idempotency-key")
    assert subdomain.provider_id == "dns-1"
    assert await provider.health("w.example.com", client.deployment_id)
    await provider.deactivate(subdomain.provider_id, "ZYLORA_SUBDOMAIN")
    assert any(method == "DELETE" for method, _, _ in client.calls)


@pytest.mark.asyncio
async def test_cloudflare_adapter_rejects_provider_failure_safely() -> None:
    with pytest.raises(DomainProviderError, match="rejected"):
        await CloudflareDomainProvider(
            cloudflare_settings(),
            client=FakeCloudflareClient(accepted=False),  # type: ignore[arg-type]
        ).create_custom("www.example.com", "idempotency-key")


def test_publication_storage_factory_is_test_only_and_fails_closed_otherwise() -> None:
    storage = publication_storage_for(
        Settings(_env_file=None, environment="test", storage_provider="memory")
    )
    assert isinstance(storage, MemoryObjectStorage)
    with pytest.raises(RuntimeError, match="not configured"):
        DisabledPublicationStorage().put_bytes(
            "deployments/a/manifest.json", b"{}", "application/json"
        )


def test_snapshot_paths_and_invariants_are_derived_from_the_immutable_version() -> None:
    version = type(
        "Version",
        (),
        {
            "page_state": [
                {"id": "home", "slug": "home", "is_home": True, "content": {}},
                {
                    "id": "services",
                    "slug": "services",
                    "parent_page_id": None,
                    "is_home": False,
                    "content": {},
                },
                {
                    "id": "seo",
                    "slug": "seo",
                    "parent_page_id": "services",
                    "is_home": False,
                    "content": {},
                },
            ]
        },
    )()
    pages = DeploymentService._snapshot_pages(version)  # type: ignore[arg-type]
    assert {item["path"] for item in pages} == {"/", "/services", "/services/seo"}
    empty_version = type("Version", (), {"page_state": []})()
    with pytest.raises(AuthProblem, match="exactly one home"):
        DeploymentService._snapshot_pages(empty_version)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_disabled_domain_provider_rejects_every_public_operation() -> None:
    provider = DisabledDomainProvider()
    deployment_id = uuid4()

    with pytest.raises(DomainProviderError, match="unavailable"):
        await provider.create_custom("www.example.com", "idempotency-key")
    with pytest.raises(DomainProviderError, match="unavailable"):
        await provider.inspect("provider-id", "www.example.com", "CUSTOM")
    with pytest.raises(DomainProviderError, match="unavailable"):
        await provider.provision_subdomain("w.example.com", "idempotency-key")
    with pytest.raises(DomainProviderError, match="unavailable"):
        await provider.health("www.example.com", deployment_id)
    with pytest.raises(DomainProviderError, match="unavailable"):
        await provider.deactivate("provider-id", "CUSTOM")


@pytest.mark.asyncio
async def test_memory_provider_is_idempotent_and_tracks_route_lifecycle() -> None:
    provider = MemoryDomainProvider()
    first = await provider.create_custom("www.example.com", "first-key")
    duplicate = await provider.create_custom("www.example.com", "second-key")
    assert duplicate == first

    route = await provider.provision_subdomain("w.example.com", "deployment-key")
    assert await provider.inspect(route.provider_id, "w.example.com", "ZYLORA_SUBDOMAIN") == route
    await provider.deactivate(route.provider_id, "ZYLORA_SUBDOMAIN")
    assert route.provider_id in provider.deactivated


@pytest.mark.asyncio
async def test_cloudflare_boundary_rejects_invalid_configuration_and_malformed_responses() -> None:
    with pytest.raises(ValueError, match="DOMAIN_PROVIDER"):
        CloudflareDomainProvider(Settings(_env_file=None, environment="test"))
    with pytest.raises(ValueError, match="incomplete"):
        CloudflareDomainProvider(
            Settings(_env_file=None, environment="test", domain_provider="cloudflare")
        )

    class MalformedCloudflareClient:
        async def request(self, *_: object, **__: object) -> httpx.Response:
            return httpx.Response(200, json={"success": True, "result": []})

    provider = CloudflareDomainProvider(
        cloudflare_settings(),
        client=MalformedCloudflareClient(),  # type: ignore[arg-type]
    )
    with pytest.raises(DomainProviderError, match="invalid domain response"):
        await provider.create_custom("www.example.com", "idempotency-key")


@pytest.mark.asyncio
async def test_cloudflare_health_and_factory_fail_safely_outside_supported_test_modes() -> None:
    class OfflineCloudflareClient:
        async def get(self, _: str) -> httpx.Response:
            raise httpx.ConnectError("offline")

    provider = CloudflareDomainProvider(
        cloudflare_settings(),
        client=OfflineCloudflareClient(),  # type: ignore[arg-type]
    )
    assert not await provider.health("www.example.com", uuid4())
    assert (await provider.inspect("dns-id", "w.example.com", "ZYLORA_SUBDOMAIN")).state == "ACTIVE"
    assert isinstance(
        domain_provider_for(Settings(_env_file=None, environment="test", domain_provider="memory")),
        MemoryDomainProvider,
    )
    assert isinstance(
        domain_provider_for(
            Settings(_env_file=None, environment="test", domain_provider="disabled")
        ),
        DisabledDomainProvider,
    )


def test_disabled_publication_storage_rejects_every_artifact_operation() -> None:
    storage = DisabledPublicationStorage()
    for operation, arguments in (
        (storage.put_bytes, ("deployments/a/manifest.json", b"{}", "application/json")),
        (storage.get_bytes, ("deployments/a/manifest.json",)),
        (storage.delete, ("deployments/a/manifest.json",)),
        (storage.presign_get, ("deployments/a/manifest.json", 60)),
    ):
        with pytest.raises(RuntimeError, match="not configured"):
            operation(*arguments)
    assert isinstance(
        publication_storage_for(
            Settings(_env_file=None, environment="test", storage_provider="disabled")
        ),
        DisabledPublicationStorage,
    )


@pytest.mark.parametrize(
    "pages, expected",
    [
        (
            [
                {"id": "home", "slug": "home", "is_home": True, "content": {}},
                {"id": "about", "slug": "", "is_home": False, "content": {}},
            ],
            "published page URL is invalid",
        ),
        (
            [
                {"id": "home", "slug": "home", "is_home": True, "content": {}},
                {
                    "id": "about",
                    "slug": "about",
                    "parent_page_id": "team",
                    "is_home": False,
                    "content": {},
                },
                {
                    "id": "team",
                    "slug": "team",
                    "parent_page_id": "about",
                    "is_home": False,
                    "content": {},
                },
            ],
            "published page hierarchy is invalid",
        ),
    ],
)
def test_snapshot_rejects_invalid_immutable_page_graphs(
    pages: list[dict[str, object]], expected: str
) -> None:
    version = type("Version", (), {"page_state": pages})()
    with pytest.raises(AuthProblem, match=expected):
        DeploymentService._snapshot_pages(version)  # type: ignore[arg-type]


def test_deployed_renderer_includes_a_real_chatbot_widget_but_export_mode_does_not() -> None:
    page: dict[str, Any] = {
        "name": "Home",
        "seo": {},
        "components": [],
    }
    deployed = render_page(page, [("Home", "/")]).decode()
    exported = render_page(page, [("Home", "/")], include_chatbot=False).decode()
    assert "/api/v1/public/chatbot/conversations" in deployed
    assert "Ask this Website" in deployed
    assert "textContent" in deployed
    assert "/api/v1/public/chatbot/conversations" not in exported
    assert "Ask this Website" not in exported
