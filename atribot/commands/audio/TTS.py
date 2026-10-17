from logging import Logger
from pathlib import Path
from typing import Any, Dict

import aiohttp

from atribot.core.atri_config import atriConfig
from atribot.core.service_container import container

# GPT-SoVITS 接口默认地址，可用 config.tts.api_url 覆盖
DEFAULT_TTS_API_URL = "http://127.0.0.1:9880"

# 参考音频默认目录名（相对 config.file_path.audio，即 document/audio）
DEFAULT_REFERENCE_DIR = "tts_reference"

# 内置默认情感配置：{情感名: (参考音频文件名, 参考文本)}
DEFAULT_EMOTIONS: Dict[str, tuple[str, str]] = {
    "高兴": ("ああ、なんて高性能なんでしょ、私は.mp3", "ああ、なんて高性能なんでしょ、私は"),
    "机械": ("あ，私です夏生さんのために動く理由が必要なんですか.mp3", "あ，私です夏生さんのために動く理由が必要なんですか"),
    "平静": ("夏生さんが望むのでしたら.mp3", "夏生さんが望むのでしたら"),
}


class TTSService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.audio_count = 1
            self.log: Logger = container.get_by_type(Logger).getChild("TTS")

            config: atriConfig = container.get("config")
            self.api_url, self.emotion_list = self._load_tts_config(config)

            self.base_output_path = config.file_path.audio
            self.relative_output_prefix = Path("TTS_output/output")
            self._initialized = True

    def _load_tts_config(self, config: atriConfig) -> tuple[str, Dict[str, Dict[str, str]]]:
        """读取 TTS 配置

        优先使用 `config.tts`（供应商无关，跨平台友好的绝对路径）：

            {
              "tts": {
                "api_url": "http://127.0.0.1:9880",
                "emotions": {
                  "高兴": {"refer_wav_path": "D:/tts/ref.mp3", "prompt_text": "...", "prompt_language": "ja"}
                }
              }
            }

        未配置时回退到内置默认情感，并把参考音频解析到
        `document/audio/tts_reference/`（不再硬编码 `/home/atri/...`）。

        Returns:
            tuple[str, Dict[str, Dict[str, str]]]: (接口地址, 情感配置字典)
        """
        api_url = DEFAULT_TTS_API_URL
        emotion_list: Dict[str, Dict[str, str]] = {}

        raw = None
        try:
            raw = config.tts
        except AttributeError:
            raw = None

        if raw:
            configured_url = raw.get("api_url") if hasattr(raw, "get") else None
            if configured_url:
                api_url = str(configured_url)
            for name, item in (raw.get("emotions") or {}).items():
                if not isinstance(item, dict) or not item.get("refer_wav_path"):
                    continue
                emotion_list[str(name)] = {
                    "refer_wav_path": str(item["refer_wav_path"]),
                    "prompt_text": str(item.get("prompt_text") or ""),
                    "prompt_language": str(item.get("prompt_language") or "auto"),
                }

        if not emotion_list:
            reference_dir = Path(config.file_path.audio) / DEFAULT_REFERENCE_DIR
            emotion_list = {
                name: {
                    "refer_wav_path": str(reference_dir / filename),
                    "prompt_text": prompt_text,
                    "prompt_language": "ja",
                }
                for name, (filename, prompt_text) in DEFAULT_EMOTIONS.items()
            }
            self.log.debug(
                "未配置 config.tts.emotions，使用内置默认情感，参考音频目录: %s", reference_dir
            )

        return api_url, emotion_list

    async def get_tts_path(self, text: str, emotion: str = "高兴", speed: float = 0.9) -> Path:
        """TTS文本合成语音

        Args:
            text (str): 需要合成的文本,支持中日英韩，但是目前不要输入韩文
            emotion (str): 音频的情感,枚举值：高兴,机械,平静
            speed (float | str): 语速,取值范围0.6~1.65,默认0.9;
                兼容字符串数字(如 LLM 输出的 "1.0"),非法值抛出 ValueError

        Raises:
            ValueError: 抛出包含错误信息的json

        Returns:
            Path: 返回wav文件的绝对路径
        """
        # raise ValueError("语音因为资源分配问题暂时被关了,不要再尝试使用")

        self._validate_parameters(text, emotion, speed)
        self._check_reference_audio(emotion)
        
        payload = self._build_payload(text, emotion, speed)
        
        return await self._send_tts_request(payload)

    def _check_reference_audio(self, emotion: str) -> None:
        """检查参考音频是否存在，缺失时给出可操作的提示

        缺少提示时用户只会看到 GPT-SoVITS 侧的报错，难以定位是路径问题。
        注意：远端 TTS 服务与 Bot 不在同一文件系统时（例如 Bot 在容器里、
        GPT-SoVITS 在宿主机），此处只做提醒，不阻断流程。

        Args:
            emotion (str): 情感名称
        """
        refer_wav_path = self.emotion_list[emotion].get("refer_wav_path", "")
        if not refer_wav_path or not Path(refer_wav_path).exists():
            self.log.warning(
                "TTS 参考音频不存在: %s（情感: %s）。请在 assets/config.json 的 "
                "tts.emotions.%s.refer_wav_path 配置可访问的绝对路径，"
                "或把参考音频放到 document/audio/%s/ 下。",
                refer_wav_path or "<未配置>", emotion, emotion, DEFAULT_REFERENCE_DIR,
            )

    def _validate_parameters(self, text: str, emotion: str, speed: float) -> None:
        """验证输入参数"""
        if emotion not in self.emotion_list:
            supported = ", ".join(self.emotion_list)
            raise ValueError(f"不支持的情感: {emotion}（当前可选: {supported}）")
        
        if 0 < len(text) > 100:
            raise ValueError(f"输入字符应在1到100之间,当前有{len(text)}个")
        
        if not 0.6 <= speed <= 1.65:
            raise ValueError(f"语速必须在0.6到1.65之间,当前值: {speed}")

    def _build_payload(self, text: str, emotion: str, speed: float) -> Dict[str, Any]:
        """构建TTS请求的负载"""
        base_payload = {
            "text": text,
            "text_language": "auto",
            "top_k": 20,
            "top_p": 0.6,
            "temperature": 0.6,
            "speed": speed,
            # 额外参考音频直接取已解析的各情感参考路径，避免硬编码宿主机绝对路径
            "inp_refs": [item["refer_wav_path"] for item in self.emotion_list.values()],
        }
        
        return base_payload | self.emotion_list[emotion]

    async def _send_tts_request(self, payload: Dict[str, Any]) -> str:
        """发送TTS请求并处理响应"""
        try:
            async with aiohttp.ClientSession() as session:  
                async with session.post(self.api_url, json=payload) as response:
                    if response.status == 200:
                        audio_bytes = await response.read()
                        return await self._save_audio_file(audio_bytes)
                    else:
                        error_data = await response.json()
                        raise ValueError(f"TTS请求失败: {error_data}")
        except aiohttp.ClientError as e:
            raise ValueError(f"网络请求错误: {str(e)}")
        except Exception as e:
            raise ValueError(f"处理TTS请求时发生错误: {str(e)}")

    async def _save_audio_file(self, audio_bytes: bytes) -> Path:
        audio_full_path = self.base_output_path / self.relative_output_prefix / f"{self.audio_count}.wav"
        
        audio_full_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(audio_full_path, "wb") as f:
            f.write(audio_bytes)
        
        self._update_audio_count()
        
        return audio_full_path

    def _update_audio_count(self) -> None:
        """更新音频文件计数器"""
        if self.audio_count >= 10:
            self.audio_count = 1
        else:
            self.audio_count += 1

    def get_supported_emotions(self) -> list:
        """获取支持的情感列表"""
        return list(self.emotion_list.keys())

    def set_output_path(self, base_path: str, relative_prefix: str = None) -> None:
        """设置输出路径配置"""
        self.base_output_path = base_path
        if relative_prefix:
            self.relative_output_prefix = relative_prefix
