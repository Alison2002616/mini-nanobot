# Providers 需求文档

本文档描述 MiniBot 的模型接入层 Provider 需求。当前阶段以实现规格为主，删除历史讨论和非必要说明。

## 1. 目标

Provider 层负责统一接入不同 LLM 服务，让 Agent、Memory、Session、Tool 和 CLI 不直接依赖具体模型厂商。

第一阶段真实接入：

- DeepSeek
- OpenAI
- Claude

后续预留扩展：

- GLM
- Qwen
- 其他模型服务

默认 Provider 为：

```text
deepseek
```

## 2. 目录

Provider 代码放在：

```text
src/minibot/providers/
```

推荐结构：

```text
src/minibot/providers/
  __init__.py
  base.py
  errors.py
  registry.py
  openai_compatible.py
  deepseek.py
  openai.py
  claude.py
```

第一阶段不创建 `glm.py` 和 `qwen.py`。

当前文档目录保留为：

```text
src/minibot/Providers/
```

## 3. 核心类型

`base.py` 定义：

- `LLMProvider`
- `LLMResponse`
- `ToolEvent`

`LLMResponse` 至少包含：

```python
class LLMResponse:
    content: str
    provider: str
    model: str
    tool_events: list
    tool_calls: list
    finish_reason: str
    usage: dict
    thinking_blocks: list
    metadata: dict
```

`thinking_blocks` 不展示给 CLI 用户，只保存在 `LLMResponse` 中。

`ToolEvent` 至少包含：

```python
class ToolEvent:
    phase: str  # start / end / error
    call_id: str
    tool_name: str
    arguments: dict
    result: object
    error: str
    metadata: dict
```

## 4. Provider 接口

所有 Provider 继承或遵守 `LLMProvider`。

Provider 必须提供两个独立方法：

```python
chat(messages, **kwargs) -> LLMResponse
chat_stream(messages, on_stream, **kwargs) -> LLMResponse
```

要求：

- `chat()` 调用底层 SDK 或 HTTP API 的非流式端点。
- `chat_stream()` 调用底层 SDK 或 HTTP API 的真实流式端点。
- `chat_stream()` 每收到文本片段，通过 `on_stream(chunk: str)` 推出。
- `on_stream` 只接收文本片段，不接收结构化事件。
- `tool_calls`、`finish_reason`、`usage`、`thinking_blocks` 等结构化信息在流结束后解析，写入最终返回的 `LLMResponse`。
- `chat_stream()` 需要支持取消或中断。

## 5. 配置

不保留旧配置名：

```text
api_key
base_url
model
```

不使用 `MINIBOT_` 前缀。

使用厂商前缀区分配置：

```text
DEFAULT_PROVIDER="deepseek"

DEEPSEEK_API_KEY="..."
DEEPSEEK_BASE_URL="..."
DEEPSEEK_MODEL="..."

OPENAI_API_KEY="..."
OPENAI_BASE_URL="..."
OPENAI_MODEL="..."

CLAUDE_API_KEY="..."
CLAUDE_BASE_URL="..."
CLAUDE_MODEL="..."
```

如果没有配置 `DEFAULT_PROVIDER`，默认使用 `deepseek`。

## 6. 超时

所有超时配置都有默认值，单位为秒。

| 配置项 | 含义 | 默认值 |
| --- | --- | --- |
| HTTP request timeout | HTTP 请求超时 | 120 |
| stream idle timeout | 流式传输中两次 chunk 之间的最大空闲时间 | 90 |
| total LLM call timeout | 单次 LLM 调用总超时 | 300 |
| chat completions request timeout | `/v1/chat/completions` 请求级超时 | 120 |

建议配置名：

