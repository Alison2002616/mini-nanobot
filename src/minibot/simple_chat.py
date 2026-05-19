import os
import sys
from typing import Any, Dict, List, Optional


if __package__ is None:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from minibot.agent import Agent
from minibot.Providers.base import LLMProvider, LLMResponse, OnStream
from minibot.session import SessionManager
from minibot.tool import Tool, ToolRegistry


class MockProvider(LLMProvider):
    name = "mock"

    def __init__(self) -> None:
        super().__init__(api_key="mock", base_url="mock", model="mock-model")
        self.calls = 0

    def chat(self, messages: List[Dict[str, Any]], **kwargs: Any) -> LLMResponse:
        self.calls += 1
        return self._response(messages)

    def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        on_stream: Optional[OnStream] = None,
        **kwargs: Any
    ) -> LLMResponse:
        self.calls += 1
        response = self._response(messages)
        if on_stream:
            on_stream(response.content)
        return response

    def _response(self, messages: List[Dict[str, Any]]) -> LLMResponse:
        last_message = messages[-1]["content"]
        if last_message.startswith("TOOL_RESULT:"):
            return LLMResponse(
                content="Tool call finished. The result is 5.",
                provider=self.name,
                model=self.model,
            )

        return LLMResponse(
            content='TOOL_CALL: add {"a": 2, "b": 3}',
            provider=self.name,
            model=self.model,
        )


class SimpleChat:
    def __init__(self) -> None:
        self.registry = ToolRegistry()
        self.sessions = SessionManager()
        self.provider = MockProvider()
        self._register_tools()
        self.agent = Agent(
            llm=self.provider,
            registry=self.registry,
            sessions=self.sessions,
        )

    def run_once(self) -> LLMResponse:
        return self.agent.chat("Please calculate 2 + 3.", session_id="simple-chat")

    def _register_tools(self) -> None:
        self.registry.register(Tool(
            name="add",
            description="Add two numbers. Args: a, b",
            call_method=lambda a, b: a + b,
        ))


def main() -> None:
    chat = SimpleChat()
    reply = chat.run_once()
    print(reply.content)


if __name__ == "__main__":
    main()
