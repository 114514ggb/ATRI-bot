from collections import defaultdict
import json
import jieba


class inverted_index():
    index_path = "assets/index.json"
    def __init__(self,json_list:list):
        self.json_list = json_list # json文件列表,越重要的，要写在后面。因为有重复的会覆盖。

        self.documents  = {}
        self.index = {}
        self.title_index = {}
        self.update_all_entry()

    def update_all_entry(self):
        """完全重新更新/重新创建数据索引"""
        self.index = {}
        title_id = text_id = 0

        for key, entries in self.documents.items():

            key_id = str(title_id) # 标题
            text_id = 0
            self.title_index[key_id] = key
            self.add_to_index(key_id, key)

            for entry in entries:
                key_id = f"{title_id}_{text_id}"# 内容块
                self.add_to_index(key_id, entry)
                text_id += 1
            title_id += 1

    def load_index(self):
        """载入索引"""
        with open(self.index_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.index = data['index']
            self.title_index = data['title_index']

    def save_index(self):
        """保存当前索引"""
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump({'index':self.index, 'title_index':self.title_index}, f, ensure_ascii=False, indent=4)

    def load_data(self):
        """载入数据"""
        for json_path in self.json_list:
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    self.documents.update(json.load(f))
            except FileNotFoundError:
                print(f"警告：文件 {json_path} 不存在")

    def save_data(self):
        """保存当前数据"""
        # for my_json in self.json_list:
        with open("assets/library.json", "w", encoding="utf-8") as f:
            json.dump(self.documents, f, ensure_ascii=False, indent=4)

    def add_entry(self, key: str, entry: str):
        """添加一个条目,更新数据和索引"""
        if key in self.documents:
            self.documents[key].append(entry)
            index_id = len(self.documents[key])-1
            title_id = self.find_key_by_value(self.title_index, key)[0]
            # print(f"添加条目：{entry} 到 {key}，索引ID为 {title_id}_{index_id}")
            self.add_to_index(f"{title_id}_{index_id}", entry)
        else:
            self.documents[key] = [entry]
            max_key = str(max(map(int, self.title_index.keys()))+1)
            self.title_index[max_key] = key
            self.add_to_index(max_key, key)
            self.add_to_index(f"{max_key}_0", entry)
    
    def find_key_by_value(self,dictionary, target_value):
        """在字典中查找具有特定值的键"""
        found_keys = [key for key, value in dictionary.items() if value == target_value]
        return found_keys if found_keys else None

    def add_to_index(self, key: str, entry: str):
        """添加一个条目到索引"""
        # 格式化条目={ 
        #     "关键词1": {
        #         "key1":"权重int",
        #         "key2":"权重int"
        #     },
        # }

        invalid_chars = {" ", ",", "，", "、", "。", ".", "!", "！", "《", "》", "<", ">"}

        for word in jieba.cut_for_search(entry.lower()):
            if word not in invalid_chars:
                if word not in self.index:
                    self.index[word] = {}
                if key not in self.index[word]:
                    self.index[word].update({key: len(word) + 1})
                else:
                    self.index[word][key] += 1

    def remove_entry(self,):
        """删除一个条目，更新数据和索引"""
        pass

    def search(self, query:str, top_n: int = 5):
        """搜索"""
        #{"包含关键词的标题1": {"id_list":["id1","id2"], "weight":"当前权重和"}}
        data_index = defaultdict(lambda: {"id_list": [], "weight": 0})

        for word in jieba.cut_for_search(query.lower()):
            if word not in self.index:
                continue

            for doc_id,weight in self.index[word].items():
                parts = doc_id.split("_")
                title_key = self.title_index[parts[0]]

                entry = data_index[title_key]
                entry['weight'] += weight

                if len(parts) > 1:
                    entry['id_list'].append(int(parts[1]))

        sorted_results = sorted(
            data_index.items(),
            key=lambda x: x[1]['weight'],
            reverse=True
        )
        
        if top_n is not None:
            sorted_results = sorted_results[:top_n]

        data = {}
        for title, entry in sorted_results:
            data_text = []
            for id in entry['id_list']:
                data_text.append(self.documents[title][id])
            data[title] = data_text

        if not data:
            return "没有找到相关结果。"
        else:
            return data

