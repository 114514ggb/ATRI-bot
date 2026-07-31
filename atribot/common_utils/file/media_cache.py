import asyncio
import base64
import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from atribot.core.service_container import container

MAX_FILE_BYTES = 50 * 1024 * 1024
"""单文件缓存体积上限(字节)，超过不写入缓存"""

MAX_FILES = 20
"""缓存文件数量上限(条目数)，超限按 mtime 淘汰最旧"""

_CACHE_SUBDIR = "media_cache"
"""缓存子目录名(位于 temp 目录下)"""

_cache_dir: Path | None = None
"""模块级懒加载缓存目录，可通过测试直接赋值注入"""

_key_locks: dict[str, asyncio.Lock] = {}
"""按缓存键区分的进程内锁，防止同一键并发重复下载+转换"""


@dataclass(frozen=True)
class MediaCacheEntry:
    """磁盘缓存条目

    Attributes:
        data: 原始字节(未做 base64 编码)
        fmt: 格式标识(同 MediaConvertResult.fmt)
        mime: 完整 MIME 类型(如 'image/jpeg'、'audio/mp3'、'video/mp4')
        converted: 是否成功转换为目标格式
    """

    data: bytes
    fmt: str
    mime: str
    converted: bool

    def to_base64(self) -> str:
        """将缓存字节编码为 base64 字符串"""
        return base64.b64encode(self.data).decode()


def _get_media_cache_dir() -> Path:
    """懒加载缓存目录并确保存在

    优先使用 ``config.file_path.temp/media_cache``，配置不可用时回退 ``./temp/media_cache``
    """
    global _cache_dir
    if _cache_dir is not None:
        return _cache_dir
    try:
        config = container.get("config")
        base = Path(config.file_path.temp)
    except Exception:
        base = Path("temp")
    _cache_dir = base / _CACHE_SUBDIR
    _cache_dir.mkdir(parents=True, exist_ok=True)
    return _cache_dir


def _cache_paths(key: str) -> tuple[Path, Path]:
    """返回 (数据文件路径, meta 文件路径)"""
    cache_dir = _get_media_cache_dir()
    return cache_dir / f"{key}.bin", cache_dir / f"{key}.json"


def _stable_identity(source: str) -> str:
    """从来源派生稳定标识

    http(s) URL 去掉 query/fragment 后整体哈希;QQ CDN 签名参数每次变化，
    但路径中内嵌内容哈希，故路径本身是稳定且基本唯一的
    """
    if source.startswith(("http://", "https://")):
        parts = urlsplit(source)
        source = f"{parts.scheme}://{parts.netloc}{parts.path}"
    return hashlib.sha1(source.encode("utf-8")).hexdigest()


def make_cache_key(kind: str, source: str, file_name: str | None, params: str) -> str:
    """生成缓存键

    Args:
        kind: 媒体类型，'image' / 'audio' / 'video'
        source: 来源字符串(http/https/file/base64 或本地路径)
        file_name: 文件名(QQ 媒体为内容哈希，稳定);None 时回退来源标识
        params: 转换参数串(如 'kb=1024'、'br=128k'、'crf=28')，保证不同参数不互相污染

    Returns:
        sha1 十六进制字符串
    """
    identity = file_name or _stable_identity(source)
    raw = f"{kind}:{identity}:{params}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


async def cache_get(key: str) -> MediaCacheEntry | None:
    """读取缓存条目

    不存在或损坏(meta 缺失/数据长度不匹配)返回 None
    """
    data_path, meta_path = _cache_paths(key)
    try:
        data = await asyncio.to_thread(data_path.read_bytes)
    except (FileNotFoundError, OSError):
        return None

    try:
        meta = await asyncio.to_thread(meta_path.read_text, encoding="utf-8")
    except (FileNotFoundError, OSError):
        await asyncio.to_thread(_remove_entry, data_path, meta_path)
        return None

    try:
        info = json.loads(meta)
        if info.get("size") != len(data):
            raise ValueError("缓存数据长度不匹配，判定为损坏")
        return MediaCacheEntry(
            data=data,
            fmt=info["fmt"],
            mime=info["mime"],
            converted=info["converted"],
        )
    except (KeyError, json.JSONDecodeError, ValueError):
        await asyncio.to_thread(_remove_entry, data_path, meta_path)
        return None


async def cache_put(
    key: str,
    data: bytes,
    fmt: str,
    mime: str,
    converted: bool,
) -> None:
    """写入缓存条目(原子)

    - 超过 ``MAX_FILE_BYTES`` 的字节直接跳过(不写入、不触发清理)
    - 先写 ``*.tmp`` 再 ``os.replace`` 原子落盘：读取方永远看不到半截文件，
      进程被杀也只残留 ``.tmp``(由清理逻辑回收)
    - 写入成功后触发数量上限清理
    """
    if len(data) > MAX_FILE_BYTES:
        return
    data_path, meta_path = _cache_paths(key)
    meta = json.dumps({"fmt": fmt, "mime": mime, "converted": converted, "size": len(data)})
    tmp_data = data_path.with_suffix(".bin.tmp")
    tmp_meta = meta_path.with_suffix(".json.tmp")
    try:
        await asyncio.to_thread(tmp_data.write_bytes, data)
        await asyncio.to_thread(tmp_meta.write_text, meta, encoding="utf-8")
        await asyncio.to_thread(os.replace, tmp_data, data_path)
        await asyncio.to_thread(os.replace, tmp_meta, meta_path)
    except OSError:
        return
    await asyncio.to_thread(enforce_cache_limit)


def _remove_entry(data_path: Path, meta_path: Path) -> None:
    """删除一对缓存文件(容忍不存在或删除失败)"""
    for p in (data_path, meta_path):
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass


def enforce_cache_limit(max_files: int = MAX_FILES) -> None:
    """文件数超过上限时按 mtime 删除最旧的数据文件(连同 meta)

    以 ``.bin`` 文件计数，一对 ``.bin``/``.json`` 视为一个条目。
    顺带清理残留超过 5 分钟的 ``*.tmp``(进程被杀遗留)，避免堆积。
    """
    cache_dir = _get_media_cache_dir()
    try:
        now = time.time()
        for tmp in cache_dir.glob("*.tmp"):
            try:
                if now - tmp.stat().st_mtime > 300:
                    tmp.unlink()
            except OSError:
                pass
        bins = sorted(cache_dir.glob("*.bin"), key=lambda p: p.stat().st_mtime)
    except OSError:
        return
    while len(bins) > max_files:
        oldest = bins.pop(0)
        _remove_entry(oldest, oldest.with_suffix(".json"))


def _get_lock(key: str) -> asyncio.Lock:
    """获取指定缓存键的进程内锁(映射有界，防止无界增长)"""
    lock = _key_locks.get(key)
    if lock is None:
        lock = _key_locks[key] = asyncio.Lock()
        if len(_key_locks) > 512:
            _key_locks.clear()
    return lock
