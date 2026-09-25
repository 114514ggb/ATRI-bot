"""Web 面板鉴权测试：全局登录锁定、会话令牌生命周期、端点防护不变量

运行：uv run python -m pytest tests/ -q
"""

import logging
import time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from atribot.web_panel import deps, session_store
from atribot.web_panel.routes import auth as auth_routes

MASTER = "correct-horse-battery-staple-0123456789"


class _FakeConfig:
    def __init__(self, raw: dict) -> None:
        self._raw_config = raw


def _set_config(monkeypatch, raw: dict) -> None:
    monkeypatch.setattr(deps, "_cfg", lambda: _FakeConfig(raw))


def _set_master(monkeypatch, token: str = MASTER) -> None:
    _set_config(monkeypatch, {"web_panel": {"access_token": token}})


def _body(token: str) -> auth_routes.LoginBody:
    return auth_routes.LoginBody(token=token)


def _request(ip: str = "127.0.0.1") -> SimpleNamespace:
    return SimpleNamespace(client=SimpleNamespace(host=ip))


@pytest.fixture(autouse=True)
def _reset_auth_state(monkeypatch):
    """每个用例前后清空模块级状态（锁定计数、令牌轮换记录、弱口令告警、会话表）"""
    monkeypatch.setattr(deps, "_login_failures", 0)
    monkeypatch.setattr(deps, "_lock_until", 0.0)
    monkeypatch.setattr(deps, "_master_token_seen", None)
    monkeypatch.setattr(deps, "_weak_token_warned", False)
    monkeypatch.delenv("ATRI_PANEL_TOKEN", raising=False)
    session_store.revoke_all()
    yield
    session_store.revoke_all()


# ---------- 登录：全局计数与硬锁定 ----------


async def test_login_failures_then_global_lock(monkeypatch):
    """连续失败 3 次触发锁定；锁定期内正确口令同样 429（硬锁定）"""
    _set_master(monkeypatch)

    with pytest.raises(HTTPException) as err1:
        await auth_routes.api_login(_body("wrong-token"), _request())
    assert err1.value.status_code == 401
    assert "还可尝试 2 次" in err1.value.detail

    with pytest.raises(HTTPException) as err2:
        await auth_routes.api_login(_body("wrong-token"), _request("10.0.0.9"))
    assert err2.value.status_code == 401
    assert "还可尝试 1 次" in err2.value.detail

    # 第 3 次失败（换 IP 也一样）→ 立即锁定
    with pytest.raises(HTTPException) as err3:
        await auth_routes.api_login(_body("wrong-token"), _request("10.0.0.9"))
    assert err3.value.status_code == 429
    assert "Retry-After" in err3.value.headers

    # 锁定期间：即使口令正确也一律拒绝，且不计数、不续期
    with pytest.raises(HTTPException) as err4:
        await auth_routes.api_login(_body(MASTER), _request())
    assert err4.value.status_code == 429
    assert deps.login_failures() == 3


async def test_login_success_issues_session_and_resets_failures(monkeypatch):
    _set_master(monkeypatch)
    deps.register_login_failure()
    deps.register_login_failure()

    resp = await auth_routes.api_login(_body(MASTER), _request())
    assert resp["status"] == "ok"
    assert resp["expires_in"] == 4 * 3600
    assert session_store.validate_session(str(resp["session_token"]))

    assert deps.login_failures() == 0
    assert deps.login_lock_remaining() is None


def test_lockout_escalation_formula_and_cap():
    assert deps._lockout_seconds(3) == 600
    assert deps._lockout_seconds(4) == 1200
    assert deps._lockout_seconds(5) == 2400
    assert deps._lockout_seconds(10) == 600 * 2**7
    assert deps._lockout_seconds(11) == 86400
    assert deps._lockout_seconds(30) == 86400


async def test_lock_expires_then_next_failure_escalates(monkeypatch):
    _set_master(monkeypatch)
    for _ in range(3):
        with pytest.raises(HTTPException):
            await auth_routes.api_login(_body("wrong-token"), _request())

    # 把锁定截止时间拨到过去，模拟锁定到期
    monkeypatch.setattr(deps, "_lock_until", time.monotonic() - 1)
    assert deps.login_lock_remaining() is None

    # 第 4 次失败 → 解锁后的下一次失败按 20 分钟锁定（翻倍升级）
    locked = deps.register_login_failure()
    assert locked is not None
    assert 1190 < locked <= 1200


async def test_login_requires_configured_master(monkeypatch):
    _set_config(monkeypatch, {})
    with pytest.raises(HTTPException) as err:
        await auth_routes.api_login(_body(MASTER), _request())
    assert err.value.status_code == 503


