"""FastAPI 依赖注入（Phase 1）。

提供数据库 session 与请求元信息（IP / UA / request_id），供 router 注入、
转交 service 用于审计写入。
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from app.config import settings
from app.db import get_db
from app.utils.net import extract_client_ip


@dataclass(frozen=True)
class RequestMeta:
    """单次请求的审计元信息。"""

    ip_address: str
    user_agent: str
    request_id: str


def get_request_meta(request: Request) -> RequestMeta:
    """提取真实客户端 IP（Q324）、UA、request_id，供审计日志使用。"""
    direct = request.client.host if request.client else ""
    xff = request.headers.get("x-forwarded-for")
    ip = extract_client_ip(direct, xff, settings.trusted_proxies)
    ua = request.headers.get("user-agent", "")
    rid = getattr(request.state, "request_id", "-")
    return RequestMeta(ip_address=ip[:45], user_agent=ua[:500], request_id=str(rid))


__all__ = ["RequestMeta", "get_db", "get_request_meta"]
