from __future__ import annotations

import json
from dataclasses import dataclass
from time import monotonic
from typing import Any, Protocol

import httpx
from pydantic import ValidationError
from zylora_api.core.config import Settings
from zylora_api.modules.editor.schemas import AiEditRequest, EditPlan

PROMPT_TEMPLATE_VERSION = "2026-08-12.1"


class AiPlanningError(RuntimeError):
    def __init__(self, code: str, safe_message: str) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message


@dataclass(frozen=True)
class PlanningContext:
    document: dict[str, object]
    page_graph: list[dict[str, object]]


@dataclass(frozen=True)
class PlannerResult:
    plan: EditPlan
    provider: str
    model: str
    usage: dict[str, int | float | str]
    latency_ms: int


class AiPlanner(Protocol):
    async def plan(
        self,
        request: AiEditRequest,
        context: PlanningContext,
        safety_identifier: str,
    ) -> PlannerResult: ...


class DisabledPlanner:
    async def plan(
        self,
        request: AiEditRequest,
        context: PlanningContext,
        safety_identifier: str,
    ) -> PlannerResult:
        del request, context, safety_identifier
        raise AiPlanningError(
            "ai_provider_unavailable",
            "AI editing is temporarily unavailable. Your Draft and credits were not changed.",
        )


def _operation_schema() -> dict[str, object]:
    nullable_string = {"type": ["string", "null"]}
    nullable_integer = {"type": ["integer", "null"]}
    nullable_boolean = {"type": ["boolean", "null"]}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "kind",
            "page_id",
            "component_id",
            "component_type",
            "property",
            "value",
            "position",
            "name",
            "slug",
            "parent_page_id",
            "show_in_navigation",
            "title",
            "description",
            "heading",
            "body",
            "section_type",
            "items",
        ],
        "properties": {
            "kind": {
                "type": "string",
                "enum": [
                    "SET_COMPONENT_PROP",
                    "SET_THEME_TOKEN",
                    "INSERT_COMPONENT",
                    "REMOVE_COMPONENT",
                    "MOVE_COMPONENT",
                    "SET_PAGE_SEO",
                    "ADD_PAGE",
                    "MOVE_PAGE",
                    "SET_NAVIGATION_VISIBILITY",
                ],
            },
            "page_id": nullable_string,
            "component_id": nullable_string,
            "component_type": {
                "type": ["string", "null"],
                "enum": [
                    "SECTION",
                    "HEADING",
                    "RICH_TEXT",
                    "TESTIMONIALS",
                    "FAQ",
                    None,
                ],
            },
            "property": nullable_string,
            "value": {"type": ["string", "integer", "boolean", "null"]},
            "position": nullable_integer,
            "name": nullable_string,
            "slug": nullable_string,
            "parent_page_id": nullable_string,
            "show_in_navigation": nullable_boolean,
            "title": nullable_string,
            "description": nullable_string,
            "heading": nullable_string,
            "body": nullable_string,
            "section_type": {
                "type": ["string", "null"],
                "enum": ["STANDARD", "FAQ", None],
            },
            "items": {
                "type": ["array", "null"],
                "items": {"type": "string"},
                "maxItems": 12,
            },
        },
    }


def _plan_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["summary", "operations"],
        "properties": {
            "summary": {"type": "string", "minLength": 1, "maxLength": 240},
            "operations": {
                "type": "array",
                "minItems": 1,
                "maxItems": 30,
                "items": _operation_schema(),
            },
        },
    }


def _clean_plan(raw: dict[str, Any]) -> EditPlan:
    operations = []
    for candidate in raw.get("operations", []):
        if not isinstance(candidate, dict):
            continue
        operation = {key: value for key, value in candidate.items() if value is not None}
        if operation.get("kind") in {"INSERT_COMPONENT", "ADD_PAGE"}:
            operation.setdefault("items", [])
        if operation.get("kind") == "INSERT_COMPONENT":
            operation.setdefault("position", 0)
            operation.setdefault("heading", "")
            operation.setdefault("body", "")
        if operation.get("kind") == "ADD_PAGE":
            operation.setdefault("show_in_navigation", True)
            operation.setdefault("section_type", "STANDARD")
        if operation.get("kind") == "MOVE_PAGE":
            operation.setdefault("position", 0)
        operations.append(operation)
    try:
        return EditPlan.model_validate({"summary": raw.get("summary"), "operations": operations})
    except ValidationError as exc:
        raise AiPlanningError(
            "ai_plan_invalid",
            "AI returned a change plan that did not pass Zylora validation. Nothing was changed.",
        ) from exc