```text
DEEPSEEK_HTTP_TIMEOUT="120"
DEEPSEEK_STREAM_IDLE_TIMEOUT="90"
DEEPSEEK_TOTAL_TIMEOUT="300"
DEEPSEEK_CHAT_COMPLETIONS_TIMEOUT="120"

OPENAI_HTTP_TIMEOUT="120"
OPENAI_STREAM_IDLE_TIMEOUT="90"
OPENAI_TOTAL_TIMEOUT="300"
OPENAI_CHAT_COMPLETIONS_TIMEOUT="120"

CLAUDE_HTTP_TIMEOUT="120"
CLAUDE_STREAM_IDLE_TIMEOUT="90"
CLAUDE_TOTAL_TIMEOUT="300"
```

## 7. Streaming 触发

Streaming 不是全局强制，采用“谁调用谁决定”的模式。

- CLI 交互模式 `minibot`：每条消息的 `metadata` 中带 `_wants_stream: True`，由 `_dispatch()` 按消息读取。
- CLI 单次模式 `minibot -m "xxx"`：传入 `on_stream` 回调时使用流式。
- Gateway / API Server / Cron：当前不支持配置 streaming；不传 `on_stream` 时使用非流式。

CLI 暂时不需要 `--provider` 参数。

## 8. OpenAI-Compatible 复用

尽量复用 OpenAI-compatible Provider。

- DeepSeek 优先复用 OpenAI-compatible 实现。
- OpenAI 优先复用 OpenAI-compatible 实现。
- Claude 如接口不同，使用单独实现。
- 后续 Qwen、GLM 如果兼容 OpenAI 风格，也可复用 OpenAI-compatible 实现。

## 9. 工具调用

工具调用协议保持：

```text
TOOL_CALL: tool_name {"key": "value"}
```

ReAct 最大轮数继续使用 10。

工具调用判断阶段不允许使用非流式替代流式。需要基于真实 streaming 结果处理，但允许先缓冲完整 streaming 内容，再决定是否展示。

如果模型输出 `TOOL_CALL` 前后混入其他文字，不视为错误：

- 混入的普通文本需要保留。
- 处理方式因 Provider 或 Agent 流程而异。

工具执行失败后，错误作为 `TOOL_RESULT` 发回模型。

## 10. 工具显示与事件

工具调用过程和工具结果需要展示给用户。

显示规则：

- 路径自动压缩为简写形式，例如 `.../very/long/path.py`。
- 相同工具调用合并显示为 `工具名 × N`。
- 工具结果展示最大长度暂定为 16,000 字符。
- 普通 CLI 使用 `minibot:` 前缀展示工具过程。
- 工具失败时展示简短错误。

结构化 channel 通过 `tool_events` 接收详细事件：

- `phase`: `start` / `end` / `error`
- `call_id`
- `tool_name`
- `arguments`
- `result`
- `error`
- `metadata`

`call_id` 由 Agent 生成。

## 11. 错误处理

Provider 层定义统一异常：

- `ProviderConfigError`
- `ProviderAuthError`
- `ProviderRequestError`
- `ProviderResponseError`
- `ProviderStreamError`
- `ProviderTimeoutError`

API Key 必须脱敏，不打印完整密钥。

CLI 默认显示简洁错误。debug 模式可显示完整异常。

## 12. 测试

第一阶段不需要 `fake.py` Provider。

测试要求：

- 使用轻量 mock 和真实数据结构。
- 零真实 API 调用。
- mock 数据不需要分别覆盖 DeepSeek、OpenAI、Claude 三种格式。
- 不需要单独编写 mock 数据文档。

建议覆盖：

- Provider 注册中心。
- `LLMResponse` 和 `ToolEvent` 数据结构。
- OpenAI-compatible streaming 解析。
- Claude streaming 解析。
- Agent 基于 streaming 的 ReAct 循环。
- 工具调用显示与合并。
- CLI 流式输出格式。

## 13. 兼容性

不需要保留 `LLMClient` 作为兼容旧代码的入口。

Provider 层后续可以替代当前 `LLMClient`。
