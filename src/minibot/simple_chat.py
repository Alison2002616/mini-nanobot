import os
import sys
from typing import Dict, List


if __package__ is None:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from minibot.agent import Agent
from minibot.session import SessionManager
from minibot.tool import Tool, ToolRegistry


class FakeLLM:
    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.2) -> str:
        last_message = messages[-1]["content"]

        if last_message.startswith("TOOL_RESULT:"):
            return "工具调用完成，计算结果是 5。"

        return 'TOOL_CALL: add {"a": 2, "b": 3}'


class SimpleChat:
    def __init__(self) -> None:
        self.registry = ToolRegistry()
        self.sessions = SessionManager()
        self.llm = FakeLLM()
        self._register_tools()
        self.agent = Agent(
            llm=self.llm,
            registry=self.registry,
            sessions=self.sessions,
        )

    def run_once(self) -> str:
        return self.agent.chat("请计算 2 + 3", session_id="simple-chat")

    def _register_tools(self) -> None:
        self.registry.register(Tool(
            name="add",
            description="Add two numbers. Args: a, b",
            call_method=lambda a, b: a + b,
        ))


def main() -> None:
    chat = SimpleChat()
    reply = chat.run_once()
    print(reply)


if __name__ == "__main__":
    main()
