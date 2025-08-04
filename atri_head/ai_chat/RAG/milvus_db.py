from pymilvus import MilvusClient

class milvus_Manager:
    
    def __init__(self, path:str="assets/ATRI_milvus.db"):
        self.client = MilvusClient(path)
    
    def create_initial_collections(self):
        """
        初始化创建Collections(类似数据库表)
        """

    def add_data(self):
        pass
    
    def inquire_data(self):
        pass