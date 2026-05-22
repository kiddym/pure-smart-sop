"""HTTP 中间件（Phase 1）。

RequestIdMiddleware：读 X-Request-Id，缺失则生成 uuid，注入日志 contextvar +
回写响应头（Q329）。
"""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.logging_config import request_id_ctx


class RequestIdMiddleware(BaseHTTPMiddleware):
    """为每个请求分配 / 透传 request_id。"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = rid
        token = request_id_ctx.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)
        response.headers["X-Request-Id"] = rid
        return response
