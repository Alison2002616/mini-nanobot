# Providers 架构设计

`Providers` 是 MiniBot 的模型接入层。它的目标是让 Agent 可以接入不同模型厂商，同时不需要修改 Agent、Memory、Session、Tool 和 CLI 的核心逻辑。

当前目录只用于保存架构设计文档，暂时不编写具体 Provider 实现文件。

## 目标

- 支持 OpenAI-compatible API、DeepSeek、OpenAI、本地模型以及后续更多模型厂商。
- 让 `Agent` 只依赖一个稳定的 `chat` 接口。
- 将不同厂商的请求地址、请求参数、鉴权方式和响应解析隐藏在 Provider 内部。
- 支持从 CLI 参数、`.env` 文件或 Python 代码中选择 Provider。
- 第一版实现保持简单，方便用 Fake Provider 做离线测试。

## 非目标

- 当前阶段不实现具体 Provider 文件。
- 第一版不处理异步调用和流式输出。
- 不重构 Memory、Session 或 Tool Calling。
- 不让 Agent 感知任何厂商特定细节。

## 目录规划

后续可能的文件结构如下：

```text
Providers/
  README.md
  base.py
  registry.py
  openai_compatible.py
  deepseek.py
  fake.py
```

如果后续需要把 Provider 层作为 Python 包发布，可以将实现迁移到：

```text
src/minibot/providers/
```

当前 `Providers` 目录仅作为架构规划空间。

## 核心接口

所有 Provider 都应该暴露统一的 `chat` 方法：

```python
class BaseProvider:
    name = "base"

    def chat(self, messages, temperature=0.2):
        raise NotImplementedError
```

输入：

- `messages`: `List[Dict[str, str]]`
- 每条消息包含 `role` 和 `content`
- 角色保持 OpenAI Chat API 风格：
  - `system`
  - `user`
  - `assistant`

输出：

- 返回一个普通字符串，即模型生成的助手回复。
- 工具调用仍然使用文本协议，由 `Agent` 继续解析。

## Provider 负责什么

Provider 应该负责：

- 构造请求 URL
- 构造请求 payload
- 添加鉴权 headers
- 发送 HTTP 请求
- 解析厂商特定响应
- 将错误整理成清晰的 Python 异常
- 只把最终回复文本返回给 `Agent`

Provider 不应该负责：

- Session 记忆
- Tool 执行
- ReAct 循环
- CLI 输入输出
- 面向用户的显示格式

## OpenAI-Compatible Provider

大多数模型厂商可以先通过一个通用的 OpenAI-compatible Provider 接入。

需要的配置：

```text
api_key
base_url
model
timeout
```

请求结构：

```json
{
  "model": "model-name",
  "messages": [],
  "temperature": 0.2
}
```

响应解析路径：

```text
choices[0].message.content
```

DeepSeek 第一阶段可以直接复用这个 Provider，因为它的 Chat Completions API 与 OpenAI 风格兼容。

## Provider 注册中心

Provider 注册中心负责把 Provider 名称映射到 Provider 类或工厂函数。

示例行为：

```python
registry.register("deepseek", DeepSeekProvider)
registry.register("openai-compatible", OpenAICompatibleProvider)
provider = registry.create("deepseek", config)
```

注册中心需要支持：

- 按名称注册 Provider
- 按名称获取 Provider
- 根据配置创建 Provider 实例
- 列出当前可用 Provider
- 对未知 Provider 给出清晰错误

## 配置方案

Provider 配置建议按以下优先级解析：

1. Python 代码中显式传入的参数
2. CLI 命令行参数
3. `.env` 文件
4. 内置默认值

建议后续扩展 `.env.example`：

```text
provider="deepseek"
api_key="your-api-key"
base_url="https://api.deepseek.com"
model="deepseek-v4-flash"
timeout="60"
```

建议后续扩展 CLI 参数：

```text
--provider deepseek
--api-key ...
--base-url ...
--model ...
--timeout 60
```

## 与 Agent 的集成方式

`Agent` 应该继续只接收一个拥有以下方法的对象：

```python
chat(messages, temperature=0.2) -> str
```

这样现有的 `LLMClient` 后续可以平滑替换成 Provider 实例，而不需要修改 ReAct 循环。

当前方式：

```python
agent = Agent(llm=LLMClient(...))
```

未来方式：

```python
provider = provider_registry.create("deepseek", config)
agent = Agent(llm=provider)
```

## 错误处理

Provider 层应该定义清晰且统一的错误类型：

- `ProviderConfigError`：配置缺失或配置非法
- `ProviderRequestError`：网络请求或 HTTP 请求失败
- `ProviderResponseError`：响应结构不符合预期
- `ProviderAuthError`：鉴权失败

CLI 层可以捕获这些错误，并输出简洁、可理解的错误信息。

## 测试策略

第一阶段测试不应该依赖真实 API：

- `FakeProvider` 返回固定文本。
- `FakeProvider` 第一次返回 `TOOL_CALL`，第二次返回最终回答。
- 注册中心可以注册、创建 Provider，并能拒绝重复注册。
- OpenAI-compatible 响应解析可以处理正常和异常响应。

真实 API 测试应该作为可选测试，默认不运行。

## 迁移步骤

1. 保持当前 `LLMClient` 可用。
2. 添加 `BaseProvider` 和 Provider 注册中心。
3. 实现 `OpenAICompatibleProvider`。
4. 让 `DeepSeekProvider` 成为 OpenAI-compatible 的轻量预设。
5. 修改 `MiniBotClient`，让它可以根据配置创建 Provider。
6. 保持直接使用 `LLMClient` 的旧方式兼容。
7. 补充 Provider 的离线测试。

## 设计原则

Provider 层应该刻意保持简单：把所有模型厂商都归一成一个很小的 `chat(messages, temperature)` 接口。

这样 Agent 可以专注于推理循环、工具调用和多轮对话，而不用关心底层模型来自哪个厂商。
