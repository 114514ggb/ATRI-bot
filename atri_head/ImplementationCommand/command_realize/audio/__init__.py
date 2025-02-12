from atri_head.Basics import Basics,Command_information


basics = Basics()


async def voice(argument,qq_TestGroup,data):
    """合成指定音频"""
    
    text = ' '.join(argument[1])
    url = basics.AI_interaction.speech_synthesis(text)

    await basics.QQ_send_message.send_group_audio(qq_TestGroup,url_audio=url)
    return "ok"


command_main = Command_information(
    name="voice",
    aliases=["说话", "voice"],
    handler=voice,
    description="合成指定文字的音频，支持中英日文.",
    parameter=[[0, 0], [1, 1]]
)