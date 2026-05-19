import json
import re
from typing import Any, Dict, List, Optional, Tuple

from minibot.llm import LLMClient
from minibot.memory import Message
from minibot.session import Session, SessionManager, session_manager
from minibot.tool import ToolRegistry, tool_registry


MAX_REACT_ROUNDS = 10
TOOL_CALL_PATTERN = re.compile(r"^\s*TOOL_CALL:\s*([A-Za-z0-9_\-]+)\s+(\{.*\})\s*$", re.DOTALL)


class Agent:
    def __init__(
        self,
        llm: LLMClient,
        registry: ToolRegistry = tool_registry,
        sessions: SessionManager = session_manager,
        max_rounds: int = MAX_REACT_ROUNDS,
    ) -> None:
        if max_rounds <= 0:
            raise ValueError("max_rounds must be greater than 0.")

        self.llm = llm
        self.registry = registry
        self.sessions = sessions
        self.max_rounds = max_rounds

    def chat(self, content: str, session_id: Optional[str] = None) -> str:
        session = self.sessions.get_or_create_session(session_id=session_id)
        session.add_message(role="user", content=content)

        scratchpad = []  # type: List[Dict[str, str]]
        last_reply = ""

        for _ in range(self.max_rounds):
            messages = self._build_messages(session=session, scratchpad=scratchpad)
            reply = self.llm.chat(messages)
            last_reply = reply

            tool_call = self._parse_tool_call(reply)
            if tool_call is None:
                session.add_message(role="assistant", content=reply)
                return reply

            tool_name, tool_args = tool_call
            tool_result = self._run_tool(tool_name=tool_name, tool_args=tool_args)
            scratchpad.append({"role": "assistant", "content": reply})
            scratchpad.append({
                "role": "user",
                "content": "TOOL_RESULT: {} {}".format(tool_name, tool_result),
            })

        final_reply = "达到最大推理轮数，最后一次模型输出：{}".format(last_reply)
        session.add_message(role="assistant", content=final_reply)
        return final_reply

    def _build_messages(
        self,
        session: Session,
        scratchpad: List[Dict[str, str]],
    ) -> List[Dict[str, str]]:
        messages = [{"role": "system", "content": self._build_system_prompt()}]

        for message in session.get_messages():
            messages.append(self._message_to_dict(message))

        messages.extend(scratchpad)
        return messages

    def _build_system_prompt(self) -> str:
        tools = self.registry.describe_tools()
        tool_text = json.dumps(tools, ensure_ascii=False)

        return (
            "你是一个可以多轮对话的智能 Agent。\n"
            "你可以直接回答用户，也可以在需要时调用工具。\n"
            "当前可用工具如下：\n"
            "{}\n\n"
            "工具调用协议：\n"
            "如果需要调用工具，只能输出一行：TOOL_CALL: tool_name {{\"key\": \"value\"}}\n"
            "不要在 TOOL_CALL 前后输出解释文字。\n"
            "工具执行结果会以 TOOL_RESULT 形式返回给你。\n"
            "拿到工具结果后，请生成给用户看的最终回答，不要再复述协议。"
        ).format(tool_text)

    def _message_to_dict(self, message: Message) -> Dict[str, str]:
        return {
            "role": message.role,
            "content": message.content,
        }

    def _parse_tool_call(self, reply: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        match = TOOL_CALL_PATTERN.match(reply)
        if not match:
            return None

        tool_name = match.group(1)
        raw_args = match.group(2)
        tool_args = json.loads(raw_args)

        if not isinstance(tool_args, dict):
            raise ValueError("tool arguments must be a JSON object.")

        return tool_name, tool_args

    def _run_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> str:
        try:
            result = self.registry.run(tool_name, **tool_args)
        except Exception as exc:
            result = {
                "error": "{}: {}".format(exc.__class__.__name__, str(exc)),
            }

        return self._format_tool_result(result)

    def _format_tool_result(self, result: Any) -> str:
        if isinstance(result, str):
            return result

        return json.dumps(result, ensure_ascii=False)
