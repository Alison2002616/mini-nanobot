import json
import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from minibot.llm import LLMClient
from minibot.Providers.deepseek import DeepSeekProvider
from minibot.Providers.openai import OpenAIProvider


class FakeHTTPResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.body


def test_legacy_llm_client_parses_chat_response(monkeypatch):
    body = json.dumps({
        "choices": [{"message": {"content": "hello"}}],
    }).encode("utf-8")

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: FakeHTTPResponse(body),
    )

    client = LLMClient(
        api_key="key",
        base_url="https://example.test/v1",
        model="mock-model",
    )

    assert client.chat([{"role": "user", "content": "hi"}]) == "hello"


def test_provider_wrappers_define_defaults():
    deepseek = DeepSeekProvider(api_key="key")
    openai = OpenAIProvider(api_key="key")

    assert deepseek.name == "deepseek"
    assert deepseek.base_url.endswith("/v1")
    assert openai.name == "openai"
    assert openai.model


def test_lowercase_providers_import_alias():
    from minibot.providers.base import LLMResponse

    assert LLMResponse(content="ok").content == "ok"
