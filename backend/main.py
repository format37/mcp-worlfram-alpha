import contextlib
import logging
import os
import re

import uvicorn
from dotenv import load_dotenv
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from wolfram_tools import query_wolfram

load_dotenv(".env")

logger = logging.getLogger(__name__)

WOLFRAM_ALPHA_APPID = os.getenv("WOLFRAM_ALPHA_APPID", "")

MCP_NAME = os.getenv("MCP_NAME", "wolfram")
_safe_name = re.sub(r"[^a-z0-9_-]", "-", MCP_NAME.lower()).strip("-") or "service"
BASE_PATH = f"/{_safe_name}"
STREAM_PATH = f"{BASE_PATH}/"

# Local-only deployment: accept localhost and the docker container hostname.
transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[
        "localhost:*",
        "127.0.0.1:*",
        "mcp-wolfram:*",
    ],
    allowed_origins=[
        "http://localhost:*",
        "https://localhost:*",
        "http://127.0.0.1:*",
        "http://mcp-wolfram:*",
    ],
)

mcp = FastMCP(
    _safe_name,
    streamable_http_path=STREAM_PATH,
    json_response=True,
    transport_security=transport_security,
)


@mcp.tool()
async def wolfram_query(
    query: str,
    maxchars: int = 6800,
    units: str = "metric",
) -> str:
    """Query Wolfram Alpha's computational engine (LLM API) and get a
    plaintext, LLM-shaped answer back.

    Use this for *self-contained* mathematics and quantitative reference —
    one atomic question per call:

      - solving equations / systems / inequalities
      - closed-form integration and differentiation, ODEs
      - series / Taylor / asymptotic expansion, limits
      - Laplace / Fourier / Z transforms
      - matrix operations (det, inverse, eigenvalues, rank)
      - simplifying or verifying a symbolic identity
      - statistical distributions, combinatorics, number theory
      - unit / physical-constant conversion
      - plotting an expression (returns plot image URLs)
      - numeric, scientific, geographic, financial reference data

    NOT a good fit: multi-step derivations where you need to carry symbolic
    intermediates across steps (e.g. RL Bellman / HJB derivations). For
    those, keep symbolic objects in memory with SymPy in a code tool and
    use this only for atomic spot-checks of individual steps.

    The response is already prose-shaped: it includes how Wolfram
    interpreted the input, the primary result, alternate forms, series,
    and any plot image URLs (https links to PNGs you can show the user).
    No XML/pod parsing is needed. On failure the result is a single line
    starting with "Error:" — including Wolfram's own rephrasing
    suggestions when it could not understand the input.

    Args:
        query: The question or expression, e.g. "integrate x^2 sin(x) dx",
            "eigenvalues {{1,2},{3,4}}", "Laplace transform of t^2 e^(-3t)",
            "solve x^2 + 3x - 4 = 0", "speed of light in furlongs per
            fortnight". Plain natural language works too.
        maxchars: Approximate response length budget. Clamped to
            200..25000. Raise it if a result looks truncated; lower it to
            save context.
        units: "metric" (default) or "imperial".
    """
    if not WOLFRAM_ALPHA_APPID:
        return "Error: WOLFRAM_ALPHA_APPID is not configured on the server"
    try:
        return await query_wolfram(
            app_id=WOLFRAM_ALPHA_APPID,
            query=query,
            maxchars=maxchars,
            units=units,
        )
    except Exception as e:  # pragma: no cover - defensive
        logger.exception("wolfram_query failed")
        return f"Error: {e}"


# Build ASGI app
mcp_asgi = mcp.streamable_http_app()


@contextlib.asynccontextmanager
async def lifespan(_: Starlette):
    async with mcp.session_manager.run():
        yield


async def health_check(request):
    return JSONResponse({"status": "healthy", "appid_configured": bool(WOLFRAM_ALPHA_APPID)})


app = Starlette(
    routes=[
        Route("/health", health_check, methods=["GET"]),
        Mount("/", app=mcp_asgi),
    ],
    lifespan=lifespan,
)


