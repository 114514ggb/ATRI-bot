from .example_plugin import example_plugin as example

class manage_Permissions(example):
    """用于管理权限"""
    register_order = ["/manage","/管理"]
    authority_level = 2
    people = None

    action_map = {
        "添加": "添加",
        "append": "添加",
        "add": "添加",
        "删除": "删除",
        "del": "删除",
        "delete": "删除",
        "查询": "查询",
        "query": "查询",
        "que": "查询"
    }

    role_map = {
        "管理": "管理员",
        "管理员": "管理员",
        "administrator": "管理员",
        "admin": "管理员",
        "黑名单": "黑名单",
        "blacklist": "黑名单",
        "black": "黑名单"
    }

    @example.store_verify_parameters(
        parameter_quantity_max_1=1,parameter_quantity_min_1=1,
        parameter_quantity_max_2=2,parameter_quantity_min_2=1,
    )
    async def manage_Permissions(self, user_input, qq_TestGroup, data, basics):
        self.people = data["user_id"]
    
        # print(self.minus_argument,self.other_argument)
        action = None
        role = None
        Be_operated_qq = None

        if self.minus_argument[0] in self.action_map:
            action = self.action_map[self.minus_argument[0]]
            if action in ["添加", "删除"]:
                Be_operated_qq = int(self.other_argument[1])

        if self.other_argument[0] in self.role_map:
            role = self.role_map[self.other_argument[0]]

        # 执行操作
        text = self.handle_operation(action, role, Be_operated_qq,qq_TestGroup)

        await self.basics.QQ_send_message.send_group_message(qq_TestGroup, text)
        
        return "ok"

    def query_admin(self):
        return f"管理员列表:\n{self.basics.Command.administrator}"

    def query_blacklist(self):
        return f"黑名单列表:\n{self.basics.Command.blacklist}"

    
    def handle_operation(self,action, role, qq_id,qq_TestGroup):
        """执行权限操作"""
        operations = {
            "添加": {
                "管理员": self.basics.Command.administrator_add,
                "黑名单": self.basics.Command.blacklist_add,
            },
            "删除": {
                "管理员": self.basics.Command.administrator_delete,
                "黑名单": self.basics.Command.blacklist_delete,
            },
            "查询": {
                "管理员": self.query_admin,
                "黑名单": self.query_blacklist,
            }
        }
        
        if action not in operations:
            raise ValueError("不支持的操作类型! 仅支持: 添加, 删除, 查询")
        if role not in operations[action]:
            raise ValueError(f"不支持的权限类型 '{role}'! 仅支持: 管理员, 黑名单")

        if action in ["添加", "删除"]:
            operations[action][role](qq_id, self.people)
            self.basics.Command.synchronous_database(qq_id, role, add=(action == "添加"))#同步数据库
            return f"已将QQ:{qq_id}\n{action}{role}"

        elif action == "查询":
            return operations[action][role]()
            