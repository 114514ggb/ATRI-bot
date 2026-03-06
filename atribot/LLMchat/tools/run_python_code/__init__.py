from atribot.core.cache.management_chat_example import ChatManager
from atribot.core.network_connections.qq_send_message import QQAPIClient
from atribot.core.service_container import container
from atribot.core.type.chat_message_type import File, FileMessageSegment, GroupMessage
from atribot.LLMchat.sandbox.sandbox_base import ExecutionResult
from atribot.LLMchat.tools.run_python_code.run_code import run_python_code_with_segments

send_message:QQAPIClient = container.get("SendMessage")
chat_manager: ChatManager = container.get("ChatManager")

tool_json = {
    "name": "run_python_code",
    "description": "在 Docker 沙盒中执行 Python 代码，可传入输入文件并返回执行结果与新生成文件。可用库：numpy, pandas, matplotlib, seaborn, pillow, opencv-python-headless。图表如需显示中文，linux 系统中有安装 fonts-wqy-zenhei 字体,环境中还有ffmpeg",
    "properties": {
        "group_id": {
            "type": "number",
            "description": "所在的当前群号",
        },
        "code": {
            "type": "string",
            "description": "The Python code to execute"
        },
        "files": {
            "type": "array",
            "description": "输入你在上下文中看到的文件名称列表，会自动把对应文件名的文件放在脚本同级目录",
            "items": {
                "type": "string"
            }
        }
    }
}

async def main(code:str, group_id:int, files:list[str] | None = None):
    
    file_segments = []
    
    if files:
        remaining_files = set(files)

        for message in (await chat_manager.get_group_context(group_id)).messages:
            for segment in message.segments:
                if not isinstance(segment, FileMessageSegment):
                    continue

                if segment.file_name in remaining_files:
                    file_segments.append(segment)
                    remaining_files.remove(segment.file_name)

                    if not remaining_files:
                        break

            if not remaining_files:
                break
    
    execution_result: ExecutionResult = await run_python_code_with_segments(
        code = code,
        file_segments = file_segments,
    )
    
    await send_message.send_group_merge_text(
        group_id = group_id,
        message = code,
        source = "执行的代码"
    )
    
    if execution_result.files:
        file = execution_result.files[0]
        filename = file.path 
        
        if filename.split('.')[-1].lower() if '.' in filename else '' in {'png', 'jpg', 'jpeg', 'gif'}:#不需要太严格的检查这样应该够了吧
            await send_message.send_group_pictures(
                group_id = group_id,
                url_img = "base64://"+file.to_base64(),
                local_Path_type = False
            )
        else:
            await send_message.send_group(
                GroupMessage(group_id=group_id).add_file(
                    File.from_base64(file.to_base64()),
                    file_name = file.path
                )
            )
        return f"代码执行结果是:{execution_result.text}\n并且已经打包发送代码生成文件:{filename}"
    
    return f"代码执行结果是:{execution_result.text}"