async def test_logout_revokes_session(monkeypatch):
    _set_master(monkeypatch)
    resp = await auth_routes.api_login(_body(MASTER), _request())
    token = str(resp["session_token"])

    assert await auth_routes.api_logout(token=token) == {"status": "ok"}
    assert session_store.validate_session(token) is False

    # 已吊销的令牌再访问任意端点（含登出自身）都会在 _auth 层被拒
    with pytest.raises(HTTPException) as err:
        await deps._auth(creds=SimpleNamespace(credentials=token))
    assert err.value.status_code == 401


# ---------- HTTP/WS/query 端点只认会话令牌 ----------


async def test_http_auth_accepts_session_only(monkeypatch):
    # 未配置主令牌 → 503（fail-closed）
    _set_config(monkeypatch, {})
    with pytest.raises(HTTPException) as err:
        await deps._auth(creds=None)
    assert err.value.status_code == 503

    _set_master(monkeypatch)
    # 无凭证 / 坏会话 → 401
    with pytest.raises(HTTPException) as err1:
        await deps._auth(creds=None)
    assert err1.value.status_code == 401
    with pytest.raises(HTTPException) as err2:
        await deps._auth(creds=SimpleNamespace(credentials="not-a-session"))
    assert err2.value.status_code == 401

    # 主令牌不能直接当会话用（只能走登录端点）
    with pytest.raises(HTTPException) as err3:
        await deps._auth(creds=SimpleNamespace(credentials=MASTER))
    assert err3.value.status_code == 401

    # 有效会话令牌 → 放行并原样返回
    token = session_store.create_session(600)
    assert await deps._auth(creds=SimpleNamespace(credentials=token)) == token

    # 过期会话 → 401
    monkeypatch.setattr(session_store, "time", SimpleNamespace(monotonic=lambda: time.monotonic() + 10_000))
    with pytest.raises(HTTPException) as err4:
        await deps._auth(creds=SimpleNamespace(credentials=token))
    assert err4.value.status_code == 401


async def test_query_session_endpoint(monkeypatch):
    _set_master(monkeypatch)
    token = session_store.create_session(600)
    deps._require_session(token)

    with pytest.raises(HTTPException) as err:
        deps._require_session("bad")
    assert err.value.status_code == 401

    _set_config(monkeypatch, {})
    with pytest.raises(HTTPException) as err2:
        deps._require_session(token)
    assert err2.value.status_code == 503


class _FakeWS:
    def __init__(self) -> None:
        self.accepted = False
        self.closed: int | None = None

    async def accept(self) -> None:
        self.accepted = True

    async def close(self, code: int = 1000) -> None:
        self.closed = code


async def test_ws_auth_and_live_recheck(monkeypatch):
    _set_master(monkeypatch)

    ws_bad = _FakeWS()
    assert await deps._ws_auth(ws_bad, "bad-session") is None
    assert ws_bad.accepted and ws_bad.closed == 4401

    ws_master = _FakeWS()
    assert await deps._ws_auth(ws_master, MASTER) is None  # 主令牌不能直连 WS
    assert ws_master.closed == 4401

    token = session_store.create_session(600)
    ws_ok = _FakeWS()
    session_ref = await deps._ws_auth(ws_ok, token)
    assert session_ref == session_store.token_digest(token)
    assert await deps._ensure_ws_session(ws_ok, session_ref) is True

    # 会话被吊销后，长连接复验应立即断开
    session_store.revoke_session(token)
    assert await deps._ensure_ws_session(ws_ok, session_ref) is False
    assert ws_ok.closed == 4401


async def test_ws_ticket_single_use_and_revocation(monkeypatch):
    """WS 一次性票据：握手成功后即失效；会话吊销后不能再签发"""
    _set_master(monkeypatch)
    token = session_store.create_session(600)

    ticket = session_store.create_ws_ticket(token)
    assert ticket

    ws_ok = _FakeWS()
    assert await deps._ws_auth(ws_ok, ticket=ticket) == session_store.token_digest(token)

    # 单次使用：同一张票再次握手必须失败
    ws_reuse = _FakeWS()
    assert await deps._ws_auth(ws_reuse, ticket=ticket) is None
    assert ws_reuse.closed == 4401

    session_store.revoke_session(token)
    assert session_store.create_ws_ticket(token) is None


def test_ws_ticket_expiry(monkeypatch):
    clock = {"now": 1000.0}
    monkeypatch.setattr(session_store, "time", SimpleNamespace(monotonic=lambda: clock["now"]))

    token = session_store.create_session(600)
    ticket = session_store.create_ws_ticket(token, ttl_seconds=30)
    assert ticket
    clock["now"] += 31
    assert session_store.consume_ws_ticket(ticket) is None


# ---------- 会话存储 ----------


