from atribot.core.service_container import container
from atribot.core.command.command_parsing import command_system
from atribot.core.cache.chan_context import context_management
from atribot.core.network_connections.qq_send_message import qq_send_message
from atribot.core.command.async_permissions_management import permissions_management
from logging import Logger


class AIContextCommands:
    """AI上下文管理命令处理器"""
    
    def __init__(self):
        self.command_system: command_system = container.get("CommandSystem")
        self.context_management: context_management = container.get("ChatContext")
        self.send_message: qq_send_message = container.get("SendMessage")
        self.permissions_management:permissions_management = container.get("PermissionsManagement")
        self.log: Logger = container.get("log")
        
        self._register_command()
    
    def _register_command(self):
        """注册AI上下文管理统一命令"""
        
        @self.command_system.register_command(
            name="chat",
            description="AI上下文和角色管理命令",
            aliases=["context", "角色管理"],
            examples=[
                "/chat role ATRI           # 切换角色",
                "/chat current             # 查看当前角色", 
                "/chat list                # 列出所有角色",
                "/chat list -d             # 详细列出所有角色",
                "/chat reload              # 重载角色配置",
                "/chat reset               # 重置上下文",
                "/chat info                # 查看上下文信息"
            ],
            authority_level=1
        )
        @self.command_system.argument(
            name="action",
            description="要执行的操作",
            required=True,
            choices=["role", "current", "list", "reload", "reset", "info"],
            metavar="ACTION"
        )
        @self.command_system.argument(
            name="target",
            description="目标角色名称（仅在action为role时需要）",
            required=False,
            metavar="ROLE_NAME"
        )
        @self.command_system.flag(
            name="detail",
            short="d",
            long="--detail", 
            description="显示详细信息（适用于list操作）"
        )
        async def ai_context_handler(message_data:dict, action: str, target: str = None, detail: bool = False):
            group_id = message_data.get('group_id', '')
            
            if not group_id:
                await self.send_message.send_group_message(
                    group_id, "错误：无法获取群组ID"
                )
                return
            
            if action == "role":
                await self._handle_set_role(group_id, target, user_id=message_data['user_id'])
            elif action == "current":
                await self._handle_current_role(group_id)
            elif action == "list":
                await self._handle_list_roles(group_id, detail)
            elif action == "reload":
                await self._handle_reload_roles(group_id, user_id=message_data['user_id'])
            elif action == "reset":
                await self._handle_reset_context(group_id, user_id=message_data['user_id'])
            elif action == "info":
                await self._handle_context_info(group_id)
    
    async def _handle_set_role(self, group_id: str, role_name: str, user_id:int):
        """处理角色切换"""
        if not role_name:
            await self.send_message.send_group_message(
                group_id, 
                "❌ 错误：切换角色需要指定角色名称\n"
                "用法：/chat role <角色名>\n"
                "使用 /chat list 查看可用角色"
            )
            return
        
        self.permissions_management.has_permission(user_id, 2)
        
        # 检查角色是否存在
        if role_name not in self.context_management.play_role_list:
            await self.send_message.send_group_message(
                group_id, 
                f"❌ 错误：角色 '{role_name}' 不存在\n"
                f"使用 /chat list 查看完整列表"
            )
            return
        
        await self.context_management.set_group_role(group_id, role_name)
        
        await self.send_message.send_group_message(
            group_id, 
            f"✅ 已将当前群角色切换为：{role_name}\n"
            f"上下文已重置，开始新的对话。"
        )
        
        self.log.info(f"群 {group_id} 切换角色为：{role_name}")
    
    async def _handle_current_role(self, group_id: str):
        """处理查看当前角色"""
        current_role = self.context_management.group_play_roles.get(
            group_id, 
            self.context_management.default_play_role
        )
        
        role_content = self.context_management.play_role_list.get(current_role, "")
        role_preview = role_content[:100] + "..." if len(role_content) > 100 else role_content
        
        message = "📋 当前群角色信息：\n"
        message += f"角色名：{current_role}\n"
        if role_content:
            message += f"角色提示词：{role_preview}"
        else:
            message += "角色提示词：无"
        
        await self.send_message.send_group_message(group_id, message)
    
    async def _handle_list_roles(self, group_id: str, detail: bool = False):
        """处理列出角色"""
        roles = self.context_management.play_role_list
        current_role = self.context_management.group_play_roles.get(
            group_id, 
            self.context_management.default_play_role
        )
        
        if not detail:
            role_names = []
            for role_name in roles.keys():
                display_name = role_name
                if role_name == current_role:
                    display_name += " ⭐"
                role_names.append(display_name)
            
            message = f"📚 可用角色列表（共{len(roles)}个）：\n"
            message += "\n".join(role_names)
            message += "\n\n💡 使用 /chat list -d 查看详细描述"
            message += "\n💡 使用 /chat role <角色名> 切换角色"
            
        else:
            message = f"📚 角色详细列表（共{len(roles)}个）：\n\n"
            
            for i, (role_name, role_content) in enumerate(roles.items(), 1):
                current_marker = " ⭐" if role_name == current_role else ""
                
                role_preview = role_content[:50] + "..." if len(role_content) > 50 else role_content
                if not role_content:
                    role_preview = "无"
                
                message += f"{i}. {role_name}{current_marker}\n"
                message += f"   {role_preview}\n\n"
            
            message += "💡 使用 /chat role <角色名> 切换角色"
        
        await self.send_message.send_group_merge_text(
            group_id, 
            message,
            source = "查看角色列表"
        )
    
    async def _handle_reload_roles(self, group_id: str, user_id:int):
        """处理重载角色配置"""
        self.permissions_management.has_permission(user_id, 3)
        
        try:
            old_count = len(self.context_management.play_role_list)
            old_roles = set(self.context_management.play_role_list.keys())
            
            self.context_management.anew_character_settings()
            
            new_count = len(self.context_management.play_role_list)
            new_roles = set(self.context_management.play_role_list.keys())
            
            added_roles = new_roles - old_roles
            removed_roles = old_roles - new_roles
            
            message = "✅ 角色配置重载完成！\n"
            message += f"重载前：{old_count} 个角色\n"
            message += f"重载后：{new_count} 个角色\n"
            
            if added_roles:
                message += f"\n🆕 新增角色：{', '.join(list(added_roles)[:5])}{'...' if len(added_roles) > 5 else ''}"
            if removed_roles:
                message += f"\n🗑️ 移除角色：{', '.join(list(removed_roles)[:5])}{'...' if len(removed_roles) > 5 else ''}"
            if not added_roles and not removed_roles and old_count == new_count:
                message += "\n📝 角色数量未变化，可能更新了角色内容"
            
            await self.send_message.send_group_message(group_id, message)
            self.log.info(f"用户在群 {group_id} 执行了角色配置重载")
            
        except Exception as e:
            error_message = f"❌ 角色配置重载失败：{str(e)}"
            await self.send_message.send_group_message(group_id, error_message)
            self.log.error(f"角色配置重载失败：{e}")
    
    async def _handle_reset_context(self, group_id: str, user_id:int):
        """处理重置上下文"""
        
        self.permissions_management.has_permission(user_id, 2)
        
        await self.context_management.reset_group_chat(group_id)
        
        message = "✅ 已重置当前群的对话上下文\n"
        message += "可以开始新的对话了！"
        
        await self.send_message.send_group_message(group_id, message)
        self.log.info(f"群 {group_id} 的对话上下文已重置")
    
    async def _handle_context_info(self, group_id: str):
        """处理查看上下文信息"""

        context = await self.context_management.get_group_chat(group_id)
        current_role = self.context_management.group_play_roles.get(
            group_id, 
            self.context_management.default_play_role
        )
        
        message_count = len(context.messages)
        max_messages = self.context_management.messages_length_limit
        
        usage_percentage = (message_count / max_messages * 100) if max_messages > 0 else 0
        
        message = "📊 当前群上下文状态：\n"
        message += f"当前角色：{current_role}\n"
        message += f"消息数量：{message_count}/{max_messages} ({usage_percentage:.1f}%)\n"
        message += f"预计上下文token: {context.get_context_forecast_token()}\n"
        
        if usage_percentage < 150:
            status_icon = "🟢"
            status_text = "正常"
        elif usage_percentage < 200:
            status_icon = "🟡" 
            status_text = "接近上限"
        else:
            status_icon = "🔴"
            status_text = "已满（将自动清理旧消息）"
        
        message += f"上下文状态：{status_icon} {status_text}\n"
        message += "\n💡 使用 /chat reset 可重置上下文"
        
        await self.send_message.send_group_message(group_id, message)