class TokenAuthMiddleware(BaseHTTPMiddleware):
    """Optional token gate for requests under BASE_PATH.

    Local-only by default: if MCP_TOKENS is unset, auth is DISABLED and any
    token-like path segment (/<service>/<token>/...) is transparently
    stripped so the endpoint works at both /<service>/ and
    /<service>/<anything>/. Set MCP_TOKENS (comma-separated) only if you
    later expose this server beyond localhost.

    Accepted token channels when enabled:
      - Authorization: Bearer <token>
      - ?token=<token>
      - path segment /<service>/<token>/...
    """

    def __init__(self, app):
        super().__init__(app)
        raw = os.getenv("MCP_TOKENS", "")
        self.allowed_tokens = {t.strip() for t in raw.split(",") if t.strip()}
        self.require_auth = (
            os.getenv("MCP_REQUIRE_AUTH", "").lower() in ("1", "true", "yes")
        )
        if not self.allowed_tokens:
            logger.warning("MCP_TOKENS not set; token auth DISABLED for %s", BASE_PATH)

    async def dispatch(self, request, call_next):
        path = request.url.path or "/"
        if not path.startswith(BASE_PATH):
            return await call_next(request)

        # Auth disabled: strip an optional token-like segment, allow.
        if not self.require_auth and not self.allowed_tokens:
            segs = [s for s in path.split("/") if s != ""]
            if len(segs) >= 2 and segs[0] == _safe_name:
                remainder = "/".join([_safe_name] + segs[2:])
                new_path = "/" + (
                    remainder + "/"
                    if path.endswith("/") or not segs[2:]
                    else remainder
                )
                if new_path == BASE_PATH:
                    new_path = STREAM_PATH
                request.scope["path"] = new_path
                if "raw_path" in request.scope:
                    request.scope["raw_path"] = new_path.encode("utf-8")
            return await call_next(request)

        if not self.allowed_tokens:
            return JSONResponse(
                {"detail": "Unauthorized"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )

        async def proceed(token_value, source):
            request.state.mcp_token = token_value
            logger.info("Authenticated %s %s via %s", request.method, path, source)
            return await call_next(request)

        # Authorization: Bearer <token>
        auth = request.headers.get("authorization") or request.headers.get(
            "Authorization"
        )
        if auth and auth.lower().startswith("bearer "):
            token = auth.split(" ", 1)[1].strip()
            if token in self.allowed_tokens:
                return await proceed(token, "header")

        # Query parameter ?token=...
        url_token = request.query_params.get("token")
        if url_token and url_token in self.allowed_tokens:
            return await proceed(url_token, "query")

        # Path segment /<service>/<token>/...
        segs = [s for s in path.split("/") if s != ""]
        if len(segs) >= 2 and segs[0] == _safe_name:
            candidate = segs[1]
            if candidate in self.allowed_tokens:
                remainder = "/".join([_safe_name] + segs[2:])
                new_path = "/" + (
                    remainder + "/"
                    if path.endswith("/") and not remainder.endswith("/")
                    else remainder
                )
                if new_path == BASE_PATH:
                    new_path = STREAM_PATH
                request.scope["path"] = new_path
                if "raw_path" in request.scope:
                    request.scope["raw_path"] = new_path.encode("utf-8")
                return await proceed(candidate, "path")

        return JSONResponse(
            {"detail": "Unauthorized"},
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )


app.add_middleware(TokenAuthMiddleware)


def main():
    PORT = int(os.getenv("PORT", "8019"))
    logger.info(f"Starting {MCP_NAME} MCP server on port {PORT} at {STREAM_PATH}")
    uvicorn.run(
        app=app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=PORT,
        log_level=os.getenv("LOG_LEVEL", "info"),
        access_log=True,
        proxy_headers=True,
        forwarded_allow_ips="*",
        timeout_keep_alive=120,
    )


if __name__ == "__main__":
    main()
