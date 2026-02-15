import os
from typing import List

from atribot.common import common


class song:
    def __init__(self, base_path: str = "document/audio/sing/"):
        """
        初始化 song 类
        
        Args:
            base_path: 歌曲文件存储的基础路径
        """
        self.base_path = base_path
        self.song_list = []  # 存储歌曲文件名列表
        self.refresh()  # 初始化时自动刷新一次
        
    def refresh(self) -> None:
        """
        刷新歌单，重新读取基础路径下的歌曲文件
        """
        self.song_list = []
        if not os.path.exists(self.base_path):
            return
            
        for file in os.listdir(self.base_path):
            file_path = os.path.join(self.base_path, file)
            if os.path.isfile(file_path):
                if file.lower().endswith(('.mp3', '.wav', '.flac', '.mp4', '.ogg')):
                    self.song_list.append(file)
    
    def _remove_extension(self, filename: str) -> str:
        """
        移除文件名的扩展名
        
        Args:
            filename: 文件名
            
        Returns:
            不带扩展名的文件名
        """
        return os.path.splitext(filename)[0]
    
    def get_song_path(self, song_name: str) -> str:
        """
        根据歌曲名获取完整文件路径或返回最相似的几个歌曲名
        
        Args:
            song_name: 歌曲名称
            
        Returns:
            如果找到完全匹配的文件，返回完整路径；
            否则返回空字符串
        """
        song_name_without_ext = self._remove_extension(song_name)
        
        for song in self.song_list:
            song_without_ext = self._remove_extension(song)
            if song_without_ext == song_name_without_ext:
                return os.path.join(self.base_path, song)
        
        return ""
    
    def find_similar_songs(self, song_name: str, top_n: int = 5) -> List[str]:
        """
        查找与输入歌曲名最相似的前几个歌曲（无视后缀）
        
        Args:
            song_name: 要匹配的歌曲名（不带后缀）
            top_n: 返回最相似歌曲的数量
            
        Returns:
            最相似的歌曲名列表
        """
        similarities = []
        for song in self.song_list:
            song_without_ext = self._remove_extension(song)
            similarity = common.jaro_winkler_similarity(song_name, song_without_ext)
            similarities.append((song, similarity))
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return [song[0] for song in similarities[:top_n]]
    
    def get_full_playlist(self) -> str:
        """
        获取完整歌单的花里胡哨格式化字符串
        
        Returns:
            格式化的歌单字符串
        """
        if not self.song_list:
            return "🎵 歌单空空如也，快去添加歌曲吧！ 🎵"
        
        header = "✨" * 5 + " 🎶 花里胡哨歌单 🎶 " + "✨" * 5
        footer = "🎧" * 20
        
        song_lines = []
        for i, song in enumerate(self.song_list, 1):
            song_name = self._remove_extension(song)
            emoji = "🎵" if i % 3 == 0 else "🎤" if i % 3 == 1 else "🎼"
            song_line = f"{emoji} {i:02d}. {song_name} "
            song_lines.append(song_line)
        
        stats = f"\n📊 总共 {len(self.song_list)} 首歌曲 | 🕒 最近更新"
        
        return f"{header}\n" + "\n".join(song_lines) + f"\n{stats}\n{footer}"

    
        
