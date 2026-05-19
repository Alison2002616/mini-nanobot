import json
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from minibot.memory import Message
from minibot.Providers.base import LLMProvider, LLMResponse, OnStream, ToolEvent
from minibot.session import Session, SessionManager, session_manager
from minibot.tool import ToolRegistry, tool_registry


MAX_REACT_ROUNDS = 10
TOOL_CALL_PATTERN = re.compile(r"^\s*TOOL_CALL:\s*([A-Za-z0-9_\-]+)\s+(\{.*\})\s*$", re.DOTALL)
MAX_TOOL_RESULT_DISPLAY = 16000


class Agent:
    def __init__(
        self,
        llm: LLMProvider,
        registry: ToolRegistry = tool_registry,
        sessions: SessionManager = session_manager,
        max_rounds: int = MAX_REACT_ROUNDS,
    ) -> None:
        if max_rounds <= 0:
            raise ValueError("max_rounds must be greater than 0.")

        self.llm = llm
        self.registry = registry
        self.sessions = sessions
        self.max_rounds = max_rounds
        self._tool_call_counter = 0

    def chat(
        self,
        content: str,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        on_stream: Optional[OnStream] = None,
        on_tool_event: Optional[Callable[[ToolEvent], Any]] = None,
    ) -> LLMResponse:
        session = self.sessions.get_or_create_session(session_id=session_id)
        metadata = metadata or {}
        session.add_message(role="user", content=content, metadata=metadata)

        wants_stream = bool(metadata.get("_wants_stream")) or on_stream is not None
        scratchpad = []  # type: List[Dict[str, Any]]
        tool_events = []  # type: List[ToolEvent]
        last_response = LLMResponse(provider=self.llm.name, model=self.llm.model)

        for _ in range(self.max_rounds):
            messages = self._build_messages(session=session, scratchpad=scratchpad)
            response = self._dispatch(messages, wants_stream=wants_stream)
            last_response = response

            tool_call = self._parse_tool_call(response.content)
            if tool_call is None:
                if wants_stream and on_stream:
                    on_stream(response.content)
                session.add_message(role="assistant", content=response.content)
                response.extend_tool_events(tool_events)
                return response

            tool_name, tool_args = tool_call
            tool_result = self._run_tool(
                tool_name=tool_name,
                tool_args=tool_args,
                tool_events=tool_events,
                on_tool_event=on_tool_event,
            )
            self._display_tool_result(tool_name, tool_result, on_stream)

            scratchpad.append({"role": "assistant", "content": response.content})
            scratchpad.append({
                "role": "user",
                "content": "TOOL_RESULT: {} {}".format(tool_name, tool_result),
            })

        final_response = LLMResponse(
            content="Reached max reasoning rounds. Last model output: {}".format(last_response.content),
            provider=self.llm.name,
            model=self.llm.model,
            tool_events=tool_events,
        )
        session.add_message(role="assistant", content=final_response.content)
        return final_response

    def _dispatch(
        self,
        messages: List[Dict[str, Any]],
        wants_stream: bool,
    ) -> LLMResponse:
        if wants_stream:
            return self.llm.chat_stream(messages, on_stream=None)
        return self.llm.chat(messages)

    def _build_messages(
        self,
        session: Session,
        scratchpad: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        messages = [{"role": "system", "content": self._build_system_prompt(), "metadata": {}}]

        for message in session.get_messages():
            messages.append(self._message_to_dict(message))

        messages.extend(scratchpad)
        return messages

    def _build_system_prompt(self) -> str:
        tools = self.registry.describe_tools()
        tool_text = json.dumps(tools, ensure_ascii=False)

        return (
            "You are a multi-turn agent.\n"
            "You may answer directly or call tools when needed.\n"
            "Available tools:\n"
            "{}\n\n"
            "Tool protocol:\n"
            "When a tool is needed, output exactly one line:\n"
            "TOOL_CALL: tool_name {{\"key\": \"value\"}}\n"
            "Do not include extra text around TOOL_CALL.\n"
            "Tool results will be returned as TOOL_RESULT.\n"
            "After receiving a tool result, produce the final user-facing answer."
        ).format(tool_text)

    def _message_to_dict(self, message: Message) -> Dict[str, Any]:
        return {
            "role": message.role,
            "content": message.content,
            "metadata": message.metadata,
        }

    def _parse_tool_call(self, reply: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        match = TOOL_CALL_PATTERN.match(reply)
        if not match:
            return None

        tool_name = match.group(1)
        raw_args = match.group(2)
        tool_args = json.loads(raw_args)

        if not isinstance(tool_args, dict):
            raise ValueError("tool arguments must be a JSON object.")

        return tool_name, tool_args

    def _run_tool(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        tool_events: List[ToolEvent],
        on_tool_event: Optional[Callable[[ToolEvent], Any]] = None,
    ) -> str:
        self._tool_call_counter += 1
        call_id = "tool-call-{}".format(self._tool_call_counter)

        start_event = ToolEvent(
            phase="start",
            call_id=call_id,
            tool_name=tool_name,
            arguments=tool_args,
        )
        self._record_tool_event(start_event, tool_events, on_tool_event)

        try:
            result = self.registry.run(tool_name, **tool_args)
            result_text = self._format_tool_result(result)
            end_event = ToolEvent(
                phase="end",
                call_id=call_id,
                tool_name=tool_name,
                arguments=tool_args,
                result=result,
            )
            self._record_tool_event(end_event, tool_events, on_tool_event)
            return result_text
        except Exception as exc:
            error_text = "{}: {}".format(exc.__class__.__name__, str(exc))
            error_event = ToolEvent(
                phase="error",
                call_id=call_id,
                tool_name=tool_name,
                arguments=tool_args,
                error=error_text,
            )
            self._record_tool_event(error_event, tool_events, on_tool_event)
            return json.dumps({"error": error_text}, ensure_ascii=False)

    def _record_tool_event(
        self,
        event: ToolEvent,
        tool_events: List[ToolEvent],
        on_tool_event: Optional[Callable[[ToolEvent], Any]] = None,
    ) -> None:
        tool_events.append(event)
        if on_tool_event:
            on_tool_event(event)

    def _display_tool_result(
        self,
        tool_name: str,
        tool_result: str,
        on_stream: Optional[OnStream],
    ) -> None:
        if not on_stream:
            return

        display_result = self._shorten_text(tool_result, MAX_TOOL_RESULT_DISPLAY)
        on_stream("\nminibot: calling tool {}...\n".format(tool_name))
        on_stream("minibot: tool result: {}\n".format(display_result))

    def _shorten_text(self, text: str, max_length: int) -> str:
        if len(text) <= max_length:
            return text
        return text[:max_length] + "...(truncated)"

    def _format_tool_result(self, result: Any) -> str:
        if isinstance(result, str):
            return result

        return json.dumps(result, ensure_ascii=False)
