import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from minibot.Providers.base import LLMProvider, LLMResponse, OnStream
from minibot.Providers.errors import (
    ProviderAuthError,
    ProviderConfigError,
    ProviderRequestError,
    ProviderResponseError,
    ProviderStreamError,
    ProviderTimeoutError,
)
from minibot.Providers.registry import provider_registry


class ClaudeProvider(LLMProvider):
    name = "claude"
    default_base_url = "https://api.anthropic.com"
    default_model = "claude-sonnet-4-5"

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
        super().__init__(
            api_key=api_key,
            base_url=base_url or self.default_base_url,
            model=model or self.default_model,
            http_timeout=http_timeout,
            stream_idle_timeout=stream_idle_timeout,
            total_timeout=total_timeout,
            chat_completions_timeout=chat_completions_timeout,
        )
        if not self.api_key:
            raise ProviderConfigError("Claude API key is required.")

    def chat(self, messages: List[Dict[str, Any]], **kwargs: Any) -> LLMResponse:
        payload = self._build_payload(messages, stream=False, **kwargs)
        data = self._post_json(payload, timeout=self.http_timeout)
        return self._response_from_json(data)

    def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        on_stream: Optional[OnStream] = None,
        **kwargs: Any
    ) -> LLMResponse:
        payload = self._build_payload(messages, stream=True, **kwargs)
        content_parts = []  # type: List[str]
        thinking_blocks = []  # type: List[Any]
        usage = {}  # type: Dict[str, Any]
        finish_reason = None
        raw_events = []  # type: List[Dict[str, Any]]
        current_event = None

        started_at = time.time()
        last_chunk_at = started_at

        request = self._request(payload)
        try:
            with urllib.request.urlopen(request, timeout=self.http_timeout) as response:
                for raw_line in response:
                    now = time.time()
                    if now - started_at > self.total_timeout:
                        raise ProviderTimeoutError("LLM call exceeded total timeout.")
                    if now - last_chunk_at > self.stream_idle_timeout:
                        raise ProviderTimeoutError("stream exceeded idle timeout.")

                    line = raw_line.decode("utf-8").strip()
                    if not line:
                        continue
                    if line.startswith("event:"):
                        current_event = line[len("event:"):].strip()
                        continue
                    if not line.startswith("data:"):
                        continue

                    event = json.loads(line[len("data:"):].strip())
                    event["_event"] = current_event
                    raw_events.append(event)
                    last_chunk_at = now

                    event_type = event.get("type") or current_event
                    if event_type == "content_block_delta":
                        delta = event.get("delta") or {}
                        if delta.get("type") == "text_delta":
                            text = delta.get("text") or ""
                            if text:
                                content_parts.append(text)
                                self._emit(on_stream, text)
                        elif delta.get("type") in ("thinking_delta", "signature_delta"):
                            thinking_blocks.append(delta)
                    elif event_type == "message_delta":
                        delta = event.get("delta") or {}
                        finish_reason = delta.get("stop_reason") or finish_reason
                        if event.get("usage"):
                            usage.update(event.get("usage") or {})
                    elif event_type == "message_stop":
                        break
        except urllib.error.HTTPError as exc:
            self._raise_http_error(exc)
        except urllib.error.URLError as exc:
            raise ProviderRequestError("Claude request failed: {}".format(exc)) from exc
        except ProviderTimeoutError:
            raise
        except KeyboardInterrupt:
            raise ProviderStreamError("stream was interrupted.")
        except Exception as exc:
            raise ProviderStreamError("stream failed: {}".format(exc)) from exc

        return LLMResponse(
            content="".join(content_parts),
            provider=self.name,
            model=self.model,
            finish_reason=finish_reason,
            usage=usage,
            thinking_blocks=thinking_blocks,
            metadata={"raw_events": raw_events},
        )

    def _build_payload(
        self,
        messages: List[Dict[str, Any]],
        stream: bool = False,
        **kwargs: Any
    ) -> Dict[str, Any]:
        system_parts = []
        claude_messages = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            if role == "system":
                system_parts.append(content)
            elif role == "assistant":
                claude_messages.append({"role": "assistant", "content": content})
            else:
                claude_messages.append({"role": "user", "content": content})

        payload = {
            "model": kwargs.get("model") or self.model,
            "messages": claude_messages,
            "max_tokens": kwargs.get("max_tokens", 1024),
            "temperature": kwargs.get("temperature", 0.2),
            "stream": stream,
        }
        if system_parts:
            payload["system"] = "\n".join(system_parts)
        return payload

    def _url(self) -> str:
        return "{}/v1/messages".format(self.base_url.rstrip("/"))

    def _request(self, payload: Dict[str, Any]) -> urllib.request.Request:
        return urllib.request.Request(
            url=self._url(),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key or "",
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )

    def _post_json(self, payload: Dict[str, Any], timeout: int) -> Dict[str, Any]:
        request = self._request(payload)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            self._raise_http_error(exc)
        except urllib.error.URLError as exc:
            raise ProviderRequestError("Claude request failed: {}".format(exc)) from exc
        raise ProviderResponseError("empty response.")

    def _response_from_json(self, data: Dict[str, Any]) -> LLMResponse:
        content_parts = []
        thinking_blocks = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                content_parts.append(block.get("text") or "")
            elif block.get("type") in ("thinking", "redacted_thinking"):
                thinking_blocks.append(block)

        return LLMResponse(
            content="".join(content_parts),
            provider=self.name,
            model=data.get("model") or self.model,
            finish_reason=data.get("stop_reason"),
            usage=data.get("usage") or {},
            thinking_blocks=thinking_blocks,
            metadata={"raw_response": data},
        )

    def _emit(self, on_stream: Optional[OnStream], text: str) -> None:
        if on_stream is None:
            return
        should_continue = on_stream(text)
        if should_continue is False:
            raise ProviderStreamError("stream was cancelled.")

    def _raise_http_error(self, exc: urllib.error.HTTPError) -> None:
        body = exc.read().decode("utf-8")
        if exc.code in (401, 403):
            raise ProviderAuthError("Claude auth failed: {}".format(body)) from exc
        raise ProviderRequestError("Claude HTTP error: {}, {}".format(exc.code, body)) from exc


provider_registry.register("claude", ClaudeProvider)

