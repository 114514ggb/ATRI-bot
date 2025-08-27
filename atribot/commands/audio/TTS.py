import aiohttp
from typing import Dict, Any
from atribot.core.service_container import container


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
            self.api_url = "http://127.0.0.1:9880"
            self.emotion_list = {
                "高兴": {
                    "refer_wav_path": "E:/ffmpeg/ああ、なんて高性能なんでしょ、私は.mp3",
                    "prompt_text": "ああ、なんて高性能なんでしょ、私は",
                    "prompt_language": "ja"
                },
                "机械": {
                    "refer_wav_path": "E:/ffmpeg/あ，私です夏生さんのために動く理由が必要なんですか.mp3",
                    "prompt_text": "あ，私です夏生さんのために動く理由が必要なんですか",
                    "prompt_language": "ja"
                },            
                "平静": {
                    "refer_wav_path": "E:/ffmpeg/夏生さんが望むのでしたら.mp3",
                    "prompt_text": "夏生さんが望むのでしたら",
                    "prompt_language": "ja"
                }
            }
            self.base_output_path = container.get("config").file_path.item_path+"document/audio/"
            self.relative_output_prefix = "TTS_output/output"
            self._initialized = True

    async def get_tts_path(self, text: str, emotion: str = "高兴", speed: float = 1) -> str:
        """TTS文本合成语音
        
        Args:
            text (str): 需要合成的文本,支持中日英韩，但是目前不要输入韩文
            emotion (str): 音频的情感,枚举值：高兴,机械,平静
            speed (float): 语速，取值范围0.6~1.65,默认1
            
        Raises:
            ValueError: 抛出包含错误信息的json

        Returns:
            str: 返回wav文件的相对路径
        """
        # raise ValueError("语音因为资源分配问题暂时被关了,不要再尝试使用")
        
        self._validate_parameters(text, emotion, speed)
        
        payload = self._build_payload(text, emotion, speed)
        
        return await self._send_tts_request(payload)

    def _validate_parameters(self, text: str, emotion: str, speed: float) -> None:
        """验证输入参数"""
        if emotion not in self.emotion_list:
            raise ValueError(f"不支持的情感: {emotion}")
        
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
            "inp_refs": [
                "E:/ffmpeg/ああ、なんて高性能なんでしょ、私は.mp3",
                "E:/ffmpeg/あ，私です夏生さんのために動く理由が必要なんですか.mp3"
            ]
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

    async def _save_audio_file(self, audio_bytes: bytes) -> str:
        """保存音频文件并返回相对路径"""
        audio_relative_path = f"{self.relative_output_prefix}{self.audio_count}.wav"
        audio_full_path = f"{self.base_output_path}{audio_relative_path}"
        
        with open(audio_full_path, "wb") as f:
            f.write(audio_bytes)
        
        self._update_audio_count()
        
        return audio_relative_path

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
