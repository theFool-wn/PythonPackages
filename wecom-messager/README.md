# WeComMessager

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0.html)  [![Made by Wang Nan](https://img.shields.io/badge/Made%20by-Wang%20Nan-brightgreen)](https://github.com/theFool-wn)  ![Python](https://img.shields.io/badge/Python-3.9+-orange)  ![Version](https://img.shields.io/badge/version-0.2.0-blueviolet)

企业微信自建应用消息发送。支持文本、Markdown、Unicode 表情、静态图片表情、图片、语音、视频和文件；支持不同企业或收件人的多个实例；VPN 开启或关闭时自动尝试可用网络路径。

## 安装

* 需要 Python 3.9 或更新版本。Windows 和其他系统都可使用；物理网卡备用路径仅在 Windows 上生效。
* 准备企业 ID、自建应用的 Secret 与 AgentID，以及接收人的 UserID。这里要填企业微信成员的 UserID，不是显示昵称。
* 接收人应在应用可见范围内。如果应用设置了企业可信 IP，发送请求使用的出口 IP 也必须在允许范围内。
```cmd
python -m pip install wecom-messager
```

## 快速开始

```python
from WeComMessager import WeComMessenger

with WeComMessenger(
    corp_id="企业 ID",
    corp_secret="自建应用 Secret",
    agent_id=123456,
    user_id="接收人的 UserID",
) as messenger:
    messenger.send_text("任务完成")
    messenger.send_markdown("**任务完成**")
    messenger.send_text("发给另一位成员", to_user="另一位成员的 UserID")
```
`user_id` 是默认收件人；`to_user` 只覆盖本次发送。`with` 结束时会关闭网络连接。如未使用 `with`，需调用 `messenger.close()`。

## 初始化参数

```python
WeComMessenger(corp_id, corp_secret, agent_id, user_id, *, proxy_url=None, timeout=10)
```

| 参数          | 允许值                                                       | 说明                                                         |
| ------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| `corp_id`     | 非空字符串                                                   | 企业 ID                                                    |
| `corp_secret` | 非空字符串                                                   | 与应用对应的 Secret                                        |
| `agent_id`    | 正整数，或仅含十进制数字的字符串                             | 应用 AgentID；不接受 `0`、负数或布尔值，建议整数         |
| `user_id`     | 非空字符串                                                   | 默认接收人的 UserID                                        |
| `proxy_url`   | `None` 或以 `http://`、`https://`、`socks5://`、`socks5h://` 开头的代理 URL | 可选，默认 `None`；例如 `http://127.0.0.1:7890`，使用 VPN 时通常无需手动填写 |
| `timeout`     | 大于 `0` 的整数或浮点数                                      | 单次连接和读取的超时秒数，默认 `10` |

初始化参数不符合要求时会抛出 `ValueError`。允许`corp_id`、`corp_secret`、`agent_id` 和 `user_id` 在不同实例中分别存在。

## 消息类型与方法

 `WeComMessenger` 实例的方法。成功时返回 `True`；所有方法都可用 `to_user="其他UserID"` 指定本次收件人。

| 方法                                                         | 内容要求                                                     | 消息形式       |
| ------------------------------------------------------------ | ------------------------------------------------------------ | -------------- |
| `send_text(content, to_user=None)`                           | 非空字符串；UTF-8 编码后最多 **2048 字节**。                 | 文本。         |
| `send_markdown(content, to_user=None)`                       | 非空字符串；UTF-8 编码后最多 **2048 字节**；使用企业微信支持的 Markdown 语法。 | Markdown。     |
| `send_emoji(emoji, to_user=None)`                            | Unicode 表情字符，也受文本长度限制。                         | 含表情的文本。 |
| `send_image(path, to_user=None)`                             | 本地 `.jpg`、`.jpeg` 或 `.png`；大于 5 字节且不超过 **2,000,000 字节**。 | 图片。         |
| `send_sticker(path, to_user=None)`                           | 与 `send_image` 相同，适用于静态 JPG/PNG 表情图。            | 图片。         |
| `send_voice(path, to_user=None)`                             | 本地 `.amr`；大于 5 字节且不超过 **2,000,000 字节**，时长不超过 60 秒。 | 语音。         |
| `send_video(path, to_user=None, *, title=None, description=None)` | 本地 `.mp4`；大于 5 字节且不超过 **10,000,000 字节**。       | 视频。         |
| `send_file(path, to_user=None)`                              | 本地文件；大于 5 字节且不超过 **20,000,000 字节**。          | 文件附件。     |

`path` 可以是路径字符串或 `pathlib.Path`。相对路径以运行程序时的工作目录为准。`send_video` 的 `title` 最多 128 个 UTF-8 字节，`description` 最多 512 个 UTF-8 字节，均可省略。语音时长由企业微信接口判断，超过限制时可能返回错误码 `45007`。

`send_sticker` 发送的是静态图片；动态 GIF 可用 `send_file("sticker.gif")` 作为附件发送。`send_emoji` 使用文本消息发送 Unicode 表情。

```python
with WeComMessenger("企业 ID", "应用 Secret", 123456, "UserA") as messenger:
    messenger.send_image("C:/private/photo.png")
    messenger.send_voice("C:/private/voice.amr")
    messenger.send_video("C:/private/video.mp4", title="会议录像", description="今日会议")
    messenger.send_file("C:/private/report.pdf", to_user="UserB")
```

## 多个实例与单次发送

同一程序可创建两个以上实例，分别对应不同企业、应用或默认接收人：

```python
from WeComMessager import WeComMessenger

with WeComMessenger("企业 A 的 ID", "应用 A 的 Secret", 100001, "UserA") as sender_a:
    with WeComMessenger("企业 B 的 ID", "应用 B 的 Secret", 100002, "UserB") as sender_b:
        sender_a.send_text("给 A 的消息")
        sender_b.send_text("给 B 的消息")
```

只发送一条文本时，可使用模块级便捷函数：

```python
from WeComMessager import send_text

send_text(
    "任务完成",
    corp_id="企业 ID",
    corp_secret="应用 Secret",
    agent_id=123456,
    user_id="接收人的 UserID",
)
```

便捷函数还接受可选的 `proxy_url`，但没有 `timeout` 或 `to_user` 参数；需要这些参数时请创建实例。

## 命令行

命令行从 UTF-8 JSON 文件读取连接参数：

```json
{
    "corp_id": "YOUR_CORP_ID",
    "corp_secret": "YOUR_APP_SECRET",
    "agent_id": 123456,
    "user_id": "YOUR_USER_ID"
}
```
可选字段为 `proxy_url` 和 `timeout`

```cmd
WeComMessager --config "C:/private/secret.json" "你好"
WeComMessager --config "C:/private/secret.json" --kind markdown "**任务完成**"
WeComMessager --config "C:/private/secret.json" --to-user "UserB" "发给另一位成员"
WeComMessager --config "C:/private/secret.json" --kind image "C:/private/photo.png"
WeComMessager --config "C:/private/secret.json" --kind voice "C:/private/voice.amr"
WeComMessager --config "C:/private/secret.json" --kind video --title "会议录像" --description "今日会议" "C:/private/video.mp4"
WeComMessager --config "C:/private/secret.json" --kind file "C:/private/report.pdf"
```
或使用 
```cmd
python -m WeComMessager --config "C:/private/secret.json" "你好"
```

| 参数            | 是否必填 | 取值与用途                                           |
| --------------- | -------- | -------------------------------------------------- |
| `content`       | 是       | 位置参数；文本内容或本地媒体文件路径。绝对或相对文件路径 |
| `--config`      | 是       | UTF-8 JSON 配置文件路径                             |
| `--kind`        | 否       | `text`、`markdown`、`image`、`voice`、`video`、`file`；默认 `text` |
| `--markdown`    | 否       | 等同于 `--kind markdown`；不能与其他非文本类型的 `--kind` 同用 |
| `--to-user`     | 否       | 覆盖 JSON 中默认接收人的 UserID，仅影响本次发送           |
| `--title`       | 否       | 视频标题，最多 128 个 UTF-8 字节                      |
| `--description` | 否       | 视频描述，最多 512 个 UTF-8 字节                      |

Unicode 表情作为普通文本发送；静态表情图用 `--kind image`，动态 GIF 附件用 `--kind file`。退出码 `0` 表示成功，`1` 表示发送失败，`2` 表示配置或参数错误。在 CMD 中执行命令后，可用 `echo %ERRORLEVEL%` 查看退出码。

## 错误处理与网络

参数、文件格式或大小不符合要求时抛出 `ValueError`；接口拒绝或网络发送失败时抛出 `WeComError`：

```python
from WeComMessager import WeComError, WeComMessenger

try:
    with WeComMessenger("企业 ID", "应用 Secret", 123456, "UserA") as messenger:
        messenger.send_text("任务完成")
except ValueError as exc:
    print(f"参数错误：{exc}")
except WeComError as exc:
    print(f"发送失败：{exc}")
    print(f"企业微信错误码：{exc.code}")  # 网络错误等情况可能为 None
    if exc.delivery_unknown:
        print("送达结果不确定；先向收件人核实，再决定是否重发")
    if exc.partial_delivery:
        print("部分收件人可能已收到；先核对收件情况")
```

| 常见错误码                         | 常见原因                                 |
| ---------------------------------- | ---------------------------------------- |
| `40001`、`40013`、`40056`          | 应用 Secret、企业 ID 或 AgentID 不正确。 |
| `40003`、`40031`、`60021`、`81013` | UserID 无效，或成员不在应用可见范围内。  |
| `60020`                            | 请求的出口 IP 不在企业可信 IP 列表中。   |
| `45001`、`45002`、`45007`          | 素材大小、文本长度或语音时长超过限制。   |
| `45009`                            | 接口调用频率超过限制。                   |

出现 `60020` 时，请核对企业微信后台的可信 IP 设置。

`WeComError.delivery_unknown=True` 表示请求是否送达无法确认；程序不会自动重发，以免产生重复消息。`partial_delivery=True` 表示企业微信报告部分接收人未收到，其他人可能已经收到，也应先核对再重发。

发送时会尝试可用的直连、系统代理及 Windows 上的物理网卡路径；设置 `proxy_url` 后先尝试指定代理。VPN 开启或关闭都使用同一套接口，但如果 VPN 阻断所有出口，或可用出口都不符合企业可信 IP 设置，仍可能发送失败。

## Refenences

* [企业微信发送应用消息](https://developer.work.weixin.qq.com/document/path/90236)
* [企业微信临时素材](https://developer.work.weixin.qq.com/document/path/90253)

## License

This project is licensed under the **[GNU Affero General Public License v3.0 (AGPL-3.0)](https://www.gnu.org/licenses/agpl-3.0.html)**.

You are free to **use, modify, and distribute** this project, including for commercial purposes, provided that:

* You **retain the copyright and license notices**.
* You **distribute modified versions under the same license**.
* You **make the corresponding source code available** as required by the AGPL-3.0, including when modified software is used to provide a network service.

See the [LICENSE](/LICENSE) file for details.

Copyright (c) 2026 Wang Nan
