from atri_head.ai_chat.tools.memory__query_library.inverted_index import inverted_index


tool_json = {
    "name": "memory__query_library",
    "description": "获取你记忆中的相关内容的工具,通过一个词或一句话来查询相关内容,你想回忆一个名字或一个词一句话可以调用这个,如果返回的是ID建议你去查看那个人的完整信息",
    "properties": {
        "word": {
            "type": "string",
            "description": "你想查询的关键词语或是一句话。"
        }
    }
}


async def main(word: str):
    return {"memory__query_library": memory__query_library(word)}


def memory__query_library(word: str):
    index = inverted_index(json_list=["assets/library.json"])
    index.load_data()
    index.load_index()

    return str(index.search(word.lower()))



if __name__ == "__main__":
    index = inverted_index(json_list=["assets/library.json", "assets/memory.json"])
    index.load_data()
    index.update_all_entry()
    # index.add_entry("1145","123456")
    index.save_index()
    index.save_data()
    # index.search("1145")