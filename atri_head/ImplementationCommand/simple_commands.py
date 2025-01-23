from ..Basics import *
import random
# import hashlib


async def test(user_input,qq_TestGroup,data,basics:Basics):
    """测试参数等"""
    [argument_1, argument_2] = basics.Command.processingParameter(user_input)

    message = "'-'开头参数:"+', '.join(argument_1)+"\n其他参数:"+', '.join(argument_2)
    await basics.QQ_send_message.send_group_message(qq_TestGroup,"ATRI接收到的参数有:\n"+message+"\n要exec语句为:"+argument_2[0])

    exec(argument_2[0])

    return "ok"

async def help(user_input,qq_TestGroup,data,basics:Basics):
    """帮助"""
    message ='''我有什么可以帮助你的吗?😀\n@我,后面接消息,我可以回答你的问题,或者与你聊天,或者为你提供一些帮助(聊天消息中不能出现/)🤔\n
发送/kill,我可以清除我的记忆,重新开始对话😰\n           
发送/fortune,我可以为你生成一个运势,并为你提供一些祝福的话😊\n
发送/img,我可以发送一张随机图片😉,可指定的格式为png,jpg,gif\n
发送/Permissions,我可以告诉你自己的权限😉\n
发送/说话，后面再加上你想要说的话，我可以帮你念出来😊目前支持中英日混合\n
发送/help,我可以显示这个帮助信息😘'''
    await basics.QQ_send_message.send_group_message(qq_TestGroup,message)
    await basics.QQ_send_message.send_group_pictures(qq_TestGroup,default = True)
    return "ok"

async def kill(user_input,qq_TestGroup,data,basics:Basics):
    """清除记忆"""
    if len(basics.AI_interaction.chat.messages) > 1:
        basics.AI_interaction.chat.reset_chat()
        await basics.QQ_send_message.send_group_message(qq_TestGroup,"ATRI的记忆已经被清除,重新开始对话吧!😊")
        return "ok"
    else:
        await basics.QQ_send_message.send_group_message(qq_TestGroup,"Type Error:\n ATRI已经没有记忆了,所以当然什么也没有发生!😓")
        return "no"


async def Random_fortune(user_input,qq_TestGroup,data,basics:Basics):
    """运势"""
    fortunes = ["大吉", "吉", "吉", "中吉", "中吉", "中吉", "小吉", "小吉", "小吉", "小吉","凶", "凶", "大凶"]
    fortune = random.choice(fortunes)
    content = f"你今天的运势是: {fortune}"
    await basics.QQ_send_message.send_group_message(qq_TestGroup,content)
    return "ok"

async def permissions_my(user_input,qq_TestGroup,data,basics:Basics):
    """查看自己的权限"""
    message = "你现在的权限等级是: " + basics.Command.my_permissions(data['user_id'])
    await basics.QQ_send_message.send_group_message(qq_TestGroup,message)
    return True

async def random_img(user_input,qq_TestGroup,data,basics:Basics):
    """随机图片,可指定的格式为png,jpg,gif"""
    argument= basics.Command.processingParameter(user_input)

    img_lest = {
        "png":796,
        "jpg":4005,
        "gif":3342,
        }
    
    if argument[0] == [] and argument[1] == []:

        random = basics.Chance.random_Radius(1,8143)

        if random <= 796:
            fiormat = "png"
        elif random <= 4801:
            fiormat = "jpg"
            random = random - 796
        else:
            fiormat = "gif"
            random = random - 4801

    elif argument[0][0] in img_lest:

        fiormat = argument[0][0]
        
        random = basics.Chance.random_Radius(1, img_lest[fiormat])

    else:
        raise Exception("图片格式错误!")

    url = f"E:/手机数据/cellphone_img ({random}).{fiormat}"

    await basics.QQ_send_message.send_group_pictures(qq_TestGroup,url)

    return "ok"

async def toggleModel(user_input,qq_TestGroup,data,basics:Basics):
    """切换模型人物,none无人物"""
    argument = basics.Command.processingParameter(user_input)
    basics.Command.verifyParameter(
        argument,parameter_quantity_max_1=0, parameter_quantity_min_1=0, 
        parameter_quantity_max_2=1, parameter_quantity_min_2=1
    )
    playRole = argument[1][0]

    if playRole in basics.AI_interaction.chat.playRole_list:
        basics.AI_interaction.chat.Default_playRole = basics.AI_interaction.chat.playRole_list[playRole]
        basics.AI_interaction.chat.reset_chat()
    else:
        raise Exception("没有这个角色")

    await basics.QQ_send_message.send_group_message(qq_TestGroup,f"已切换为人物:{playRole}")

    return "ok"

