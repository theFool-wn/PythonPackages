# @             Project: WeComMessager -> cli.py
# @     Release Version: 0.2.0
# @              Author: WangNan
# @       Creation Date: 2026/10/21
# @         Description: Send a WeCom application message from the command line
# @ Version Information: Created by WangNan, 2026/10/21, organized into a Python package
# ===================================================================================


"""Send one WeCom application message from a private JSON configuration file."""


from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .client import WeComError, WeComMessenger


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="发送一条企业微信应用消息")
    parser.add_argument("content", help="文本内容，或本地图片/语音/视频/文件路径")
    parser.add_argument("--config", required=True, help="私有配置 JSON 路径 (corp_id, corp_secret, agent_id, user_id)")
    parser.add_argument("--to-user", help="临时指定接收人的 UserID")
    parser.add_argument("--kind", choices=("text", "markdown", "image", "voice", "video", "file"), default="text", help="消息类型，默认 text")
    parser.add_argument("--markdown", action="store_true", help="等同于 --kind markdown")
    parser.add_argument("--title", help="视频标题，至多 128 字节")
    parser.add_argument("--description", help="视频描述，至多 512 字节")
    args = parser.parse_args(argv)

    try:
        if args.markdown and args.kind not in {"text", "markdown"}:
            raise ValueError("--markdown 不能与其他 --kind 类型一起使用")
        config = json.loads(Path(args.config).read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            raise ValueError("配置必须是 JSON 对象")
        with WeComMessenger(**config) as messenger:
            messenger.send(
                args.content,
                kind="markdown" if args.markdown else args.kind,
                to_user=args.to_user,
                title=args.title,
                description=args.description,
            )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"配置或参数错误：{exc}", file=sys.stderr)
        return 2
    except WeComError as exc:
        print(f"发送失败：{exc}", file=sys.stderr)
        return 1
    print("消息发送成功")
    return 0
