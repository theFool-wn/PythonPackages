# @             Project: BuaaNetworkAutoLogin -> service.py
# @     Release Version: 0.2.0
# @              Author: WangNan
# @       Creation Date: 2025/10/9 15:01
# @         Description: Check BUAA network connectivity and restore internet access
# @ Version Information: Created by WangNan, 2025/10/9
#                        Revised by WangNan, 2026/10/21, package API and configurable notifications
# ===================================================================================


"""One-call BUAA internet restoration with a visible result."""


from __future__ import annotations

import json
import re
import socket
import time
import requests

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection

from .logs import DEFAULT_LOG_PATH, append_result, validate_log_path
from .network import campus_wifi_connected, internet_route, physical_ipv4_interfaces, portal_redirect_detected
from .protocol import build_login_params


_PORTAL = "https://gw.buaa.edu.cn/cgi-bin"


@dataclass(frozen=True)
class LoginResult:
    status: str
    message: str
    internet_available: bool
    campus_detected: bool
    notification_sent: bool = False

    def __str__(self) -> str:
        return self.message


class _GatewayError(RuntimeError):
    pass


def _send_notification(message: str, wecom: dict[str, Any] | None, messenger: Any, notification_format: str = "text") -> None:
    if notification_format not in {"text", "markdown"}:
        raise ValueError("notification_format 只能是 text 或 markdown")
    method = "send_markdown" if notification_format == "markdown" else "send_text"
    if messenger is not None:
        sent = getattr(messenger, method)(message)
        if sent is False:
            raise RuntimeError("企业微信客户端未确认消息发送成功")
        return
    from WeComMessager import WeComMessenger

    with WeComMessenger(**wecom) as client:
        sent = getattr(client, method)(message)
        if sent is False:
            raise RuntimeError("企业微信客户端未确认消息发送成功")


def _notification_error(exc: Exception) -> str:
    """Show safe WeCom errors without exposing a request URL or credentials."""
    if exc.__class__.__name__ == "WeComError":
        return str(exc)
    if isinstance(exc, (ImportError, AttributeError)):
        return "企业微信包未安装或不支持所选消息格式"
    if isinstance(exc, ValueError):
        return str(exc)[:160]
    if isinstance(exc, TypeError):
        return "企业微信参数或自定义客户端调用方式不正确"
    return type(exc).__name__


class _PhysicalAdapter(HTTPAdapter):
    """Ask Windows to route a gateway socket over one physical IPv4 adapter."""
    def __init__(self, source_ip: str, interface_index: int):
        self.source_ip = source_ip
        self.interface_index = interface_index
        super().__init__()

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        # Windows IP_UNICAST_IF expects the interface index in network byte order.
        option = getattr(socket, "IP_UNICAST_IF", 31)
        pool_kwargs["source_address"] = (self.source_ip, 0)
        pool_kwargs["socket_options"] = HTTPConnection.default_socket_options + [
            (socket.IPPROTO_IP, option, socket.htonl(self.interface_index)),
        ]
        super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)


