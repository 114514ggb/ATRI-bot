import json
import os
from pathlib import Path
from typing import Any, Callable


def set_nested_value(data: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current = data
    for key in path[:-1]:
        next_value = current.get(key)
        if not isinstance(next_value, dict):
            next_value = {}
            current[key] = next_value
        current = next_value
    current[path[-1]] = value


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file_handler:
        return json.load(file_handler)


def main() -> None:
    source_config_path = Path(os.environ.get("ATRI_SOURCE_CONFIG_PATH", "/app/assets/config.json"))
    runtime_config_path = Path(os.environ.get("ATRI_RUNTIME_CONFIG_PATH", "/tmp/atri-config.runtime.json"))

    config_data = load_json(source_config_path)

    overrides: list[tuple[str, tuple[str, ...], Callable[[str], Any] | None]] = [
        ("ATRI_DOCUMENT_ROOT", ("file_path", "document_root"), None),
        ("ATRI_SUPPLIER_CONFIG_PATH", ("file_path", "relative_to_root", "supplier_config_path"), None),
        ("ATRI_NETWORK_CONNECTION_TYPE", ("network", "connection_type"), None),
        ("ATRI_NETWORK_URL", ("network", "url"), None),
        ("ATRI_NETWORK_HOST", ("network", "host"), None),
        ("ATRI_NETWORK_SERVER_PORT", ("network", "server_port"), int),
        ("ATRI_NETWORK_ACCESS_TOKEN", ("network", "access_token"), None),
        ("ATRI_DB_HOST", ("database", "host"), None),
        ("ATRI_DB_PORT", ("database", "port"), int),
        ("ATRI_DB_USER", ("database", "user"), None),
        ("ATRI_DB_PASSWORD", ("database", "password"), None),
        ("ATRI_SANDBOX_IMAGE", ("sand_box", "image"), None),
    ]

    for env_name, path, cast in overrides:
        raw_value = os.environ.get(env_name)
        if raw_value is None or raw_value == "":
            continue
        value = cast(raw_value) if cast else raw_value
        set_nested_value(config_data, path, value)

    runtime_config_path.parent.mkdir(parents=True, exist_ok=True)
    with runtime_config_path.open("w", encoding="utf-8") as file_handler:
        json.dump(config_data, file_handler, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    main()