tool_json = {
    "name": "python_calculator",
    "description": "你想计算简单数学公式时非常有用",
    "properties": {
        "formula": {
            "type": "string",
            "description": "放入需要计算的数学公式，例如：1+1，2*3，3/4，2**3等,要是Python环境能直接计算出来的",
        }
    }
}

async def main(formula):
    return {"python_calculator":f"{formula} == {eval(formula)}"}



