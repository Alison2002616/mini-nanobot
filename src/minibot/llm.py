import json
import os
import urllib.error
import urllib.request
from typing import Dict, List, Optional


class LLMClient:
    """
    最小版 LLM 客户端。
    直接调用 OpenAI-compatible Chat Completions API。
    兼容：
    - OpenAI
    - DeepSeek
    - 其他兼容 OpenAI 接口的模型服务
    """

    def __init__(self,
                api_key: Optional[str] = None,
                base_url: Optional[str] = None,
                model: Optional[str] = None,
                timeout: int = 60,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL") 
        self.model = model or os.getenv("OPENAI_MODEL")
        self.timeout = timeout

        if not self.api_key:
            raise ValueError("Missing OPENAI_API_KEY.")

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.2) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }

        request = urllib.request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8")
            raise RuntimeError(f"LLM HTTP error: {exc.code}, {error_body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"LLM request failed: {exc}") from exc
        return data["choices"][0]["message"]["content"]
    
