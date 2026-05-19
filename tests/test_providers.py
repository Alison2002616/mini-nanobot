import json
import os
import sys

import pytest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from minibot.Providers.base import LLMResponse, ToolEvent
from minibot.Providers.claude import ClaudeProvider
from minibot.Providers.errors import ProviderConfigError, ProviderStreamError
from minibot.Providers.openai_compatible import OpenAICompatibleProvider
from minibot.Providers.registry import ProviderRegistry


class FakeHTTPResponse:
    def __init__(self, body=None, lines=None):
        self.body = body or b""
        self.lines = lines or []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.body

    def __iter__(self):
        return iter(self.lines)


def test_llm_response_and_tool_event_to_dict():
    event = ToolEvent("start", "call-1", "echo", {"text": "hi"})
    response = LLMResponse(
        content="hello",
        provider="mock",
        model="mock-model",
        tool_events=[event],
        usage={"total_tokens": 1},
    )

    data = response.to_dict()

    assert data["content"] == "hello"
    assert data["tool_events"][0]["call_id"] == "call-1"
    assert data["usage"]["total_tokens"] == 1


def test_provider_registry_registers_and_creates_provider():
    class MockProvider(OpenAICompatibleProvider):
        name = "mock"
        default_base_url = "https://example.test/v1"
        default_model = "mock-model"

    registry = ProviderRegistry()
    registry.register("mock", MockProvider)
    provider = registry.create("mock", api_key="key")

    assert provider.name == "mock"
    assert registry.list_providers() == ["mock"]
    assert registry.register("mock", MockProvider) is MockProvider


def test_provider_registry_rejects_unknown_provider():
    registry = ProviderRegistry()

    with pytest.raises(ProviderConfigError):
        registry.get("missing")


def test_openai_compatible_requires_config():
    with pytest.raises(ProviderConfigError):
        OpenAICompatibleProvider()


def test_openai_compatible_chat_parses_response(monkeypatch):
    body = json.dumps({
        "model": "mock-model",
        "choices": [{
            "message": {"content": "hello"},
            "finish_reason": "stop",
        }],
        "usage": {"total_tokens": 3},
    }).encode("utf-8")

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: FakeHTTPResponse(body=body),
    )

    provider = OpenAICompatibleProvider(
        api_key="key",
        base_url="https://example.test/v1",
        model="mock-model",
    )
    response = provider.chat([{"role": "user", "content": "hi"}])

    assert response.content == "hello"
    assert response.finish_reason == "stop"
    assert response.usage["total_tokens"] == 3


def test_openai_compatible_stream_parses_chunks(monkeypatch):
    events = [
        b'data: {"choices":[{"delta":{"content":"he"}}]}\n',
        b'data: {"choices":[{"delta":{"content":"llo"},"finish_reason":"stop"}],"usage":{"total_tokens":3}}\n',
        b"data: [DONE]\n",
    ]
    chunks = []

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: FakeHTTPResponse(lines=events),
    )

    provider = OpenAICompatibleProvider(
        api_key="key",
        base_url="https://example.test/v1",
        model="mock-model",
    )
    response = provider.chat_stream(
        [{"role": "user", "content": "hi"}],
        on_stream=lambda text: chunks.append(text),
    )

    assert response.content == "hello"
    assert chunks == ["he", "llo"]
    assert response.finish_reason == "stop"


def test_openai_compatible_stream_can_be_cancelled(monkeypatch):
    events = [b'data: {"choices":[{"delta":{"content":"he"}}]}\n']

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: FakeHTTPResponse(lines=events),
    )

    provider = OpenAICompatibleProvider(
        api_key="key",
        base_url="https://example.test/v1",
        model="mock-model",
    )

    with pytest.raises(ProviderStreamError):
        provider.chat_stream(
            [{"role": "user", "content": "hi"}],
            on_stream=lambda text: False,
        )


def test_claude_chat_parses_response(monkeypatch):
    body = json.dumps({
        "model": "claude-mock",
        "content": [{"type": "text", "text": "hello"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }).encode("utf-8")

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: FakeHTTPResponse(body=body),
    )

    provider = ClaudeProvider(api_key="key", model="claude-mock")
    response = provider.chat([{"role": "user", "content": "hi"}])

    assert response.content == "hello"
    assert response.finish_reason == "end_turn"


def test_claude_stream_parses_text_delta(monkeypatch):
    events = [
        b"event: content_block_delta\n",
        b'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"hi"}}\n',
        b"event: message_delta\n",
        b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":1}}\n',
        b"event: message_stop\n",
        b'data: {"type":"message_stop"}\n',
    ]
    chunks = []

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: FakeHTTPResponse(lines=events),
    )

    provider = ClaudeProvider(api_key="key", model="claude-mock")
    response = provider.chat_stream(
        [{"role": "user", "content": "hi"}],
        on_stream=lambda text: chunks.append(text),
    )

    assert response.content == "hi"
    assert chunks == ["hi"]
    assert response.finish_reason == "end_turn"
