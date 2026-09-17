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


@router.get("/", response_class=HTMLResponse)
async def panel_index() -> HTMLResponse:
    html_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read(), headers={"Cache-Control": "no-store"})
