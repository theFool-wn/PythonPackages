# PythonPackages

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0.html)  [![Made by Wang Nan](https://img.shields.io/badge/Made%20by-Wang%20Nan-brightgreen)](https://github.com/theFool-wn)  ![Python](https://img.shields.io/badge/Python-3.9+-orange)  ![Platform](https://img.shields.io/badge/Platform-Github%20%2F%20PyPI-blueviolet)

打包为 Python Packages 发布到 PyPI
企业微信自建应用消息发送。支持文本、Markdown、Unicode 表情、静态图片表情、图片、语音、视频和文件；支持不同企业或收件人的多个实例；VPN 开启或关闭时自动尝试可用网络路径。


WeComMessager & BuaaNetworkAutoLogin


两个独立的 Python 包：一个发送企业微信应用消息，另一个监测北航校园网并在需要时恢复联网。校园网包可以选择调用企业微信包发送状态通知。代码在 WangNan 原有脚本的基础上整理，账号和密钥由使用者在调用时传入或保存在自己的配置文件中。

校园网自动登录与网卡检测面向 Windows；企业微信消息包可独立使用，物理网卡绕过 VPN 的补救路径仅在 Windows 上提供。

## Packages

| 包 | 功能 |
| --- | --- |
| **WeComMessager** | 发送企业微信应用消息。支持文本、Markdown、Unicode 表情、静态图片表情、图片、语音、视频与文件；支持不同企业或收件人的多个实例；VPN 开启或关闭时自动尝试可用网络路径 |
| **BuaaNetworkAutoLogin** | 监测并保持 BUAA 校园网在线，支持单次检查或持续监测，可设置定时通知（需安装 `WeComMessager`） |

## 安装

```cmd
python -m pip install wecom-messager
python -m pip install buaa-network-autologin
```

校园网需要企业微信通知时
```cmd
python -m pip install wecom-messager
python -m pip install "buaa-network-autologin[wecom]"
```

## WeComMessager

```python
from WeComMessager import WeComMessenger

sender_a = WeComMessenger("企业 A 的 ID", "应用 A 的 Secret", 100001, "UserA")
sender_b = WeComMessenger("企业 B 的 ID", "应用 B 的 Secret", 100002, "UserB")
try:
    sender_a.send_text("任务完成")
    sender_b.send_markdown("**任务完成**")
    sender_a.send_image("photo.png")
    sender_b.send_file("report.pdf")
finally:
    sender_a.close()
    sender_b.close()
```

支持命令行
```cmd
WeComMessager --config "C:/private/secret.json" "你好"
WeComMessager --config "C:/private/secret.json" --kind markdown "**任务完成**"
WeComMessager --config "C:/private/secret.json" --to-user "UserB" "发给另一位成员"
```

详细使用方法阅读 [WeComMessager](/wecom-messager/README.md)

## BuaaNetworkAutoLogin

直接传参：

```python
from BuaaNetworkAutoLogin import ensure_online, watch_online

result = ensure_online("校园网账号", "校园网密码")
print(result.status, result.message)

watch_online(
    "校园网账号", "校园网密码",
    interval_seconds=600,
    on_result=lambda result: print(result.message),
)
```

从配置文件读取：

```python
from BuaaNetworkAutoLogin import ensure_online_from_config, watch_online_from_config

result = ensure_online_from_config("C:/private/BuaaNetworkAutoLogin.json")
print(result.message)

watch_online_from_config(
    "C:/private/BuaaNetworkAutoLogin.json",
    on_result=lambda result: print(result.message),
)
```

支持命令行

```cmd
BuaaNetworkAutoLogin once --config "C:/private/BuaaNetworkAutoLogin.json"
BuaaNetworkAutoLogin watch --config "C:/private/BuaaNetworkAutoLogin.json"
```

详细使用方法阅读 [BuaaNetworkAutoLogin](/buaa-network-autologin/README.md)

## Refenences

* [企业微信发送应用消息](https://developer.work.weixin.qq.com/document/path/90236)
* [企业微信临时素材](https://developer.work.weixin.qq.com/document/path/90253)
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