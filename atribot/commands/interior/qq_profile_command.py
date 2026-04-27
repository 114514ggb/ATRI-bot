import time

from atribot.core.command.command_parsing import CommandSystem
from atribot.core.network_connections.qq_send_message import QQAPIClient
from atribot.core.service_container import container
from atribot.core.type.chat_message_types import ChatMessage

cmd_system: CommandSystem = container.get("CommandSystem")
send_message: QQAPIClient = container.get("SendMessage")


@cmd_system.register_command(
    name='qq',
    description='查看qq账号的一些信息',
    aliases=['账号信息', 'qqProfile'],
    examples=[
        '/qq',
        '/qqProfile 168238719'
    ]
)
@cmd_system.argument(
    name="qq_id",
    description="QQ账号",
    required=False,
    metavar="qq_id",
    type=int
)
async def get_qq_profile(message_data: ChatMessage, qq_id: int = None):

    target_id = qq_id or message_data.user_id

    resp: dict = await send_message.get_stranger_info(target_id)
    
    if not resp or not isinstance(resp, dict) or not resp.get('data'):
        await send_message.send_group_merge_text(
            group_id=message_data.group_id,
            message=f"⚠️ 哎呀？找不到 QQ:{target_id} 的资料呢，是不是被外星人抓走了？",
            source="系统提示"
        )
        return

    data = resp['data']

    def format_timestamp(timestamp):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp)) if timestamp else "未知时间"

    nickname = data.get("nickname", "未知用户")
    display_id = data.get("qid") or target_id 
    age = data.get("age", "秘密")
    sex = data.get("sex", "未知")
    level = data.get("qqLevel", 0)

    is_vip = "👑尊贵会员" if data.get("is_vip") else "✨普通用户"
    if data.get("is_years_vip"): 
        is_vip = "💎年费大佬"
        
    reg_time = format_timestamp(data.get("reg_time", 0))

    country = data.get('country', '')
    province = data.get('province', '')
    city = data.get('city', '')
    location_parts = [p for p in [country, province, city] if p]
    location = "-".join(location_parts) if location_parts else "未知坐标"
    
    sign = data.get("long_nick") or "这个人很懒，什么都没写~"

    card = (
        f"║📂 用户档案 | 🆔 {str(display_id):<14}\n"
        f"╠══════════════════════════════\n"
        f"║ 👤 昵称: {nickname}\n"
        f"║ ⚧  性别: {sex}  | 🎂 年龄: {age}\n"
        f"║ 🌟 等级: Lv.{str(level):<3} | 🏷️ 身份: {is_vip}\n"
        f"║ 🌍 地区: {location}\n"
        f"║ 📅 注册: {reg_time}\n"
        f"╠══════════════════════════════\n"
        f"║ 📝 个性签名:\n"
        f"║ {sign}\n"
    )

    await send_message.send_group_merge_text(
        group_id=message_data.group_id,
        message=card,
        source="QQ账号信息"
    )
