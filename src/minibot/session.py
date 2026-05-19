import uuid
from typing import Dict, List, Optional

from minibot.memory import MAX_MESSAGES, Memory, Message


class Session:
    def __init__(
        self,
        session_id: Optional[str] = None,
        memory: Optional[Memory] = None,
        max_messages: int = MAX_MESSAGES,
    ) -> None:
        self.session_id = session_id or str(uuid.uuid4())
        self.memory = memory or Memory(max_messages=max_messages)

    def add_message(self, role: str, content: str) -> Message:
        return self.memory.add_message(role=role, content=content)

    def get_messages(self) -> List[Message]:
        return self.memory.get_messages()

    def clear(self) -> None:
        self.memory.clear()


class SessionManager:
    def __init__(self) -> None:
        self._sessions = {}  # type: Dict[str, Session]

    def create_session(
        self,
        session_id: Optional[str] = None,
        max_messages: int = MAX_MESSAGES,
    ) -> Session:
        session = Session(session_id=session_id, max_messages=max_messages)

        if session.session_id in self._sessions:
            raise ValueError("session already exists: {}".format(session.session_id))

        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> Session:
        if session_id not in self._sessions:
            raise KeyError("session not found: {}".format(session_id))

        return self._sessions[session_id]

    def get_or_create_session(
        self,
        session_id: Optional[str] = None,
        max_messages: int = MAX_MESSAGES,
    ) -> Session:
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]

        return self.create_session(session_id=session_id, max_messages=max_messages)

    def delete_session(self, session_id: str) -> Optional[Session]:
        return self._sessions.pop(session_id, None)

    def list_sessions(self) -> List[str]:
        return list(self._sessions.keys())

    def clear(self) -> None:
        self._sessions.clear()


session_manager = SessionManager()
