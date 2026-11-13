"""QQ 官方机器人 openid 与整数 ID 的稳定映射

QQ 官方 API 的 ``group_openid`` / ``user_openid`` / 消息 ``id`` 都是字符串，
而本项目下游（数据库 BIGINT 列、白名单、上下文键）全部按整数工作。

这里用带类型前缀的 blake2b 摘要生成稳定的 62 位整数，并把最高位置 1
（结果落在 2^62 ~ 2^63 区间），避免与真实 QQ 号（远小于 2^32）混淆。
映射结果只由 openid 决定，进程重启后不变，因此无需持久化。
"""
import hashlib
from logging import Logger
from typing import Literal

IDKind = Literal["group", "user", "message"]
"""ID 种类：群 / 用户 / 消息"""

_HIGH_BIT = 1 << 62
"""合成 ID 的最高位，置 1 后归属 QQ 官方机器人域"""

_LOW_MASK = _HIGH_BIT - 1

_KIND_PREFIX: dict[str, bytes] = {
    "group": b"qqbot-group|",
    "user": b"qqbot-user|",
    "message": b"qqbot-message|",
}


def make_synthetic_id(kind: IDKind, raw: str) -> int:
    """把原始 openid / 消息 ID 转换为稳定的整数 ID

    Args:
        kind: ID 种类
        raw: 原始字符串

    Returns:
        62 位正整数（最高位固定为 1）；``raw`` 为空时返回 0
    """
    if not raw:
        return 0
    prefix = _KIND_PREFIX.get(kind, b"qqbot-other|")
    digest = hashlib.blake2b(prefix + raw.encode("utf-8"), digest_size=8).digest()
    return _HIGH_BIT | (int.from_bytes(digest, "big") & _LOW_MASK)


class QQBotIdMapper:
    """openid ↔ 整数 ID 双向映射

    - 未配置手工映射时使用稳定哈希
    - 可通过 ``config.platforms.<name>.id_map`` 手工指定，例如
      ``{"group": {"<group_openid>": 123456789}, "user": {...}}``
    """

    def __init__(
        self,
        id_map: dict[str, dict[str, int]] | None = None,
        log: Logger | None = None,
    ) -> None:
        self._log = log
        self._overrides: dict[str, dict[str, int]] = {}
        self._reverse: dict[str, dict[int, str]] = {}

        for kind, mapping in (id_map or {}).items():
            if kind not in _KIND_PREFIX or not isinstance(mapping, dict):
                continue
            normalized: dict[str, int] = {}
            for raw, value in mapping.items():
                try:
                    normalized[str(raw)] = int(value)
                except (TypeError, ValueError):
                    continue
            if normalized:
                self._overrides[kind] = normalized
                for raw, value in normalized.items():
                    self._reverse.setdefault(kind, {})[value] = raw

        self._seen: dict[tuple[str, str], int] = {}

    def to_id(self, kind: IDKind, raw: str | None) -> int:
        """把原始 openid / 消息 ID 转换为整数 ID（幂等）"""
        if raw is None or raw == "":
            return 0
        key = (kind, raw)
        cached = self._seen.get(key)
        if cached is not None:
            return cached

        override = self._overrides.get(kind, {}).get(raw)
        value = override if override is not None else make_synthetic_id(kind, raw)
        self._seen[key] = value
        self._reverse.setdefault(kind, {})[value] = raw

        if kind in ("group", "user") and self._log is not None:
            self._log.info(
                "QQ 官方机器人 ID 映射: %s openid=%s -> %s",
                "群" if kind == "group" else "用户",
                raw,
                value,
            )
        return value

    def to_raw(self, kind: IDKind, value: int | str | None) -> str | None:
        """把整数 ID 还原为原始 openid（未见过时返回 None）"""
        if value is None:
            return None
        try:
            int_value = int(value)
        except (TypeError, ValueError):
            return None
        return self._reverse.get(kind, {}).get(int_value)

    def reconcile(self, kind: IDKind, raw: str, value: int) -> None:
        """按配置声明的映射对齐（供适配器把页面/配置里的数字 ID 反查到 openid）"""
        self._overrides.setdefault(kind, {})[raw] = value
        self._seen[(kind, raw)] = value
        self._reverse.setdefault(kind, {})[value] = raw
