from ...Basics import Basics

class example_plugin():
    """插件类示例,一般要继承这个类来写插件"""
    my_name = "acquiesce_plugin_name" #插件名称
    authority_level = 1
    """执行需求的权限等级,0为所有人,1为游客,2为管理员,3为root"""
    register_order = ["/plugin","/插件"]
    """注册的命令"""
    user_input = None
    qq_TestGroup = None
    data = None
    argument = None

    def __init__(self):
        self.basics = Basics()

    def store(self,user_input,qq_TestGroup,data):
        self.user_input = user_input
        self.qq_TestGroup = qq_TestGroup
        self.data = data
        self.argument = self.basics.Command.processingParameter(user_input)


        

        