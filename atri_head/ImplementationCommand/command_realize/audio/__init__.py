from atri_head.Basics import Basics,Command_information


basics = Basics()


async def voice(argument,group_ID,data):
    """合成指定音频"""
    await basics.QQ_send_message.send_group_message(group_ID,"新一代模型在训练，合成音频功能暂时关闭!")
    return
    text = ' '.join(argument[1])
    url = await basics.AI_interaction.speech_synthesis(text)

    await basics.QQ_send_message.send_group_audio(group_ID,url_audio=url)
    return "ok"


command_main = Command_information(
    name="voice",
    aliases=["说话", "say"],
    handler=voice,
    description="合成指定文字的音频，支持中英日文.",
    parameter=[[0, 0], [1, 100]]
)