import math

tool_json = {
    "name": "python_calculator",
    "description": "执行数学表达式计算的工具，支持四则运算/幂运算/三角函数等基础运算,在你被问道数学计算问题时使用，你不使用的话就无法正确回答数学运算",
    "properties": {
        "formula": {
            "type": "string",
            "description": "Python可解析的数学表达式（示例：2*(3+5)、math.sqrt(4)、pow(2,3)），须包含完整运算符且符合Python语法规范,默认可以使用math库",
        }
    }
}

async def main(formula):
    return {"python_calculator":f"{formula} == {eval(formula)}"}



