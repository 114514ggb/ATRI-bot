# Copilot Instructions for ATRI-main

## 项目架构概览
- 该项目为多组件 AI 聊天/管理系统，核心目录有：
  - `atribot/LLMchat/`：大语言模型聊天、提示词构建、API 管理、表情系统等
  - `atribot/core/`：配置、数据管理、日志、消息上下文、服务容器等基础设施
  - `assets/`：配置和数据文件（如 SQL、JSON 配置）
  - `document/`：音频、图片、文档等素材资源
- 主要通过依赖注入（`container.get(...)`）管理各服务实例，便于解耦和扩展。
- 聊天主流程以 `chat_baseics`（抽象基类）为核心，`group_chat` 为群聊实现，负责消息处理、上下文维护、API 降级等。

## 关键开发工作流
- 启动服务：
  ```bash
  nohup ./run_atri.sh > /dev/null 2>&1 &
  ps aux | grep main.py
  ```
- 配置项主要集中在 `assets/config.json` 和 `atribot/core/atri_config.py`。
- 依赖管理：使用 `requirements.txt` 和 `pyproject.toml`，如需新包请同步两处。
- 日志输出在 `log/` 目录，按日期分文件。

## 代码风格与约定
- 聊天相关类需继承 `chat_baseics`，实现 `step`、`prompt_structure`、`send_reply_message` 等方法。
- 服务获取统一用 `container.get("ServiceName")`，如 `container.get("LLMsupervisor")`。
- 配置、上下文、缓存等均通过依赖注入获取，避免直接实例化。
- API 降级（fallback）机制见 `group_chat._try_model_request`，遍历备用模型参数自动切换。
- 消息分段、表情标签处理见 `emoji_core` 相关方法。

## 集成与扩展
- 新增模型/供应商需在配置文件和 `ai_connection_manager` 注册，并在 `config.model.standby_model` 配置备用。
- 新增命令、工具建议放在 `atribot/commands/` 或 `atribot/LLMchat/tools/`。
- 资源文件（如图片、音频）统一放在 `document/` 下对应子目录。

## 重要文件/目录参考
- `atribot/LLMchat/chat.py`：群聊主逻辑、API 调用、消息处理范例
- `atribot/core/service_container.py`：依赖注入容器实现
- `assets/config.json`：主要配置项
- `run_atri.sh`：服务启动脚本

## 其他说明
- 项目大量使用异步（async/await），注意方法签名和调用方式。
- 若需调试/测试，建议新建脚本于根目录或 `test.py`，避免污染主流程
