import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import minibot
from minibot.cli import MiniBotClient, build_parser, create_provider_from_env, load_env_file
from minibot.Providers.base import LLMProvider, LLMResponse
from minibot.simple_chat import SimpleChat


class MockProvider(LLMProvider):
    name = "mock"

    def __init__(self):
        super().__init__(api_key="mock", base_url="mock", model="mock-model")

    def chat(self, messages, **kwargs):
        return LLMResponse(content="hello", provider=self.name, model=self.model)

    def chat_stream(self, messages, on_stream=None, **kwargs):
        if on_stream:
            on_stream("hello")
        return LLMResponse(content="hello", provider=self.name, model=self.model)


def test_package_exports_core_types():
    assert minibot.Agent.__name__ == "Agent"
    assert minibot.LLMResponse(content="x").content == "x"


def test_load_env_file_reads_key_values(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text('DEFAULT_PROVIDER="deepseek"\nDEEPSEEK_MODEL="m"\n')

    env = load_env_file(str(env_file))

    assert env["DEFAULT_PROVIDER"] == "deepseek"
    assert env["DEEPSEEK_MODEL"] == "m"


def test_create_provider_from_env_uses_vendor_prefixes():
    provider = create_provider_from_env({
        "DEFAULT_PROVIDER": "deepseek",
        "DEEPSEEK_API_KEY": "key",
        "DEEPSEEK_BASE_URL": "https://example.test/v1",
        "DEEPSEEK_MODEL": "model",
    })

    assert provider.name == "deepseek"
    assert provider.model == "model"


def test_minibot_client_accepts_injected_provider():
    client = MiniBotClient(provider=MockProvider())
    response = client.ask("hi")

    assert response.content == "hello"


def test_minibot_client_streams_with_callback():
    chunks = []
    client = MiniBotClient(provider=MockProvider())

    response = client.ask("hi", stream=True, on_stream=lambda text: chunks.append(text))

    assert response.content == "hello"
    assert chunks == ["hello"]


def test_cli_parser_accepts_message_option():
    parser = build_parser()
    args = parser.parse_args(["-m", "hello"])

    assert args.message_option == "hello"


def test_simple_chat_runs_mock_react_flow():
    response = SimpleChat().run_once()

    assert response.content == "Tool call finished. The result is 5."
