import base64
import io
import os

import pytest

from atribot.common_utils.file import media_cache as mc
from atribot.common_utils.file.image_utils import url_to_image_jpeg
from atribot.core.type.chat_message_types import File


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    """将缓存目录注入临时目录并缩小体积上限，测试后自动还原"""
    monkeypatch.setattr(mc, "_cache_dir", tmp_path)
    monkeypatch.setattr(mc, "MAX_FILE_BYTES", 1024)
    yield tmp_path
    monkeypatch.setattr(mc, "_cache_dir", None)



def test_make_cache_key_stable_for_same_file_name():
    """同一 file_name 时,URL 签名(query)变化不影响缓存键"""
    k1 = mc.make_cache_key("image", "http://a/b.jpg?sig=1", "abc.image", "kb=1024")
    k2 = mc.make_cache_key("image", "http://a/b.jpg?sig=2", "abc.image", "kb=1024")
    assert k1 == k2


def test_make_cache_key_differs_by_params():
    k1 = mc.make_cache_key("image", "src", "abc.image", "kb=1024")
    k2 = mc.make_cache_key("image", "src", "abc.image", "kb=512")
    assert k1 != k2


def test_make_cache_key_differs_by_kind():
    k1 = mc.make_cache_key("image", "src", "abc.image", "kb=1024")
    k2 = mc.make_cache_key("audio", "src", "abc.image", "kb=1024")
    assert k1 != k2


def test_make_cache_key_stable_url_without_file_name():
    """无 file_name 时回退 URL 路径(去掉 query),QQ CDN 签名变化不影响键"""
    k1 = mc.make_cache_key("image", "https://cdn.example.com/x/abc-123-0.jpg?sig=aaa", None, "kb=1024")
    k2 = mc.make_cache_key("image", "https://cdn.example.com/x/abc-123-0.jpg?sig=bbb", None, "kb=1024")
    assert k1 == k2


def test_make_cache_key_differs_for_different_urls():
    k1 = mc.make_cache_key("image", "https://cdn.example.com/a/1-0.jpg?sig=1", None, "kb=1024")
    k2 = mc.make_cache_key("image", "https://cdn.example.com/b/2-0.jpg?sig=2", None, "kb=1024")
    assert k1 != k2


@pytest.mark.asyncio
async def test_cache_get_miss_returns_none(cache_dir):
    assert await mc.cache_get("not-exist") is None


@pytest.mark.asyncio
async def test_cache_put_get_roundtrip(cache_dir):
    raw = b"\x00\x01\x02data"
    await mc.cache_put("abc", raw, fmt="jpeg", mime="image/jpeg", converted=True)

    entry = await mc.cache_get("abc")
    assert entry is not None
    assert entry.data == raw
    assert entry.fmt == "jpeg"
    assert entry.mime == "image/jpeg"
    assert entry.converted is True
    assert entry.to_base64() == base64.b64encode(raw).decode()


@pytest.mark.asyncio
async def test_cache_get_self_heals_corrupt_entry(cache_dir):
    """截断的 .bin + 长度不匹配的 meta 会被识别为损坏并自愈删除"""
    key = "corrupt"
    data_path = cache_dir / f"{key}.bin"
    meta_path = cache_dir / f"{key}.json"
    # 模拟进程被杀留下的半截数据文件
    data_path.write_bytes(b"truncated-jpeg-data")
    meta_path.write_text(
        '{"fmt": "jpeg", "mime": "image/jpeg", "converted": true, "size": 99999}',
        encoding="utf-8",
    )

    assert await mc.cache_get(key) is None
    # 自愈：损坏条目被删除，避免被永久命中
    assert not data_path.exists()
    assert not meta_path.exists()


@pytest.mark.asyncio
async def test_cache_get_cleans_orphan_data(cache_dir):
    """有数据无 meta 的孤儿条目(崩溃残留)被清除"""
    key = "orphan"
    data_path = cache_dir / f"{key}.bin"
    data_path.write_bytes(b"data-without-meta")

    assert await mc.cache_get(key) is None
    assert not data_path.exists()


@pytest.mark.asyncio
async def test_cache_put_skips_oversize(cache_dir):
    """超过单文件体积上限不写入"""
    await mc.cache_put("big", b"x" * (mc.MAX_FILE_BYTES + 1), fmt="video/mp4", mime="video/mp4", converted=True)
    assert await mc.cache_get("big") is None
    assert not (cache_dir / "big.bin").exists()


@pytest.mark.asyncio
async def test_enforce_cache_limit_evicts_oldest(cache_dir):
    """文件数超过上限时按 mtime 淘汰最旧条目(连同 meta)"""
    for i in range(5):
        await mc.cache_put(f"key-{i}", bytes([i]) * 100, fmt="jpeg", mime="image/jpeg", converted=True)

    # 显式设置递增的 mtime，key-0 最旧
    for i in range(5):
        os.utime(cache_dir / f"key-{i}.bin", (i, i))

    mc.enforce_cache_limit(3)

    remaining = sorted(p.stem for p in cache_dir.glob("*.bin"))
    assert remaining == ["key-2", "key-3", "key-4"]
    # 被淘汰条目的 meta 同步删除
    assert not (cache_dir / "key-0.json").exists()
    assert not (cache_dir / "key-1.json").exists()


@pytest.mark.asyncio
async def test_url_to_image_jpeg_uses_cache(tmp_path, monkeypatch):
    """同一本地图片第二次调用直接命中磁盘缓存，不重复压缩"""
    monkeypatch.setattr(mc, "_cache_dir", tmp_path)

    buf = io.BytesIO()
    from PIL import Image

    Image.new("RGB", (64, 64), color="red").save(buf, format="JPEG")
    image_path = tmp_path / "test.jpg"
    image_path.write_bytes(buf.getvalue())

    source = File.from_local_path(str(image_path))
    first = await url_to_image_jpeg(source, file_name="stable.image")
    second = await url_to_image_jpeg(source, file_name="stable.image")

    assert first.data == second.data
    # 磁盘上只有 1 个缓存条目，说明第二次未重新下载/压缩
    assert len(list(tmp_path.glob("*.bin"))) == 1
