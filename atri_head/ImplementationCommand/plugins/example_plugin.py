from ...Basics import Basics

class example_plugin():
    """插件类示例,一般要继承这个类来写插件"""
    my_name = "acquiesce_plugin_name" 
    """插件名称"""
    authority_level = 1
    """执行需求的权限等级,0为所有人,1为游客,2为管理员,3为root"""
    register_order = ["/plugin","/插件"]
    """插件注册的触发命令"""
    user_input = None
    """用户输入（纯文本）"""
    qq_TestGroup = None
    """发起命令的群号"""
    data = None
    """原始消息数据"""
    basics : Basics= None
    """基础类"""
    argument = None
    """总参数列表"""
    minus_argument = None
    """'-'参数列表"""
    other_argument = None
    """其他参数列表"""

    @classmethod
    def store_verify_parameters(
        cls,           
        parameter_quantity_max_1: int = 0, parameter_quantity_min_1: int = 0, 
        parameter_quantity_max_2: int = 0, parameter_quantity_min_2: int = 0
    ):
        """参数验证和初始化"""
        def decorator(func):
            async def wrapper(self,user_input,qq_TestGroup,data,basics:Basics):
                cls.basics = basics
                cls.user_input = user_input
                cls.qq_TestGroup = qq_TestGroup
                cls.data = data
                cls.argument = cls.basics.Command.processingParameter(user_input)
                cls.minus_argument,cls.other_argument = cls.argument

                cls.basics.Command.verifyParameter(
                    cls.argument,
                    parameter_quantity_max_1=parameter_quantity_max_1, parameter_quantity_min_1=parameter_quantity_min_1,  
                    parameter_quantity_max_2=parameter_quantity_max_2, parameter_quantity_min_2=parameter_quantity_min_2,
                )

                return await func(self,user_input,qq_TestGroup,data,basics)
            return wrapper
        return decorator
        

        