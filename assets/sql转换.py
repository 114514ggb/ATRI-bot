import re

def convert_mysql_to_pgsql(input_file, output_file):
    """
    转换MySQL SQL文件到PostgreSQL格式
    """
    # 定义转换规则列表 - 全部使用正则表达式
    rules = [
        # (模式, 替换内容)
        (r"\\'", "''"),           # 单引号转义: \' -> ''
        (r'\\`', '"'),            # 反引号转义: \` -> "
        (r'\\\\n', '\n'),         # 换行符转义: \\n -> \n
        (r'\\\\t', '\t'),         # 制表符转义: \\t -> \t
        (r'\\\\r', '\r'),         # 回车符转义: \\r -> \r
        (r'\\Z', ''),             # 移除 \Z
        (r'\\:', ':'),            # 冒号转义: \: -> :
        (r'\\,', ','),            # 逗号转义: \, -> ,
        (r'\\=', '='),            # 等号转义: \= -> =
        (r'\\@', '@'),            # @符号转义: \@ -> @
        (r"\\'", "''"),           # 单引号转义
    ]
    
    try:
        # 读取输入文件
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 应用所有转换规则
        for pattern, replacement in rules:
            content = re.sub(pattern, replacement, content)

        # 写入输出文件
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"转换完成！输出文件: {output_file}")
        return True
        
    except Exception as e:
        print(f"转换失败: {e}")
        return False


if __name__ == "__main__":
    
    # input_file = "/home/atri/text.txt"
    # input_file = "/home/atri/atri_db.sql"
    input_file = "/home/atri/atri.sql"
    output_file = "/home/atri/atri_1.sql"
    
    convert_mysql_to_pgsql(input_file, output_file)