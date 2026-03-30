import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Iterable, List


class ToolCallsStopIteration(Exception):
    """结束工具调用异常"""
    def __init__(self, message: str = ""):
        if message:
            super().__init__(f"'tool_calls_end': {message}")
        else:
            super().__init__("end tool call")


class MessageBuilder:
    """链式消息构建器，支持多模态内容自动合并相邻文本块"""
    __slots__ = ['_role', '_parts']

    def __init__(self, role: str = "user"):
        self._role = role
        self._parts: list = []

    def _last_is_text(self) -> bool:
        return bool(self._parts) and self._parts[-1]["type"] == "text"

    def add_text(self, text: str) -> "MessageBuilder":
        """添加文本，与前一个文本块自动合并"""
        if self._last_is_text():
            self._parts[-1]["text"] += text
        else:
            self._parts.append({"type": "text", "text": text})
        return self

    def add_image(self, url: str, detail: str = "auto") -> "MessageBuilder":
        """添加图片 URL"""
        self._parts.append({
            "type": "image_url",
            "image_url": {"url": url, "detail": detail}
        })
        return self

    def add_image_base64(self, data: str, mime: str = "image/png") -> "MessageBuilder":
        """添加 base64 图片"""
        self._parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{data}"}
        })
        return self

    def add_audio(self, data: str, fmt: str = "wav") -> "MessageBuilder":
        """添加 base64 音频"""
        self._parts.append({
            "type": "input_audio",
            "input_audio": {"data": data, "format": fmt}
        })
        return self

    def add_video(self, url: str) -> "MessageBuilder":
        """添加视频 URL"""
        self._parts.append({
            "type": "video_url",
            "video_url": {"url": url}
        })
        return self

    def add_video_base64(self, data: str, mime: str = "video/mp4") -> "MessageBuilder":
        """添加 base64 视频"""
        self._parts.append({
            "type": "video_url",
            "video_url": {"url": f"data:{mime};base64,{data}"}
        })
        return self

    def add_file(self, url: str, mime: str = "") -> "MessageBuilder":
        """添加文件"""
        self._parts.append({
            "type": "file",
            "file": {"url": url, **({"mime_type": mime} if mime else {})}
        })
        return self

    def merge(self, other: "MessageBuilder") -> "MessageBuilder":
        """和另一个构建合并"""
        if not other._parts:
            return self

        first = other._parts[0]

        start = 0
        if first["type"] == "text":
            self.add_text(first["text"])
            start = 1

        self._parts.extend(other._parts[start:])
        return self

    def build_content(self) -> str | list:
        """仅返回 content,纯文本时为 str,多模态时为 list"""
        if len(self._parts) == 1 and self._parts[0]["type"] == "text":
            return self._parts[0]["text"]
        return list(self._parts)

    def build(self) -> Dict[str, Any]:
        """构建消息 dict"""
        if len(self._parts) == 1 and self._parts[0]["type"] == "text":
            return {"role": self._role, "content": self._parts[0]["text"]}
        return {"role": self._role, "content": list(self._parts)}

    def build_and_add(self, ctx: "Context") -> None:
        """构建并直接追加到 Context"""
        ctx.append(self.build())

    @classmethod
    def user(cls) -> "MessageBuilder":
        return cls("user")

    @classmethod
    def assistant(cls) -> "MessageBuilder":
        return cls("assistant")

    @classmethod
    def system(cls) -> "MessageBuilder":
        return cls("system")


