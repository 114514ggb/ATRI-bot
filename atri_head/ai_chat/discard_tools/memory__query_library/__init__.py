# from atri_head.ai_chat.tools.memory__query_library.inverted_index import inverted_index


# tool_json = {
#     "name": "memory__query_library",
#     "description": "关键词记忆检索工具。当需要回忆特定名称、事件或细节时触发，返回结果若包含id可考虑调用memory__read_memory获取更多详情",
#     "properties": {
#         "word": {
#             "type": "string",
#             "description": "记忆检索的关键词或短语"
#         }
#     }
# }


# async def main(word: str):
#     return {"memory__query_library": memory__query_library(word)}


# def memory__query_library(word: str):
#     index = inverted_index(json_list=["assets/library.json"])
#     index.load_data()
#     index.load_index()

#     return str(index.search(word.lower()))



# if __name__ == "__main__":
#     index = inverted_index(json_list=["assets/library.json", "assets/memory.json"])
#     index.load_data()
#     index.update_all_entry()
#     # index.add_entry("1145","123456")
#     index.save_index()
#     index.save_data()
#     # index.search("1145")