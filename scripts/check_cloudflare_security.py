from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLOUDFLARE = ROOT / "infra" / "cloudflare"


def require(text: str, values: tuple[str, ...], source: str) -> None:
    missing = [value for value in values if value not in text]
    if missing:
        raise SystemExit(f"{source} is missing required Cloudflare controls: {missing}")


def main() -> None:
    versions = (CLOUDFLARE / "versions.tf").read_text(encoding="utf-8")
    main_tf = (CLOUDFLARE / "main.tf").read_text(encoding="utf-8")
    outputs = (CLOUDFLARE / "outputs.tf").read_text(encoding="utf-8")

    require(versions, ('required_version = "= 1.14.6"', 'version = "= 5.22.0"'), "versions.tf")
    require(
        main_tf,
        (
            'resource "cloudflare_turnstile_widget"',
            'mode            = "managed"',
            'clearance_level = "no_clearance"',
            'phase       = "http_request_firewall_managed"',
            'phase       = "http_request_firewall_custom"',
            'phase       = "http_ratelimit"',
            "efb7b8c949ac4650a09736fc376e9aee",
            "4814384a9e5d4991b9815dcfc25d2f1f",
            '["cf.colo.id", "ip.src"]',
            '"/api/v1/auth/signup"',
            '"/api/v1/auth/login"',
            '"/api/v1/auth/verify-email"',
            '"/api/v1/auth/password-reset/request"',
            '"/api/v1/auth/google/start"',
            '"/api/v1/admin/auth/login"',
            "/api/v1/chatbot",
            "/api/v1/leads",
        ),
        "main.tf",
    )
    if 'output "turnstile_secret' in outputs.casefold():
        raise SystemExit("outputs.tf must never expose the Turnstile secret")
    print("Cloudflare Turnstile, managed WAF, custom WAF, and rate-limit controls verified.")


if __name__ == "__main__":
    main()
