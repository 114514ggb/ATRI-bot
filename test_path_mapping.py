"""path_mapping 发送路径拼接检测脚本

在项目根目录执行: .venv/Scripts/python.exe test_path_mapping.py

验证 assets/config.json 中 file_path.path_mapping 配置生效后，
各"本地路径 → 发送消息"拼接点(表情包、关键词图片、send.py 媒体 API)
产出的 file:// 路径会被映射成协议端(WSL 侧 NapCat)可访问的路径；
同时验证本地路径的读取(如 resolve_file_to_bytes)完全不受映射影响。
"""

import asyncio
import logging
import shutil
import subprocess
import sys
from pathlib import Path

from atribot.common_utils.file.file_utils import resolve_file_to_bytes
from atribot.core.atri_config import FilePathConfig, atriConfig
from atribot.core.platform.onebot.send import OneBotSendClient
from atribot.core.type.chat_message_types import GroupMessage
from atribot.LLMchat.emoji_system import EmojiCore

logging.basicConfig(level=logging.WARNING)

SCRATCH_DIR_NAME = ".tmp_path_mapping_check"


class StubWSConnection:
    """记录实际发往协议端的 action/params 的假连接"""

    def __init__(self):
        self.sent: list[dict] = []

    async def send(self, message: dict, with_echo: bool = True) -> dict:
        self.sent.append(message)
        return {"status": "ok", "retcode": 0, "data": {}}


FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("✅ " if ok else "❌ ") + name + (f"\n     {detail}" if detail else ""))
    if not ok:
        FAILURES.append(name)


