# @             Project: WeComMessager -> client.py
# @     Release Version: 0.2.0
# @              Author: WangNan
# @       Creation Date: 2025/10/8 16:00
# @         Description: Send WeCom application messages through available network routes
# @ Version Information: Created by WangNan, 2025/10/8
#                        Revised by WangNan, 2026/10/21, organized into a Python package
# ===================================================================================


from __future__ import annotations

import os
import json
import time
import requests
import socket
import mimetypes
import subprocess

from dataclasses import dataclass
from ipaddress import IPv4Address
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection
from urllib3.exceptions import MaxRetryError, NewConnectionError


_BASE = "https://qyapi.weixin.qq.com/cgi-bin"
_TOKEN_ERRORS = {40014, 42001}
_MEDIA_LIMITS = {"image": 2_000_000, "voice": 2_000_000, "video": 10_000_000, "file": 20_000_000}
_MEDIA_EXTENSIONS = {"image": {".jpg", ".jpeg", ".png"}, "voice": {".amr"}, "video": {".mp4"}}
_ERROR_HINTS = {
    -1: "企业微信服务暂时繁忙，请稍后再试",
    40001: "应用 Secret 无效；检查它是否与企业 ID 匹配，或应用是否已停用",
    40003: "收件人的 UserID 无效或不存在",
    40004: "媒体文件类型不符合企业微信要求",
    40005: "上传素材类型不正确",
    40006: "媒体文件大小不符合企业微信要求",
    40007: "media_id 无效、过期（临时素材有效期三天）或与消息类型不符",
    40008: "消息类型不受支持",
    40009: "图片文件大小不符合要求",
    40011: "视频文件大小不符合要求",
    40013: "企业 ID 无效",
    40014: "access_token 无效；已尝试刷新，检查应用配置",
    40031: "收件人 UserID 列表无效；检查拼写和应用可见范围",
    40056: "应用 AgentID 无效或不属于当前企业",
    42001: "access_token 已过期；已尝试刷新，检查应用配置",
    44001: "上传的素材为空或 multipart 格式不正确",
    44004: "文本消息内容为空",
    45001: "上传的媒体文件超过企业微信大小限制",
    45002: "消息内容超过企业微信长度限制",
    45007: "语音时长超过 60 秒",
    45009: "企业微信接口调用频率超过限制，请稍后再试",
    48001: "应用没有获授权使用此接口",
    48002: "应用无权调用此接口；检查应用类型和接口权限",
    60020: "当前出口 IP 不在应用的企业可信 IP 列表中",
    60021: "收件人不在应用可见范围内",
    81013: "所有收件人均无效或无权限；检查 UserID 和应用可见范围",
    82001: "收件人列表为空",
}


class WeComError(RuntimeError):
    """A safe-to-display error; request URLs and credentials are never included."""
    def __init__(self, message: str, code: int | None = None, *, delivery_unknown: bool = False, partial_delivery: bool = False):
        super().__init__(message)
        self.code = code
        self.delivery_unknown = delivery_unknown
        self.partial_delivery = partial_delivery


class _NetworkError(WeComError):
    """A route failed before an API response could be read."""
    def __init__(self, message: str, *, retry_safe: bool = False):
        super().__init__(message)
        self.retry_safe = retry_safe


def _code(result: dict) -> int:
    try:
        return int(result["errcode"])
    except (TypeError, ValueError):
        raise WeComError("企业微信返回了无效的错误码") from None


def _rejected_users(result: dict) -> str | None:
    rejected = []
    for key, reason in (
        ("invaliduser", "UserID 不存在或不在应用可见范围"),
        ("unlicenseduser", "未获基础接口许可"),
    ):
        value = result.get(key)
        if value:
            people = "|".join(str(item) for item in value) if isinstance(value, list) else str(value)
            rejected.append(f"{reason}: {people}")
    return "；".join(rejected) if rejected else None


@dataclass
class _Route:
    name: str
    session: requests.Session
    proxies: dict[str, str] | None = None
    token: str | None = None
    expires_at: float = 0.0


