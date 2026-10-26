"""平台适配器状态查询命令"""

from logging import Logger

from atribot.commands.interior.platform_status import build_platform_report
from atribot.core.atri_config import atriConfig
from atribot.core.command.command_parsing import CommandSystem
from atribot.core.platform import get_registered_adapters
from atribot.core.platform.manager import PlatformManager
from atribot.core.service_container import container
from atribot.core.type.bot_types import MessageEventEnvelope

cmd_system: CommandSystem = container.get("CommandSystem")
config: atriConfig = container.get("config")
log: Logger = container.get_by_type(Logger).getChild("PlatformCmd")

MERGE_SOURCE = "平台适配器状态"


def collect_platform_report() -> str:
    """从容器与 PlatformManager 收集数据并生成状态报告"""
    manager: PlatformManager | None
    try:
        manager = container.get_by_type(PlatformManager)
    except ValueError:
        manager = None

    instances = config.platforms.instances if config.platforms else {}

    return build_platform_report(
        instances=instances,
        adapters=manager.adapters if manager else {},
        registered=get_registered_adapters(),
        manager_running=bool(manager and manager.is_running),
        manager_available=manager is not None,
        queue_stats=manager.queue.stats() if manager else None,
    )


@cmd_system.register_command(
    name="platform",
    description="查看平台适配器类型、连接状态、目标地址与端口",
    aliases=["platforms", "adapter", "适配器", "平台"],
    authority_level=2,
    examples=["/platform"],
)
async def platform_handler(message_data: MessageEventEnvelope) -> None:
    try:
        report = collect_platform_report()
    except Exception as e:
        log.exception(f"生成平台状态报告失败: {e}")
        report = f"❌ 生成平台状态报告失败：{e}"

    try:
        if message_data.group_id:
            await message_data.send_client.send_group_merge_text(
                group_id=message_data.group_id,
                message=report,
                source=MERGE_SOURCE,
            )
        else:
            await message_data.send_client.send_private_merge_text(
                qq_id=message_data.user_id,
                message=report,
                source=MERGE_SOURCE,
            )
    except Exception as e:
        log.error(f"发送平台状态报告失败: {e}")
