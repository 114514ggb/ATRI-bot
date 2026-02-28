# ATRI-bot AI Coding Instructions

## Architecture Overview
- **Core Framework**: `atribot/bot_framework.py` handles initialization. The project uses a central service container (`atribot/core/service_container.py`) for dependency injection.
- **Service Registration**: Access shared instances via `container.get("ServiceName")`. Common names: `log`, `config`, `database`, `SendMessage`, `LLMSupplier`, `CommandSystem`.
- **Message Flow**: `NapCat` (External) -> `WebSocketClient` -> `message_router` -> `CommandSystem` or `LLMCoordinator`.
- **Database**: PostgreSQL with `pgvector`. All DB operations are asynchronous (see `atribot/core/db/`).

## Key Extension Patterns

### 1. Adding New Commands
- Locate in `atribot/commands/`. Group related commands in a class.
- Use `self.command_system.register_command` decoration inside the `__init__` or a registration method.
- **Example Pattern**:
  ```python
  @self.command_system.register_command(name="cmd", description="...", authority_level=1)
  @self.command_system.argument(name="param", description="...", required=True)
  async def handler(message_data: dict, param: str):
      group_id = message_data.get('group_id')
      # Use self.send_message to respond
  ```

### 2. LLM Tooling (Function Calling)
- Define tools in `atribot/LLMchat/tools/` as directories containing an `__init__.py`.
- Each tool must export a `tool_json` (OpenAI format) and an `async def main(...)` function.
- Tools automatically receive parameters defined in their `tool_json`.

### 3. MCP (Model Context Protocol)
- Servers/tools registered in `atribot/LLMchat/MCP/`. Managed by `FuncCall`.

## Coding Standards
- **Asynchronous First**: Use `async/await` for IO-bound tasks (DB, Network, LLM APIs).
- **Paths**: Use `container.get("config").file_path.procedure_root` to build absolute paths for assets/logs.
- **Logging**: Use the system logger: `self.log = container.get("log")`.
- **Typing**: Use type hints for all parameters and return types.

## Critical Workflows
- **Database Schema**: Reference `docker/db/info.sql` before altering persistence logic.
- **Config**: Settings are in `assets/config.json`, accessed via `atriConfig`.
- **RAG/Memory**: Memory operations are in `atribot/LLMchat/memory/`. Use `memorySystem` for knowledge retrieval.
