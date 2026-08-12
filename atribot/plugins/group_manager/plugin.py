import json
import re
from pathlib import Path

from atribot.core.command.async_permissions_management import PermissionsManagement
from atribot.core.db.async_db_basics import AsyncDatabaseBase
from atribot.core.service_container import container
from atribot.core.type.bot_types import (
    MessageEventEnvelope,
    NoticeEnvelope,
    RequestEnvelope,
)
from atribot.core.type.onebot_event_types import (
    GroupDecreaseEvent,
    GroupDecreaseSubType,
    GroupIncreaseEvent,
    GroupIncreaseSubType,
    GroupRequestEvent,
)
from atribot.plugins.group_manager._keyword_responder import KeywordResponder
from atribot.plugins.plugin import Plugin


class GroupManagerPlugin(Plugin):
    """群管理插件

    自动处理群成员变动通知和加群请求审批。
    """

    plugin_name = "group_manager"
    plugin_version = "1.0.0"
    plugin_description = "群管理通知、加群审批与关键词回复"
    plugin_author = "ATRI"

    def __init__(self) -> None:
        super().__init__()
        self.keyword_rsp = KeywordResponder()
        self.blacklist = container.get_by_type(PermissionsManagement).blacklist
        self._load_white_list_group()

    def _load_white_list_group(self) -> None:
        """加载群加群白名单 JSON 配置"""
        json_path = Path(__file__).parent / "white_list_group.json"
        try:
            with open(json_path, encoding="utf-8") as f:
                raw: dict[str, list[str]] = json.load(f)
            self.white_list_group: dict[int, list[str]] = {
                int(k): v for k, v in raw.items()
            }
        except Exception as e:
            self.log.warning("加载 white_list_group.json 失败: %s", e)
            self.white_list_group = {}

    @Plugin.on_message(priority=0)
    async def on_keyword_response(self, event: MessageEventEnvelope) -> None:
        """关键词匹配回复 —— 直接使用 event 信封

        处理纯文本/图片/音频/混合消息的自动回复。
        """
        try:
            if event.user_id not in self.blacklist:#过滤
                await self.keyword_rsp.handle(event)
        except Exception as e:
            self.log.exception("关键词回复处理异常: %s", e)

    @Plugin.on_notice(priority=0)
    async def on_group_inform(self, event: NoticeEnvelope) -> None:
        """群成员变动通知（欢迎进群、踢人/退群）"""
        ev = event.event

        if isinstance(ev, GroupIncreaseEvent):
            await self._handle_group_increase(event, ev)
        elif isinstance(ev, GroupDecreaseEvent):
            await self._handle_group_decrease(event, ev)

    async def _handle_group_increase(
        self, event: NoticeEnvelope, ev: GroupIncreaseEvent
    ) -> None:
        """处理群成员增加（同意加群 / 邀请入群）"""
        if ev.sub_type != GroupIncreaseSubType.APPROVE:
            return

        group_id = ev.group_id
        user_id = ev.user_id

        # 发送欢迎消息
        await event.send_client.send_group_msg(
            group_id, f"欢迎[CQ:at,qq={user_id}]加入群聊！"
        )

        # 记录用户到数据库
        try:
            db: AsyncDatabaseBase = container.get_by_type(AsyncDatabaseBase)
            await db.add_user(user_id=user_id, nickname="NOT_SET")
        except Exception as e:
            self.log.warning("用户信息存储失败: %s", e)

    async def _handle_group_decrease(
        self, event: NoticeEnvelope, ev: GroupDecreaseEvent
    ) -> None:
        """处理群成员减少（踢人 / 退群）"""
        group_id = ev.group_id
        user_id = ev.user_id

        if ev.sub_type == GroupDecreaseSubType.KICK:
            operator_id = ev.operator_id
            await event.send_client.send_group_msg(
                group_id,
                f"[CQ:at,qq={user_id}]({user_id})被[CQ:at,qq={operator_id}]请出群聊！",
            )
        elif ev.sub_type == GroupDecreaseSubType.LEAVE:
            await event.send_client.send_group_msg(
                group_id,
                f"[CQ:at,qq={user_id}]({user_id})永久的离开了我们！希望以后安好~",
            )

    @Plugin.on_request(priority=0)
    async def on_group_request(self, event: RequestEnvelope) -> None:
        """加群请求自动审批"""
        ev = event.event
        if not isinstance(ev, GroupRequestEvent):
            return
        if ev.sub_type != "add":
            return

        await self._handle_group_add_request(event, ev)

    async def _handle_group_add_request(
        self, event: RequestEnvelope, ev: GroupRequestEvent
    ) -> None:
        """执行加群审批逻辑"""
        send = event.send_client
        group_id = ev.group_id
        user_id = ev.user_id
        comment = ev.comment
        flag = ev.flag

        if match := re.search(r"学习|交流|谢谢|同意|趣味相投|小白", comment):
            await send.set_group_add_request(flag, False)
            await send.send_group_msg(
                group_id,
                f"已自动拒绝可疑加群请求！匹配到关键词：{match.group()}\n验证信息:\n{comment}",
            )
            return

        if group_id in self.white_list_group:
            if answer_match := re.search(r"答案：\s*(.*)", comment):
                answer = answer_match.group(1).strip()
                for pattern in self.white_list_group[group_id]:
                    if re.search(pattern, answer, re.IGNORECASE):
                        await send.set_group_add_request(flag, True)
                        return

            try:
                stranger_info = await send.get_stranger_info(user_id)
                qq_level = stranger_info.get("qqLevel", 0) if isinstance(stranger_info, dict) else 0
            except Exception:
                qq_level = 0

            if qq_level and qq_level < 10:
                await send.set_group_add_request(flag, False)
                await send.send_group_msg(
                    group_id,
                    f"已自动拒绝可疑加群请求！等级过低:{qq_level}级\n验证信息:\n{comment or 'None'}",
                )
                return

        await send.send_group_msg(
            group_id,
            f"有人申请加群了!\n[CQ:at,qq={user_id}]({user_id})\n{comment}",
        )
