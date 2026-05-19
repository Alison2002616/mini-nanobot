import argparse
import os
import sys
from datetime import datetime
from typing import Dict, Optional


if __package__ is None:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from minibot.agent import Agent
from minibot.llm import LLMClient
from minibot.session import SessionManager
from minibot.tool import Tool, ToolRegistry


DEFAULT_SESSION_ID = "default"
BLUE = "\033[34m"
YELLOW = "\033[33m"
RESET = "\033[0m"


class MiniBotClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        session_id: str = DEFAULT_SESSION_ID,
        env_file: str = ".env",
    ) -> None:
        env = load_env_file(env_file)

        self.session_id = session_id
        self.registry = ToolRegistry()
        self.sessions = SessionManager()
        self._register_default_tools()

        self.llm = LLMClient(
            api_key=api_key or env.get("api_key") or env.get("OPENAI_API_KEY"),
            base_url=base_url or env.get("base_url") or env.get("OPENAI_BASE_URL"),
            model=model or env.get("model") or env.get("OPENAI_MODEL"),
        )
        self.agent = Agent(
            llm=self.llm,
            registry=self.registry,
            sessions=self.sessions,
        )

    def ask(self, content: str, session_id: Optional[str] = None) -> str:
        return self.agent.chat(content=content, session_id=session_id or self.session_id)

    def set_session(self, session_id: str) -> None:
        self.session_id = session_id
        self.sessions.get_or_create_session(session_id=session_id)

    def clear_session(self, session_id: Optional[str] = None) -> None:
        session = self.sessions.get_or_create_session(session_id=session_id or self.session_id)
        session.clear()

    def list_tools(self) -> str:
        tools = self.registry.describe_tools()
        if not tools:
            return "No tools registered."

        lines = []
        for tool in tools:
            lines.append("- {name}: {description}".format(**tool))
        return "\n".join(lines)

    def _register_default_tools(self) -> None:
        self.registry.register(Tool(
            name="echo",
            description="Return the input text. Args: text",
            call_method=lambda text: text,
        ))
        self.registry.register(Tool(
            name="now",
            description="Return current local datetime. Args: none",
            call_method=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ))


def _resolve_path(path: str) -> Optional[str]:
    if not path:
        return None
    if os.path.isabs(path):
        return path if os.path.exists(path) else None

    # 从当前工作目录向上查找
    directory = os.getcwd()
    for _ in range(6):
        candidate = os.path.join(directory, path)
        if os.path.exists(candidate):
            return candidate
        parent = os.path.dirname(directory)
        if parent == directory:
            break
        directory = parent
    return None


def load_env_file(path: str) -> Dict[str, str]:
    env = {}  # type: Dict[str, str]
    resolved = _resolve_path(path)
    if not resolved:
        return env

    with open(resolved, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            env[key] = value

    return env


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MiniBot command line client.")
    parser.add_argument("message", nargs="*", help="Message to send. Empty means interactive mode.")
    parser.add_argument("--session", default=DEFAULT_SESSION_ID, help="Session id for memory isolation.")
    parser.add_argument("--api-key", default=None, help="API key. Defaults to .env or environment variables.")
    parser.add_argument("--base-url", default=None, help="OpenAI-compatible API base URL.")
    parser.add_argument("--model", default=None, help="Model name.")
    parser.add_argument("--env-file", default=".env", help="Path to env file.")
    return parser


def run_interactive(client: MiniBotClient) -> None:
    print("MiniBot CLI. Type /help for commands, /exit to quit.")

    while True:
        try:
            content = input("{}you:{} ".format(BLUE, RESET)).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if not content:
            continue

        if content in ("/exit", "/quit"):
            return
        if content == "/help":
            print("/help                 show commands")
            print("/exit                 quit")
            print("/tools                list tools")
            print("/clear                clear current session memory")
            print("/session <id>         switch session")
            continue
        if content == "/tools":
            print(client.list_tools())
            continue
        if content == "/clear":
            client.clear_session()
            print("Session memory cleared.")
            continue
        if content.startswith("/session "):
            session_id = content[len("/session "):].strip()
            if session_id:
                client.set_session(session_id)
                print("Switched to session: {}".format(session_id))
            continue

        print()
        print("{}minibot:{} {}".format(YELLOW, RESET, client.ask(content)))
        print()


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    client = MiniBotClient(
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
        session_id=args.session,
        env_file=args.env_file,
    )

    if args.message:
        print("{}minibot:{} {}".format(YELLOW, RESET, client.ask(" ".join(args.message))))
        return

    run_interactive(client)


if __name__ == "__main__":
    main()
