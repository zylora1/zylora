from __future__ import annotations

import json
from typing import ClassVar
from uuid import uuid4

import httpx
import pytest
import zylora_api.modules.editor.provider as provider
from zylora_api.core.config import Settings
from zylora_api.modules.editor.provider import (
    AiPlanningError,
    DisabledPlanner,
    OpenAIPlanner,
    PlanningContext,
)
from zylora_api.modules.editor.schemas import AiEditRequest


def request(scope: str = "WEBSITE") -> AiEditRequest:
    selected = uuid4() if scope == "PAGE" else None
    return AiEditRequest(
        operation_id=uuid4(),
        base_revision=1,
        prompt="Rewrite the heading",
        scope=scope,
        selected_page_id=selected,
    )


def context(selected_page_id: object | None = None) -> PlanningContext:
    page = {"id": "page", "database_id": str(selected_page_id or ""), "components": []}
    return PlanningContext(
        document={"theme": {}, "pages": [page]},
        page_graph=[{"id": str(selected_page_id or uuid4()), "name": "Home"}],
    )


class FakeResponse:
    def __init__(self, payload: dict[str, object], fail: bool = False) -> None:
        self.payload = payload
        self.fail = fail

    def raise_for_status(self) -> None:
        if self.fail:
            raise httpx.HTTPStatusError(
                "provider failed",
                request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
                response=httpx.Response(503),
            )

    def json(self) -> dict[str, object]:
        return self.payload


class FakeClient:
    response = FakeResponse({})
    body: ClassVar[dict[str, object]] = {}

    def __init__(self, timeout: int) -> None:
        assert timeout > 0

    async def __aenter__(self) -> FakeClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(
        self, url: str, headers: dict[str, str], json: dict[str, object]
    ) -> FakeResponse:
        assert url == "https://api.openai.com/v1/responses"
        assert headers["Authorization"].startswith("Bearer ")
        type(self).body = json
        return type(self).response


def completed(text: str) -> dict[str, object]:
    return {
        "status": "completed",
        "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}],
        "usage": {"input_tokens": 30, "output_tokens": 12, "ignored": None},
    }


@pytest.mark.asyncio
async def test_disabled_planner_fails_closed() -> None:
    with pytest.raises(AiPlanningError, match="temporarily unavailable") as failure:
        await DisabledPlanner().plan(request(), context(), "safe")
    assert failure.value.code == "ai_provider_unavailable"


@pytest.mark.asyncio
async def test_openai_planner_uses_responses_structured_output_and_page_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_request = request("PAGE")
    plan = {
        "summary": "Rewrite heading",
        "operations": [
            {
                "kind": "SET_COMPONENT_PROP",
                "page_id": str(selected_request.selected_page_id),
                "component_id": "hero-home",
                "property": "heading",
                "value": "A better heading",
                "position": None,
                "name": None,
                "slug": None,
                "parent_page_id": None,
                "show_in_navigation": None,
                "title": None,
                "description": None,
                "heading": None,
                "body": None,
                "component_type": None,
                "section_type": None,
                "items": None,
            }
        ],
    }
    FakeClient.response = FakeResponse(completed(json.dumps(plan)))
    monkeypatch.setattr(provider.httpx, "AsyncClient", FakeClient)
    settings = Settings(
        environment="test",
        storage_provider="memory",
        ai_provider="openai",
        openai_api_key="secret",
        _env_file=None,
    )
    result = await OpenAIPlanner(settings).plan(
        selected_request,
        context(selected_request.selected_page_id),
        "safe-user",
    )
    assert result.plan.summary == "Rewrite heading"
    assert result.usage == {"input_tokens": 30, "output_tokens": 12}
    assert FakeClient.body["store"] is False
    assert FakeClient.body["model"] == "gpt-5.6-terra"
    assert FakeClient.body["text"]["format"]["strict"] is True  # type: ignore[index]


@pytest.mark.asyncio
async def test_openai_planner_normalizes_defaults_and_provider_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        environment="test",
        storage_provider="memory",
        ai_provider="openai",
        openai_api_key="secret",
        _env_file=None,
    )
    monkeypatch.setattr(provider.httpx, "AsyncClient", FakeClient)
    add_page = {
        "summary": "Add FAQ",
        "operations": [
            {
                "kind": "ADD_PAGE",
                "name": "FAQ",
                "slug": "faq",
                "heading": "FAQ",
                "body": "Answers.",
            }
        ],
    }
    FakeClient.response = FakeResponse(completed(json.dumps(add_page)))
    result = await OpenAIPlanner(settings).plan(request(), context(), "safe")
    assert result.plan.operations[0].kind == "ADD_PAGE"
    assert result.plan.operations[0].show_in_navigation is True  # type: ignore[union-attr]

    FakeClient.response = FakeResponse({}, fail=True)
    with pytest.raises(AiPlanningError) as failure:
        await OpenAIPlanner(settings).plan(request(), context(), "safe")
    assert failure.value.code == "ai_provider_failure"


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({"status": "incomplete"}, "ai_generation_incomplete"),
        (
            {
                "status": "completed",
                "output": [{"type": "message", "content": [{"type": "refusal", "text": "no"}]}],
            },
            "ai_request_refused",
        ),
        ({"status": "completed", "output": []}, "ai_response_missing"),
    ],
)
def test_output_text_fails_safely(payload: dict[str, object], code: str) -> None:
    with pytest.raises(AiPlanningError) as failure:
        provider._output_text(payload)
    assert failure.value.code == code


@pytest.mark.parametrize("body", ["not-json", "[]", '{"summary":"missing operations"}'])
@pytest.mark.asyncio
async def test_openai_planner_rejects_malformed_or_invalid_plans(
    body: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    FakeClient.response = FakeResponse(completed(body))
    monkeypatch.setattr(provider.httpx, "AsyncClient", FakeClient)
    settings = Settings(
        environment="test",
        storage_provider="memory",
        ai_provider="openai",
        openai_api_key="secret",
        _env_file=None,
    )
    with pytest.raises(AiPlanningError) as failure:
        await OpenAIPlanner(settings).plan(request(), context(), "safe")
    assert failure.value.code == "ai_plan_invalid"


def test_planner_factory_selects_real_or_disabled_adapter() -> None:
    disabled = Settings(environment="test", storage_provider="memory", _env_file=None)
    enabled = Settings(
        environment="test",
        storage_provider="memory",
        ai_provider="openai",
        openai_api_key="secret",
        _env_file=None,
    )
    assert isinstance(provider.get_ai_planner(disabled), DisabledPlanner)
    assert isinstance(provider.get_ai_planner(enabled), OpenAIPlanner)
