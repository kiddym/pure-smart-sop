"""utils.net 单测：真实客户端 IP 解析（Q324）。"""

from __future__ import annotations

from app.utils import net


def test_no_xff_returns_direct() -> None:
    assert net.extract_client_ip("198.51.100.1", None, ["10.0.0.1"]) == "198.51.100.1"


def test_xff_ignored_without_trusted_proxies() -> None:
    # 未配置可信代理时不轻信 XFF（可伪造）
    assert net.extract_client_ip("198.51.100.1", "1.2.3.4", []) == "198.51.100.1"


def test_xff_ignored_when_direct_peer_untrusted() -> None:
    # 直连对端不可信 → 忽略 XFF
    assert net.extract_client_ip("198.51.100.1", "1.2.3.4", ["10.0.0.1"]) == "198.51.100.1"


def test_returns_client_behind_trusted_proxy() -> None:
    result = net.extract_client_ip("10.0.0.1", "203.0.113.9", ["10.0.0.1"])
    assert result == "203.0.113.9"


def test_strips_chain_of_trusted_proxies() -> None:
    result = net.extract_client_ip(
        "10.0.0.1", "203.0.113.9, 10.0.0.2, 10.0.0.3", ["10.0.0.1", "10.0.0.2", "10.0.0.3"]
    )
    assert result == "203.0.113.9"


def test_cidr_trusted_match() -> None:
    result = net.extract_client_ip("10.0.0.5", "203.0.113.9", ["10.0.0.0/24"])
    assert result == "203.0.113.9"


def test_all_trusted_returns_leftmost() -> None:
    result = net.extract_client_ip("10.0.0.1", "10.0.0.9", ["10.0.0.0/8"])
    assert result == "10.0.0.9"


def test_is_trusted_proxy_invalid_ip() -> None:
    assert net.is_trusted_proxy("not-an-ip", ["10.0.0.0/8"]) is False
