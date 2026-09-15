import socket
import sys


def try_bind_port(host: str, port: int) -> socket.socket | None:
    """尝试绑定 (host, port)，成功返回已绑定的 socket,端口被占用等失败返回 None

    返回的 socket 已绑定但未监听，可直接交给 asyncio/uvicorn 的
    serve(sockets=[...]) 使用（所有权随之转移，由其负责关闭）
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if sys.platform != "win32":
        # 对齐 asyncio 服务端默认行为，避免快速重启时被 TIME_WAIT 误判为占用；
        # Windows 下 SO_REUSEADDR 允许重复绑定，会让占用检测失效，因此不设置
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((host, port))
    except (OSError, OverflowError):  # 端口越界时 socket 抛的是 OverflowError
        sock.close()
        return None
    return sock


def is_port_in_use(host: str, port: int) -> bool:
    """探测 (host, port) 是否已被占用（探测后立即释放，不占住端口）"""
    sock = try_bind_port(host, port)
    if sock is None:
        return True
    sock.close()
    return False


def bind_port_with_fallback(
    host: str, port: int, max_attempts: int = 10
) -> tuple[socket.socket, int] | None:
    """从 port 起尝试绑定，被占用则自动 +1 递增，最多 max_attempts 次

    成功返回 (已绑定的 socket, 实际端口)，失败返回 None
    """
    for candidate in range(port, port + max_attempts):
        sock = try_bind_port(host, candidate)
        if sock is not None:
            return sock, sock.getsockname()[1]
    return None
