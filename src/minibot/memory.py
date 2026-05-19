from typing import List


MAX_MESSAGES = 20


class Message:
    def __init__(self, role: str, content: str) -> None:
        self.role = role
        self.content = content


class Memory:
    def __init__(self, max_messages: int = MAX_MESSAGES) -> None:
        if max_messages <= 0:
            raise ValueError("max_messages must be greater than 0.")

        self.max_messages = max_messages
        self.messages = []  # list[Message]
        self._next_index = 0

    def add_message(self, role: str, content: str) -> Message:
        message = Message(role=role, content=content)

        if len(self.messages) < self.max_messages:
            self.messages.append(message)
        else:
            self.messages[self._next_index] = message

        self._next_index = (self._next_index + 1) % self.max_messages
        return message

    def get_messages(self) -> List[Message]:
        if len(self.messages) < self.max_messages:
            return list(self.messages)

        return self.messages[self._next_index:] + self.messages[:self._next_index]

    def clear(self) -> None:
        self.messages.clear()
        self._next_index = 0
