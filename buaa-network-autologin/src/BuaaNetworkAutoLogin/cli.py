# @             Project: BuaaNetworkAutoLogin -> cli.py
# @     Release Version: 0.2.0
# @              Author: WangNan
# @       Creation Date: 2026/10/21
# @         Description: Command-line access to BUAA network checks and monitoring
# @ Version Information: Created by WangNan, 2026/10/21
# ===================================================================================


"""Command-line entry point for one check or continuous monitoring."""


from __future__ import annotations

import argparse
import sys

from datetime import datetime

from .config import _load_config
from .logs import DEFAULT_LOG_PATH
from .monitor import watch_online
from .service import ensure_online


def main() -> int:
    parser = argparse.ArgumentParser(description="检查并保持 BUAA 校园网联网")
    parser.add_argument("command", choices=("once", "watch"))
    parser.add_argument("--config", required=True, help="私有配置 JSON 路径")
    parser.add_argument("--interval-seconds", type=int, help="覆盖配置中的检查间隔")
    parser.add_argument("--heartbeat-seconds", type=int, help="覆盖配置中的状态通知间隔")
    parser.add_argument("--notification-time", action="append", dest="notification_times", help="每日通知时间 HH:MM，可重复填写")
    parser.add_argument("--log-path", help="覆盖配置中的日志文件路径")
    args = parser.parse_args()
    try:
        config = _load_config(args.config)
        log_path = args.log_path if args.log_path is not None else config.get("log_path", DEFAULT_LOG_PATH)

        def show_result(result):
            print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {result.message}", flush=True)

        common = dict(
            notify=config.get("notify", False), wecom=config.get("wecom"),
            verify_tls=config.get("verify_tls", True),
            restore_message=config.get("restore_message"),
            notification_format=config.get("notification_format", "text"),
            log_path=log_path,
        )
        if args.command == "once":
            result = ensure_online(config["username"], config["password"], **common)
            show_result(result)
            return 0 if result.internet_available else 1

        watch_online(
            config["username"], config["password"], **common,
            interval_seconds=args.interval_seconds if args.interval_seconds is not None else config.get("interval_seconds", 600),
            heartbeat_seconds=args.heartbeat_seconds if args.heartbeat_seconds is not None else config.get("heartbeat_seconds", 21600),
            notification_times=args.notification_times if args.notification_times is not None else config.get("notification_times"),
            heartbeat_message=config.get("heartbeat_message", "校园网连接正常"),
            failure_message=config.get("failure_message", "校园网连接异常：{reason}"),
            on_result=show_result,
        )
        return 0
    except (ValueError, TypeError, OSError, ImportError) as exc:
        print(f"配置或运行错误：{exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
