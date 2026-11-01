# @             Project: BuaaNetworkAutoLogin -> monitor.py
# @     Release Version: 0.2.0
# @              Author: WangNan
# @       Creation Date: 2025/10/9 15:01
# @         Description: Recheck internet access and send scheduled status notices
# @ Version Information: Created by WangNan, 2025/10/9
#                        Revised by WangNan, 2026/10/21
# ===================================================================================


"""Repeated checks, reconnect notifications, and timed health reports."""


from __future__ import annotations

import re
import time

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime, time as clock_time, timedelta
from pathlib import Path
from typing import Any, Callable

from .logs import DEFAULT_LOG_PATH, append_result, validate_log_path
from .service import LoginResult, _notification_error, _send_notification, ensure_online


def _parse_notification_times(values: str | Sequence[str] | None) -> tuple[clock_time, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        values = (values,)
    if not isinstance(values, Sequence) or not values:
        raise ValueError("notification_times 需要 HH:MM 时间或非空时间列表")
    parsed = set()
    for value in values:
        if not isinstance(value, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
            raise ValueError("notification_times 的时间格式必须为 HH:MM")
        parsed.add(clock_time(int(value[:2]), int(value[3:])))
    return tuple(sorted(parsed))


def _next_notification_at(after: datetime, times: tuple[clock_time, ...]) -> datetime:
    for notice_time in times:
        candidate = datetime.combine(after.date(), notice_time)
        if candidate > after:
            return candidate
    return datetime.combine(after.date() + timedelta(days=1), times[0])


def _possibly_delivered(exc: Exception) -> bool:
    """Do not retry automatically when a message might have reached a recipient."""
    return bool(getattr(exc, "delivery_unknown", False) or getattr(exc, "partial_delivery", False))


def watch_online(
    username: str,
    password: str,
    *,
    notify: bool = False,
    wecom: dict[str, Any] | None = None,
    messenger: Any = None,
    interval_seconds: int = 600,
    heartbeat_seconds: int = 21600,
    notification_times: str | Sequence[str] | None = None,
    restore_message: str | None = None,
    heartbeat_message: str = "校园网连接正常",
    failure_message: str | None = "校园网连接异常：{reason}",
    notification_format: str = "text",
    log_path: str | Path | None = DEFAULT_LOG_PATH,
    verify_tls: bool = True,
    on_result: Callable[[LoginResult], None] | None = None,
) -> None:
    """
    Check every ten minutes by default until interrupted.

    When notifications are enabled, send on reconnection and after each six
    hours of healthy internet by default. ``notification_times`` switches to
    daily local-clock times such as ("08:00", "20:00"). A scheduled message
    goes out on the first successful check at or after that time.
    """
    validate_log_path(log_path)
    if isinstance(interval_seconds, bool) or not isinstance(interval_seconds, int) or interval_seconds < 30:
        raise ValueError("interval_seconds 必须至少 30")
    scheduled_times = _parse_notification_times(notification_times)
    if isinstance(heartbeat_seconds, bool) or not isinstance(heartbeat_seconds, int) or heartbeat_seconds <= 0:
        raise ValueError("heartbeat_seconds 必须是正整数")
    if not scheduled_times and heartbeat_seconds < interval_seconds:
        raise ValueError("heartbeat_seconds 不能小于 interval_seconds")
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        raise ValueError("需要填写北航统一认证账号和密码")
    if not isinstance(notify, bool):
        raise ValueError("notify 必须是 bool")
    if wecom is not None and not isinstance(wecom, dict):
        raise ValueError("wecom 必须是企业微信参数字典")
    if notify and not (wecom or messenger):
        raise ValueError("notify=True 时需要填写 wecom 参数或传入 messenger")
    if notification_format not in {"text", "markdown"}:
        raise ValueError("notification_format 只能是 text 或 markdown")
    for name, value in (("restore_message", restore_message), ("heartbeat_message", heartbeat_message),
                        ("failure_message", failure_message)):
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"{name} 必须是非空字符串，failure_message 也可以是 None")

    last_status_message = time.monotonic()
    next_notification = _next_notification_at(datetime.now(), scheduled_times) if scheduled_times else None
    last_failure_status: str | None = None
    was_offline = False
    pending_restore_text: str | None = None
    while True:
        try:
            result = ensure_online(username, password, notify=False, verify_tls=verify_tls, log_path=None)
        except Exception as exc:
            result = LoginResult("check_error", f"联网检查失败（{type(exc).__name__}）；稍后重试", False, False)
        now = time.monotonic()
        if next_notification is not None:
            clock_now = datetime.now()
            notification_due = clock_now >= next_notification
        else:
            notification_due = now - last_status_message >= heartbeat_seconds
        if not result.internet_available:
            was_offline = True
            pending_restore_text = None
            last_status_message = now
            if notify and failure_message is not None and result.campus_detected and result.status != last_failure_status:
                try:
                    message = failure_message.replace("{reason}", result.message)
                    _send_notification(message, wecom, messenger, notification_format)
                    result = replace(result, message=result.message + "；故障通知已发送", notification_sent=True)
                except Exception as exc:
                    result = replace(result, message=result.message + f"；故障通知失败（{_notification_error(exc)}）")
                    if _possibly_delivered(exc):
                        last_failure_status = result.status
                else:
                    last_failure_status = result.status
            elif not result.campus_detected:
                last_failure_status = None
        else:
            last_failure_status = None
            if result.status == "restored" or was_offline:
                pending_restore_text = restore_message or (
                    result.message if result.status == "restored" else "互联网连接已恢复"
                )
                was_offline = False
            if pending_restore_text is not None:
                retry_safe = True
                if notify:
                    try:
                        _send_notification(pending_restore_text, wecom, messenger, notification_format)
                        result = replace(result, message=result.message + "；恢复通知已发送", notification_sent=True)
                    except Exception as exc:
                        result = replace(result, message=result.message + f"；恢复通知失败（{_notification_error(exc)}）")
                        retry_safe = not _possibly_delivered(exc)
                if not notify or result.notification_sent or not retry_safe:
                    pending_restore_text = None
                    last_status_message = now
                    if notification_due and next_notification is not None:
                        next_notification = _next_notification_at(clock_now, scheduled_times)
            elif notify and notification_due:
                retry_safe = True
                try:
                    _send_notification(heartbeat_message, wecom, messenger, notification_format)
                    result = replace(result, message=result.message + "；状态通知已发送", notification_sent=True)
                except Exception as exc:
                    result = replace(result, message=result.message + f"；状态通知失败（{_notification_error(exc)}）")
                    retry_safe = not _possibly_delivered(exc)
                if result.notification_sent or not retry_safe:
                    last_status_message = now
                    if next_notification is not None:
                        next_notification = _next_notification_at(clock_now, scheduled_times)
        secrets = [username, password]
        if wecom:
            secrets.extend(wecom.get(key) for key in ("corp_id", "corp_secret", "user_id", "proxy_url"))
        log_error = append_result(result, log_path, secrets)
        if log_error:
            result = replace(result, message=result.message + f"；{log_error}")
        if on_result is not None:
            on_result(result)
        time.sleep(interval_seconds)
