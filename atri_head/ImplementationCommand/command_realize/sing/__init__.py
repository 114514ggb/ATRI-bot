from atri_head.Basics import Basics,Command_information
import os


class sing():

    folder_path = "document\\audio\\sing"
    """歌曲文件夹路径"""
    
    def __init__(self):
        self.basics = Basics()
        self.sing_list = self.load_song()
    
    def load_song(self):
        """加载歌曲"""
        files_dict = {}
        
        for filename in os.listdir(self.folder_path):
            name,_ = os.path.splitext(filename)
            files_dict[name] = filename

        return files_dict
            
        
    async def main(self,argument,qq_TestGroup,data):
        """发送对应歌曲"""
        name = ' '.join(argument[1])

        if name in self.sing_list:
            if argument[0] != [] and argument[0][0] == "d":
                await self.basics.QQ_send_message.send_group_file(qq_TestGroup,url_file = "E:/程序文件/python/ATRI/document/audio/sing/"+self.sing_list[name])
            else:
                await self.basics.QQ_send_message.send_group_audio(qq_TestGroup,"sing/"+self.sing_list[name],default=True)
        else:
            raise Exception("没有这个歌曲")
        return "ok"


my_sing = sing()

command_main = Command_information(
    name="sing",
    aliases=["唱歌", "sing"],
    handler=my_sing.main,
    description="输出歌单上有的歌曲,加入-d参数发送音频文件",
    authority_level=2, 
    parameter=[[0, 1], [1, 10]]
)