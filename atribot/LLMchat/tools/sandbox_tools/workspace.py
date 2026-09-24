"""沙盒内会话工作区的统一路径规则

群聊按群号隔离、私聊按用户隔离，两者都挂在沙盒后端的工作区根目录下：

```
{work_dir}/groups/<群号>/data      群聊持久化数据目录
{work_dir}/private/<QQ号>/data     私聊持久化数据目录
{work_dir}/groups/<群号>/tmp       群聊临时执行目录(执行后清理)
{work_dir}/private/<QQ号>/tmp      私聊临时执行目录(执行后清理)
{work_dir}/shared                  全局共享目录
```

- 隔离后端(docker)：根目录为容器内固定的 ``/workspace``
- 本地后端(no-sandbox)：根目录默认落在项目 ``document/work``，可用
  ``sand_box.work_dir`` 覆盖
"""

from atribot.LLMchat.tools.sandbox_tools.runtime import work_dir


def session_dirs(group_id: int | None, user_id: int | None = None) -> tuple[str, str, str, str]:
    """返回会话工作区路由信息

    群聊按群号隔离: {work_dir}/groups/<群号>/
    私聊按用户隔离: {work_dir}/private/<QQ号>/
    执行结束后只清理 tmp/run_{uuid} 临时目录,data/ 目录永久保留

    Returns:
        tuple: (data_dir, shared_dir, session_type, session_id)
    """
    root = work_dir()
    if group_id is not None:
        session_type, session_id = "group", str(group_id)
    else:
        session_type = "private"
        session_id = str(user_id) if user_id is not None else "anonymous"
    session_root = f"{root}/{'groups' if session_type == 'group' else 'private'}/{session_id}"
    return f"{session_root}/data", f"{root}/shared", session_type, session_id


def session_workspace(group_id: int | None, user_id: int | None = None) -> str:
    """返回会话(群/私聊用户)的持久化数据目录(沙盒内绝对路径)"""
    return session_dirs(group_id, user_id)[0]


def session_tmp_dir(group_id: int | None, user_id: int | None = None) -> str:
    """返回会话临时目录(其下按执行批次创建 ``run_<id>``)"""
    data_dir = session_workspace(group_id, user_id)
    return f"{data_dir.rsplit('/', 1)[0]}/tmp"