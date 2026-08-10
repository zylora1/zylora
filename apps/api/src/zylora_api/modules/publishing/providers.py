from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import NoReturn, Protocol
from uuid import UUID, uuid4

import httpx
from zylora_api.core.config import Settings


class DomainProviderError(RuntimeError):
    def __init__(self, code: str, safe_message: str) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message


@dataclass(frozen=True)
class ProviderDomain:
    provider_id: str
    state: str
    tls_status: str
    verification_name: str | None = None
    verification_type: str | None = None
    verification_value: str | None = None


class DomainProvider(Protocol):
    async def create_custom(self, hostname: str, idempotency_key: str) -> ProviderDomain: ...

    async def inspect(
        self, provider_id: str, hostname: str, domain_type: str
    ) -> ProviderDomain: ...

    async def provision_subdomain(self, hostname: str, idempotency_key: str) -> ProviderDomain: ...

    async def health(self, hostname: str, deployment_id: UUID) -> bool: ...

    async def deactivate(self, provider_id: str, domain_type: str) -> None: ...


class DisabledDomainProvider:
    def _raise(self) -> NoReturn:
        raise DomainProviderError(
            "domain_provider_unavailable",
            "Domain publishing is unavailable until Cloudflare SaaS configuration is complete.",
        )

    async def create_custom(self, hostname: str, idempotency_key: str) -> ProviderDomain:
        self._raise()

    async def inspect(self, provider_id: str, hostname: str, domain_type: str) -> ProviderDomain:
        self._raise()

    async def provision_subdomain(self, hostname: str, idempotency_key: str) -> ProviderDomain:
        self._raise()

    async def health(self, hostname: str, deployment_id: UUID) -> bool:
        self._raise()

    async def deactivate(self, provider_id: str, domain_type: str) -> None:
        self._raise()


class MemoryDomainProvider:
    """Deterministic adapter for tests; it is prohibited outside test settings."""

    def __init__(self) -> None:
        self.custom: dict[str, ProviderDomain] = {}
        self.subdomains: dict[str, ProviderDomain] = {}
        self.healthy: set[tuple[str, UUID]] = set()
        self.deactivated: set[str] = set()

    async def create_custom(self, hostname: str, idempotency_key: str) -> ProviderDomain:
        existing = self.custom.get(hostname)
        if existing:
            return existing
        token = sha256(f"{hostname}:{idempotency_key}".encode()).hexdigest()[:32]
        result = ProviderDomain(
            provider_id=f"custom-{uuid4().hex}",
            state="PENDING_DNS",
            tls_status="PENDING",
            verification_name=f"_cf-custom-hostname.{hostname}",
            verification_type="TXT",
            verification_value=token,
        )
        self.custom[hostname] = result
        return result

    def mark_custom_active(self, hostname: str) -> None:
        current = self.custom[hostname]
        self.custom[hostname] = ProviderDomain(current.provider_id, "ACTIVE", "ACTIVE")

    async def inspect(self, provider_id: str, hostname: str, domain_type: str) -> ProviderDomain:
        if domain_type == "ZYLORA_SUBDOMAIN":
            return self.subdomains[hostname]
        return self.custom[hostname]

    async def provision_subdomain(self, hostname: str, idempotency_key: str) -> ProviderDomain:
        return self.subdomains.setdefault(
            hostname,
            ProviderDomain(f"dns-{uuid4().hex}", "ACTIVE", "ACTIVE"),
        )

    async def health(self, hostname: str, deployment_id: UUID) -> bool:
        return (hostname, deployment_id) in self.healthy

    async def deactivate(self, provider_id: str, domain_type: str) -> None:
        self.deactivated.add(provider_id)


