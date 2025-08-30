from atribot.LLMchat.MCP.mcp_tool_manager import FuncCall
from atribot.core.service_container import container
from datetime import datetime
import psutil

mcp:FuncCall = container.get("MCP")

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
        
        for func in mcp.func_list:
            status = "✅" if func.active else "❌"
            
            origin_info = f"来源: {func.origin}"
            if func.origin == "mcp" and func.mcp_server_name:
                origin_info += f" (服务: {func.mcp_server_name})"
            
            params_info = []
            for param, detail in func.parameters["properties"].items():
                param_type = detail.get("type", "unknown")
                param_desc = detail.get("description", "无描述")
                params_info.append(f"    ▪ {param}: {param_type} - {param_desc}")

            parameters = "\n参数:\n" + "\n".join(params_info) if params_info else "\n参数: 无"
            
            tool_info = f"""🔧 工具名称: {func.name} {status}{origin_info}📝 描述: {func.description}{parameters}""".strip()
            
            tools_info.append(tool_info)
        
        separator = "\n" + "━" * 20 + "\n"
        header = "📡 系统MCP工具列表 (共{}个)\n".format(len(tools_info)) + "="*20
        return header + "\n" + separator.join(tools_info) + "\n" + "="*20

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
                
            else:
                # 忽略无效参数或者已经处理过的参数
                continue
        
        return "\n".join(output)

