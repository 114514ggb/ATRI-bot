from atri_head.Basics import Basics
import time

tool_json = {
    "name": "get_stranger_info",
    "description": "获取一个QQ账号的信息",
    "properties": {
        "qq_id": {
            "type": "string",
            "description": "qq_id,QQ号",
        }
    }
}


qq_send_message = Basics().QQ_send_message

async def main(qq_id):
    qq_data = await qq_send_message.get_stranger_info(qq_id)
    return {"get_stranger_info": parse_qq_profile(qq_data)}



def parse_qq_profile(json_data:dict)->dict:
    """解析QQ用户资料JSON数据，返回人类可读的格式

    Args:
        json_data (dict): 包含用户资料的JSON对象

    Returns:
        str: 字典形式的人类可读用户资料      
    """
    data = json_data.get('data', {})
    
    def format_timestamp(timestamp):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
    
    result = {
        "昵称": data.get("nickname", "未知"),
        "年龄": data.get("age", 0),
        "QQID": data.get("qid", "未知"),
        "账号等级": data.get("qqLevel", 0),
        "性别": data.get("sex", "未知"),
        "个性签名": data.get("long_nick", "暂无签名"),
        "注册时间": format_timestamp(data.get("reg_time", 0)),
        "是否会员": "是" if data.get("is_vip", False) else "否",
        "是否年费会员": "是" if data.get("is_years_vip", False) else "否",
        "会员等级": data.get("vip_level", 0),
        "备注": data.get("remark", "无备注"),
        "地区": f"{data.get('country', '')}{data.get('province', '')}{data.get('city', '')}",
        "邮箱": data.get("eMail", "未设置")
    }
    return result