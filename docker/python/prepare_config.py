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


def _parse_bool(value: str) -> bool:
    """解析布尔环境变量值"""
    return value.strip().lower() in {"1", "true", "yes", "on"}


def ensure_platform(config_data: dict[str, Any], name: str) -> None:
    """确保 platforms.<name> 存在，新建平台时给出可用的默认结构"""
    platforms = config_data.setdefault("platforms", {})
    if not isinstance(platforms, dict):
        platforms = {}
        config_data["platforms"] = platforms
    if not isinstance(platforms.get(name), dict):
        platforms[name] = {"adapter": "onebot", "enabled": True}


# ATRI_PLATFORM_<NAME>_<FIELD> 平台字段覆盖：字段名 -> 类型转换函数
_PLATFORM_FIELD_CASTS: dict[str, Callable[[str], Any]] = {
    "adapter": str,
    "connection_type": str,
    "access_token": str,
    "url": str,
    "host": str,
    "port": int,
    "source_name": str,
    "enabled": _parse_bool,
}


def apply_platform_overrides(config_data: dict[str, Any]) -> None:
    """将 ATRI_PLATFORM_<NAME>_<FIELD> 环境变量写入 platforms.<name>.<field>

    字段名支持复合词（如 connection_type、access_token），按已知字段正匹配，
    平台名取剩余前缀（可含下划线）。
    """
    prefix = "ATRI_PLATFORM_"
    for env_name, raw_value in os.environ.items():
        if not env_name.startswith(prefix):
            continue
        suffix = env_name[len(prefix):]
        for field in _PLATFORM_FIELD_CASTS:
            field_suffix = f"_{field.upper()}"
            if not suffix.upper().endswith(field_suffix):
                continue
            platform_name = suffix[: -len(field_suffix)].lower()
            if not platform_name:
                break
            ensure_platform(config_data, platform_name)
            set_nested_value(
                config_data,
                ("platforms", platform_name, field),
                _PLATFORM_FIELD_CASTS[field](raw_value),
            )
            break


def main() -> None:
    source_config_path = Path(os.environ.get("ATRI_SOURCE_CONFIG_PATH", "/app/assets/config.json"))
    runtime_config_path = Path(os.environ.get("ATRI_RUNTIME_CONFIG_PATH", "/tmp/atri-config.runtime.json"))

    config_data = load_json(source_config_path)

    overrides: list[tuple[str, tuple[str, ...], Callable[[str], Any] | None]] = [
        ("ATRI_DOCUMENT_ROOT", ("file_path", "document_root"), None),
        ("ATRI_SUPPLIER_CONFIG_PATH", ("file_path", "relative_to_root", "supplier_config_path"), None),
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

    apply_platform_overrides(config_data)

    runtime_config_path.parent.mkdir(parents=True, exist_ok=True)
    with runtime_config_path.open("w", encoding="utf-8") as file_handler:
        json.dump(config_data, file_handler, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    main()