import subprocess



tool_json = {
    "name": "get_python_code_result",
    "description": "执行Python代码并返回标准输出结果，适用于数学计算、数据处理及算法验证等场景。请确保代码包含完整的执行逻辑并通过print()输出结果。",
    "properties": {
        "code": {
            "type": "string",
            "description": "需要执行的完整Python代码，必须包含print语句输出目标结果（如：print(1+1)）"
        }
    }
}

code_url = "document\\code.py"
async def get_python_code_result(code):
    """获取python代码运行结果"""
    with open(code_url, "w", encoding='utf-8') as f:
        f.write(code)

    result = subprocess.run(["python", code_url], capture_output=True, text=True)

    if result.returncode != 0:
        return {"error": result.stderr}
    else:
        return {"command_line_interface":result.stdout}
    
async def main(code: str):
    return await get_python_code_result(code)