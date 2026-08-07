from logging import Logger
from typing import Optional

from atribot.common_utils.file.image_utils import url_to_image_jpeg
from atribot.core.service_container import container
from atribot.LLMchat.model_api.universal_async_llm_api import universal_ai_api


class MediaProcessor:
    """多模态媒体转文本处理

    将图片、音频、视频等非文本内容转换为文字，
    为不支持多模态输入的 LLM 提供预处理能力
    """

    def __init__(self) -> None:
        config = container.get("config")
        supplier = container.get("LLMSupplier")
        self.log: Logger = container.get_by_type(Logger).getChild("Media")

        # 图像识别
        try:
            self._image_api: Optional[universal_ai_api] = supplier.connections[
                config.model.detection_image.supplier
            ].connection_object
            self._image_model: Optional[str] = config.model.detection_image.model_name
        except Exception as e:
            self.log.error(f"MediaProcessor图像识别初始化失败: {e}")
            self._image_api = None
            self._image_model = None

        # 音频识别
        try:
            if detection_audio := config.model.detection_audio:
                self._audio_api: Optional[universal_ai_api] = supplier.connections[
                    detection_audio.supplier
                ].connection_object
                self._audio_model: Optional[str] = detection_audio.model_name
            else:
                self._audio_api = None
                self._audio_model = None
        except Exception as e:
            self.log.error(f"MediaProcessor音频识别初始化失败: {e}")
            self._audio_api = None
            self._audio_model = None

        # 视频识别
        try:
            if detection_video := config.model.detection_video:
                self._video_api: Optional[universal_ai_api] = supplier.connections[
                    detection_video.supplier
                ].connection_object
                self._video_model: Optional[str] = detection_video.model_name
            else:
                self._video_api = None
                self._video_model = None
        except Exception as e:
            self.log.error(f"MediaProcessor视频识别初始化失败: {e}")
            self._video_api = None
            self._video_model = None

    async def image_to_text(self, image_url: str) -> str:
        """将图片转换为文字描述。

        先本地下载并统一转码为 JPEG base64 再交由识别模型处理
        
        Args:
            image_url: 图片地址(http/https 或 base64://)

        Returns:
            模型生成的图片内容描述
        """
        if not self._image_api:
            return "图像识别失败"
        if not image_url:
            return "图片识别出现错误: 图片地址为空"
        try:
            convert_result = await url_to_image_jpeg(image_url)
            image_data = convert_result.data_uri
            response = await self._image_api.generate_text_lightweight(
                model=self._image_model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_data}},
                        {"type": "text", "text": "请详细描述你看到的东西，上面是什么、有什么、在什么地方，如果上面有文字也要详细说清楚，如果有什么自己的理解可以说出来，如果上面是什么你认识的可以介绍一下"}
                    ]
                }]
            )
            return response["choices"][0]["message"]["content"]
        except Exception as e:
            self.log.warning(f"图片识别失败 url={image_url}: {e}")
            return f"图片识别出现错误: {e}"

    async def audio_to_text(self, audio_url: str) -> str:
        """将音频转换为文字

        Args:
            audio_url: 音频地址

        Returns:
            语音识别或听觉理解的文字内容
        """
        if not self._audio_api:
            return "音频转文本失败,未配置"
        try:
            result = await self._audio_api.generate_text_lightweight(
                model=self._audio_model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "input_audio", "input_audio": {"url": audio_url}},
                        {"type": "text", "text": "请将音频内容转录为文字，并描述其中的语气、情绪或背景声音"}
                    ]
                }]
            )
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            return f"音频识别出现错误: {result if 'result' in locals() else e}"

    async def video_to_text(self, video_url: str) -> str:
        """将视频转换为文字描述（需配置 config.model.detection_video）

        Args:
            video_url: 视频地址

        Returns:
            视频内容的文字描述
        """
        if not self._video_api:
            return "视频转文本失败,未配置"
        try:
            result = await self._video_api.generate_text_lightweight(
                model=self._video_model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "video_url", "video_url": {"url": video_url}},
                        {"type": "text", "text": "请详细描述视频中的内容，包括画面、声音、人物行为和文字信息"}
                    ]
                }]
            )
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            return f"视频识别出现错误: {result if 'result' in locals() else e}"
