import os
import sys

import pytest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from minibot.memory import Memory, Message
from minibot.session import Session, SessionManager
from minibot.tool import Tool, ToolRegistry


def test_message_stores_role_content_and_metadata():
    message = Message("user", "hello", metadata={"_wants_stream": True})

    assert message.role == "user"
    assert message.content == "hello"
    assert message.metadata["_wants_stream"] is True


def test_memory_keeps_latest_messages_in_order():
    memory = Memory(max_messages=3)

    for index in range(5):
        memory.add_message("user", str(index))

    assert [message.content for message in memory.get_messages()] == ["2", "3", "4"]


def test_memory_rejects_invalid_max_messages():
    with pytest.raises(ValueError):
        Memory(max_messages=0)


def test_session_wraps_memory_and_preserves_metadata():
    session = Session(session_id="s1", max_messages=2)

    session.add_message("user", "hello", metadata={"source": "test"})

    assert session.session_id == "s1"
    assert session.get_messages()[0].metadata["source"] == "test"


def test_session_manager_creates_gets_and_deletes_sessions():
    manager = SessionManager()

    session = manager.create_session("s1")

    assert manager.get_session("s1") is session
    assert manager.get_or_create_session("s1") is session
    assert manager.list_sessions() == ["s1"]
    assert manager.delete_session("s1") is session
    assert manager.list_sessions() == []


def test_session_manager_rejects_duplicate_session():
    manager = SessionManager()
    manager.create_session("s1")

    with pytest.raises(ValueError):
        manager.create_session("s1")


def test_tool_registry_registers_and_runs_tools():
    registry = ToolRegistry()
    registry.register(Tool("add", "Add", lambda a, b: a + b))

    assert registry.run("add", 2, 3) == 5
    assert registry.describe_tools() == [{"name": "add", "description": "Add"}]


def test_tool_registry_handles_duplicates_and_missing_tools():
    registry = ToolRegistry()
    registry.register(Tool("echo", "Echo", lambda text: text))

    with pytest.raises(ValueError):
        registry.register(Tool("echo", "Echo", lambda text: text))

    with pytest.raises(KeyError):
        registry.get("missing")
