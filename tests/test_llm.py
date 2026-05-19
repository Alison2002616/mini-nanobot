import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from minibot.agent import Agent
from minibot.Providers.base import LLMProvider, LLMResponse
from minibot.session import SessionManager
from minibot.tool import Tool, ToolRegistry


class MockProvider(LLMProvider):
    name = "mock"

    def __init__(self):
        super().__init__(api_key="mock", base_url="mock", model="mock-model")
        self.calls = 0

    def chat(self, messages, **kwargs):
        self.calls += 1
        return self._response(messages)

    def chat_stream(self, messages, on_stream=None, **kwargs):
        self.calls += 1
        response = self._response(messages)
        if on_stream:
            on_stream(response.content)
        return response

    def _response(self, messages):
        if messages[-1]["content"].startswith("TOOL_RESULT:"):
            return LLMResponse(
                content="The result is 5.",
                provider=self.name,
                model=self.model,
            )
        return LLMResponse(
            content='TOOL_CALL: add {"a": 2, "b": 3}',
            provider=self.name,
            model=self.model,
        )


def test_agent_react_loop_with_mock_provider():
    registry = ToolRegistry()
    registry.register(Tool("add", "Add two numbers", lambda a, b: a + b))

    agent = Agent(
        llm=MockProvider(),
        registry=registry,
        sessions=SessionManager(),
    )

    response = agent.chat("2 + 3?", session_id="test")

    assert response.content == "The result is 5."
    assert [event.phase for event in response.tool_events] == ["start", "end"]


def test_agent_streaming_path_buffers_final_response():
    registry = ToolRegistry()
    registry.register(Tool("add", "Add two numbers", lambda a, b: a + b))

    chunks = []
    agent = Agent(
        llm=MockProvider(),
        registry=registry,
        sessions=SessionManager(),
    )

    response = agent.chat(
        "2 + 3?",
        session_id="stream-test",
        metadata={"_wants_stream": True},
        on_stream=lambda text: chunks.append(text),
    )

    assert response.content == "The result is 5."
    assert chunks
