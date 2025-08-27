from atri_head.Basics import Basics,Command_information
import psutil
from datetime import datetime

basics = Basics()


def bytes_to_human(bytes_value):
    """将字节转换为人类可读格式"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"

def create_bar(percentage, width=50):
    """创建进度条"""
    filled = int(width * percentage / 100)
    bar = '█' * filled + '░' * (width - filled)
    return f"[{bar}] {percentage:.1f}%"

def get_cpu_info():
    """获取CPU信息并返回字符串"""
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count_logical = psutil.cpu_count(logical=True)
    cpu_count_physical = psutil.cpu_count(logical=False)
    cpu_freq = psutil.cpu_freq()
    
    output = ["=" * 10]
    output.append("🖥️  CPU 信息")
    output.append("=" * 10)
    output.append(f"CPU 使用率:      {create_bar(cpu_percent)}")
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
        output.append(f"  核心 {i+1:2d}:       {create_bar(percent, 30)} ")
    
    return "\n".join(output)

def get_memory_info():
    """获取内存信息并返回字符串"""
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    
    output = ["=" * 10]
    output.append("💾 内存信息")
    output.append("=" * 10)
    output.append(f"总内存:          {bytes_to_human(memory.total)}")
    output.append(f"已用内存:        {bytes_to_human(memory.used)}")
    output.append(f"可用内存:        {bytes_to_human(memory.available)}")
    output.append(f"内存使用率:      {create_bar(memory.percent)}")
    
    if hasattr(memory, 'cached'):
        output.append(f"缓存内存:        {bytes_to_human(memory.cached)}")
    if hasattr(memory, 'buffers'):
        output.append(f"缓冲区内存:      {bytes_to_human(memory.buffers)}")
    if hasattr(memory, 'shared'):
        output.append(f"共享内存:        {bytes_to_human(memory.shared)}")
    
    output.append("\n交换分区:")
    output.append(f"总交换空间:      {bytes_to_human(swap.total)}")
    output.append(f"已用交换空间:    {bytes_to_human(swap.used)}")
    output.append(f"可用交换空间:    {bytes_to_human(swap.free)}")
    output.append(f"交换空间使用率:  {create_bar(swap.percent)}")
    
    return "\n".join(output)

def get_disk_info():
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
            
            # output.append(f"\n设备: {partition.device}")
            # output.append(f"文件系统: {partition.fstype}")
            # output.append(f"总大小:          {bytes_to_human(disk_usage.total)}")
            # output.append(f"已用空间:        {bytes_to_human(disk_usage.used)}")
            # output.append(f"可用空间:        {bytes_to_human(disk_usage.free)}")
            # usage_percent = (disk_usage.used / disk_usage.total) * 100
            # output.append(f"使用率:          {create_bar(usage_percent)}")
            
        except PermissionError:
            output.append(f"无权限访问 {partition.device}")
            continue
    
    if total_size > 0:
        total_usage_percent = (total_used / total_size) * 100
        output.append(f"\n{'='*10}")
        output.append("📊 磁盘总计")
        output.append(f"{'='*10}")
        output.append(f"总磁盘空间:      {bytes_to_human(total_size)}")
        output.append(f"已用空间:        {bytes_to_human(total_used)}")
        output.append(f"可用空间:        {bytes_to_human(total_free)}")
        output.append(f"总使用率:        {create_bar(total_usage_percent)}")
    
    return "\n".join(output)

def get_system_info():
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

def get_mcp_info():
    """查看系统MCP工具信息，返回格式化的字符串"""
    tools_info = []
    
    for func in basics.mcp_tool.func_list:
        status = "✅" if func.active else "❌"
        
        origin_info = f"来源: {func.origin}"
        if func.origin == "mcp" and func.mcp_server_name:
            origin_info += f" (服务: {func.mcp_server_name})"
        
        params_info = []
        for param,detail in func.parameters["properties"].items():
            param_type = detail.get("type", "unknown")
            param_desc = detail.get("description", "无描述")
            params_info.append(f"    ▪ {param}: {param_type} - {param_desc}")

        
        parameters = "参数:\n" + "\n".join(params_info) if params_info else "参数: 无"
        
        tool_info = f"""
🔧 工具名称: {func.name} {status}
{origin_info}
📝 描述: {func.description}
{parameters}
        """.strip()
        
        tools_info.append(tool_info)
    
    separator = "\n" + "━" * 20 + "\n"
    header = "📡 系统MCP工具列表 (共{}个)\n".format(len(tools_info)) + "="*20
    return header + "\n" + separator.join(tools_info) + "\n" + "="*20


async def view_lsit(argument,group_ID,data):
    """查看指定东西的list信息"""
    argument = argument[1][0]
    time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    output = [f"🔍 查看系统list (请求: {argument})"]
    output.append(f"生成时间: {time_str}\n")
    

    if argument == "all":
        output.append(get_system_info())
        output.append("\n" + get_cpu_info())
        output.append("\n" + get_memory_info())
        output.append("\n" + get_disk_info())
    elif argument == "cpu":
        output.append(get_cpu_info())
    elif argument == "mem":
        output.append(get_memory_info())
    elif argument == "disk":
        output.append(get_disk_info())
    elif argument == "sys":
        output.append(get_system_info())
    elif argument == "mcp":
        output.append(get_mcp_info())
    else:
        raise ValueError(f"无效参数: {argument}\n可用参数: all, cpu, mem, disk, sys, mcp")
    
    await basics.QQ_send_message.send_group_merge_forward(
        group_id=group_ID,
        message = "\n".join(output),
        source = "查看列表返回值"
    )




    
command_main = Command_information(
    name="ls",
    aliases=["lsit", "ls"],
    handler=view_lsit,
    description="查看指定list,可用参数: all, cpu, mem, disk, sys, mcp",
    parameter=[[0, 0], [1, 1]],
    authority_level=2
)
