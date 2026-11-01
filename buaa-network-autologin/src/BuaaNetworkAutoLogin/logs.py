# @             Project: BuaaNetworkAutoLogin -> logs.py
# @     Release Version: 0.2.0
# @              Author: WangNan
# @       Creation Date: 2025/10/9 15:01
# @         Description: Write sanitized campus-network status logs
# @ Version Information: Created by WangNan, 2025/10/9
#                        Revised by WangNan, 2026/10/21
# ===================================================================================


"""Small local result log with no credential or notification payload fields."""


from __future__ import annotations

import os

from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


_state_dir = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "state")
DEFAULT_LOG_PATH = _state_dir / "BuaaNetworkAutoLogin" / "BuaaNetworkAutoLogin.log"


def validate_log_path(value: str | os.PathLike[str] | None) -> Path | None:
    """None explicitly disables logging; the omitted API default enables it."""
    if value is None:
        return None
    if not isinstance(value, (str, os.PathLike)) or not str(value).strip():
        raise ValueError("log_path 必须是文件路径，或设为 None 关闭日志")
    return Path(value).expanduser()


def append_result(result: Any, log_path: str | os.PathLike[str] | None, secrets: Iterable[Any] = ()) -> str | None:
    """Return a displayable write error while leaving the network result intact."""
    path = validate_log_path(log_path)
    if path is None:
        return None
    
    # The message includes the outcome and safe error description. Never log
    # custom notification payloads or request bodies; redact known secrets too.
    message = result.message.replace("\r", " ").replace("\n", " ")
    for secret in secrets:
        if secret is not None and str(secret):
            message = message.replace(str(secret), "***")
    line = (
        f"{datetime.now():%Y-%m-%d %H:%M:%S} "
        f"status={result.status} online={int(result.internet_available)} "
        f"campus={int(result.campus_detected)} notified={int(result.notification_sent)} "
        f"{message}\n"
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(line)
    except (OSError, ValueError) as exc:
        return f"日志写入失败（{type(exc).__name__}），路径：{path}"
    return None