class CloudflareDomainProvider:
    """Cloudflare for SaaS/DNS adapter. Tokens remain server-side in Settings only."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        if settings.domain_provider != "cloudflare":
            raise ValueError("Cloudflare adapter requires DOMAIN_PROVIDER=cloudflare")
        if not all(
            (
                settings.cloudflare_api_token,
                settings.cloudflare_zone_id,
                settings.cloudflare_published_origin,
            )
        ):
            raise ValueError("Cloudflare domain settings are incomplete")
        self.settings = settings
        self.client = client or httpx.AsyncClient(
            base_url="https://api.cloudflare.com/client/v4",
            timeout=settings.cloudflare_api_timeout_seconds,
            headers={"Authorization": f"Bearer {settings.cloudflare_api_token}"},
        )

    async def _request(
        self, method: str, url: str, *, json: dict[str, object] | None = None
    ) -> dict[str, object]:
        try:
            response = await self.client.request(method, url, json=json)
            body = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise DomainProviderError(
                "cloudflare_unavailable", "Cloudflare could not be reached."
            ) from error
        if not response.is_success or body.get("success") is not True:
            raise DomainProviderError(
                "cloudflare_rejected", "Cloudflare rejected the domain operation."
            )
        result = body.get("result")
        if not isinstance(result, dict):
            raise DomainProviderError(
                "cloudflare_malformed", "Cloudflare returned an invalid domain response."
            )
        return result

    @staticmethod
    def _status(result: dict[str, object]) -> ProviderDomain:
        state = str(result.get("status", "pending")).upper()
        ssl = result.get("ssl")
        ssl_status = (
            str(ssl.get("status", "pending")).upper() if isinstance(ssl, dict) else "PENDING"
        )
        ownership = result.get("ownership_verification")
        return ProviderDomain(
            provider_id=str(result["id"]),
            state="ACTIVE" if state in {"ACTIVE", "PROVISIONED"} else state,
            tls_status="ACTIVE" if ssl_status == "ACTIVE" else "PENDING",
            verification_name=str(ownership.get("name")) if isinstance(ownership, dict) else None,
            verification_type=str(ownership.get("type", "TXT")).upper()
            if isinstance(ownership, dict)
            else None,
            verification_value=str(ownership.get("value")) if isinstance(ownership, dict) else None,
        )

    async def create_custom(self, hostname: str, idempotency_key: str) -> ProviderDomain:
        result = await self._request(
            "POST",
            f"/zones/{self.settings.cloudflare_zone_id}/custom_hostnames",
            json={
                "hostname": hostname,
                "custom_origin_server": self.settings.cloudflare_published_origin,
                "custom_origin_sni": self.settings.cloudflare_published_origin,
                "ssl": {"method": "txt", "type": "dv"},
                "custom_metadata": {"zylora_request": idempotency_key},
            },
        )
        return self._status(result)

    async def inspect(self, provider_id: str, hostname: str, domain_type: str) -> ProviderDomain:
        if domain_type == "ZYLORA_SUBDOMAIN":
            return ProviderDomain(provider_id, "ACTIVE", "ACTIVE")
        result = await self._request(
            "GET", f"/zones/{self.settings.cloudflare_zone_id}/custom_hostnames/{provider_id}"
        )
        return self._status(result)

    async def provision_subdomain(self, hostname: str, idempotency_key: str) -> ProviderDomain:
        result = await self._request(
            "POST",
            f"/zones/{self.settings.cloudflare_zone_id}/dns_records",
            json={
                "type": "CNAME",
                "name": hostname,
                "content": self.settings.cloudflare_published_origin,
                "proxied": True,
                "ttl": 1,
                "comment": f"zylora deployment {idempotency_key}",
            },
        )
        return ProviderDomain(str(result["id"]), "ACTIVE", "ACTIVE")

    async def health(self, hostname: str, deployment_id: UUID) -> bool:
        try:
            response = await self.client.get(f"https://{hostname}/_zylora/health")
        except httpx.HTTPError:
            return False
        return response.status_code == 200 and response.headers.get("x-zylora-deployment") == str(
            deployment_id
        )

    async def deactivate(self, provider_id: str, domain_type: str) -> None:
        resource = "custom_hostnames" if domain_type == "CUSTOM" else "dns_records"
        await self._request(
            "DELETE", f"/zones/{self.settings.cloudflare_zone_id}/{resource}/{provider_id}"
        )


def domain_provider_for(settings: Settings) -> DomainProvider:
    if settings.domain_provider == "cloudflare":
        return CloudflareDomainProvider(settings)
    if settings.domain_provider == "memory" and settings.environment == "test":
        return MemoryDomainProvider()
    return DisabledDomainProvider()
