


tool_json = {
    "name": "time_trigger",
    "description": "定时唤醒你自己",
    "properties": {
        "group_id": {
            "type": "string",
            "description": "触发的群号",
        },
        "How_long_to_wait": {
            "type": "integer",
            "description": "等待多长时间后再触发",
        },
        "The_time_that_needs_to_be_waited": {
            "type": "string",
            "description": "需要等到触发的未来时间,格式要求:%Y-%m-%d %H:%M:%S",
        },
        "discourse": {
            "type": "string",
            "description": "送给你未来的话，描述要触发的情况",
        },
    }
}