def test_session_store_expiry_and_revoke(monkeypatch):
    clock = {"now": 1000.0}
    monkeypatch.setattr(session_store, "time", SimpleNamespace(monotonic=lambda: clock["now"]))

    token = session_store.create_session(60)
    assert session_store.validate_session(token) is True
    clock["now"] += 59
    assert session_store.validate_session(token) is True
    clock["now"] += 2
    assert session_store.validate_session(token) is False
    assert session_store.session_count() == 0

    token2 = session_store.create_session(60)
    assert session_store.revoke_session(token2) is True
    assert session_store.revoke_session(token2) is False
    assert session_store.validate_session(token2) is False


def test_session_store_capacity_evicts_earliest(monkeypatch):
    clock = {"now": 1000.0}
    monkeypatch.setattr(session_store, "time", SimpleNamespace(monotonic=lambda: clock["now"]))

    tokens = [session_store.create_session(600) for _ in range(session_store.MAX_SESSIONS + 1)]
    assert session_store.session_count() == session_store.MAX_SESSIONS
    assert session_store.validate_session(tokens[0]) is False  # 最早签发/最早到期者被逐出
    assert session_store.validate_session(tokens[-1]) is True


def test_session_store_keeps_digest_only():
    token = session_store.create_session(60)
    assert token not in session_store._sessions
    assert session_store._sessions  # 表里存的是摘要而非明文


# ---------- 主令牌读取：弱口令告警 / 轮换清空 / TTL ----------


def test_weak_token_warning_once(monkeypatch, caplog):
    _set_config(monkeypatch, {"web_panel": {"access_token": "short"}})
    with caplog.at_level(logging.WARNING, logger="atri-bot.WebPanel"):
        deps._access_token()
        deps._access_token()
    assert sum("过弱" in r.getMessage() for r in caplog.records) == 1


def test_weak_token_warning_when_matches_platform(monkeypatch, caplog):
    _set_config(
        monkeypatch,
        {
            "web_panel": {"access_token": "platform-shared-token-123"},
            "platforms": {"napcat": {"access_token": "platform-shared-token-123"}},
        },
    )
    with caplog.at_level(logging.WARNING, logger="atri-bot.WebPanel"):
        deps._access_token()
    assert any("与平台 napcat 的 access_token 相同" in r.getMessage() for r in caplog.records)


def test_master_rotation_revokes_sessions(monkeypatch):
    _set_master(monkeypatch, "old-master-token-1234567890")
    assert deps._access_token() == "old-master-token-1234567890"
    token = session_store.create_session(600)
    assert session_store.validate_session(token) is True

    # 改配置（轮换主令牌）→ 下一次读取时清空全部旧会话
    _set_master(monkeypatch, "new-master-token-0987654321")
    assert deps._access_token() == "new-master-token-0987654321"
    assert session_store.validate_session(token) is False


def test_no_platform_token_fallback(monkeypatch):
    _set_config(monkeypatch, {"platforms": {"napcat": {"access_token": "ATRI114514"}}})
    assert deps._access_token() is None
    monkeypatch.setenv("ATRI_PANEL_TOKEN", "env-master-token-1234567890")
    assert deps._access_token() == "env-master-token-1234567890"


def test_session_ttl_config_clamped(monkeypatch):
    _set_config(monkeypatch, {"web_panel": {"access_token": MASTER}})
    assert deps._session_ttl_seconds() == 4 * 3600
    _set_config(monkeypatch, {"web_panel": {"session_ttl_hours": 0.5}})
    assert deps._session_ttl_seconds() == 3600
    _set_config(monkeypatch, {"web_panel": {"session_ttl_hours": 99}})
    assert deps._session_ttl_seconds() == 24 * 3600
    _set_config(monkeypatch, {"web_panel": {"session_ttl_hours": "bad"}})
    assert deps._session_ttl_seconds() == 4 * 3600


# ---------- 端点防护不变量 ----------


def test_all_api_routes_require_session_auth():
    """除登录/logo 白名单外，所有 HTTP API 路由必须挂 _auth 依赖"""
    from fastapi.routing import APIRoute

    from atribot.web_panel.routes import all_routers

    # 该 FastAPI 版本 include_router 为惰性（_IncludedRouter 占位），故直接遍历各子路由
    # 媒体端点（img/audio 标签无法带 Header）在函数体内调用 _require_session 校验会话，
    # 不通过依赖项；白名单外的路由必须显式挂 _auth。
    query_token_endpoints = {"/admin/api/chat/files/{file_id}", "/admin/api/chat/avatar"}
    exempt = {"/admin/api/login", "/admin/api/panel/logo"} | query_token_endpoints
    checked = 0
    for sub_router in all_routers:
        for route in sub_router.routes:
            if not isinstance(route, APIRoute):
                continue
            path = "/admin" + route.path
            if path in exempt:
                continue
            calls = [dependency.call for dependency in route.dependant.dependencies]
            assert deps._auth in calls, f"缺少鉴权依赖: {path}"
            checked += 1
    assert checked >= 45
