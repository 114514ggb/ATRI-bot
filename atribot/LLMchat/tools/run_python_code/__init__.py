from atribot.core.network_connections.qq_send_message import qq_send_message
from atribot.LLMchat.sandbox.docker_sandbox import DockerSandbox
from atribot.LLMchat.sandbox.sandbox_base import ExecutionResult
from atribot.core.service_container import container


sand_box:DockerSandbox = container.get("SandBox")
send_message:qq_send_message = container.get("SendMessage")

tool_json = {
    "name": "run_python_code",
    "description": "在一个沙箱环境中执行Python代码可用于科学计算和数据可视化。可用库：numpy, pandas, matplotlib, seaborn, pillow, opencv-python-headless。使用约束：1. 由于没有输入文件,数据需在代码中生成。2. 生成图表什么的必须生成文件3. 图表如需显示中文，linxu系统中有安装fonts-wqy-zenhei字体",
    "properties": {
        "group_id": {
            "type": "number",
            "description": "所在的当前群号",
        },
        "code": {
            "type": "string",
            "description": "The Python code to execute"
        }
    }
}

async def main(code:str, group_id:int):
    
    execution_result: ExecutionResult = await sand_box.run_python_code(
        code = code
    )
    
    await send_message.send_group_merge_text(
        group_id = group_id,
        message = code,
        source = "执行的代码"
    )
    
    if execution_result.files:
        file = execution_result.files[0]
        await send_message.send_group_file(
            group_id = group_id,
            name = file.path,
            url_file = "base64://"+file.to_base64(),
            local_Path_type = False
        )
        return f"代码执行结果是:{execution_result.text}\n已经打包发送生成文件{file.path}"
    
    return f"代码执行结果是:{execution_result.text}"