from __future__ import annotations

import math
from types import SimpleNamespace

import httpx
import pytest
from zylora_api.core.config import Settings
from zylora_api.modules.chatbot import embeddings
from zylora_api.modules.chatbot.embeddings import (
    DeterministicEmbeddingProvider,
    EmbeddingProviderError,
    OpenAIEmbeddingProvider,
)
from zylora_api.modules.chatbot.indexing import FaissIndexCodec, KnowledgeIndexService
from zylora_api.modules.chatbot.service import ChatbotService
from zylora_api.storage.memory import MemoryObjectStorage


class FakeResponse:
    def __init__(self, body: object) -> None:
        self.body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self.body


class FakeClient:
    def __init__(self, response: FakeResponse | Exception) -> None:
        self.response = response
        self.request: dict[str, object] | None = None

    async def __aenter__(self) -> FakeClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.request = {"url": url, **kwargs}
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@pytest.mark.asyncio
async def test_openai_embedding_adapter_validates_server_response_and_fails_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        environment="test",
        openai_api_key="server-only-test-key",
        chatbot_embedding_model="embedding-test",
    )
    client = FakeClient(
        FakeResponse({"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]})
    )
    monkeypatch.setattr(embeddings.httpx, "AsyncClient", lambda **_: client)
    provider = OpenAIEmbeddingProvider(settings)
    assert await provider.embed(["one", "two"]) == [[0.1, 0.2], [0.3, 0.4]]
    assert client.request and client.request["url"] == "https://api.openai.com/v1/embeddings"

    offline = FakeClient(httpx.ConnectError("offline"))
    monkeypatch.setattr(embeddings.httpx, "AsyncClient", lambda **_: offline)
    with pytest.raises(EmbeddingProviderError):
        await provider.embed(["one"])


@pytest.mark.asyncio
async def test_deterministic_embeddings_and_faiss_codec_reject_invalid_artifacts() -> None:
    provider = DeterministicEmbeddingProvider(8)
    vectors = await provider.embed(["Dental implants", "artisan bread", ""])
    assert len(vectors) == 3 and all(len(vector) == 8 for vector in vectors)
    assert vectors[2][0] == 1.0

    artifact = FaissIndexCodec.build([[1.0, 0.0], [0.0, 1.0]])
    assert FaissIndexCodec.search(artifact, [1.0, 0.0], 1) == [0]
    with pytest.raises(ValueError, match="nonempty"):
        FaissIndexCodec.build([])
    with pytest.raises(ValueError, match="finite"):
        FaissIndexCodec.build([[math.inf, 0.0]])
    with pytest.raises(ValueError, match="between"):
        FaissIndexCodec.search(artifact, [1.0, 0.0], 0)
    with pytest.raises(ValueError, match="dimension"):
        FaissIndexCodec.search(artifact, [1.0, 0.0, 0.0], 1)


def test_published_text_extraction_discards_urls_and_chunks_long_content() -> None:
    long_text = " ".join(["useful"] * 200)
    version = SimpleNamespace(
        page_state=[
            {
                "id": "home",
                "slug": "",
                "is_home": True,
                "name": "Home",
                "content": {
                    "components": [
                        {
                            "props": {
                                "heading": "  Trusted   dental care  ",
                                "href": "https://outside.example/path",
                                "nested": ["/internal-path", {"copy": long_text}],
                            }
                        },
                        {"props": "not-indexable"},
                    ]
                },
            },
            {
                "id": "services",
                "slug": "services",
                "parent_page_id": "home",
                "is_home": False,
                "label": "Services",
                "content": {"components": []},
            },
        ]
    )

    extracted = KnowledgeIndexService._extract(version)
    content = " ".join(item.content for item in extracted)
    assert {item.page_path for item in extracted} == {"/", "/services"}
    assert "Trusted dental care" in content
    assert "outside.example" not in content and "internal-path" not in content
    assert len([item for item in extracted if item.component_path == "components[0]"]) >= 2


@pytest.mark.asyncio
async def test_embedding_adapter_rejects_empty_credentials_and_malformed_provider_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    no_key = OpenAIEmbeddingProvider(Settings(_env_file=None, environment="test"))
    with pytest.raises(EmbeddingProviderError):
        await no_key.embed(["private content"])
    with pytest.raises(ValueError, match="dimension"):
        DeterministicEmbeddingProvider(7)

    settings = Settings(
        _env_file=None,
        environment="test",
        openai_api_key="server-only-test-key",
    )
    provider = OpenAIEmbeddingProvider(settings)
    for body in ({"data": "invalid"}, {"data": [{}]}, {"data": [{"embedding": ["bad"]}]}):
        monkeypatch.setattr(
            embeddings.httpx, "AsyncClient", lambda body=body, **_: FakeClient(FakeResponse(body))
        )
        with pytest.raises(EmbeddingProviderError):
            await provider.embed(["private content"])

    chatbot = ChatbotService.from_settings(object(), MemoryObjectStorage(), settings)
    assert isinstance(chatbot.embeddings, OpenAIEmbeddingProvider)