@dataclass(slots=True)
class Context():
    """对话上下文"""
    messages: List[Dict[str, Any]] = None
    """原始的上下文"""
    user_max_record: int = 20
    """user最多消息条数限制"""
    user_max_token: int = 40000 #一般模型的上下文是128K的token
    """user消息token限制"""
    play_role:str = ""
    """模型人物提示词"""
    total_tokens:int = 0
    """上一轮api响应中给出的上下文token"""
    async_lock:asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    """异步锁"""

    def __post_init__(self):
        if self.messages is None:
            self.messages = []

    def __getitem__(self, index):
        return self.get_messages()[index]

    def __len__(self):
        return len(self.get_messages())

    def __iter__(self):
        return iter(self.get_messages())

    def __contains__(self, item):
        return item in self.get_messages()

    def __reversed__(self):
        return reversed(self.get_messages())

    def __str__(self):
        return str(self.get_messages())

    def __repr__(self):
        return repr(self.get_messages())

    def append(self, dict: Dict[str, Any]) -> None:
        """添加内容"""
        self.messages.append(dict)

    def extend(self, Iterable: List) -> None:
        """用可迭代对象来扩展列表"""
        self.messages.extend(Iterable)

    def get_messages(self, inject_text: str = "") -> List[Dict[str, str]]:
        """获取当前的上下文List

        Args:
            inject_text (str): 要注入到人设后面的提示词.如果没有Play_role会在开头新建一个system

        Returns:
            List[Dict[str, Any]]: 上下文list
        """
        if parts := [p for p in (self.play_role, inject_text) if p]:
            return [{"role": "system", "content": "\n\n".join(parts)}, *self.messages]

        return self.messages

    def add_message(self, role: str, content: str | list, tool_call_id: int = None) -> None:
        """添加消息

        Args:
            role (str): 消息枚举值"user", "assistant", "system", "tool"
            content (str): 内容
            tool_call_id (int): 工具id,当类型为tool时可能需要
        """
        if tool_call_id:
            self.messages.append({
                "role": role,
                "content": content,
                "tool_call_id": tool_call_id
            })
            return

        self.messages.append({"role": role, "content": content})

    def add_img_message(self, role: str, text: str, image_urls: list) -> None:
        """添加带图片消息

        Args:
            role (str): 消息枚举值"user", "assistant", "system", "tool"
            text (str): 文本内容
            image_urls (list): 图片的 URL 列表，每个 URL 都会被作为独立的图片项添加到 content
        """
        self.messages.append({
            "role": role,
            "content": [{"type": "image_url", "image_url": {"url": url}} for url in image_urls] + [{"type": "text", "text": text}]
        })

    def add_user_message(self, content: str) -> None:
        """添加用户消息"""
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str | None, reasoning_content: str | None = None) -> None:
        """添加助手消息"""
        assistant_message = {
            "role": "assistant",
            "content": content
        }

        if reasoning_content:
            assistant_message["reasoning_content"] = reasoning_content

        self.messages.append(assistant_message)

    def add_assistant_message_flexible(self, assistant_message: Dict) -> None:
        """灵活的添加user消息

        Args:
            assistant_message (Dict): 模型返回原始消息字段
        """
        self.messages.append(assistant_message)

    def add_assistant_tool_message(self, content: str | None, tool_calls: List[Dict], reasoning_content: str | None = None) -> None:
        """添加助手调用工具消息"""
        tool_message = {
            "role": "assistant",
            "tool_calls": tool_calls
        }

        if content:
            tool_message["content"] = content
        if reasoning_content:
            tool_message["reasoning_content"] = reasoning_content

        self.messages.append(tool_message)

    def add_system_message(self, content: str) -> None:
        """添加系统消息"""
        self.messages.append({"role": "system", "content": content})

    def add_tool_message(self, naem: str, tool_call_id: str, content: str | list) -> None:
        """添加工具消息"""
        self.messages.append({
            "role": "tool",
            "name": naem,
            "tool_call_id": tool_call_id,
            "content": content#纯文本(str)或多模态内容列表(list)
        })

    def clear(self) -> None:
        """清除上下文"""
        self.messages.clear()

    def record_validity_check(self) -> list:
        """
        针对消息条数的验证，需要显式调用
        如果 user 消息数超过限制，会截取到总长度为 user_max_record
        并确保最后一条消息是 user 消息（向下取整）
        如果token到达一定值也会触发

        Returns:
            list: 被截取掉的消息列表,如果有的话
        """

        if sum(1 for msg in self.messages if msg["role"] == "user") > self.user_max_record or self.total_tokens > self.user_max_token:
            # 先截取到总长度为 user_max_record
            kept_messages = self.messages[-self.user_max_record:]

            # 从后往前找到最后一个 user 消息的位置
            last_user_index = -1
            for i in range(0, len(kept_messages)):
                if kept_messages[i]["role"] == "user":
                    last_user_index = i
                    break

            # 截取到最近条 user 消息
            if last_user_index != -1:
                kept_messages = kept_messages[last_user_index:]
            else:
                import copy
                removed_messages = copy.copy(self.messages)
                self.messages.clear()
                return removed_messages

            # 计算被删除的消息
            removed_messages = self.messages[:len(self.messages) - len(kept_messages)]
            self.messages = kept_messages
            return removed_messages

        return None

    def _estimate_string_tokens(self, text: str) -> float:
        """
        辅助方法：估算纯文本的 Token 数
        利用 UTF-8 字节长度快速区分 ASCII (英文/数字) 和 非ASCII (中文)
        """
        if not text:
            return 0

        length = len(text)
        # ASCII占1byte，常用汉字占3bytes
        # 通过字节差值估算非ASCII字符数量

        non_ascii_count = (len(text.encode('utf-8')) - length) // 2
        ascii_count = length - non_ascii_count

        return (ascii_count * 0.25) + (non_ascii_count * 0.7)

    def get_context_forecast_token(self) -> int:
        """
        获取上下文 Token 估算值 (保守估计，区分中英文)
        """
        total_tokens = 0
        messages = self.get_messages()

        for msg in messages:
            total_tokens += 5

            content = msg.get("content")
            if content:
                if isinstance(content, str):
                    total_tokens += self._estimate_string_tokens(content)
                elif isinstance(content, list):
                    for item in content:
                        item: Dict
                        if item.get("type") == "text":
                            total_tokens += self._estimate_string_tokens(item.get("text", ""))
                        elif item.get("type") == "image_url":
                            total_tokens += 1000

            if "tool_calls" in msg and msg["tool_calls"]:
                total_tokens += self._estimate_string_tokens(str(msg["tool_calls"]))

        return int(total_tokens)


