# BuaaNetworkAutoLogin

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0.html)  [![Made by Wang Nan](https://img.shields.io/badge/Made%20by-Wang%20Nan-brightgreen)](https://github.com/theFool-wn)  ![Python](https://img.shields.io/badge/Python-3.9+-orange)  ![Version](https://img.shields.io/badge/version-0.2.0-blueviolet)

保持北航校园网的互联网连接，支持单次检查、持续监测和可选的企业微信通知。

## 功能

* 默认每 10 分钟检查一次；断线后尝试恢复联网。
* 可在恢复、故障或正常运行时发送通知；正常状态默认每 6 小时通知，也可指定每天的通知时间。
* 通知内容、文本或 Markdown 格式、检查间隔和日志路径均可调整。
* 提供直接传参和读取 JSON 配置文件两种 Python 调用方式，以及命令行方式。

## 安装

* 运行环境：Windows、Python 3.9 或更新版本。
* 准备北航统一认证账号和密码。使用自动恢复功能时，电脑需要有可用的北航校园网环境。
* 默认不发送企业微信消息。需要通知时，还需准备企业微信自建应用的企业 ID、Secret、AgentID 和接收人的 UserID；参数说明见 [WeComMessager 使用文档](../wecom-messager/README.md)。
```cmd
python -m pip install buaa-network-autologin
```

需要企业微信通知时
```cmd
python -m pip install "buaa-network-autologin[wecom]"
```

## 使用

直接传参，检查一次：

```python
from BuaaNetworkAutoLogin import ensure_online

result = ensure_online("校园网账号", "校园网密码")
print(result.status, result.message)
```

直接传参，持续监测：

```python
from BuaaNetworkAutoLogin import watch_online

watch_online(
    "校园网账号", "校园网密码",
    interval_seconds=600,
    on_result=lambda result: print(result.message),
)
```

使用配置文件时，以下两种调用方式按需要选择其一：

```python
from BuaaNetworkAutoLogin import ensure_online_from_config

result = ensure_online_from_config("C:/private/BuaaNetworkAutoLogin.json")
print(result.message)
```

```python
from BuaaNetworkAutoLogin import watch_online_from_config

watch_online_from_config(
    "C:/private/BuaaNetworkAutoLogin.json",
    on_result=lambda result: print(result.message),
)
```

## 参数

下面的通用参数适用于 `ensure_online(username, password, *, ...)` 和 `watch_online(username, password, *, ...)`。

| 参数                  | 允许值与默认值                                         | 说明                                                         |
| --------------------- | ------------------------------------------------------ | ------------------------------------------------------------ |
| `username`            | 非空字符串；必填                                       | 北航校园网账号。                                             |
| `password`            | 非空字符串；必填                                       | 北航校园网密码。                                             |
| `notify`              | `False` 或 `True`；默认 `False`                        | 是否发送企业微信通知。单次检查只在成功恢复互联网时通知；持续监测还可发送故障和正常状态通知。 |
| `wecom`               | 参数字典或 `None`；默认 `None`                         | `notify=True` 时可提供此参数。字典包含 `corp_id`、`corp_secret`、`agent_id`、`user_id`，可选 `proxy_url`、`timeout`。 |
| `messenger`           | 已创建的消息客户端或 `None`；默认 `None`               | `notify=True` 时可传入现有客户端；文本通知需有 `send_text(message)`，Markdown 通知需有 `send_markdown(message)`。与 `wecom` 同时提供时优先使用此客户端。 |
| `verify_tls`          | 布尔值；默认 `True`                                    | 是否校验校园网关的 HTTPS 证书。                              |
| `restore_message`     | 非空字符串或 `None`；默认 `None`                       | 恢复连接时的企业微信通知内容；`None` 使用默认内容，不改变返回结果的说明文字。 |
| `notification_format` | `"text"` 或 `"markdown"`；默认 `"text"`                | 企业微信通知格式。                                           |
| `log_path`            | 路径字符串、`pathlib.Path` 或 `None`；默认本机日志路径 | 文件日志位置；传 `None` 关闭文件日志。直接调用时，相对路径以程序的当前工作目录为准。 |

`watch_online` 另有这些参数：

| 参数                 | 允许值与默认值                                               | 说明                                                         |
| -------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| `interval_seconds`   | 不小于 `30` 的整数；默认 `600`                               | 两次检查之间等待的秒数。                                     |
| `heartbeat_seconds`  | 正整数；默认 `21600`（6 小时）                               | 未指定 `notification_times` 时，正常状态通知的间隔；此时不得小于 `interval_seconds`。 |
| `notification_times` | `None`、一个 `"HH:MM"` 字符串，或非空的时间字符串序列；默认 `None` | 指定后，改为按本机每天的时间发送正常状态通知。例如 `"08:00"` 或 `["08:00", "20:00"]`；小时和分钟均需两位数。 |
| `heartbeat_message`  | 非空字符串；默认 `"校园网连接正常"`                          | 正常状态通知内容。                                           |
| `failure_message`    | 非空字符串或 `None`；默认 `"校园网连接异常：{reason}"`       | 故障通知内容；`{reason}` 会替换为本次检查结果。设为 `None` 可关闭故障通知。 |
| `on_result`          | 接收一个 `LoginResult` 参数的函数，或 `None`；默认 `None`    | 每次检查完成后调用，可用于界面或控制台显示结果。             |

启用通知时，`wecom` 或 `messenger` 至少提供一个。

定时通知只会在检查结果显示互联网可用时发送。如果到点时正在恢复连接，恢复通知可能占用该次检查；后续正常状态通知仍按时间安排。故障通知需要 `notify=True` 且检测到校园网环境；相同故障状态不会在每次检查时无条件重复发送。

### 直接传参并开启通知

```python
from BuaaNetworkAutoLogin import watch_online

watch_online(
    "校园网账号",
    "校园网密码",
    notify=True,
    wecom={
        "corp_id": "企业 ID",
        "corp_secret": "应用 Secret",
        "agent_id": 123456,
        "user_id": "接收人的 UserID",
    },
    interval_seconds=600,
    notification_times=["08:00", "20:00"],
    restore_message="校园网连接已恢复",
    heartbeat_message="互联网连接正常",
    failure_message="校园网异常：{reason}",
    notification_format="text",
    on_result=lambda result: print(result.message),
)
```

## 配置文件接口

`ensure_online_from_config(config_path, *, messenger=None)` 和 `watch_online_from_config(config_path, *, messenger=None, on_result=None)` 分别对应单次检查和持续监测。`config_path` 可为路径字符串或 `pathlib.Path`；`messenger` 和 `on_result` 是 Python 对象，不能写入 JSON。

最小的 UTF-8 JSON 配置如下，可保存为 `C:/private/BuaaNetworkAutoLogin.json`：

```json
{
    "username": "YOUR_BUAA_USERNAME",
    "password": "YOUR_BUAA_PASSWORD"
}
```

企业微信通知配置
```json
{
    "username": "YOUR_BUAA_USERNAME",
    "password": "YOUR_BUAA_PASSWORD",
    "notify": true,
    "wecom": {
        "corp_id": "YOUR_CORP_ID",
        "corp_secret": "YOUR_NEW_APP_SECRET",
        "agent_id": 123456,
        "user_id": "YOUR_USER_ID"
    }
}
```

完整配置
```json
{
    "username": "YOUR_BUAA_USERNAME",
    "password": "YOUR_BUAA_PASSWORD",
    "notify": true,
    "wecom": {
        "corp_id": "YOUR_CORP_ID",
        "corp_secret": "YOUR_APP_SECRET",
        "agent_id": 123456,
        "user_id": "YOUR_USER_ID"
    },
    "verify_tls": true,
    "interval_seconds": 600,
    "notification_times": ["08:00", "20:00"],
    "restore_message": "校园网已恢复，互联网可用",
    "heartbeat_message": "校园网运行正常",
    "failure_message": "校园网连接异常：{reason}",
    "notification_format": "text",
    "log_path": "C:/private/BuaaNetworkAutoLogin.log"
}
```
`username` 和 `password` 必填，其他未知键会报错，持续监测专用的字段对单次检查不起作用。。

JSON 中的布尔值写 `true`、`false`，关闭文件日志写 `"log_path": null`；Python 直接调用则写 `log_path=None`。不要写成带引号的 `"null"` 或 `"None"`，它们会被当作文件路径。省略 `log_path` 会使用默认日志路径；JSON 中的相对日志路径以配置文件所在目录为准。Windows 默认日志位置是 `%LOCALAPPDATA%\BuaaNetworkAutoLogin\BuaaNetworkAutoLogin.log`。

## 命令行

```cmd
BuaaNetworkAutoLogin once --config "C:/private/BuaaNetworkAutoLogin.json"
BuaaNetworkAutoLogin watch --config "C:/private/BuaaNetworkAutoLogin.json"
BuaaNetworkAutoLogin watch --config "C:/private/BuaaNetworkAutoLogin.json" --interval-seconds 300 --heartbeat-seconds 7200
BuaaNetworkAutoLogin watch --config "C:/private/BuaaNetworkAutoLogin.json" --notification-time 08:00 --notification-time 20:00
BuaaNetworkAutoLogin once --config "C:/private/BuaaNetworkAutoLogin.json" --log-path "C:/private/BuaaNetworkAutoLogin.log"
```

也可以通过安装该包的 Python 环境运行模块：

```cmd
python -m BuaaNetworkAutoLogin once --config "C:/private/BuaaNetworkAutoLogin.json"
python -m BuaaNetworkAutoLogin watch --config "C:/private/BuaaNetworkAutoLogin.json"
```

| 参数                  | 是否必填 | 取值与用途                                                   |
| --------------------- | -------- | ------------------------------------------------------------ |
| `once` 或 `watch`     | 是       | 单次检查，或持续监测。                                       |
| `--config`            | 是       | 私有 JSON 配置文件路径。                                     |
| `--interval-seconds`  | 否       | `watch` 的检查间隔，覆盖 JSON 中的 `interval_seconds`。      |
| `--heartbeat-seconds` | 否       | `watch` 的正常状态通知间隔，覆盖 JSON 中的 `heartbeat_seconds`。 |
| `--notification-time` | 否       | `watch` 的每日通知时间，格式 `HH:MM`；可重复填写，填写后覆盖 JSON 中的 `notification_times`。 |
| `--log-path`          | 否       | 覆盖 JSON 中的日志路径；只接受路径。要关闭文件日志，请在 JSON 中写 `"log_path": null`，并且不要传此选项。 |

`once` 的退出码 `0` 表示本次检查确认互联网可用，`1` 表示未确认可用，`2` 表示配置或运行参数错误。`watch` 会持续运行，命令行显示每次检查结果。CMD 中可用 `echo %ERRORLEVEL%` 查看结束后的退出码。

## 返回结果与错误

单次检查返回 `LoginResult`：

| 属性                 | 含义                                                         |
| -------------------- | ------------------------------------------------------------ |
| `status`             | 供程序判断的结果代码，见下表。                               |
| `message`            | 显示给用户的说明；`str(result)` 与它相同。                   |
| `internet_available` | 本次检查是否确认互联网可用。                                 |
| `campus_detected`    | 本次检查是否检测到校园网环境；互联网已经可用时不会继续做校园网判断，因此此值可能为 `False`。 |
| `notification_sent`  | 本次检查是否成功发送企业微信通知。                           |

| `status`                    | 含义                                               |
| --------------------------- | -------------------------------------------------- |
| `internet_ok`               | 互联网已可用，不需要登录。                         |
| `restored`                  | 发起登录后确认互联网恢复。                         |
| `not_campus`                | 无法确认处于可操作的北航校园网环境，未尝试登录。   |
| `campus_route_blocked`      | 网关请求返回的 IP 与物理网卡不匹配，未尝试登录。   |
| `gateway_unreachable`       | 检测到校园网线索，但网关不可访问，未尝试登录。     |
| `gateway_unknown`           | 网关在线状态无法查询或识别，未尝试登录。           |
| `campus_online_no_internet` | 网关认为账号已在线，但互联网检查仍失败。           |
| `login_failed`              | 登录请求失败，或网关未返回预期的成功状态。         |
| `logged_in_no_internet`     | 网关接受登录，但随后尚未确认互联网可用。           |
| `check_error`               | 持续监测中的单次检查发生异常，会在下一轮继续检查。 |

参数或 JSON 格式错误会抛出 `ValueError`。网络、网关或认证失败通常由 `LoginResult.status` 和 `message` 表达；企业微信通知失败通常会附加在 `message` 中，不会把已恢复的互联网结果改成失败。若文件日志写入失败，错误会附加到 `message`，但不改变网络检查结果。

## 参考项目

* [zzdyyy/buaa_gateway_login](https://github.com/zzdyyy/buaa_gateway_login)
* [Tony15246/buaa_wifi_login](https://github.com/Tony15246/buaa_wifi_login)

## License

This project is licensed under the **[GNU Affero General Public License v3.0 (AGPL-3.0)](https://www.gnu.org/licenses/agpl-3.0.html)**.

You are free to **use, modify, and distribute** this project, including for commercial purposes, provided that:

* You **retain the copyright and license notices**.
* You **distribute modified versions under the same license**.
* You **make the corresponding source code available** as required by the AGPL-3.0, including when modified software is used to provide a network service.

See the [LICENSE](/LICENSE) file for details.

Copyright (c) 2026 Wang Nan
