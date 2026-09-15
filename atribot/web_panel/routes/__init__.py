"""面板 API 路由，按功能域（对应前端页面）拆分为子模块

all_routers 由 panel_router 聚合挂载到 /admin 前缀下，
子模块内路由路径不带前缀（如 /api/status）。
"""

from . import config, dashboard, data, database, memory, message, personas, system, tools

all_routers = [
    dashboard.router,
    data.router,
    memory.router,
    tools.router,
    database.router,
    config.router,
    personas.router,
    message.router,
    system.router,
]
