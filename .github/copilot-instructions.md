# ATRI-bot AI Coding Instructions

## Architecture Overview
- **Core Framework**: `main.py` is the entry point, resolving to `atribot/bot_framework.py` which handles initialization. The project uses a central service container (`atribot/core/service_container.py`) for dependency injection.
- **Service Registration**: Access shared instances via `container.get("ServiceName")`. Common names: `log`, `config`, `database`, `SendMessage`, `LLMSupplier`, `CommandSystem`, `memirySystem` (note the spelling!), `SandBox`, `SkillsManager`.
- **Message Flow**: `NapCat` (External) -> `WebSocketClient` -> `message_router` -> `CommandSystem` or `LLMCoordinator`.
- **Database**: PostgreSQL with `pgvector` used for standard db operations and RAG. All DB operations are asynchronous (see `atribot/core/db/`).

## Key Extension Patterns

### 1. Adding New Commands
- Locate in `atribot/commands/<category>/`. Group related commands under `__init__.py` or specific files.
- Use the `@cmd_system.register_command` decorator from `container.get("CommandSystem")`.
- **Example Pattern**:
  ```python
  from atribot.core.service_container import container

  cmd_system = container.get("CommandSystem")
  send_message = container.get("SendMessage")

  @cmd_system.register_command(name="cmd", description="...", authority_level=1)
  @cmd_system.argument(name="param", description="...", required=True)
  async def handler(message_data: dict, param: str):
      group_id = message_data.get('group_id')
      await send_message.send_group_msg(group_id, f"Response: {param}")
  ```

### 2. LLM Tooling (Function Calling)
- Define tools in `atribot/LLMchat/tools/` as directories containing an `__init__.py`.
- Each tool must export a `tool_json` (OpenAI format with properties) and an `async def main(...)` function matching the parameters defined in `tool_json`.
- Tools automatically receive parameters defined in their `tool_json` and are exposed to the `LLMCoordinator`.

### 3. MCP & Skills
- **MCP Servers/Tools**: Registered in `atribot/LLMchat/MCP/` and managed by `FuncCall`.
- **Agent Skills**: Markdown files placed in `atribot/LLMchat/skills/agent_skills/` to inject custom prompts/systems using `SkillsManager`.

### 4. SandBox Environment
- The project includes a Docker-based sandbox (`atribot/LLMchat/sandbox/docker_sandbox.py`) for the AI to execute code securely.
- Handled by the `SandBox` service from the container.

## Coding Standards
- **Asynchronous First**: Use `async/await` for IO-bound tasks (DB, Network, LLM APIs).
- **Paths**: Use `container.get("config").file_path.document_root` to build absolute paths for assets/logs instead of using relative ones.
- **Logging**: Use the system logger: `log = container.get("log")`.
- **Typing**: Use type hints for all parameters and return types.

## Critical Developer Workflows
- **Running the Bot**: Use `uv run main.py` or `python main.py` from the **project root directory** to avoid path resolution errors.
- **Database Schema**: Reference `docker/db/info.sql` before altering persistence logic. All tables should be initially specified here.
- **Config Management**: Base settings are in `assets/config.json` and `assets/supplier_config.json`, wrapping via `atriConfig`.
- **RAG/Memory**: Memory operations are in `atribot/LLMchat/memory/`. Use `container.get("memirySystem")` (with an "i") for knowledge retrieval.
