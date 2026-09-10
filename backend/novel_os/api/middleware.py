import logging
import re
from time import perf_counter
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from novel_os.core.logging import request_id_context

logger = logging.getLogger(__name__)
REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,128}")


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        supplied_ids = Headers(scope=scope).getlist("x-request-id")
        request_id = (
            supplied_ids[0]
            if len(supplied_ids) == 1 and REQUEST_ID_PATTERN.fullmatch(supplied_ids[0])
            else str(uuid4())
        )
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_context.set(request_id)
        started = perf_counter()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            logger.info(
                "request_completed",
                extra={
                    "request_id": request_id,
                    "method": scope["method"],
                    "path": scope["path"],
                    "status_code": status_code,
                    "duration_ms": round((perf_counter() - started) * 1000, 3),
                },
            )
            request_id_context.reset(token)
