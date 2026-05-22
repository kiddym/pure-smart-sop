"""网络相关工具：可信代理与真实客户端 IP 解析（Q324）。

纯函数，便于单测。审计中间件 / deps 调用 `extract_client_ip` 取真实客户端 IP。
"""

from __future__ import annotations

import ipaddress
from collections.abc import Sequence


def _matches(ip: str, pattern: str) -> bool:
    """ip 是否匹配单个 pattern（精确 IP 或 CIDR 网段）。"""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if "/" in pattern:
        try:
            return addr in ipaddress.ip_network(pattern, strict=False)
        except ValueError:
            return False
    try:
        return addr == ipaddress.ip_address(pattern)
    except ValueError:
        return False


def is_trusted_proxy(ip: str, trusted: Sequence[str]) -> bool:
    """ip 是否属于可信代理列表（支持精确 IP 与 CIDR）。"""
    return any(_matches(ip, pattern) for pattern in trusted)


def extract_client_ip(
    direct_ip: str, xff_header: str | None, trusted_proxies: Sequence[str]
) -> str:
    """从直连对端 IP + X-Forwarded-For 解析真实客户端 IP（Q324）。

    规则：仅当直连对端是可信代理时才采信 XFF。从右（最近一跳）向左跳过连续的
    可信代理，第一个非可信地址即真实客户端；全部可信则取链首（最初客户端声明）。
    未配置可信代理或无 XFF 时，直接返回直连 IP（不轻信可伪造的 XFF）。
    """
    direct_ip = direct_ip or ""
    if not xff_header or not trusted_proxies:
        return direct_ip
    hops = [hop.strip() for hop in xff_header.split(",") if hop.strip()]
    hops.append(direct_ip)
    for ip in reversed(hops):
        if not is_trusted_proxy(ip, trusted_proxies):
            return ip
    return hops[0]
