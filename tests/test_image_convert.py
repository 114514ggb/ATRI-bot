"""图片统一转码(convert_to_jpeg / compress_image / url_to_image_jpeg)测试

覆盖:任意格式强制转 JPEG、动画 GIF 取首帧、RGBA 透明白底合成、
损坏/截断数据返回 None 且不入缓存。
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
    """带 JPEG 魔数但内容损坏/截断的数据"""
    return b"\xff\xd8\xff\xe0" + b"this-is-not-a-real-image" * 4


def test_convert_to_jpeg_output_is_valid_jpeg():
    """JPEG/PNG/动画GIF 输入统一输出可被 PIL 打开的标准 JPEG"""
    for raw in (_jpeg_bytes(), _png_bytes(), _animated_gif_bytes()):
        result = convert_to_jpeg(raw, max_size_kb=1024)
        assert result is not None
        with Image.open(io.BytesIO(result)) as img:
            assert img.format == "JPEG"
            img.verify()


def test_convert_to_jpeg_animated_gif_takes_first_frame():
    """动画 GIF 转码后为单帧静态图"""
    result = convert_to_jpeg(_animated_gif_bytes())
    assert result is not None
    with Image.open(io.BytesIO(result)) as img:
        assert img.format == "JPEG"
        assert getattr(img, "is_animated", False) is False
        assert getattr(img, "n_frames", 1) == 1


def test_convert_to_jpeg_rgba_uses_white_background():
    """RGBA 透明图合成白底,避免转 RGB 变黑"""
    result = convert_to_jpeg(_rgba_transparent_png_bytes())
    assert result is not None
    with Image.open(io.BytesIO(result)) as img:
        img.load()
        pixel = img.convert("RGB").getpixel((0, 0))
        assert pixel == (255, 255, 255)


def test_convert_to_jpeg_corrupt_returns_none():
    """损坏/截断/非图片数据返回 None"""
    assert convert_to_jpeg(_corrupt_bytes(), max_size_kb=1024) is None
    assert convert_to_jpeg(b"") is None
    assert convert_to_jpeg(b"not an image at all") is None


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

    assert first is not None and second is not None
    assert first.fmt == "jpeg"
    assert first.mime == "image/jpeg"
    assert first.data == second.data
    # 磁盘上只有 1 个缓存条目,说明第二次未重新下载/转码
    assert len(list(image_cache_dir.glob("*.bin"))) == 1


@pytest.mark.asyncio
async def test_url_to_image_jpeg_corrupt_not_cached(image_cache_dir):
    """损坏图片返回 None 且不写入磁盘缓存"""
    path = image_cache_dir / "broken.jpg"
    path.write_bytes(_corrupt_bytes())
    source = File.from_local_path(str(path))

    result = await url_to_image_jpeg(source, file_name="broken.jpg")

    assert result is None
    assert len(list(image_cache_dir.glob("*.bin"))) == 0
