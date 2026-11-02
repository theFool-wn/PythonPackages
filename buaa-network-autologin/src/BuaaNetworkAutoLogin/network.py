# @             Project: BuaaNetworkAutoLogin -> network.py
# @     Release Version: 0.2.0
# @              Author: WangNan
# @       Creation Date: 2026/10/20
# @         Description: Detect internet access and the BUAA physical network
# @ Version Information: Created by WangNan, 2026/10/20
#                        Revised by WangNan, 2026/11/02, use dedicated connectivity probes
#                        Revised by WangNan, 2026/11/02, decode Windows command output safely
# ===================================================================================


"""Automatic internet and physical-campus-network detection on Windows."""


from __future__ import annotations

import json
import locale
import socket
import subprocess
import psutil
import requests

from urllib.parse import urlparse
from urllib.request import getproxies


_INTERNET_PROBES = (
    ("http://www.msftconnecttest.com/connecttest.txt", 200, "Microsoft Connect Test"),
    ("https://connectivitycheck.gstatic.com/generate_204", 204, None),
    ("https://www.microsoft.com/", 200, None),
)
_BUAA_SSIDS = {"BUAA-WiFi", "BUAA-Mobile", "BUAA-WiFi-Free"}
_PORTAL_HOST = "gw.buaa.edu.cn"


def _system_proxy_present() -> bool:
    proxies = getproxies()
    return any(proxies.get(key) for key in ("https", "http", "all"))


def internet_route() -> str | None:
    """Find a usable route across several internet probe endpoints."""
    routes = (("direct", False), ("system proxy", True))
    for name, trust_env in routes:
        if trust_env and not _system_proxy_present():
            continue
        with requests.Session() as session:
            session.trust_env = trust_env
            for url, expected_status, expected_body in _INTERNET_PROBES:
                try:
                    response = session.get(url, timeout=(4, 5), allow_redirects=False, stream=True)
                    try:
                        expected_host = urlparse(url).hostname
                        final_host = urlparse(response.url).hostname
                        if (response.status_code == expected_status
                                and final_host == expected_host
                                and (expected_body is None or response.text.strip() == expected_body)):
                            return name
                    finally:
                        response.close()
                except requests.exceptions.RequestException:
                    continue
    return None


def _command(*args: str) -> str:
    """Read Windows command output without assuming the Python locale encoding."""
    try:
        process = subprocess.run(args, capture_output=True, timeout=8, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if process.returncode != 0:
        return ""
    output = process.stdout or b""
    if output.startswith((b"\xff\xfe", b"\xfe\xff")):
        return output.decode("utf-16", errors="replace")
    for encoding in ("utf-8-sig", locale.getpreferredencoding(False), "gb18030"):
        try:
            return output.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return output.decode("utf-8", errors="replace")


def campus_wifi_connected() -> bool:
    output = _command("netsh", "wlan", "show", "interfaces")
    for line in output.splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip().upper() == "SSID" and value.strip() in _BUAA_SSIDS:
            return True
    return False


def physical_ipv4_interfaces() -> list[tuple[str, int]]:
    """Read live physical adapter IPv4 addresses and Windows interface indexes."""
    output = _command(
        "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
        "Get-NetAdapter -Physical | Where-Object {$_.Status -eq 'Up'} | "
        "Select-Object Name,ifIndex | ConvertTo-Json -Compress",
    ).strip()
    if not output:
        return []
    try:
        names = json.loads(output)
    except ValueError:
        return []
    if isinstance(names, dict):
        names = [names]
    if not isinstance(names, list):
        return []
    interfaces = psutil.net_if_addrs()
    found: list[tuple[str, int]] = []
    for item in names:
        if not isinstance(item, dict) or not item.get("Name") or not item.get("ifIndex"):
            continue
        for address in interfaces.get(item["Name"], []):
            if address.family == socket.AF_INET and not address.address.startswith(("127.", "169.254.")):
                found.append((address.address, int(item["ifIndex"])))
    return found


def portal_redirect_detected() -> bool:
    """A direct HTTP captive-portal redirect is evidence of BUAA access."""
    with requests.Session() as session:
        session.trust_env = False
        try:
            response = session.get(
                "http://www.msftconnecttest.com/connecttest.txt",
                timeout=(2, 3), allow_redirects=False,
            )
        except requests.exceptions.RequestException:
            return False
    location = response.headers.get("Location", "")
    if urlparse(location).hostname == _PORTAL_HOST:
        return True
    return _PORTAL_HOST in response.text[:2000].lower()
