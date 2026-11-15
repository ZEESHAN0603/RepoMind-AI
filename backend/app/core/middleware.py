import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import logger


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    """Middleware that assigns a unique Correlation ID to each request and logs duration."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract existing X-Request-ID or generate new UUID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        start_time = time.perf_counter()

        response = await call_next(request)

        process_time_ms = (time.perf_counter() - start_time) * 1000

        # Inject correlation ID in response header
        response.headers["X-Request-ID"] = request_id

        # Log structured request summary
        logger.info(
            f"{request.method} {request.url.path} - status={response.status_code} "
            f"latency={process_time_ms:.2f}ms [req_id={request_id}]"
        )

        return response

