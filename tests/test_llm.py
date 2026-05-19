import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from minibot.llm import LLMClient

client = LLMClient(
    api_key="sk-",
    base_url="https://api.deepseek.com",
    model="deepseek-v4-flash",
)

reply = client.chat([{"role": "user", "content": "今天南京天气怎么样"}])
print(f"Response: {reply}")