class _PhysicalAdapter(HTTPAdapter):
    """Keep one Windows HTTPS socket on a physical interface despite VPN routes."""
    def __init__(self, source_ip: str, interface_index: int):
        self.source_ip = source_ip
        self.interface_index = interface_index
        super().__init__()

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        pool_kwargs["source_address"] = (self.source_ip, 0)
        pool_kwargs["socket_options"] = HTTPConnection.default_socket_options + [
            (socket.IPPROTO_IP, getattr(socket, "IP_UNICAST_IF", 31), socket.htonl(self.interface_index)),
        ]
        super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)


def _physical_interfaces() -> list[tuple[str, int]]:
    """Discover active Windows hardware NICs only when ordinary routes fail."""
    if os.name != "nt":
        return []
    command = (
        "Get-NetAdapter -Physical | Where-Object {$_.Status -eq 'Up'} | "
        "ForEach-Object { Get-NetIPAddress -InterfaceIndex $_.ifIndex -AddressFamily IPv4 "
        "-ErrorAction SilentlyContinue | Where-Object {$_.IPAddress -notlike '169.254.*'} | "
        "Select-Object IPAddress,InterfaceIndex } | ConvertTo-Json -Compress"
    )

    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True, text=True, timeout=8, check=False,
        )
        if completed.returncode or not completed.stdout.strip():
            return []
        data = json.loads(completed.stdout.lstrip("\ufeff"))
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return []
    
    items = data if isinstance(data, list) else [data]
    found: list[tuple[str, int]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            address = str(IPv4Address(item["IPAddress"]))
            index = int(item["InterfaceIndex"])
        except (KeyError, TypeError, ValueError):
            continue
        if index > 0 and address not in {"0.0.0.0", "127.0.0.1"}:
            found.append((address, index))
    return found


class WeComMessenger:
    """
    An independent sender for one enterprise, application, and default recipient.

    ``proxy_url`` is optional. Without it, the client tries direct access and
    then the operating system/environment proxy when one is configured.
    Create as many instances as needed for other enterprises or recipients.
    """
    def __init__(self, corp_id: str, corp_secret: str, agent_id: int, user_id: str, *, proxy_url: str | None = None, timeout: float = 10) -> None:
        if any(not isinstance(value, str) or not value.strip() for value in (corp_id, corp_secret, user_id)):
            raise ValueError("corp_id、corp_secret 和 user_id 必须是非空文本")
        if isinstance(agent_id, bool) or not (isinstance(agent_id, int) or (isinstance(agent_id, str) and agent_id.isdecimal())):
            raise ValueError("agent_id 必须是正整数")
        parsed_agent_id = int(agent_id)
        if parsed_agent_id <= 0:
            raise ValueError("agent_id 必须是正整数")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
            raise ValueError("timeout 必须是正数")

        self.corp_id = corp_id
        self._corp_secret = corp_secret
        self.agent_id = parsed_agent_id
        self.user_id = user_id
        self.timeout = timeout
        self._routes: list[_Route] = []

        if proxy_url is not None:
            if not isinstance(proxy_url, str) or not proxy_url:
                raise ValueError("proxy_url 必须是非空代理 URL")
            if not proxy_url.startswith(("http://", "https://", "socks5://", "socks5h://")):
                raise ValueError("proxy_url needs an HTTP(S) or SOCKS URL scheme")
            session = requests.Session()
            session.trust_env = False
            self._routes.append(_Route("specified proxy", session, {"http": proxy_url, "https": proxy_url}))
        
        direct = requests.Session()
        direct.trust_env = False
        self._routes.append(_Route("direct", direct))

        # Keep this route even if no proxy is configured now: VPN software may
        # change Windows proxy settings after the messenger is constructed.
        system = requests.Session()
        system.trust_env = True
        self._routes.append(_Route("system proxy", system))

    def close(self) -> None:
        for route in self._routes:
            route.session.close()

    def _reset_route(self, route: _Route) -> None:
        """Discard a failed route's cached token and persistent connections."""
        route.token = None
        route.expires_at = 0.0
        if any(configured is route for configured in self._routes):
            previous = route.session
            fresh = requests.Session()
            fresh.trust_env = previous.trust_env
            route.session = fresh
            previous.close()

    def __enter__(self) -> "WeComMessenger":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _request(self, route: _Route, method: str, endpoint: str, **kwargs) -> dict:
        try:
            response = route.session.request(
                method,
                f"{_BASE}/{endpoint}",
                proxies=route.proxies,
                timeout=(self.timeout, self.timeout),
                **kwargs,
            )
            response.raise_for_status()
            result = response.json()
        except requests.exceptions.ConnectTimeout:
            raise _NetworkError(f"{route.name}: 连接企业微信超时", retry_safe=True) from None
        except requests.exceptions.ReadTimeout:
            raise _NetworkError(f"{route.name}: 等待企业微信响应超时") from None
        except requests.exceptions.Timeout:
            raise _NetworkError(f"{route.name}: 企业微信请求超时") from None
        except requests.exceptions.ProxyError:
            raise _NetworkError(f"{route.name}: 代理连接失败；检查 VPN 或系统代理", retry_safe=True) from None
        except requests.exceptions.SSLError:
            raise _NetworkError(f"{route.name}: TLS 校验失败；检查系统时间或 VPN 证书") from None
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "未知"
            raise _NetworkError(f"{route.name}: 企业微信 HTTP {status}") from None
        except requests.exceptions.ConnectionError as exc:
            # Requests wraps a failed new socket/DNS lookup in MaxRetryError.
            # Other connection errors may have occurred after a POST was sent.
            retry_safe = any(
                isinstance(arg, MaxRetryError) and isinstance(arg.reason, NewConnectionError)
                for arg in exc.args
            )
            raise _NetworkError(
                f"{route.name}: 网络连接失败 ({type(exc).__name__})",
                retry_safe=retry_safe,
            ) from None
        except requests.exceptions.RequestException as exc:
            # str(exc) may embed the token or secret in its request URL.
            raise _NetworkError(f"{route.name}: 网络连接失败 ({type(exc).__name__})") from None
        except ValueError:
            raise _NetworkError(f"{route.name}: 企业微信返回了非 JSON 内容") from None
        if not isinstance(result, dict) or "errcode" not in result:
            raise _NetworkError(f"{route.name}: 企业微信返回内容缺少 errcode")
        return result

    def _api_error(self, route: _Route, operation: str, result: dict) -> WeComError:
        code = _code(result)
        hint = _ERROR_HINTS.get(code, "企业微信拒绝了请求")
        rejected = _rejected_users(result)
        if rejected:
            hint += f"；{rejected}"
        # Unknown error codes remain diagnosable without leaking URLs/tokens.
        detail = result.get("errmsg", "")
        if isinstance(detail, str) and detail and code not in _ERROR_HINTS:
            for secret in (self._corp_secret, route.token, *(item.token for item in self._routes)):
                if secret:
                    detail = detail.replace(secret, "[已隐藏]")
            hint += f"；接口说明: {detail[:160]}"
        return WeComError(f"{route.name}: {operation} 失败 (errcode={code})：{hint}", code)

    def _token(self, route: _Route, force: bool = False) -> str:
        if not force and route.token and time.monotonic() < route.expires_at:
            return route.token
        data = self._request(
            route, "GET", "gettoken",
            params={"corpid": self.corp_id, "corpsecret": self._corp_secret},
        )
        code = _code(data)
        if code:
            raise self._api_error(route, "获取 access_token", data)
        token = data.get("access_token")
        try:
            lifetime = int(data.get("expires_in", 0))
        except (TypeError, ValueError):
            lifetime = 0
        if not token or lifetime <= 0:
            raise _NetworkError(f"{route.name}: 企业微信返回了无效的 access_token")
        route.token = str(token)
        route.expires_at = time.monotonic() + max(0, lifetime - 60)
        return route.token

    @staticmethod
    def _media_file(content: str | os.PathLike[str], kind: str) -> Path:
        try:
            path = Path(content).expanduser()
            size = path.stat().st_size
        except FileNotFoundError:
            raise ValueError(f"{kind}文件不存在：{content}") from None
        except PermissionError:
            raise ValueError(f"没有权限读取{kind}文件：{content}") from None
        except (OSError, TypeError, ValueError) as exc:
            raise ValueError(f"无法读取{kind}文件：{type(exc).__name__}") from None
        if not path.is_file():
            raise ValueError(f"{kind}路径不是普通文件：{path}")
        if size <= 5 or size > _MEDIA_LIMITS[kind]:
            raise ValueError(f"{kind}文件必须大于 5 字节，且不超过 {_MEDIA_LIMITS[kind] // 1_000_000} MB")
        extensions = _MEDIA_EXTENSIONS.get(kind)
        if extensions and path.suffix.lower() not in extensions:
            raise ValueError(f"{kind}文件格式不支持；可用后缀：{', '.join(sorted(extensions))}")
        return path

    def _upload_via_route(self, route: _Route, path: Path, kind: str, failures: list[str]) -> str | None:
        try:
            token = self._token(route)
        except WeComError as exc:
            if exc.code is not None and exc.code != 60020:
                raise
            if isinstance(exc, _NetworkError):
                self._reset_route(route)
            failures.append(str(exc))
            return None
        
        mime_type = (
            "audio/amr" if kind == "voice" else
            "video/mp4" if kind == "video" else
            mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        )
        for attempt in range(2):
            try:
                with path.open("rb") as stream:
                    result = self._request(
                        route, "POST", "media/upload",
                        params={"access_token": token, "type": kind},
                        files={"media": (path.name, stream, mime_type)},
                    )
            except _NetworkError as exc:
                # Uploading media cannot itself deliver a user message.
                self._reset_route(route)
                failures.append(str(exc))
                return None
            except OSError as exc:
                raise WeComError(f"读取待发送文件失败 ({type(exc).__name__})") from None
            
            code = _code(result)
            if code in _TOKEN_ERRORS and attempt == 0:
                route.token = None
                try:
                    token = self._token(route, force=True)
                except WeComError as exc:
                    if exc.code is not None and exc.code != 60020:
                        raise
                    if isinstance(exc, _NetworkError):
                        self._reset_route(route)
                    failures.append(str(exc))
                    return None
                continue
            if code == 60020:
                failures.append(str(self._api_error(route, "上传素材", result)))
                return None
            if code:
                raise self._api_error(route, "上传素材", result)
            
            media_id = result.get("media_id")
            if not isinstance(media_id, str) or not media_id:
                raise WeComError(f"{route.name}: 企业微信上传成功但未返回 media_id")
            return media_id
        return None

    def send(self, content: str | os.PathLike[str], *, kind: str = "text", to_user: str | None = None, title: str | None = None, description: str | None = None) -> bool:
        """
        Send text/markdown, or upload and send a local image/voice/video/file.

        Retry another route only when the message POST could not be sent.
        If delivery is uncertain, stop to avoid a duplicate message.
        """
        if kind not in {"text", "markdown", *_MEDIA_LIMITS}:
            raise ValueError("kind 必须是 text/markdown/image/voice/video/file")
        recipient = self.user_id if to_user is None else to_user
        if not isinstance(recipient, str) or not recipient.strip():
            raise ValueError("to_user 或默认 user_id 不能为空")
        if kind != "video" and (title is not None or description is not None):
            raise ValueError("title 和 description 只适用于视频消息")
        if kind == "video":
            for name, value, limit in (("title", title, 128), ("description", description, 512)):
                if value is not None and (not isinstance(value, str) or len(value.encode("utf-8")) > limit):
                    raise ValueError(f"{name} 必须是至多 {limit} 字节的 UTF-8 文本")
        path = None
        if kind in {"text", "markdown"}:
            if not isinstance(content, str) or not content or len(content.encode("utf-8")) > 2048:
                raise ValueError("文本或 Markdown 消息须为 1 至 2048 字节的 UTF-8 文本")
            body = {"content": content}
        else:
            path = self._media_file(content, kind)
            body = None
        
        base = {"touser": recipient, "msgtype": kind, "agentid": self.agent_id}
        failures: list[str] = []
        for route in self._routes:
            if self._send_on_route(route, base, kind, body, path, title, description, failures):
                return True
        # A full-tunnel VPN or a WeCom trusted-IP restriction may block both
        # ordinary paths. Windows can still have a reachable physical NIC.
        for source_ip, interface_index in _physical_interfaces():
            with requests.Session() as session:
                session.trust_env = False
                session.mount("https://", _PhysicalAdapter(source_ip, interface_index))
                route = _Route(f"physical interface {interface_index}", session)
                if self._send_on_route(route, base, kind, body, path, title, description, failures):
                    return True
        raise WeComError("无法通过当前网络访问企业微信；" + "; ".join(failures))

    def _send_on_route(self, route: _Route, base: dict, kind: str, body: dict | None, path: Path | None, title: str | None, description: str | None, failures: list[str]) -> bool:
        if path is not None:
            media_id = self._upload_via_route(route, path, kind, failures)
            if media_id is None:
                return False
            body = {"media_id": media_id}
            if kind == "video":
                if title is not None:
                    body["title"] = title
                if description is not None:
                    body["description"] = description
        payload = {**base, kind: body}
        return self._send_via_route(route, payload, failures)

    def _send_via_route(self, route: _Route, payload: dict, failures: list[str]) -> bool:
        try:
            token = self._token(route)
        except WeComError as exc:
            # gettoken is read-only, so trying the next network route is safe.
            if exc.code is not None and exc.code != 60020:
                raise
            if isinstance(exc, _NetworkError):
                self._reset_route(route)
            failures.append(str(exc))
            return False
        
        for attempt in range(2):
            try:
                result = self._request(
                    route, "POST", "message/send",
                    params={"access_token": token}, json=payload
                )
            except _NetworkError as exc:
                if exc.retry_safe:
                    self._reset_route(route)
                    failures.append(str(exc))
                    return False
                raise WeComError(f"{exc}；消息是否送达无法确认，请先检查收件人再决定是否重发", delivery_unknown=True) from None
            except WeComError as exc:
                # POST may have arrived despite a lost response. No automatic
                # replay here, because it could duplicate a delivered message.
                raise WeComError(f"{exc}；消息是否送达无法确认，请先检查收件人再决定是否重发", delivery_unknown=True) from None
            try:
                code = _code(result)
            except WeComError as exc:
                raise WeComError(f"{route.name}: {exc}；消息是否送达无法确认，请检查收件人后再决定是否重发", delivery_unknown=True) from None
            
            if code in _TOKEN_ERRORS and attempt == 0:
                route.token = None
                try:
                    token = self._token(route, force=True)
                except WeComError as exc:
                    if exc.code is not None and exc.code != 60020:
                        raise
                    if isinstance(exc, _NetworkError):
                        self._reset_route(route)
                    failures.append(str(exc))
                    return False
                continue
            if code == 60020:
                failures.append(str(self._api_error(route, "发送消息", result)))
                return False  # Explicit rejection means no message was delivered.
            if code:
                raise self._api_error(route, "发送消息", result)
            rejected = _rejected_users(result)
            if rejected:
                raise WeComError(f"企业微信返回成功，但部分收件人未收到：{rejected}；其他收件人可能已收到，请勿直接重试整批", partial_delivery=True)
            return True
        return False

    def send_text(self, content: str, to_user: str | None = None) -> bool:
        return self.send(content, kind="text", to_user=to_user)

    def send_markdown(self, content: str, to_user: str | None = None) -> bool:
        return self.send(content, kind="markdown", to_user=to_user)

    def send_emoji(self, emoji: str, to_user: str | None = None) -> bool:
        """Send Unicode emoji as text (e.g. '🎉'); use send_sticker for an image."""
        return self.send_text(emoji, to_user=to_user)

    def send_image(self, path: str | os.PathLike[str], to_user: str | None = None) -> bool:
        return self.send(path, kind="image", to_user=to_user)

    def send_sticker(self, path: str | os.PathLike[str], to_user: str | None = None) -> bool:
        """Send a static JPG/PNG sticker; animated GIF can be sent as a file."""
        return self.send_image(path, to_user=to_user)

    def send_voice(self, path: str | os.PathLike[str], to_user: str | None = None) -> bool:
        """Voice must be an AMR file no longer than 60 seconds."""
        return self.send(path, kind="voice", to_user=to_user)

    def send_video(self, path: str | os.PathLike[str], to_user: str | None = None, *, title: str | None = None, description: str | None = None) -> bool:
        return self.send(path, kind="video", to_user=to_user, title=title, description=description)

    def send_file(self, path: str | os.PathLike[str], to_user: str | None = None) -> bool:
        return self.send(path, kind="file", to_user=to_user)


def send_text(content: str, *, corp_id: str, corp_secret: str, agent_id: int, user_id: str, proxy_url: str | None = None) -> bool:
    """
    One-shot convenience function,
    use WeComMessenger for repeated sends.
    """
    with WeComMessenger(corp_id, corp_secret, agent_id, user_id, proxy_url=proxy_url) as client:
        return client.send_text(content)