async def audio(user_input,qq_TestGroup,data,basics:Basics):
    """合成指定音频"""
    argument= basics.Command.processingParameter(user_input)
    basics.Command.verifyParameter(
        argument,
        parameter_quantity_max_1=0, parameter_quantity_min_1=0, 
        parameter_quantity_max_2=100, parameter_quantity_min_2=1
        )
    
    text = ' '.join(argument[1])
    url = basics.AI_interaction.speech_synthesis(text)

    await basics.QQ_send_message.send_group_audio(qq_TestGroup,url_audio=url)
    return "ok"

# async def encryptedMessage(user_input,qq_TestGroup,data,basics:Basics):
#     """MD5加密消息"""
#     argument = basics.Command.processingParameter(user_input)
#     basics.Command.verifyParameter(argument,parameter_quantity_max_1=0, parameter_quantity_min_1=0, parameter_quantity_max_2=1, parameter_quantity_min_2=1)
#     text = argument[1][0].strip().replace("\n", "").encode()

#     myMd5 = hashlib.md5()
#     myMd5.update(text)
#     myMd5_Digest = myMd5.hexdigest()

#     await basics.QQ_send_message.send_group_message(qq_TestGroup,f"MD5加密后的消息为:{myMd5_Digest}")

async def sing(user_input,qq_TestGroup,data,basics:Basics):
    """唱歌"""
    sing_list ={
        "インドア系ならトラックメイカ":"室内系_TrackMaker.mp3",
        "我的悲伤是水做的":"我的悲伤是水做的.mp4",
        "Eastof Eden":"EastofEden.mp4",
        "running up that hill":"runningupthathill.mp4",
        "千本桜":"千本桜.mp4",
        "但（电棍）":"但.mp3",
        "呐呐呐":"呐呐呐.mp4",
        "打上花火":"打上花火.mp4",
        "要来段bassline吗？笑":"要来段bassline吗？笑.mp3",
        "自伤无色":"自伤无色.mp4",
        "群星闪烁的夜晚":"群星闪烁的夜晚.mp4",
        "月光奏鸣曲电音版":"月光奏鸣曲（电音版）.mp4",
        "不眠之夜":"ATRI_不眠之夜.mp4",
        "chen不眠之夜":"不眠之夜.mp4",
        "恋之歌":"恋之歌.mp4",
        "永远不会放弃你":"永远不会放弃你.mp4",
        "这么可爱真是抱歉":"这么可爱真是抱歉.mp4",
        "蓝书签之歌":"蓝书签之歌.mp4",
        "隐形的翅膀":"隐形的翅膀.mp3",
        "Don't be so serious":"别那么认真了.mp4",
        "一路生花":"一路生花.mp4",
        "Humble":"Humble.mp4",
        "春日影":"春日影.mp3",
        "Humble":"Humble.mp4",
        "Fairlane":"Fairlane.mp3",
        "Lo Fi":"Lo-Fi.mp4",
        "fly me to the moon":"flymetothemoon.mp4",
        "bite me":"bite_me.mp4",
        "More One Night":"MoreOneNight.mp3",
        "One Last Kiss":"One_Last_Kiss.mp3",
        "ROVE":"ROVE.mp3",
        "小小恋歌":"小小恋歌.mp3",
        "恭喜发财":"恭喜发财.mp3",
        "喀秋莎":"喀秋莎.mp3",
        "晚安喵":"晚安喵.mp3",
        "室内系_TrackMaker":"室内系_TrackMaker.mp3",
        "HandClap":"HandClap.mp3",
        "Not_Angry":"Not_Angry.mp3",
        "bury_the_light":"bury_the_light.mp3",
        "恋爱循环":"恋爱循环.mp3",
        "恭喜你苏卡不列":"恭喜你苏卡不列.mp3",
        "Mystic_Light_Quest":"Mystic_Light_Quest.mp3",
        "520AM":"520AM.mp3",
        "stay":"stay.mp3",
        "晴天":"晴天.mp3",
        "Dear_Moments":"Dear_Moments.wav",
        "亲爱的你":"亲爱的你.mp3",
        "ツバサ":"ツバサ.mp3",
        "我爱你上海蟹":"我爱你上海蟹.mp3",
        "I_really":"I_really.mp3",
    }

    argument= basics.Command.processingParameter(user_input)
    basics.Command.verifyParameter(
        argument,
        parameter_quantity_max_1=1, parameter_quantity_min_1=0, 
        parameter_quantity_max_2=10, parameter_quantity_min_2=1
        )

    name = ' '.join(argument[1])

    if name in sing_list:
        if argument[0] != [] and argument[0][0] == "d":
            await basics.QQ_send_message.send_group_file(qq_TestGroup,url_file = "E:/程序文件/python/ATRI/document/audio/sing/"+sing_list[name])
        else:
            await basics.QQ_send_message.send_group_audio(qq_TestGroup,"sing/"+sing_list[name],default=True)
    else:
        raise Exception("没有这个歌曲")
    return "ok"

