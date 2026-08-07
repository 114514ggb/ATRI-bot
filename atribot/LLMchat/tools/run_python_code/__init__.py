from atribot.core.atri_config import atriConfig
from atribot.core.cache.management_chat_example import ChatManager
from atribot.core.service_container import container
from atribot.core.type.bot_types import atriMessageEvent
from atribot.core.type.chat_message_types import FileMessageSegment
from atribot.LLMchat.sandbox.sandbox_base import ExecutionResult
from atribot.LLMchat.tools.run_python_code.run_code import run_python_code_with_segments

chat_manager: ChatManager = container.get("ChatManager")
config:atriConfig = container.get("config")

_MAX_OUTPUT_CHARS = 3000

tool_json = {
    "name": "run_python_code",
    "description": (
        "在沙盒中执行Python代码,可传入输入文件并返回执行结果与新生成文件"
        "可用库:numpy,pandas,matplotlib,seaborn,pillow,opencv-python-headless"
        "图表如需显示中文,linux安装了fonts-wqy-zenhei字体,环境还有ffmpeg"
        "每个群组持久化工作区可通过os.environ访问:"
        "GROUP_WORKSPACE=本群持久目录, SHARED_DIR=共享目录"
        "生成文件直接写在脚本同级目录大小不超过 20MB 就会自动发送,跨次调用保留文件写入GROUP_WORKSPACE"
    ),
    "properties": {
        "code": {
            "type": "string",
            "description": "The Python code to execute"
        },
        "files": {
            "type": "array",
            "description": "你在上下文中看到的要临时使用文件名称列表，会自动把对应文件名的文件放在脚本同级目录,脚本运行完后删除",
            "items": {
                "type": "string"
            }
        }
    }
}

async def main(code: str, message_data: atriMessageEvent, files: list[str] | None = None) -> str:

    file_segments = []
    group_id = message_data.group_id

    if files:
        remaining_files = set(files)

        for message in list((await chat_manager.get_group_context(group_id)).messages):
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
        group_id = group_id,
        file_segments = file_segments,
    )
    
    output_text = execution_result.text
    if len(output_text) > _MAX_OUTPUT_CHARS:
        output_text = f"[截取末尾{_MAX_OUTPUT_CHARS}字符]\n...{output_text[-_MAX_OUTPUT_CHARS:]}"

    await message_data.send_client.send_group_merge_text(
        group_id = group_id,
        message = f"{code}\n\n执行的输出:\n{output_text}",
        source = "执行的代码"
    )

    if execution_result.files:
        file = execution_result.files[0]
        filename = file.path
        
        if (filename.rsplit('.', 1)[-1].lower() if '.' in filename else '') in {'png', 'jpg', 'jpeg', 'gif'}:
            await message_data.send_client.send_group_pictures(
                group_id = group_id,
                url_img = "base64://" + file.to_base64(),
                local_Path_type = False
            )
            return f"代码执行结果是:{output_text}\n并且已经发送代码生成图片:{filename}"
        else:
            await message_data.send_client.send_group_file(
                group_id = group_id,
                url_file = "base64://" + file.to_base64(),
                name = file.path,
                local_Path_type = False,
            )

            return f"代码执行结果是:{output_text}\n并且已经打包发送代码生成文件:{filename}"
    
    return f"代码执行结果是:{output_text}"