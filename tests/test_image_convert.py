"""图片统一转码(convert_to_jpeg / compress_image / url_to_image_jpeg)测试

覆盖:任意格式强制转 JPEG、动画 GIF 取首帧、RGBA 透明白底合成、
完全损坏数据抛出异常且不入缓存、尾部截断图片容忍处理、截断重试逻辑。
"""

import io

import pytest
from PIL import Image

from atribot.common_utils.file import media_cache as mc
from atribot.common_utils.file.image_utils import (
    compress_image,
    convert_to_jpeg,
    url_to_image_jpeg,
)
from atribot.core.type.chat_message_types import File


def _jpeg_bytes(color: str = "red", size: int = 64) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (size, size), color=color).save(buf, format="JPEG")
    return buf.getvalue()


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color="green").save(buf, format="PNG")
    return buf.getvalue()


def _rgba_transparent_png_bytes() -> bytes:
    """全透明的 RGBA PNG(如带透明通道的表情包)"""
    buf = io.BytesIO()
    Image.new("RGBA", (64, 64), (255, 0, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()


def _animated_gif_bytes() -> bytes:
    """两帧动画 GIF"""
    buf = io.BytesIO()
    frames = [Image.new("RGB", (32, 32), c) for c in ("red", "blue")]
    frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=100,
        loop=0,
    )
    return buf.getvalue()


def _corrupt_bytes() -> bytes:
    """带 JPEG 魔数但内容完全损坏的数据（非截断,无法解码）"""
    return b"\xff\xd8\xff\xe0" + b"this-is-not-a-real-image" * 4


def _truncated_jpeg_bytes(missing: int = 20) -> bytes:
    """尾部截断的有效 JPEG（模拟 QQ CDN 下载不完整,仅缺尾部少量字节）"""
    return _jpeg_bytes(size=128)[:-missing]


def test_convert_to_jpeg_output_is_valid_jpeg():
    """JPEG/PNG/动画GIF 输入统一输出可被 PIL 打开的标准 JPEG"""
    for raw in (_jpeg_bytes(), _png_bytes(), _animated_gif_bytes()):
        result = convert_to_jpeg(raw, max_size_kb=1024)
        with Image.open(io.BytesIO(result)) as img:
            assert img.format == "JPEG"
            img.verify()


def test_convert_to_jpeg_animated_gif_takes_first_frame():
    """动画 GIF 转码后为单帧静态图"""
    result = convert_to_jpeg(_animated_gif_bytes())
    with Image.open(io.BytesIO(result)) as img:
        assert img.format == "JPEG"
        assert getattr(img, "is_animated", False) is False
        assert getattr(img, "n_frames", 1) == 1


def test_convert_to_jpeg_rgba_uses_white_background():
    """RGBA 透明图合成白底,避免转 RGB 变黑"""
    result = convert_to_jpeg(_rgba_transparent_png_bytes())
    with Image.open(io.BytesIO(result)) as img:
        img.load()
        pixel = img.convert("RGB").getpixel((0, 0))
        assert pixel == (255, 255, 255)


def test_convert_to_jpeg_corrupt_raises():
    """完全损坏/非图片数据抛出异常"""
    with pytest.raises(Exception):
        convert_to_jpeg(_corrupt_bytes(), max_size_kb=1024)
    with pytest.raises(Exception):
        convert_to_jpeg(b"")
    with pytest.raises(Exception):
        convert_to_jpeg(b"not an image at all")


def test_convert_to_jpeg_truncated_succeeds():
    """尾部截断的 JPEG 在 LOAD_TRUNCATED_IMAGES=True 下可正常转码"""
    result = convert_to_jpeg(_truncated_jpeg_bytes(), max_size_kb=1024)
    with Image.open(io.BytesIO(result)) as img:
        assert img.format == "JPEG"
        img.verify()


def test_compress_image_falls_back_to_raw_on_corrupt():
    """compress_image 兼容封装:损坏数据回退原始字节"""
    raw = _corrupt_bytes()
    assert compress_image(raw, 1024) == raw


def test_compress_image_transcodes_small_image():
    """小图不再透传:PNG 输入压缩后输出为标准 JPEG"""
    raw = _png_bytes()
    result = compress_image(raw, 1024)
    assert result != raw
    with Image.open(io.BytesIO(result)) as img:
        assert img.format == "JPEG"


@pytest.fixture
def image_cache_dir(tmp_path, monkeypatch):
    """注入临时缓存目录,测试后还原"""
    monkeypatch.setattr(mc, "_cache_dir", tmp_path)
    yield tmp_path
    monkeypatch.setattr(mc, "_cache_dir", None)


@pytest.mark.asyncio
async def test_url_to_image_jpeg_png_to_jpeg_and_cached(image_cache_dir):
    """PNG 本地文件 → 统一 JPEG,且第二次命中缓存"""
    path = image_cache_dir / "pic.png"
    path.write_bytes(_png_bytes())
    source = File.from_local_path(str(path))

    first = await url_to_image_jpeg(source, file_name="pic.png")
    second = await url_to_image_jpeg(source, file_name="pic.png")

    assert first.fmt == "jpeg"
    assert first.mime == "image/jpeg"
    assert first.data == second.data
    # 磁盘上只有 1 个缓存条目,说明第二次未重新下载/转码
    assert len(list(image_cache_dir.glob("*.bin"))) == 1


@pytest.mark.asyncio
async def test_url_to_image_jpeg_corrupt_not_cached(image_cache_dir):
    """完全损坏图片抛出异常且不写入磁盘缓存"""
    path = image_cache_dir / "broken.jpg"
    path.write_bytes(_corrupt_bytes())
    source = File.from_local_path(str(path))

    with pytest.raises(Exception):
        await url_to_image_jpeg(source, file_name="broken.jpg")

    assert len(list(image_cache_dir.glob("*.bin"))) == 0


@pytest.mark.asyncio
async def test_url_to_image_jpeg_retries_on_truncated(image_cache_dir, monkeypatch):
    """截断图片触发重试:第一次 OSError('truncated'),第二次成功"""
    from atribot.common_utils.file import image_utils

    # 准备一个有效 JPEG 本地文件
    path = image_cache_dir / "pic.jpg"
    path.write_bytes(_jpeg_bytes(size=128))
    source = File.from_local_path(str(path))

    call_count = 0
    real_convert = image_utils.convert_to_jpeg

    def flaky_convert(data, max_size_kb=None, **kw):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise OSError("image file is truncated (17 bytes not processed)")
        return real_convert(data, max_size_kb=max_size_kb)

    monkeypatch.setattr(image_utils, "convert_to_jpeg", flaky_convert)

    result = await url_to_image_jpeg(source, file_name="retry.jpg")
    assert result.fmt == "jpeg"
    assert result.mime == "image/jpeg"
    assert call_count == 2  # 第一次失败,重试成功