@dataclass(slots=True)
class ContextDeque:
    """对话上下文 (优化版),不是很确定实战效果使用了双端队列来实现"""

    messages: Deque[Dict[str, Any]] = field(default_factory=deque)
    """原始的上下文"""

    user_max_record: int = 20
    """user最多消息条数限制"""

    play_role: str = ""
    """模型人物提示词"""

    async_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    """异步锁"""

    def __post_init__(self):
        if self.messages is None:
            self.messages = deque()
        elif isinstance(self.messages, list):
            self.messages = deque(self.messages)

    def __getitem__(self, index):
        return self.messages[index]

    def __len__(self):
        return len(self.messages)

    def __iter__(self):
        return iter(self.messages)

    def __contains__(self, item):
        return item in self.messages

    def __reversed__(self):
        return reversed(self.messages)

    def __str__(self):
        return str(list(self.messages))

    def __repr__(self):
        return repr(list(self.messages))

    def append(self, data: Dict[str, Any]) -> None:
        """添加内容"""
        self.messages.append(data)

    def extend(self, iterable: Iterable) -> None:
        """扩展列表"""
        self.messages.extend(iterable)

    def get_messages(self, inject_text: str = "") -> List[Dict[str, str]]:
        """获取当前的上下文 List"""
        system_content = "\n\n".join(filter(None, [self.play_role, inject_text]))
        system_msg = [{"role": "system", "content": system_content}] if system_content else []

        return system_msg + list(self.messages)

    def clear(self) -> None:
        """清除上下文"""
        self.messages.clear()

    def record_validity_check(self) -> List[Dict[str, Any]]:
        """
        针对消息条数的验证。
        优化后：使用 popleft() 移除头部元素，避免了列表切片的内存拷贝和移动。
        """
        removed_messages = []

        user_count = sum(1 for msg in self.messages if msg["role"] == "user")

        if user_count <= self.user_max_record:
            return None

        while user_count > self.user_max_record and self.messages:
            msg = self.messages.popleft()
            removed_messages.append(msg)
            if msg["role"] == "user":
                user_count -= 1

        while self.messages and self.messages[0]["role"] != "user":
            msg = self.messages.popleft()
            removed_messages.append(msg)

        return removed_messages

    def add_message(self, role: str, content: str | list, tool_call_id: int = None) -> None:
        if tool_call_id:
            self.messages.append({
                "role": role,
                "content": content,
                "tool_call_id": tool_call_id
            })
            return
        self.messages.append({"role": role, "content": content})

    def add_img_message(self, role: str, text: str, image_urls: list) -> None:
        self.messages.append({
            "role": role,
            "content": [{"type": "image_url", "image_url": {"url": url}} for url in image_urls] + [{"type": "text", "text": text}]
        })

    def add_user_message(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str | None) -> None:
        self.messages.append({"role": "assistant", "content": content})

    def add_assistant_message_flexible(self, assistant_message: Dict) -> None:
        self.messages.append(assistant_message)

    def add_assistant_tool_message(self, content: str | None, tool_calls: List[Dict] = None) -> None:
        msg = {"role": "assistant", "tool_calls": tool_calls}
        if content:
            msg["content"] = content
        self.messages.append(msg)

    def add_system_message(self, content: str) -> None:
        self.messages.append({"role": "system", "content": content})

    def add_tool_message(self, name: str, tool_call_id: str, content: str) -> None:
        self.messages.append({
            "role": "tool",
            "name": name,
            "tool_call_id": tool_call_id,
            "content": content
        })

    def _estimate_string_tokens(self, text: str) -> float:
        if not text:
            return 0
        length = len(text)
        non_ascii_count = (len(text.encode('utf-8')) - length) // 2
        ascii_count = length - non_ascii_count
        return (ascii_count * 0.25) + (non_ascii_count * 0.7)

    def get_context_forecast_token(self) -> int:
        total_tokens = 0
        for msg in self.messages:
            total_tokens += 5
            content = msg.get("content")
            if content:
                if isinstance(content, str):
                    total_tokens += self._estimate_string_tokens(content)
                elif isinstance(content, list):
                    for item in content:
                        if item.get("type") == "text":
                            total_tokens += self._estimate_string_tokens(item.get("text", ""))
                        elif item.get("type") == "image_url":
                            total_tokens += 1000
            if "tool_calls" in msg and msg["tool_calls"]:
                total_tokens += self._estimate_string_tokens(str(msg["tool_calls"]))
        return int(total_tokens)
