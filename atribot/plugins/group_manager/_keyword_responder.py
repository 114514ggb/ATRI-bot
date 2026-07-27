import random
import time
from enum import Enum
from logging import Logger
from typing import Any, Dict, List, Tuple, Union

import ahocorasick

from atribot.core.atri_config import atriConfig
from atribot.core.cache.management_chat_example import ChatManager
from atribot.core.service_container import container
from atribot.core.type.bot_types import MessageEventEnvelope
from atribot.plugins.group_manager.data_alike import monitoring_alike_list
from atribot.plugins.group_manager.data_have import monitoring_have_list


class ResponseType(Enum):
    TEXT = "text"
    IMAGE = "img"
    AUDIO = "audio"
    MIXTURE = "mixture"


def construction_message_dict(
    template: list[dict], url_prefix: str = ""
) -> list[dict]:
    """构造 OneBot 消息段列表"""
    result = []
    for item in template:
        for key, value in item.items():
            if not value:
                continue
            if key == "image":
                image_path = url_prefix + value if url_prefix else value
                result.append({"type": "image", "data": {"file": image_path}})
            elif key == "text":
                result.append({"type": "text", "data": {"text": value}})
    return result


class KeywordResponder:
    """关键词回复器"""

    def __init__(self) -> None:
        self.log: Logger = container.get_by_type(Logger).getChild("KeywordRsp")
        config: atriConfig = container.get_by_type(atriConfig)
        self.url_prefix: str = f"file://{config.file_path.img.as_posix()}"
        self.context_management: ChatManager = container.get_by_type(ChatManager)

        self.monitoring_alike_list = monitoring_alike_list
        self.monitoring_have_list = monitoring_have_list
        self._build_automaton()

    def _build_automaton(self) -> None:
        """构建 AC 自动机（用于包含匹配）"""
        self.automaton = ahocorasick.Automaton()
        for keyword in self.monitoring_have_list.keys():
            self.automaton.add_word(keyword, keyword)
        self.automaton.make_automaton()

    async def handle(self, event: MessageEventEnvelope) -> bool:
        """主处理逻辑 —— 使用 event 信封直接处理

        Args:
            event: 消息事件信封

        Returns:
            True 表示已回复,False 表示未匹配
        """
        group_id = event.group_id
        if group_id is None:
            return False

        send = event.send_client
        raw_text = event.event.raw_message

        async def _send(send_type: ResponseType, document: Any) -> None:
            if send_type is ResponseType.TEXT:
                await send.send_group_msg(group_id, document)
            elif send_type is ResponseType.IMAGE:
                await send.send_group_pictures(group_id, document, True)
            elif send_type is ResponseType.AUDIO:
                await send.send_group_audio(group_id, document, True)
            elif send_type is ResponseType.MIXTURE:
                await send.send_group_msg(
                    group_id, construction_message_dict(document, self.url_prefix)
                )

        # 间隔太短不处理
        try:
            ctx = await self.context_management.get_group_context(group_id)
            if time.time() - ctx.last_msg_at < 5:
                return False
        except Exception:
            pass

        if template := self._process_string(raw_text):
            send_type, document = template
            await _send(send_type, document)
            return True
        return False

    def _process_string(
        self, text: str
    ) -> Tuple[ResponseType, Union[str, List[str], Dict[str, Any]]] | None:
        """处理字符串，返回匹配的配置"""
        # 精确匹配
        if text in self.monitoring_alike_list:
            return self._get_random_response(self.monitoring_alike_list[text])

        # 包含匹配（AC 自动机）
        for _, keyword in self.automaton.iter(text):
            if keyword in self.monitoring_have_list:
                return self._get_random_response(self.monitoring_have_list[keyword])

        return None

    def _get_random_response(
        self, config_list: List[List]
    ) -> Tuple[ResponseType, Union[str, List[str], Dict[str, Any]]]:
        """从配置列表中随机选择一个返回"""
        selected_config = random.choice(config_list)
        response_type_str = selected_config[0]
        content_list = selected_config[1]

        response_type = ResponseType(response_type_str)

        if response_type == ResponseType.MIXTURE:
            return response_type, random.choice(content_list)
        else:
            if len(content_list) == 1:
                return response_type, content_list[0]
            else:
                return response_type, random.choice(content_list)

    def add_alike_config(self, keyword: str, config: List[List]) -> None:
        """添加完全匹配配置"""
        self.monitoring_alike_list[keyword] = config

    def add_have_config(self, keyword: str, config: List[List]) -> None:
        """添加包含匹配配置"""
        self.monitoring_have_list[keyword] = config
        self._build_automaton()

    def remove_config(self, keyword: str, config_type: str = "both") -> None:
        """删除配置"""
        if config_type in ["alike", "both"]:
            self.monitoring_alike_list.pop(keyword, None)
        if config_type in ["have", "both"]:
            self.monitoring_have_list.pop(keyword, None)
            self._build_automaton()
