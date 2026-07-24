"""CaseRaft MCP server: FastMCP app, auth wiring, tools, and prompts.

Run locally:
    uvicorn caseraft_mcp.server:app --port 8300

Transport notes:
  * Streamable HTTP (current transport; SSE is legacy) at /mcp, STATELESS
    mode so multiple uvicorn workers or Railway replicas need no sticky
    sessions, with JSON responses enabled.
  * The canonical URL users paste into Claude is
    https://mcp.caseraft.com/mcp (see config.py).
  * 401s from the MCP endpoint carry
        WWW-Authenticate: Bearer resource_metadata="https://mcp.caseraft.com/.well-known/oauth-protected-resource"
    which is the discovery path Claude actually honors (Phase 0 finding:
    the header is only read on 401 responses, never on 200s).

Tools and prompts live in caseraft_mcp/tools.py; every tool call writes an
audit_logs row (see caseraft_mcp/audit.py).
"""

import logging

from starlette.responses import JSONResponse

from fastmcp import FastMCP

from .config import settings
from .oauth import CaseRaftOAuthProvider
from .tools import register_prompts, register_tools

logger = logging.getLogger(__name__)

auth_provider = CaseRaftOAuthProvider()

mcp = FastMCP("CaseRaft", auth=auth_provider)

register_tools(mcp)
register_prompts(mcp)


@mcp.custom_route("/health", methods=["GET"])
async def health(request):
    """Unauthenticated liveness check (Railway / Better Stack)."""
    return JSONResponse({"ok": True})


class CanonicalWWWAuthenticateMiddleware:
    """Rewrites the WWW-Authenticate header on 401s from the MCP endpoint to
    point at the ROOT protected-resource metadata URL (the exact value the
    Phase 0 doc requires). FastMCP's default header points at the RFC 9728
    path-scoped URL; both documents are served, but the header must carry
    the root form."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or scope.get("path", "").rstrip("/") != "/mcp":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if (
                message["type"] == "http.response.start"
                and message.get("status") == 401
            ):
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() != b"www-authenticate"
                ]
                header_value = (
                    f'Bearer resource_metadata="{settings.resource_metadata_url}"'
                )
                headers.append((b"www-authenticate", header_value.encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)


def create_app():
    inner = mcp.http_app(path="/mcp", stateless_http=True, json_response=True)
    return CanonicalWWWAuthenticateMiddleware(inner)


app = create_app()
