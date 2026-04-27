from atribot.core.command.command_parsing import CommandSystem
from atribot.core.network_connections.qq_send_message import QQAPIClient
from atribot.core.service_container import container
from atribot.core.type.chat_message_types import ChatMessage

from .ATRI_encrypt import Encrypt

cmd_system: CommandSystem = container.get("CommandSystem")
send_message: QQAPIClient = container.get("SendMessage")


@cmd_system.register_command(
    name='atri',
    description='ATRI 特殊编码 - 基于Unicode特殊字符的文本加密/解密工具',
    aliases=['encrypt', 'atri加密', 'atri解密'],
    examples=[
        '/atri 加密这段文字',
        '/atri -d āŢĀāŢţ',
        '/atri --decode āŢĀāŢţ'
    ],
    authority_level=1
)
@cmd_system.argument(
    name="text",
    description="要加密或解密的文本内容",
    required=False,
    metavar="TEXT",
    multiple=True,
    type=str
)
@cmd_system.flag(
    name="decode",
    short="-d",
    long="--decode",
    description="解码模式：将ATRI编码的Unicode字符还原为原始文本",
)
@cmd_system.option(
    name="encoding",
    short="-c",
    long="--encoding",
    description="指定字符编码格式（默认utf-8）",
    required=False,
    default="utf-8",
    choices=["utf-8", "gbk", "gb2312"],
    metavar="ENCODING",
    type=str
)
async def atri_encrypt_command(
    message_data: ChatMessage,
    text: list = None,
    decode: bool = False,
    encoding: str = "utf-8",
):
    """
    ATRI 加密/解密命令处理器
    """

    encryptor = Encrypt()
    group_id = message_data.group_id

    input_text = " ".join(text) if isinstance(text, list) else str(text)

    if not input_text or not input_text.strip():
        await send_message.send_group_merge_text(
            group_id=group_id,
            message="语法: /atri [-d] [-c 编码] <文本>\n加密示例: /atri 你好\n解密示例: /atri -d āŢĀāŢţ",
            source="ATRI编码语法"
        )
        return

    try:
        is_decode = decode or any(c in input_text[:10] for c in encryptor.cr + encryptor.cc + encryptor.cn + encryptor.cb)

        if is_decode:
            result = encryptor.decode(input_text, encoding=encoding)
            title = "🔓 解码结果"
        else:
            result = encryptor.encode(input_text, encoding=encoding)
            title = "🔒 编码结果"

        if len(result) > 3000:
            result = result[:3000] + "\n... (已截断)"

        await send_message.send_group_merge_text(
            group_id=group_id,
            message=f"{title}\n{result}",
            source="ATRI编码"
        )

    except Exception as e:
        await send_message.send_group_merge_text(
            group_id=group_id,
            message=f"错误: {str(e)}",
            source="ATRI编码错误"
        )