class _Gateway:
    def __init__(self, verify_tls: bool, interface: tuple[str, int] | None = None):
        self.session = requests.Session()
        self.session.trust_env = False  # Never send campus credentials through a proxy.
        self.session.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0"
        if interface is not None:
            self.session.mount("https://", _PhysicalAdapter(*interface))
        self.verify_tls = verify_tls

    def close(self) -> None:
        self.session.close()

    def _get(self, endpoint: str, params: dict[str, Any]) -> requests.Response:
        try:
            response = self.session.get(
                f"{_PORTAL}/{endpoint}", params=params,
                timeout=(10, 10), verify=self.verify_tls, allow_redirects=False,
            )
            response.raise_for_status()
        except requests.exceptions.SSLError:
            raise _GatewayError("网关 TLS 证书校验失败") from None
        except requests.exceptions.Timeout:
            raise _GatewayError("网关请求超时") from None
        except requests.exceptions.ConnectionError:
            raise _GatewayError("网关连接失败") from None
        except requests.exceptions.HTTPError as exc:
            # Exception text or URL could include the login request parameters.
            status = exc.response.status_code if exc.response is not None else "未知"
            raise _GatewayError(f"网关 HTTP {status}") from None
        except requests.exceptions.RequestException as exc:
            raise _GatewayError(f"网关请求失败（{type(exc).__name__}）") from None
        if response.is_redirect:
            raise _GatewayError("网关发生意外重定向")
        return response

    def jsonp(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        callback = "wn_" + str(int(time.time() * 1000))
        body = self._get(endpoint, dict(params, callback=callback)).text.strip()
        match = re.fullmatch(re.escape(callback) + r"\((.*)\);?", body, re.DOTALL)
        if not match:
            raise _GatewayError("网关返回格式无法识别")
        try:
            result = json.loads(match.group(1))
        except ValueError:
            raise _GatewayError("网关返回 JSON 无法解析") from None
        if not isinstance(result, dict):
            raise _GatewayError("网关返回数据类型错误")
        return result

    def challenge(self, username: str) -> tuple[str, str]:
        result = self.jsonp("get_challenge", {"username": username, "ip": "0.0.0.0", "_": int(time.time() * 1000)})
        if not result.get("client_ip") or not result.get("challenge"):
            raise _GatewayError("网关未返回客户端 IP 或 challenge 值")
        return str(result["client_ip"]), str(result["challenge"])

    def status(self, username: str) -> str:
        body = self._get("rad_user_info", {"_": int(time.time() * 1000)}).text.strip()
        if "not_online" in body.lower():
            return "offline"
        if body.startswith(username + ","):
            return "online"
        return "unknown"

    def login(self, username: str, password: str, ip: str, token: str) -> dict[str, Any]:
        return self.jsonp("srun_portal", build_login_params(username, password, ip, token))


def _ensure_online(
    username: str,
    password: str,
    *,
    notify: bool = False,
    wecom: dict[str, Any] | None = None,
    messenger: Any = None,
    verify_tls: bool = True,
    restore_message: str | None = None,
    notification_format: str = "text",
) -> LoginResult:
    """
    Keep internet available through BUAA; at most one login attempt per call.

    Set ``notify=True`` with the four WeCom parameters in ``wecom`` to send
    a message when login restores internet. A reusable ``messenger`` may also
    be supplied instead.
    """
    if not username or not password:
        raise ValueError("需要填写北航统一认证账号和密码")
    if notify and not (wecom or messenger):
        raise ValueError("notify=True 时需要填写 wecom 参数或传入 messenger")

    route = internet_route()
    if route:
        return LoginResult("internet_ok", f"互联网可用（{route}），无需登录校园网", True, False)

    wifi = campus_wifi_connected()
    redirect = portal_redirect_detected()
    try:
        interfaces = physical_ipv4_interfaces()
    except OSError:
        interfaces = []
    if not interfaces:
        reason = "检测到校园网，但无法识别本机物理网卡 IP" if wifi or redirect else "未检测到北航校园网连接"
        return LoginResult("not_campus", reason + "；未尝试登录", False, wifi or redirect)

    gateway = None
    gateway_ip = token = ""
    received_challenge = False
    last_gateway_error = ""
    for interface in [None, *interfaces]:
        candidate = _Gateway(verify_tls, interface)
        try:
            candidate_ip, candidate_token = candidate.challenge(username)
            received_challenge = True
        except _GatewayError as exc:
            last_gateway_error = str(exc)
            candidate.close()
            continue
        expected_ips = {ip for ip, _ in interfaces} if interface is None else {interface[0]}
        if candidate_ip in expected_ips:
            gateway = candidate
            gateway_ip, token = candidate_ip, candidate_token
            break
        candidate.close()
    if gateway is None:
        if wifi or redirect:
            if received_challenge:
                return LoginResult("campus_route_blocked", "网关请求未走校园网物理网卡（可能被 VPN 接管）；未尝试登录", False, True)
            detail = f"（{last_gateway_error}）" if last_gateway_error else ""
            return LoginResult("gateway_unreachable", f"已检测到北航校园网，但网关不可访问{detail}；未尝试登录", False, True)
        return LoginResult("not_campus", "无法确认处于北航校园网；未尝试登录", False, False)

    try:
        try:
            status = gateway.status(username)
        except _GatewayError as exc:
            return LoginResult("gateway_unknown", f"{exc}；未尝试登录", False, True)
        if status == "online":
            return LoginResult("campus_online_no_internet", "校园网账号已在线，但互联网仍不可用", False, True)
        if status != "offline":
            return LoginResult("gateway_unknown", "网关在线状态无法识别；未尝试登录", False, True)

        try:
            response = gateway.login(username, password, gateway_ip, token)
        except _GatewayError as exc:
            return LoginResult("login_failed", f"校园网登录请求失败：{exc}", False, True)
        if response.get("error") != "ok":
            code = response.get("error", "unknown")
            return LoginResult("login_failed", f"校园网拒绝登录：{code}", False, True)
    finally:
        gateway.close()

    route = None
    for attempt in range(3):
        route = internet_route()
        if route:
            break
        if attempt < 2:
            time.sleep(2)
    if not route:
        return LoginResult("logged_in_no_internet", "网关接受了登录，但尚未检测到互联网；请稍后再检查", False, True)

    notification_sent = False
    message = f"校园网登录成功，互联网已恢复（{route}）"
    if notify:
        try:
            _send_notification(restore_message or message, wecom, messenger, notification_format)
            notification_sent = True
        except Exception as exc:
            message += f"；企业微信通知失败（{_notification_error(exc)}）"
    return LoginResult("restored", message, True, True, notification_sent)


def ensure_online(
    username: str,
    password: str,
    *,
    notify: bool = False,
    wecom: dict[str, Any] | None = None,
    messenger: Any = None,
    verify_tls: bool = True,
    restore_message: str | None = None,
    notification_format: str = "text",
    log_path: str | Path | None = DEFAULT_LOG_PATH,
) -> LoginResult:
    """
    Check once and return the outcome. Only a successful reconnection sends a message.

    ``restore_message`` customizes notification content; the result always
    describes the actual connection outcome. ``log_path=None`` disables the
    local log. No credential or custom notification payload is written to it.
    """
    validate_log_path(log_path)
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        raise ValueError("需要填写北航统一认证账号和密码")
    if not isinstance(notify, bool):
        raise ValueError("notify 必须是 bool")
    if wecom is not None and not isinstance(wecom, dict):
        raise ValueError("wecom 必须是企业微信参数字典")
    if notification_format not in {"text", "markdown"}:
        raise ValueError("notification_format 只能是 text 或 markdown")
    if restore_message is not None and (not isinstance(restore_message, str) or not restore_message.strip()):
        raise ValueError("restore_message 必须是非空字符串")
    if notify and not (wecom or messenger):
        raise ValueError("notify=True 时需要填写 wecom 参数或传入 messenger")
    
    result = _ensure_online(
        username, password, notify=notify, wecom=wecom, messenger=messenger,
        verify_tls=verify_tls, restore_message=restore_message,
        notification_format=notification_format,
    )
    secrets = [username, password]
    if wecom:
        secrets.extend(wecom.get(key) for key in ("corp_id", "corp_secret", "user_id", "proxy_url"))
    log_error = append_result(result, log_path, secrets)
    return replace(result, message=f"{result.message}；{log_error}") if log_error else result
