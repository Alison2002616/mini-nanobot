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


class OpenAICompatibleProvider(LLMProvider):
    name = "openai_compatible"
    default_base_url = ""
    default_model = ""

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
            raise ProviderConfigError("{} API key is required.".format(self.name))
        if not self.base_url:
            raise ProviderConfigError("{} base URL is required.".format(self.name))
        if not self.model:
            raise ProviderConfigError("{} model is required.".format(self.name))

    def chat(self, messages: List[Dict[str, Any]], **kwargs: Any) -> LLMResponse:
        payload = self._build_payload(messages, stream=False, **kwargs)
        data = self._post_json(payload, timeout=self.chat_completions_timeout)
        return self._response_from_json(data)

    def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        on_stream: Optional[OnStream] = None,
        **kwargs: Any
    ) -> LLMResponse:
        payload = self._build_payload(messages, stream=True, **kwargs)
        content_parts = []  # type: List[str]
        tool_calls = []  # type: List[Dict[str, Any]]
        usage = {}  # type: Dict[str, Any]
        finish_reason = None
        raw_events = []  # type: List[Dict[str, Any]]

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
                    if not line.startswith("data:"):
                        continue

                    data_text = line[len("data:"):].strip()
                    if data_text == "[DONE]":
                        break

                    event = json.loads(data_text)
                    raw_events.append(event)
                    last_chunk_at = now

                    if event.get("usage"):
                        usage = event.get("usage") or {}

                    for choice in event.get("choices", []):
                        if choice.get("finish_reason"):
                            finish_reason = choice.get("finish_reason")
                        delta = choice.get("delta") or {}
                        text = delta.get("content")
                        if text:
                            content_parts.append(text)
                            self._emit(on_stream, text)
                        if delta.get("tool_calls"):
                            tool_calls.extend(delta.get("tool_calls") or [])
        except urllib.error.HTTPError as exc:
            self._raise_http_error(exc)
        except urllib.error.URLError as exc:
            raise ProviderRequestError("LLM request failed: {}".format(exc)) from exc
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
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
            metadata={"raw_events": raw_events},
        )

    def _build_payload(
        self,
        messages: List[Dict[str, Any]],
        stream: bool = False,
        **kwargs: Any
    ) -> Dict[str, Any]:
        payload = {
            "model": kwargs.get("model") or self.model,
            "messages": self._normalize_messages(messages),
            "temperature": kwargs.get("temperature", 0.2),
            "stream": stream,
        }
        if stream:
            payload["stream_options"] = {"include_usage": True}
        return payload

    def _normalize_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        normalized = []
        for message in messages:
            normalized.append({
                "role": message.get("role", "user"),
                "content": message.get("content", ""),
            })
        return normalized

    def _url(self) -> str:
        return "{}/chat/completions".format(self.base_url.rstrip("/"))

    def _request(self, payload: Dict[str, Any]) -> urllib.request.Request:
        return urllib.request.Request(
            url=self._url(),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.api_key),
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
            raise ProviderRequestError("LLM request failed: {}".format(exc)) from exc
        raise ProviderResponseError("empty response.")

    def _response_from_json(self, data: Dict[str, Any]) -> LLMResponse:
        try:
            choice = data["choices"][0]
            message = choice.get("message") or {}
            content = message.get("content") or ""
            tool_calls = message.get("tool_calls") or []
            finish_reason = choice.get("finish_reason")
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderResponseError("unexpected response shape.") from exc

        return LLMResponse(
            content=content,
            provider=self.name,
            model=data.get("model") or self.model,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=data.get("usage") or {},
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
            raise ProviderAuthError("LLM auth failed: {}".format(body)) from exc
        raise ProviderRequestError("LLM HTTP error: {}, {}".format(exc.code, body)) from exc