def _output_text(payload: dict[str, Any]) -> str:
    if payload.get("status") != "completed":
        raise AiPlanningError(
            "ai_generation_incomplete",
            "AI could not finish the change plan. Your Draft and credits were not changed.",
        )
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "refusal":
                raise AiPlanningError(
                    "ai_request_refused",
                    "AI could not process that request. Your Draft and credits were not changed.",
                )
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                return str(content["text"])
    raise AiPlanningError(
        "ai_response_missing",
        "AI returned no usable change plan. Your Draft and credits were not changed.",
    )


class OpenAIPlanner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def plan(
        self,
        request: AiEditRequest,
        context: PlanningContext,
        safety_identifier: str,
    ) -> PlannerResult:
        instructions = (
            "You are Zylora's structured Website editing planner. "
            "Operate only on the supplied existing template-based Draft. "
            "Return the narrowest operations needed for the user's request. "
            "Never invent Page IDs or component IDs. Respect the requested PAGE or WEBSITE scope. "
            "Use ADD_PAGE or MOVE_PAGE for hierarchy changes and preserve home-page invariants. "
            "Do not output prose outside the schema."
        )
        selected_document: dict[str, object]
        if request.scope == "PAGE":
            document_pages = context.document.get("pages", [])
            if not isinstance(document_pages, list):
                document_pages = []
            selected = [
                page
                for page in document_pages
                if isinstance(page, dict)
                and page.get("database_id") == str(request.selected_page_id)
            ]
            selected_document = {
                "theme": context.document.get("theme", {}),
                "pages": selected,
            }
        else:
            selected_document = context.document
        user_input = json.dumps(
            {
                "request": request.prompt,
                "scope": request.scope,
                "selected_page_id": str(request.selected_page_id or ""),
                "page_graph": context.page_graph,
                "document": selected_document,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        body = {
            "model": self.settings.openai_model,
            "store": False,
            "instructions": instructions,
            "input": user_input,
            "max_output_tokens": self.settings.ai_max_output_tokens,
            "reasoning": {"effort": "low"},
            "safety_identifier": safety_identifier,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "zylora_edit_plan",
                    "strict": True,
                    "schema": _plan_schema(),
                }
            },
        }
        started = monotonic()
        try:
            async with httpx.AsyncClient(timeout=self.settings.ai_timeout_seconds) as client:
                response = await client.post(
                    self.settings.openai_base_url.rstrip("/") + "/responses",
                    headers={
                        "Authorization": f"Bearer {self.settings.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AiPlanningError(
                "ai_provider_failure",
                "AI editing could not be reached. Your Draft and credits were not changed.",
            ) from exc
        latency_ms = int((monotonic() - started) * 1000)
        try:
            raw_plan = json.loads(_output_text(payload))
        except json.JSONDecodeError as exc:
            raise AiPlanningError(
                "ai_plan_invalid",
                "AI returned an invalid change plan. Nothing was changed.",
            ) from exc
        if not isinstance(raw_plan, dict):
            raise AiPlanningError("ai_plan_invalid", "AI returned an invalid change plan.")
        usage = {
            key: value
            for key, value in dict(payload.get("usage") or {}).items()
            if isinstance(value, (int, float, str))
        }
        return PlannerResult(
            plan=_clean_plan(raw_plan),
            provider="OPENAI",
            model=self.settings.openai_model,
            usage=usage,
            latency_ms=latency_ms,
        )


def get_ai_planner(settings: Settings) -> AiPlanner:
    if settings.ai_provider == "openai" and settings.openai_api_key:
        return OpenAIPlanner(settings)
    return DisabledPlanner()
