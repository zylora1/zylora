from __future__ import annotations

from types import SimpleNamespace

import pytest
from zylora_api.modules.auth.errors import AuthProblem
from zylora_api.modules.commerce.service import (
    PLAN_CODES,
    REQUIRED_CAPABILITIES,
    CatalogService,
    entitlement_value,
    snapshot_entitlements,
)


def test_catalog_validation_and_entitlement_snapshots_fail_closed() -> None:
    def bundle(
        code: str,
        slot: int,
        entitlements: dict[str, object],
        *,
        most_popular: bool = False,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            plan=SimpleNamespace(code=code, slot=slot, most_popular=most_popular),
            entitlements=entitlements,
        )

    with pytest.raises(AuthProblem, match="invalid_plan_catalog"):
        CatalogService._validate([bundle("NOT_A_PLAN", 1, {})])

    incomplete = [bundle(code, index, {}) for index, code in enumerate(PLAN_CODES, 1)]
    with pytest.raises(AuthProblem, match="invalid_plan_catalog"):
        CatalogService._validate(incomplete)  # type: ignore[arg-type]

    full = [
        bundle(code, index, dict.fromkeys(REQUIRED_CAPABILITIES, True))
        for index, code in enumerate(PLAN_CODES, 1)
    ]
    with pytest.raises(AuthProblem, match="invalid_plan_catalog"):
        CatalogService._validate(full)  # type: ignore[arg-type]

    with pytest.raises(AuthProblem, match="invalid_plan_catalog"):
        entitlement_value(SimpleNamespace(value_type="BOOLEAN", value_bool=None))
    with pytest.raises(AuthProblem, match="invalid_plan_catalog"):
        snapshot_entitlements({"unsupported": object()})
