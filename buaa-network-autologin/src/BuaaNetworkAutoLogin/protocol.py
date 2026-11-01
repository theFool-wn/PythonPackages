# @             Project: BuaaNetworkAutoLogin -> protocol.py
# @     Release Version: 0.2.0
# @              Author: WangNan
# @       Creation Date: 2025/10/9 15:01
# @         Description: Build the BUAA gateway login request
# @ Version Information: Created by WangNan, 2025/10/9
#                        Revised by WangNan, 2026/10/20
# ===================================================================================


"""The Srun request encoding used by the BUAA gateway."""


from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time


_STANDARD = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
_SRUN = b"LVoJPiCN2R8G90yg+hmFHuacZ1OWMnrsSTXkYpUq/3dlbfKwv6xztjI7DeBE45QA"
_MASK = 0xFFFFFFFF
_DELTA = 0x9E3779B9


def _words(data: bytes, include_length: bool) -> list[int]:
    words = [int.from_bytes(data[i:i + 4].ljust(4, b"\0"), "little") for i in range(0, len(data), 4)]
    if include_length:
        words.append(len(data))
    return words


def _xencode(data: bytes, key: bytes) -> bytes:
    if not data:
        return b""
    values = _words(data, True)
    keys = (_words(key, False) + [0, 0, 0, 0])[:4]
    n = len(values) - 1
    z = values[n]
    summation = 0
    rounds = 6 + 52 // (n + 1)
    for _ in range(rounds):
        summation = (summation + _DELTA) & _MASK
        e = (summation >> 2) & 3
        for p in range(n):
            y = values[p + 1]
            mix = (z >> 5 ^ y << 2) + ((y >> 3 ^ z << 4) ^ (summation ^ y))
            mix += keys[(p & 3) ^ e] ^ z
            values[p] = (values[p] + mix) & _MASK
            z = values[p]
        y = values[0]
        mix = (z >> 5 ^ y << 2) + ((y >> 3 ^ z << 4) ^ (summation ^ y))
        mix += keys[(n & 3) ^ e] ^ z
        values[n] = (values[n] + mix) & _MASK
        z = values[n]
    return b"".join(value.to_bytes(4, "little") for value in values)


def build_login_params(username: str, password: str, ip: str, challenge: str) -> dict[str, str | int]:
    """Build the BUAA Srun login request using its current fixed metadata."""
    ac_id, n, login_type = "1", "200", "1"
    info = json.dumps(
        {
            "username": username,
            "password": password,
            "ip": ip,
            "acid": ac_id,
            "enc_ver": "srun_bx1",
        },
        ensure_ascii=True,
    ).encode("ascii")
    encoded = base64.b64encode(_xencode(info, challenge.encode("ascii"))).translate(
        bytes.maketrans(_STANDARD, _SRUN)
    ).decode("ascii")
    info_value = "{SRBX1}" + encoded
    password_md5 = hmac.new(challenge.encode("ascii"), password.encode("utf-8"), hashlib.md5).hexdigest()
    checksum = "".join(challenge + part for part in (username, password_md5, ac_id, ip, n, login_type, info_value))
    return {
        "action": "login",
        "username": username,
        "password": "{MD5}" + password_md5,
        "ac_id": ac_id,
        "ip": ip,
        "info": info_value,
        "n": n,
        "type": login_type,
        "os": "Windows+10",
        "name": "Windows",
        "double_stack": "0",
        "chksum": hashlib.sha1(checksum.encode("utf-8")).hexdigest(),
        "_": int(time.time() * 1000),
    }
