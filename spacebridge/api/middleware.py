import os
from typing import Awaitable, Callable

import httpx
from fastapi import Request
from fastapi.responses import FileResponse, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class UIRoutingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ):
        # Allow API calls, static assets, docs, approval pages, and invitation pages to pass through
        if (
            request.url.path.startswith("/api")
            or request.url.path.startswith("/mcp")
            or request.url.path.startswith("/approval")
            or request.url.path.startswith("/invitations")
            or request.url.path.startswith("/assets")
            or request.url.path.startswith("/docs")
            or request.url.path.startswith("/openapi.json")
        ):
            return await call_next(request)

        dev_mode = os.getenv("DEV_MODE", "false").lower() == "true"

        if dev_mode:
            vite_client = httpx.AsyncClient(base_url="http://localhost:5173")
            url = httpx.URL(
                path=request.url.path, query=request.url.query.encode("utf-8")
            )
            rp_req = vite_client.build_request(
                request.method,
                url,
                headers=request.headers.raw,
                content=await request.body(),
            )
            rp_resp = await vite_client.send(rp_req, stream=True)
            return StreamingResponse(
                rp_resp.aiter_raw(),
                status_code=rp_resp.status_code,
                headers=rp_resp.headers,
                background=rp_resp.aclose,
            )
        else:
            # Serve the SpaceLit index.html for any non-API/static route
            return FileResponse("SpaceLit/dist/index.html")
