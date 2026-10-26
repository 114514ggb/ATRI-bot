from atribot.core.platform import register_adapter
from atribot.core.platform.onebot.adapter import OneBotAdapter
from atribot.core.platform.snowluma.message_event import SnowLumaMessageEvent
from atribot.core.platform.snowluma.send import SnowLumaSendClient


@register_adapter("snowluma")
class SnowLumaAdapter(OneBotAdapter):
    """SnowLuma（OneBot v11）平台适配器

    连接、事件解析与发送逻辑全部复用 OneBotAdapter，
    差异集中在类属性中：日志名、事件信封、发送客户端与默认 WS 路径。
    """

    _log_name = "SnowLumaAdapter"
    _message_event_cls = SnowLumaMessageEvent
    _send_client_cls = SnowLumaSendClient
    _default_ws_path = "/"
