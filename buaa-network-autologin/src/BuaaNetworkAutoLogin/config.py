# @             Project: BuaaNetworkAutoLogin -> config.py
# @     Release Version: 0.2.0
# @              Author: WangNan
# @       Creation Date: 2026/10/21
# @         Description: Load private settings for one-time and continuous checks
# @ Version Information: Created by WangNan, 2026/10/21
# ===================================================================================


"""File-based alternatives to the direct campus-network APIs."""


from __future__ import annotations

import json

from pathlib import Path
from typing import Any, Callable

from .logs import DEFAULT_LOG_PATH
from .monitor import watch_online
from .service import LoginResult, ensure_online


_ALLOWED_KEYS = {
    "username", "password", "notify", "wecom", "verify_tls", "log_path",
    "restore_message", "heartbeat_message", "failure_message",
    "notification_format", "interval_seconds", "heartbeat_seconds", "notification_times",
}


def _load_config(config_path: str | Path) -> dict[str, Any]:
    path = Path(config_path).expanduser()
    try:
        content = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ValueError(f"无法读取配置文件 {path}（{type(exc).__name__}）") from None
    try:
        config = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"配置文件 JSON 格式错误：第 {exc.lineno} 行，第 {exc.colno} 列") from None
    if not isinstance(config, dict):
        raise ValueError("配置文件顶层必须是 JSON 对象")
    unexpected = sorted(set(config) - _ALLOWED_KEYS)
    if unexpected:
        raise ValueError("配置文件包含未知参数：" + ", ".join(unexpected))
    for key in ("username", "password"):
        if not isinstance(config.get(key), str) or not config[key]:
            raise ValueError(f"配置文件需要非空的 {key}")
    if not isinstance(config.get("notify", False), bool):
        raise ValueError("配置文件 notify 必须为 true 或 false")
    if not isinstance(config.get("verify_tls", True), bool):
        raise ValueError("配置文件 verify_tls 必须为 true 或 false")
    if config.get("notify", False) and "wecom" in config:
        wecom = config["wecom"]
        if not isinstance(wecom, dict) or not all(wecom.get(key) for key in ("corp_id", "corp_secret", "agent_id", "user_id")):
            raise ValueError("notify=true 时 wecom 需要 corp_id、corp_secret、agent_id、user_id")
    if "log_path" in config and config["log_path"] is not None:
        log_path = config["log_path"]
        if not isinstance(log_path, str) or not log_path.strip():
            raise ValueError("log_path 必须是文件路径，或设为 null 关闭日志")
        candidate = Path(log_path).expanduser()
        config["log_path"] = candidate if candidate.is_absolute() else path.resolve().parent / candidate
    return config


def ensure_online_from_config(config_path: str | Path, *, messenger: Any = None) -> LoginResult:
    """Read one private JSON file and perform exactly one connectivity check."""
    config = _load_config(config_path)
    return ensure_online(
        config["username"], config["password"],
        notify=config.get("notify", False), wecom=config.get("wecom"), messenger=messenger,
        verify_tls=config.get("verify_tls", True),
        restore_message=config.get("restore_message"),
        notification_format=config.get("notification_format", "text"),
        log_path=config.get("log_path", DEFAULT_LOG_PATH),
    )


def watch_online_from_config(config_path: str | Path, *, messenger: Any = None, on_result: Callable[[LoginResult], None] | None = None) -> None:
    """Read one private JSON file, then check repeatedly until interrupted."""
    config = _load_config(config_path)
    watch_online(
        config["username"], config["password"],
        notify=config.get("notify", False), wecom=config.get("wecom"), messenger=messenger,
        verify_tls=config.get("verify_tls", True),
        interval_seconds=config.get("interval_seconds", 600),
        heartbeat_seconds=config.get("heartbeat_seconds", 21600),
        notification_times=config.get("notification_times"),
        restore_message=config.get("restore_message"),
        heartbeat_message=config.get("heartbeat_message", "校园网连接正常"),
        failure_message=config.get("failure_message", "校园网连接异常：{reason}"),
        notification_format=config.get("notification_format", "text"),
        log_path=config.get("log_path", DEFAULT_LOG_PATH), on_result=on_result,
    )
