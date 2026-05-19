# mini-nanobot

一个用于学习 Agent 基础机制的轻量级 Python 项目，实现了模型调用、多轮记忆、会话隔离、工具注册与 ReAct 风格工具调用。

## Features

- OpenAI-compatible LLM client
- Multi-turn chat memory
- Session isolation
- Tool registry
- Simple ReAct loop
- Command line interface

## Usage

```bash
cp .env.example .env
uv sync
uv run minibot