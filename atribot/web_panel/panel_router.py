"""ATRI Web 管理面板后端路由（聚合层）

具体路由实现按功能域拆分在 routes/ 包内，共享依赖在 deps.py。
所有服务依赖均为惰性获取（请求内从 DI 容器解析），
使面板可以在不完整的运行环境中安全导入与独立调试。
"""

import os

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .deps import _ensure_log_handler as _ensure_log_handler  # 再导出：bot_framework / dev_server 从本模块导入
from .routes import all_routers

router = APIRouter(prefix="/admin", tags=["admin"])

for _sub_router in all_routers:
    router.include_router(_sub_router)


def mount_static(app) -> None:
    """将面板静态资源目录挂载到 FastAPI 应用（/admin/static），并对面板资源禁用缓存

    面板 HTML 与静态 JS/CSS 均以 no-store 下发，保证改动后普通刷新即可拿到最新前端，
    避免浏览器启发式缓存导致新旧脚本混跑。正式环境（bot_framework）与开发服务器共用此处。
    """
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.mount("/admin/static", StaticFiles(directory=static_dir), name="admin_static")

    @app.middleware("http")
    async def _no_cache_panel_assets(request, call_next):
        resp = await call_next(request)
        if request.url.path.startswith("/admin/static"):
            resp.headers["Cache-Control"] = "no-store"
        return resp


_CSP = (
    "default-src 'none'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https://latex.codecogs.com; "
    "media-src 'self' blob:; "
    "connect-src 'self'; "
    "font-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'none'; "
    "form-action 'none'; "
    "object-src 'none'"
)
"""面板 CSP：脚本只允许同源外部文件（index.html 的内联主题脚本已抽到 theme-init.js），
样式保留 'unsafe-inline'（视图大量使用行内 style 属性），图片仅同源 + data: + 公式服务"""

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": _CSP,
}


def install_security_headers(app) -> None:
    """给面板全部响应补齐安全头，并让 /admin/api 响应禁缓存

    - nosniff：阻止浏览器对上传附件做 MIME 嗅探（配合 FileResponse 的 attachment）
    - X-Frame-Options / CSP frame-ancestors：禁止被 iframe 嵌套（防点击劫持）
    - Referrer-Policy: no-referrer：避免把含 ?token= 的 URL 通过 Referer 泄给外站
    - Cache-Control: no-store：配置/密钥/日志等敏感 JSON 不留在浏览器与代理缓存里
    正式环境（bot_framework）与开发服务器共用此处，必须在应用开始接请求前调用。
    """

    @app.middleware("http")
    async def _panel_security_headers(request, call_next):
        resp = await call_next(request)
        path = request.url.path
        if path.startswith("/admin"):
            for name, value in _SECURITY_HEADERS.items():
                resp.headers.setdefault(name, value)
            if path.startswith("/admin/api"):
                resp.headers.setdefault("Cache-Control", "no-store")
        return resp


@router.get("/", response_class=HTMLResponse)
async def panel_index() -> HTMLResponse:
    html_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read(), headers={"Cache-Control": "no-store"})