def check_wsl_mount(remote_prefix: str) -> None:
    """信息性检查: 默认 WSL 发行版里能否看到映射后的目录(不影响整体结果)"""
    try:
        result = subprocess.run(
            ["wsl", "ls", remote_prefix],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except Exception as error:
        print(f"⚠️  无法调用 wsl 命令检查挂载: {error}")
        return
    if result.returncode == 0:
        print(f"✅ WSL 中可以访问 {remote_prefix}")
    else:
        print(
            f"⚠️  默认 WSL 发行版访问 {remote_prefix} 失败: {(result.stderr or '').strip()}\n"
            "     若 NapCat 所在发行版已关闭 automount, 需在 /etc/wsl.conf 的 [automount] 里开启 enabled=true"
        )


def image_files(segments) -> list[str]:
    """从消息段列表里取出所有 image 段的 file 值"""
    return [
        seg["data"]["file"]
        for seg in segments
        if isinstance(seg, dict) and seg.get("type") == "image"
    ]


async def main() -> int:
    config = atriConfig()
    file_paths: FilePathConfig = config.file_path
    mapping: dict[str, str] = file_paths.path_mapping
    print(f"配置文件: {config.config_file_path}")
    print(f"path_mapping = {mapping}")
    if not mapping:
        print("❌ assets/config.json 的 file_path.path_mapping 为空, 请先配置后再检测")
        return 1

    local_prefix, remote_prefix = sorted(
        mapping.items(), key=lambda pair: len(pair[0]), reverse=True
    )[0]
    sample_local = f"{local_prefix}/document/img/x.png"
    sample_remote = f"{remote_prefix}/document/img/x.png"

    # ---------- 1. 映射语义 ----------
    print("\n[1] 前缀映射语义")
    check("基本前缀映射", file_paths.map_to_remote(sample_local) == sample_remote)
    lowered = sample_local.replace(local_prefix, local_prefix.lower(), 1)
    check("前缀大小写不敏感", file_paths.map_to_remote(lowered) == sample_remote, lowered)
    backslashed = sample_local.replace("/", "\\")
    check("反斜杠路径兼容", file_paths.map_to_remote(backslashed) == sample_remote)
    check("未命中前缀原样返回", file_paths.map_to_remote("D:/other/x.png") == "D:/other/x.png")
    check("空映射直通", FilePathConfig.apply_path_mapping(sample_local, {}) == sample_local)
    longest = FilePathConfig.apply_path_mapping(
        f"{local_prefix}/document/a.png",
        {local_prefix: remote_prefix, local_prefix + "/document": remote_prefix + "/doc2"},
    )
    check("最长前缀优先", longest == f"{remote_prefix}/doc2/a.png", longest)

    # ---------- 2. 表情包四条拼接链路 ----------
    print("\n[2] emoji_system 表情包拼接")
    scratch = Path(file_paths.project_root) / SCRATCH_DIR_NAME
    happy_dir = scratch / "happy"
    happy_dir.mkdir(parents=True, exist_ok=True)
    (happy_dir / "a.png").write_bytes(b"\x89PNG-check")
    try:
        core = EmojiCore(folder_path=scratch, path_mapping=dict(mapping))
        emoji_local = (happy_dir / "a.png").resolve().as_posix()
        emoji_expected = f"file://{FilePathConfig.apply_path_mapping(emoji_local, mapping)}"
        emoji_dict = {"happy": True}

        cq = core.parse_text_to_cqcode_with_emotion("[happy] 嗨", emoji_dict, reply_id=7)
        check(
            "CQ 字符串链路(主聊天表情)",
            emoji_expected in cq and "file://E:/" not in cq,
            cq,
        )

        segments = core.parse_text_with_emotion_tags("[happy] 嗨", emoji_dict)
        files = image_files(segments)
        check("结构化段链路", files == [emoji_expected], str(files))

        message = GroupMessage(group_id=1)
        core.parse_text_with_emotion_tags_return_construction("[happy] 嗨", emoji_dict, message)
        files = image_files(message.data)
        check("GroupMessage 构造链路", files == [emoji_expected], str(files))

        segments = core.parse_text_with_emotion_tags_separator("[happy] 嗨", emoji_dict, separator="\n")
        files = image_files(segments)
        check("separator 构造链路", files == [emoji_expected], str(files))

        check(
            "初始化用本地路径扫描索引",
            core.emoji_file_dict == {"happy": ["a.png"]},
            str(core.emoji_file_dict),
        )
        expected_dir = FilePathConfig.apply_path_mapping(str(scratch.resolve()), dict(mapping))
        check(
            "self.file 初始化时即存映射后路径",
            core.file.as_posix() == expected_dir,
            core.file.as_posix(),
        )
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    # ---------- 3. send.py 媒体 API 拼接 ----------
    print("\n[3] onebot/send.py 媒体 API")
    stub = StubWSConnection()
    client = OneBotSendClient(
        connection_type="WebSocket_client",
        ws_connection=stub,
        file_paths=file_paths,
    )
    await client.send_group_pictures(10086, sample_local, local_Path_type=True)
    await client.send_group_audio(10086, sample_local, local_Path_type=True)
    await client.send_group_file(10086, sample_local, local_Path_type=True)
    await client.send_personal_file(10000, sample_local, local_Path_type=True)
    await client.send_group_pictures(10086, "https://a.com/x.png", local_Path_type=True)

    picture_file = stub.sent[0]["params"]["message"][0]["data"]["file"]
    check("send_group_pictures 映射", picture_file == f"file://{sample_remote}", picture_file)
    audio_file = stub.sent[1]["params"]["message"][0]["data"]["file"]
    check("send_group_audio 映射", audio_file == f"file://{sample_remote}", audio_file)
    group_file = stub.sent[2]["params"]["message"][0]["data"]["file"]
    check("send_group_file 映射", group_file == f"file://{sample_remote}", group_file)
    personal_file = stub.sent[3]["params"]["message"][0]["data"]["file"]
    check("send_personal_file 映射", personal_file == f"file://{sample_remote}", personal_file)
    http_file = stub.sent[4]["params"]["message"][0]["data"]["file"]
    check("http URL 不受影响", http_file == "https://a.com/x.png", http_file)

    # ---------- 4. 关键词回复图片前缀 ----------
    print("\n[4] 关键词回复 url_prefix")
    url_prefix = f"file://{file_paths.map_to_remote(file_paths.img.as_posix())}"
    expected_prefix = f"file://{FilePathConfig.apply_path_mapping(file_paths.img.as_posix(), mapping)}"
    check("url_prefix 已映射", url_prefix == expected_prefix and "file://E:/" not in url_prefix, url_prefix)

    # ---------- 5. 本地读取不受影响(顾虑点回归) ----------
    print("\n[5] 本地读取回归")
    scratch = Path(file_paths.project_root) / SCRATCH_DIR_NAME
    scratch.mkdir(parents=True, exist_ok=True)
    local_file = scratch / "local_read_check.bin"
    local_file.write_bytes(b"local-bytes")
    try:
        local_posix = local_file.resolve().as_posix()
        check(
            "该路径确实在映射范围内(对照组)",
            file_paths.map_to_remote(local_posix).startswith(remote_prefix),
            file_paths.map_to_remote(local_posix),
        )
        name, data = await resolve_file_to_bytes(f"file://{local_posix}", "fallback.bin")
        check(
            "resolve_file_to_bytes 仍读本地路径",
            data == b"local-bytes" and name == "local_read_check.bin",
            f"name={name}",
        )
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    # ---------- 6. WSL 挂载信息 ----------
    print()
    check_wsl_mount(remote_prefix)

    print()
    if FAILURES:
        print(f"共 {len(FAILURES)} 项未通过: {FAILURES}")
        return 1
    print("全部检测通过 ✅  重启 bot 后在群里触发一次带表情包的回复即可做最终验证")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
