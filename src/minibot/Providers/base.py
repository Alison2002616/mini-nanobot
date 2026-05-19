from abc import ABCMeta, abstractmethod
from typing import Any, Callable, Dict, List, Optional


OnStream = Callable[[str], Any]


class ToolEvent:
    def __init__(
        self,
        phase: str,
        call_id: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        result: Any = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.phase = phase
        self.call_id = call_id
        self.tool_name = tool_name
        self.arguments = arguments or {}
        self.result = result
        self.error = error
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
        }


class LLMResponse:
    def __init__(
        self,
        content: str = "",
        provider: str = "",
        model: str = "",
        tool_events: Optional[List[ToolEvent]] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        finish_reason: Optional[str] = None,
        usage: Optional[Dict[str, Any]] = None,
        thinking_blocks: Optional[List[Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.content = content
        self.provider = provider
        self.model = model
        self.tool_events = tool_events or []
        self.tool_calls = tool_calls or []
        self.finish_reason = finish_reason
        self.usage = usage or {}
        self.thinking_blocks = thinking_blocks or []
        self.metadata = metadata or {}

    def extend_tool_events(self, events: List[ToolEvent]) -> None:
        self.tool_events.extend(events)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "provider": self.provider,
            "model": self.model,
            "tool_events": [
                event.to_dict() if hasattr(event, "to_dict") else event
                for event in self.tool_events
            ],
            "tool_calls": self.tool_calls,
            "finish_reason": self.finish_reason,
            "usage": self.usage,
            "thinking_blocks": self.thinking_blocks,
            "metadata": self.metadata,
        }


class LLMProvider(metaclass=ABCMeta):
    name = "base"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        http_timeout: int = 120,
        stream_idle_timeout: int = 90,
        total_timeout: int = 300,
        chat_completions_timeout: int = 120,
    ) -> None:
        self.api_key = api_key
        self.base_url = (base_url or "").rstrip("/")
        self.model = model or ""
        self.http_timeout = http_timeout
        self.stream_idle_timeout = stream_idle_timeout
        self.total_timeout = total_timeout
        self.chat_completions_timeout = chat_completions_timeout

    @abstractmethod
    def chat(self, messages: List[Dict[str, Any]], **kwargs: Any) -> LLMResponse:
        raise NotImplementedError

    @abstractmethod
    def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        on_stream: Optional[OnStream] = None,
        **kwargs: Any
    ) -> LLMResponse:
        raise NotImplementedError

