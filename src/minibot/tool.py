from typing import Any, Callable, Dict, List, Optional


class Tool:
    def __init__(
        self,
        name: str,
        description: str,
        call_method: Callable[..., Any],
    ) -> None:
        if not name:
            raise ValueError("tool name cannot be empty.")
        if not callable(call_method):
            raise ValueError("call_method must be callable.")

        self.name = name
        self.description = description
        self.call_method = call_method

    def run(self, *args: Any, **kwargs: Any) -> Any:
        return self.call_method(*args, **kwargs)

    def to_dict(self) -> Dict[str, str]:
        return {
            "name": self.name,
            "description": self.description,
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools = {}  # type: Dict[str, Tool]

    def register(self, tool: Tool) -> Tool:
        if tool.name in self._tools:
            raise ValueError("tool already registered: {}".format(tool.name))

        self._tools[tool.name] = tool
        return tool

    def unregister(self, name: str) -> Optional[Tool]:
        return self._tools.pop(name, None)

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError("tool not found: {}".format(name))

        return self._tools[name]

    def list_tools(self) -> List[Tool]:
        return list(self._tools.values())

    def describe_tools(self) -> List[Dict[str, str]]:
        return [tool.to_dict() for tool in self.list_tools()]

    def run(self, name: str, *args: Any, **kwargs: Any) -> Any:
        return self.get(name).run(*args, **kwargs)


tool_registry = ToolRegistry()
