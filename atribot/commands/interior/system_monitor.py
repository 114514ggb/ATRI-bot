import asyncio
from datetime import datetime

import psutil

from atribot.core.db.async_postgresql import AsyncPostgreSQL
from atribot.core.network_connections.WebSocketBase import WebSocketBase
from atribot.core.service_container import container
from atribot.LLMchat.MCP.tool_calls import ToolCalls
from atribot.LLMchat.MCP.tool_model import MCPTool

tool_set: ToolCalls = container.get("ToolCalls")
config = container.get("config")

class SystemMonitor:
    """系统监控类，用于获取和展示系统信息"""
    
    @staticmethod
    def bytes_to_human(bytes_value):
        """将字节转换为人类可读格式"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.2f} PB"

    @staticmethod
    def create_bar(percentage, width=50):
        """创建进度条"""
        filled = int(width * percentage / 100)
        bar = '█' * filled + '░' * (width - filled)
        return f"[{bar}] {percentage:.1f}%"

    def get_cpu_info(self):
        """获取CPU信息并返回字符串"""
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count_logical = psutil.cpu_count(logical=True)
        cpu_count_physical = psutil.cpu_count(logical=False)
        cpu_freq = psutil.cpu_freq()
        
        output = ["=" * 10]
        output.append("🖥️  CPU 信息")
        output.append("=" * 10)
        output.append(f"CPU 使用率:      {self.create_bar(cpu_percent)}")
        output.append(f"逻辑核心数:      {cpu_count_logical}")
        output.append(f"物理核心数:      {cpu_count_physical}")
        
        if cpu_freq:
            output.append(f"当前频率:        {cpu_freq.current:.2f} MHz")
            output.append(f"最大频率:        {cpu_freq.max:.2f} MHz")
            output.append(f"最小频率:        {cpu_freq.min:.2f} MHz")
        
        # 各核心使用率
        cpu_percents = psutil.cpu_percent(percpu=True)
        output.append("\n各核心使用率:")
        for i, percent in enumerate(cpu_percents):
            output.append(f"  核心 {i+1:2d}:       {self.create_bar(percent, 30)} ")
        
        return "\n".join(output)

    def get_memory_info(self):
        """获取内存信息并返回字符串"""
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        output = ["=" * 10]
        output.append("💾 内存信息")
        output.append("=" * 10)
        output.append(f"总内存:          {self.bytes_to_human(memory.total)}")
        output.append(f"已用内存:        {self.bytes_to_human(memory.used)}")
        output.append(f"可用内存:        {self.bytes_to_human(memory.available)}")
        output.append(f"内存使用率:      {self.create_bar(memory.percent)}")
        
        if hasattr(memory, 'cached'):
            output.append(f"缓存内存:        {self.bytes_to_human(memory.cached)}")
        if hasattr(memory, 'buffers'):
            output.append(f"缓冲区内存:      {self.bytes_to_human(memory.buffers)}")
        if hasattr(memory, 'shared'):
            output.append(f"共享内存:        {self.bytes_to_human(memory.shared)}")
        
        output.append("\n交换分区:")
        output.append(f"总交换空间:      {self.bytes_to_human(swap.total)}")
        output.append(f"已用交换空间:    {self.bytes_to_human(swap.used)}")
        output.append(f"可用交换空间:    {self.bytes_to_human(swap.free)}")
        output.append(f"交换空间使用率:  {self.create_bar(swap.percent)}")
        
        return "\n".join(output)

    def get_disk_info(self):
        """获取磁盘信息并返回字符串"""
        output = []
        
        partitions = psutil.disk_partitions()
        total_size = 0
        total_used = 0
        total_free = 0
        
        for partition in partitions:
            try:
                disk_usage = psutil.disk_usage(partition.mountpoint)
                total_size += disk_usage.total
                total_used += disk_usage.used
                total_free += disk_usage.free
                
            except PermissionError:
                output.append(f"无权限访问 {partition.device}")
                continue
        
        if total_size > 0:
            total_usage_percent = (total_used / total_size) * 100
            output.append(f"\n{'='*10}")
            output.append("📊 磁盘总计")
            output.append(f"{'='*10}")
            output.append(f"总磁盘空间:      {self.bytes_to_human(total_size)}")
            output.append(f"已用空间:        {self.bytes_to_human(total_used)}")
            output.append(f"可用空间:        {self.bytes_to_human(total_free)}")
            output.append(f"总使用率:        {self.create_bar(total_usage_percent)}")
        
        return "\n".join(output)

    def get_system_info(self):
        """获取系统基本信息并返回字符串"""
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        
        output = ["=" * 10]
        output.append("⚡ 系统信息")
        output.append("=" * 10)
        output.append(f"系统启动时间:    {boot_time.strftime('%Y-%m-%d %H:%M:%S')}")
        output.append(f"运行时长:        {str(uptime).split('.')[0]}")
        output.append(f"当前时间:        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return "\n".join(output)

    def get_mcp_info(self):
        """查看系统MCP工具信息，返回格式化的字符串"""
        tools_info = []
        
        for func in tool_set.func_list:
            status = "✅" if func.active else "❌"
            
            origin_info = f"来源: {'mcp' if isinstance(func, MCPTool) else 'local'}"
            if isinstance(func, MCPTool) and func.mcp_server_name:
                origin_info += f" (服务: {func.mcp_server_name})"
            
            params_info = []
            for param, detail in func.parameters["properties"].items():
                param_type = detail.get("type", "unknown")
                param_desc = detail.get("description", "无描述")
                params_info.append(f"    ▪ {param}: {param_type} - {param_desc}")

            parameters = "\n参数:\n" + "\n".join(params_info) if params_info else "\n参数: 无"
            
            tool_info = f"""🔧 工具名称: {func.name} {status}{origin_info}\n📝 描述: {func.description}{parameters}""".strip()
            
            tools_info.append(tool_info)
        
        separator = "\n" + "━" * 20 + "\n"
        header = "📡 系统MCP工具列表 (共{}个)\n".format(len(tools_info)) + "="*20
        return header + "\n" + separator.join(tools_info) + "\n" + "="*20

    def get_model_info(self) -> str:
        """返回模型信息 (通用动态版本)"""
        chief_model = config.model.connect.model_name
        spare_model_list = config.model.standby_model
        model_parameter = config.model.chat_parameter

        spare_emoji = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩"]
        spare_text = "\n".join([
            f"   {spare_emoji[i] if i < len(spare_emoji) else i+1} {model['model_name']}"
            for i, model in enumerate(spare_model_list)
        ])

        parameter_text = "\n".join([
            f"   📝 {key}: {value}"
            for key, value in model_parameter.items()
        ])

        return (
            f"✨ 模型配置信息 ✨\n\n"
            f"🎯 主模型: 🚀 {chief_model}\n\n"
            f"🔄 备用模型:\n"
            f"{spare_text if spare_text else '   (无备用模型)'}\n\n"  
            f"⚙️  参数设置:\n"
            f"{parameter_text if parameter_text else '   (无自定义参数)'}\n\n" 
        )

    def _safe_attr(self, obj, attr_name: str, default=None):
        """安全获取对象属性，避免监控逻辑因字段不存在中断"""
        try:
            return getattr(obj, attr_name, default)
        except Exception:
            return default

    async def get_database_pool_info(self) -> str:
        """返回数据库连接池状态信息"""
        output = ["=" * 10]
        output.append("🗄️  数据库连接池")
        output.append("=" * 10)

        if not container.exists("database"):
            output.append("服务状态:        未注册")
            return "\n".join(output)

        db:AsyncPostgreSQL = container.get("database")
        pool = self._safe_attr(db, "_pool")

        output.append("服务状态:        已注册")
        output.append(f"连接池实例:      {'已创建' if pool else '未创建'}")

        if pool:
            for label, method_name in [
                ("最小连接数", "get_min_size"),
                ("最大连接数", "get_max_size"),
                ("当前连接数", "get_size"),
                ("空闲连接数", "get_idle_size"),
            ]:
                getter = self._safe_attr(pool, method_name)
                if callable(getter):
                    try:
                        output.append(f"{label}:      {getter()}")
                    except Exception:
                        output.append(f"{label}:      获取失败")

        try:
            async with db as conn_db:
                table_count_row = await conn_db.execute_with_pool(
                    query="""
                    SELECT
                        (SELECT COUNT(*) FROM atri_memory) AS atri_memory_count,
                        (SELECT COUNT(*) FROM message) AS message_count,
                        (SELECT COUNT(*) FROM users) AS users_count,
                        (SELECT COUNT(*) FROM user_group) AS user_group_count
                    """,
                    params = None,
                    fetch_type = "one"
                )
                if table_count_row:
                    output.append("\n核心表记录数:")
                    output.append(f"atri_memory:      {table_count_row.get('atri_memory_count', 0)}")
                    output.append(f"message:          {table_count_row.get('message_count', 0)}")
                    output.append(f"users:            {table_count_row.get('users_count', 0)}")
                    output.append(f"user_group:       {table_count_row.get('user_group_count', 0)}")
        except Exception as e:
            output.append(f"连通性检查:      异常 ({type(e).__name__})")

        return "\n".join(output)

    def get_scheduler_info(self) -> str:
        """返回时间调度器状态信息"""
        output = ["=" * 10]
        output.append("⏱️  时间调度器")
        output.append("=" * 10)

        if not container.exists("TimeTriggerSupervisor"):
            output.append("服务状态:        未注册")
            return "\n".join(output)

        trigger = container.get("TimeTriggerSupervisor")
        running = self._safe_attr(trigger, "_running", False)
        queue = self._safe_attr(trigger, "_queue", []) or []
        task_map = self._safe_attr(trigger, "_task_map", {}) or {}
        running_tasks = self._safe_attr(trigger, "_running_tasks", set()) or set()

        output.append("服务状态:        已注册")
        output.append(f"运行中:          {'是' if running else '否'}")
        output.append(f"队列任务数:      {len(queue)}")
        output.append(f"索引任务数:      {len(task_map)}")
        output.append(f"执行中任务数:    {len(running_tasks)}")

        if queue:
            next_task = queue[0]
            task_id = self._safe_attr(next_task, "task_id", "unknown")
            remarks = self._safe_attr(next_task, "remarks", "") or "(无备注)"
            next_ts = self._safe_attr(next_task, "trigger_timestamp")
            eta = "未知"
            if isinstance(next_ts, (int, float)):
                try:
                    eta_seconds = max(0.0, next_ts - trigger.now())
                    eta = f"{eta_seconds:.2f}s"
                except Exception:
                    pass

            output.append(f"最近任务ID:      {task_id}")
            output.append(f"最近触发倒计时:  {eta}")
            output.append(f"最近任务备注:    {remarks}")

        return "\n".join(output)

    def get_services_info(self) -> str:
        """返回容器服务注册状态"""
        output = ["=" * 10]
        output.append("🧩 服务容器状态")
        output.append("=" * 10)

        services = self._safe_attr(container, "_services", {}) or {}
        cleanup_handlers = self._safe_attr(container, "_cleanup_handlers", {}) or {}

        output.append(f"服务总数:        {len(services)}")
        output.append(f"可回收服务数:    {len(cleanup_handlers)}")

        if services:
            service_names = sorted(list(services.keys()))
            output.append("已注册服务:")
            output.append("  " + ", ".join(service_names))

        return "\n".join(output)

    def get_websocket_info(self) -> str:
        """返回WebSocket运行状态"""
        output = ["=" * 10]
        output.append("🌐 WebSocket 状态")
        output.append("=" * 10)

        if not container.exists("WebSocket"):
            output.append("服务状态:        未注册")
            return "\n".join(output)

        ws = container.get_by_type(WebSocketBase)
        ws_type = type(ws).__name__
        running = self._safe_attr(ws, "_running", False)
        connected = False

        if hasattr(ws, "is_connected"):
            try:
                connected = bool(ws.is_connected)
            except Exception:
                connected = False
        else:
            connected_event = self._safe_attr(ws, "_connected")
            if connected_event is not None and hasattr(connected_event, "is_set"):
                connected = bool(connected_event.is_set())

        message_queue = self._safe_attr(ws, "message_queue")
        queue_size = message_queue.qsize() if message_queue and hasattr(message_queue, "qsize") else 0
        listeners = self._safe_attr(ws, "_listeners", []) or []
        pending_requests = self._safe_attr(ws, "pending_requests", {}) or {}

        output.append(f"服务类型:        {ws_type}")
        output.append(f"运行中:          {'是' if running else '否'}")
        output.append(f"已连接:          {'是' if connected else '否'}")
        output.append(f"监听器数量:      {len(listeners)}")
        output.append(f"待处理消息数:    {queue_size}")
        output.append(f"待回声请求数:    {len(pending_requests)}")

        return "\n".join(output)

    async def get_sandbox_info(self) -> str:
        """返回沙盒运行状态"""
        output = ["=" * 10]
        output.append("📦 SandBox 状态")
        output.append("=" * 10)

        if not container.exists("SandBox"):
            output.append("服务状态:        未注册/初始化失败")
            return "\n".join(output)

        sandbox = container.get("SandBox")
        output.append("服务状态:        已注册")
        output.append(f"实现类型:        {type(sandbox).__name__}")
        is_running = self._safe_attr(sandbox, 'is_running', False)
        output.append(f"运行中:          {'是' if is_running else '否'}")
        output.append(f"镜像:            {self._safe_attr(sandbox, 'image', 'unknown')}")
        output.append(f"容器名:          {self._safe_attr(sandbox, 'container_name', 'unknown')}")
        output.append(f"内存限制:        {self._safe_attr(sandbox, 'mem_limit', 'unknown')}")
        output.append(f"CPU配额:         {self._safe_attr(sandbox, 'cpu_quota', 'unknown')}/{self._safe_attr(sandbox, 'cpu_period', 'unknown')}")
        output.append(f"PIDs限制:        {self._safe_attr(sandbox, 'pids_limit', 'unknown')}")

        container_obj = self._safe_attr(sandbox, 'container')
        if not is_running or container_obj is None:
            return "\n".join(output)

        try:
            await asyncio.to_thread(container_obj.reload)
            status = self._safe_attr(container_obj, 'status', 'unknown')
            output.append(f"容器状态:        {status}")

            stats = await asyncio.to_thread(container_obj.stats, stream=False)

            mem_stats = stats.get('memory_stats', {}) if isinstance(stats, dict) else {}
            mem_usage = mem_stats.get('usage', 0) or 0
            mem_limit = mem_stats.get('limit', 0) or 0
            mem_percent = (mem_usage / mem_limit * 100) if mem_limit else 0.0
            output.append(f"内存占用:        {self.bytes_to_human(mem_usage)} / {self.bytes_to_human(mem_limit)}")
            output.append(f"内存占比:        {self.create_bar(min(mem_percent, 100.0))}")

            cpu_stats = stats.get('cpu_stats', {}) if isinstance(stats, dict) else {}
            precpu_stats = stats.get('precpu_stats', {}) if isinstance(stats, dict) else {}
            cpu_delta = (cpu_stats.get('cpu_usage', {}) or {}).get('total_usage', 0) - (precpu_stats.get('cpu_usage', {}) or {}).get('total_usage', 0)
            sys_delta = (cpu_stats.get('system_cpu_usage', 0) or 0) - (precpu_stats.get('system_cpu_usage', 0) or 0)
            online_cpus = cpu_stats.get('online_cpus') or len((cpu_stats.get('cpu_usage', {}) or {}).get('percpu_usage', []) or []) or 1
            cpu_percent = (cpu_delta / sys_delta * online_cpus * 100.0) if sys_delta > 0 and cpu_delta > 0 else 0.0
            output.append(f"CPU占比:         {self.create_bar(min(cpu_percent, 100.0))}")

            networks = stats.get('networks', {}) if isinstance(stats, dict) else {}
            total_rx = 0
            total_tx = 0
            for item in networks.values():
                total_rx += item.get('rx_bytes', 0) or 0
                total_tx += item.get('tx_bytes', 0) or 0
            output.append(f"网络接收:        {self.bytes_to_human(total_rx)}")
            output.append(f"网络发送:        {self.bytes_to_human(total_tx)}")

            blkio = stats.get('blkio_stats', {}) if isinstance(stats, dict) else {}
            io_list = blkio.get('io_service_bytes_recursive', []) or []
            io_read = 0
            io_write = 0
            for io_item in io_list:
                op = str(io_item.get('op', '')).lower()
                value = io_item.get('value', 0) or 0
                if op == 'read':
                    io_read += value
                elif op == 'write':
                    io_write += value
            output.append(f"块IO读:          {self.bytes_to_human(io_read)}")
            output.append(f"块IO写:          {self.bytes_to_human(io_write)}")

            pids = stats.get('pids_stats', {}) if isinstance(stats, dict) else {}
            output.append(f"PIDs占用:        {pids.get('current', 0) or 0}")
        except Exception as e:
            output.append(f"资源占用采集:    异常 ({type(e).__name__})")

        return "\n".join(output)

    def get_llm_supplier_info(self) -> str:
        """返回LLM供应商连接状态"""
        output = ["=" * 10]
        output.append("🤖 LLM 供应商状态")
        output.append("=" * 10)

        if not container.exists("LLMSupplier"):
            output.append("服务状态:        未注册")
            return "\n".join(output)

        supplier = container.get("LLMSupplier")
        connections = self._safe_attr(supplier, "connections", {}) or {}

        output.append("服务状态:        已注册")
        output.append(f"供应商数量:      {len(connections)}")

        if connections:
            output.append("连接明细:")
            for name, conn in connections.items():
                model_dict = self._safe_attr(conn, "model_dict", {}) or {}
                api_obj = self._safe_attr(conn, "connection_object")
                output.append(
                    f"  - {name}: models={len(model_dict)}, api={type(api_obj).__name__ if api_obj else 'None'}"
                )

        return "\n".join(output)

    def get_chat_manager_info(self) -> str:
        """返回聊天上下文缓存状态"""
        output = ["=" * 10]
        output.append("💬 ChatManager 状态")
        output.append("=" * 10)

        if not container.exists("ChatManager"):
            output.append("服务状态:        未注册")
            return "\n".join(output)

        chat_manager = container.get("ChatManager")
        group_dict = self._safe_attr(chat_manager, "group_dict", {}) or {}
        private_dict = self._safe_attr(chat_manager, "private_dict", {}) or {}
        output.append("服务状态:        已注册")
        output.append(f"群上下文数量:    {len(group_dict)}")
        output.append(f"活跃user上下文数量:  {len(private_dict)}")
        output.append(f"群消息上限:      {self._safe_attr(chat_manager, 'group_max_record', 'unknown')}")
        output.append(f"user消息上限:    {self._safe_attr(chat_manager, 'private_max_record', 'unknown')}")
        output.append(f"LLM轮次上限:     {self._safe_attr(chat_manager, 'LLM_max_record', 'unknown')}")

        return "\n".join(output)

        
    
    async def view_list(self, arguments: list[str]) -> str:
        """查看指定东西的list信息，根据参数列表返回组合的系统信息"""
        time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        requested_args = ", ".join(arguments) if arguments else "无"
        output = [f"🔍 查看系统list (请求: {requested_args})"]
        output.append(f"生成时间: {time_str}\n")
        
        if not arguments:
            return ""
        
        sections_added = set()
        
        for arg in arguments:
            if arg in sections_added:
                continue
                
            if arg == "all":
                if "sys" not in sections_added:
                    output.append(self.get_system_info())
                    sections_added.add("sys")
                if "cpu" not in sections_added:
                    output.append("\n" + self.get_cpu_info())
                    sections_added.add("cpu")
                if "mem" not in sections_added:
                    output.append("\n" + self.get_memory_info())
                    sections_added.add("mem")
                if "disk" not in sections_added:
                    output.append("\n" + self.get_disk_info())
                    sections_added.add("disk")
                if "db" not in sections_added:
                    output.append("\n" + await self.get_database_pool_info())
                    sections_added.add("db")
                if "scheduler" not in sections_added:
                    output.append("\n" + self.get_scheduler_info())
                    sections_added.add("scheduler")
                if "services" not in sections_added:
                    output.append("\n" + self.get_services_info())
                    sections_added.add("services")
                if "sandbox" not in sections_added:
                    output.append("\n" + await self.get_sandbox_info())
                    sections_added.add("sandbox")
                if "llm" not in sections_added:
                    output.append("\n" + self.get_llm_supplier_info())
                    sections_added.add("llm")
                if "chat" not in sections_added:
                    output.append("\n" + self.get_chat_manager_info())
                    sections_added.add("chat")
                sections_added.add("all")
                
            elif arg == "cpu" and "cpu" not in sections_added:
                output.append(self.get_cpu_info())
                sections_added.add("cpu")
                
            elif arg == "mem" and "mem" not in sections_added:
                output.append(self.get_memory_info())
                sections_added.add("mem")
                
            elif arg == "disk" and "disk" not in sections_added:
                output.append(self.get_disk_info())
                sections_added.add("disk")
                
            elif arg == "sys" and "sys" not in sections_added:
                output.append(self.get_system_info())
                sections_added.add("sys")
                
            elif arg == "mcp":
                output.append(self.get_mcp_info())
                sections_added.add("mcp")
            
            elif arg == "model":
                output.append(self.get_model_info())
                sections_added.add("model")

            elif arg == "db" and "db" not in sections_added:
                output.append(await self.get_database_pool_info())
                sections_added.add("db")

            elif arg == "scheduler" and "scheduler" not in sections_added:
                output.append(self.get_scheduler_info())
                sections_added.add("scheduler")

            elif arg == "services" and "services" not in sections_added:
                output.append(self.get_services_info())
                sections_added.add("services")

            elif arg == "sandbox" and "sandbox" not in sections_added:
                output.append(await self.get_sandbox_info())
                sections_added.add("sandbox")

            elif arg == "llm" and "llm" not in sections_added:
                output.append(self.get_llm_supplier_info())
                sections_added.add("llm")

            elif arg == "chat" and "chat" not in sections_added:
                output.append(self.get_chat_manager_info())
                sections_added.add("chat")
                
            else:
                # 忽略无效参数或者已经处理过的参数
                continue
        
        return "\n".join(output)

