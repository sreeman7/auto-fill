"""Small, privacy-conscious API safeguards for a single worker."""

import json
import hashlib
import logging
import time
from collections import OrderedDict, deque
from threading import Lock
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse, Response

logger = logging.getLogger("auto_fill.api")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)

# Uvicorn's default access line includes the query string. Our own log below
# records only route templates, status, duration and a random request ID.
logging.getLogger("uvicorn.access").disabled = True


class RateLimiter:
    def __init__(self, max_keys: int = 10_000):
        self.max_keys = max_keys
        self.buckets: OrderedDict[tuple[str, str], deque[float]] = OrderedDict()
        self.lock = Lock()

    def check(self, key: tuple[str, str], limit: int, window: float = 60.0) -> int:
        now = time.monotonic()
        with self.lock:
            bucket = self.buckets.get(key)
            if bucket is None:
                if len(self.buckets) >= self.max_keys:
                    self.buckets.popitem(last=False)
                bucket = deque()
                self.buckets[key] = bucket
            self.buckets.move_to_end(key)
            while bucket and bucket[0] <= now - window:
                bucket.popleft()
            if len(bucket) >= limit:
                return max(1, int(window - (now - bucket[0])) + 1)
            bucket.append(now)
            return 0


limiter = RateLimiter()


async def protect_and_monitor(request: Request, call_next) -> Response:
    start = time.monotonic()
    request_id = uuid4().hex
    path = request.url.path
    status = 500
    route = "unmatched"
    try:
        if path not in {"/api/v1/health"}:
            client = request.client.host if request.client else "unknown"
            credential = request.headers.get("Authorization", "")
            token = credential[7:].strip() if credential.lower().startswith("bearer ") else ""
            identity = hashlib.sha256(token.encode("utf-8")).hexdigest() if token else client
            retry_after = limiter.check((client, "ip"), 600)
            if not retry_after:
                retry_after = limiter.check((identity, "all"), 120)
            if retry_after:
                response = JSONResponse({"detail": "Too many requests. Try again shortly."}, status_code=429,
                                        headers={"Retry-After": str(retry_after)})
                route = "rate_limited"
            else:
                response = await call_next(request)
                route = getattr(request.scope.get("route"), "path", "unmatched")
        else:
            response = await call_next(request)
            route = getattr(request.scope.get("route"), "path", "unmatched")
        status = response.status_code
    except Exception:
        response = JSONResponse({"detail": "Internal server error"}, status_code=500)
        route = getattr(request.scope.get("route"), "path", "unmatched")
    response.headers["X-Request-ID"] = request_id
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    if path.startswith("/api/"):
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    logger.info(json.dumps({"event": "api_request", "requestId": request_id, "route": route,
                            "method": request.method, "status": status,
                            "durationMs": round((time.monotonic() - start) * 1000)}))
    return response
