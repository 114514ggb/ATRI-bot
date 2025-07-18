from atri_head.Basics import Basics,Command_information


basics = Basics()


async def voice(argument,group_ID,data):
    """合成指定音频"""
    emotion = "高兴"
    
    if argument[0]:
        if argument[0][0] == "e":
            if text := ' '.join(argument[1][1:]):
                emotion = argument[1][0]
            else:
                raise ValueError("文本为空")
        else:
            raise ValueError(f"不支持的操作符:{argument[0][0]}")
    else:
        text = ' '.join(argument[1])
        
    url = await basics.AI_interaction.get_tts_path(
            text,
            emotion
        )
    await basics.QQ_send_message.send_group_audio(group_ID,url_audio=url,default=True)
    return "ok"


command_main = Command_information(
    name="voice",
    aliases=["说话", "say"],
    handler=voice,
    description="合成指定文字的音频，支持中文,英文,日语,韩文.\n传入-e参数可以指定感情,支持高兴,机械,平静\n默认高兴",
    parameter=[[0, 1], [1, 100]]
)