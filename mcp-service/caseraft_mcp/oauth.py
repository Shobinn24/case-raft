"""OAuth 2.1 authorization server for the CaseRaft MCP service.

Subclasses FastMCP's OAuthProvider (which composes the MCP SDK's OAuth route
handlers: /register JSON DCR, /authorize, /token form-urlencoded with PKCE
S256 verification, /revoke, and the .well-known metadata endpoints) and
persists everything to the shared Postgres:

    mcp_clients     DCR registrations
    mcp_auth_codes  authorization codes minted by the Flask consent page
                    (SHA-256 hash only)
    mcp_tokens      access + refresh tokens (SHA-256 hashes only)

Flow (two services, one database):

    Claude -> GET {issuer}/authorize            (this service)
           -> 302 to CONSENT_URL?...            (Flask: login + consent)
           -> Flask mints a row in mcp_auth_codes, 302 to Claude's
              redirect_uri with code + state
    Claude -> POST {issuer}/token               (this service; PKCE verified
              by the SDK handler against the stored code_challenge)

Phase 0 requirements honored here:
  * PKCE S256 mandatory, advertised via code_challenge_methods_supported.
  * offline_access included in scopes_supported (refresh-token behavior).
  * Refresh tokens ROTATE: each refresh grant revokes the old token row
    (killing its access token too) and issues a new pair. A dead refresh
    token yields error code invalid_grant (the SDK produces it when
    load_refresh_token returns None).
  * Redirect URIs: only Claude's callback and loopback URLs are accepted,
    with port-agnostic loopback matching (RFC 8252 style) for Claude Code.
  * Clients are normalized to PUBLIC clients (token_endpoint_auth_method
    "none"). PKCE is the security boundary; a client secret adds nothing
    for public clients and the mcp_clients table intentionally stores none.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlparse

from mcp.server.auth.provider import (
    AuthorizationCode,
    AuthorizationParams,
    RefreshToken,
    RegistrationError,
    TokenError,
)
from mcp.server.auth.settings import ClientRegistrationOptions, RevocationOptions
from mcp.shared.auth import (
    InvalidRedirectUriError,
    OAuthClientInformationFull,
    OAuthToken,
)
from pydantic import AnyUrl
from starlette.routing import Route

from fastmcp.server.auth import OAuthProvider
from fastmcp.server.auth.auth import AccessToken

from .config import settings
from .crypto import sha256_hex
from .db import MCPAuthCode, MCPClient, MCPToken, User, session_scope

logger = logging.getLogger(__name__)

CLAUDE_CALLBACK = "https://claude.ai/api/mcp/auth_callback"
LOOPBACK_HOSTS = {"localhost", "127.0.0.1"}

SUPPORTED_SCOPES = ["clio:read", "offline_access"]

SUBSCRIPTION_REQUIRED_MESSAGE = (
    "An active CaseRaft subscription is required to use CaseRaft for Claude. "
    "Visit https://caseraft.com/billing to upgrade, then reconnect."
)


def _is_loopback(uri):
    parsed = urlparse(str(uri))
    return parsed.scheme == "http" and parsed.hostname in LOOPBACK_HOSTS


def redirect_uri_allowed(uri):
    """Registration-time policy: Claude's callback, or a loopback URL."""
    return str(uri) == CLAUDE_CALLBACK or _is_loopback(uri)


def _loopback_match(candidate, registered):
    """Port-agnostic loopback comparison (RFC 8252 section 7.3): Claude Code
    binds an ephemeral port per run, so any localhost/127.0.0.1 port matches
    a registered loopback URI with the same path."""
    if not (_is_loopback(candidate) and _is_loopback(registered)):
        return False
    c = urlparse(str(candidate))
    r = urlparse(str(registered))
    return (c.path or "/") == (r.path or "/")


def redirect_uri_matches_registered(candidate, registered_uris):
    for registered in registered_uris or []:
        if str(candidate) == str(registered):
            return True
        if _loopback_match(candidate, registered):
            return True
    return False


class CaseRaftClient(OAuthClientInformationFull):
    """Client info with port-agnostic loopback redirect validation."""

    def validate_redirect_uri(self, redirect_uri):
        if redirect_uri is None:
            return super().validate_redirect_uri(None)
        if redirect_uri_matches_registered(redirect_uri, self.redirect_uris):
            return redirect_uri
        raise InvalidRedirectUriError(
            f"Redirect URI '{redirect_uri}' not registered for client"
        )


class CaseRaftAuthorizationCode(AuthorizationCode):
    user_id: int


class CaseRaftRefreshToken(RefreshToken):
    user_id: int


def _mint_token_pair(session, *, user_id, client_id, scopes):
    """Create a fresh access+refresh pair, store only hashes, return raws."""
    access_token = "crt_" + secrets.token_urlsafe(43)  # > 256 bits entropy
    refresh_token = "crr_" + secrets.token_urlsafe(43)
    expires_at = datetime.utcnow() + timedelta(seconds=settings.access_token_ttl)
    session.add(
        MCPToken(
            token_hash=sha256_hex(access_token),
            refresh_token_hash=sha256_hex(refresh_token),
            user_id=user_id,
            client_id=client_id,
            scopes=" ".join(scopes) if scopes else None,
            expires_at=expires_at,
            revoked=False,
        )
    )
    return access_token, refresh_token


def _subscription_gate_failure(session, user_id):
    """Subscription gate at token issuance (and refresh). Returns a
    (code, description) tuple to raise as TokenError, or None when the user
    may proceed. Returned rather than raised because TokenError is a FROZEN
    dataclass: contextlib's generator __exit__ assigns __traceback__ on
    exceptions raised through a @contextmanager block, which explodes with
    FrozenInstanceError. All TokenErrors are therefore raised OUTSIDE
    session_scope()."""
    user = session.get(User, user_id)
    if user is None:
        return ("invalid_grant", "Unknown CaseRaft user")
    if not user.is_paid:
        return ("invalid_grant", SUBSCRIPTION_REQUIRED_MESSAGE)
    return None


class CaseRaftOAuthProvider(OAuthProvider):
    """OAuth server persisting to the shared CaseRaft Postgres."""

    def __init__(self):
        super().__init__(
            base_url=settings.mcp_issuer_url,
            issuer_url=settings.mcp_issuer_url,
            client_registration_options=ClientRegistrationOptions(
                enabled=True,
                valid_scopes=SUPPORTED_SCOPES,
                default_scopes=SUPPORTED_SCOPES,
            ),
            revocation_options=RevocationOptions(enabled=True),
        )

    # ------------------------------------------------------------------
    # Dynamic Client Registration (RFC 7591; /register takes a JSON body)
    # ------------------------------------------------------------------

    async def get_client(self, client_id):
        with session_scope() as session:
            row = (
                session.query(MCPClient).filter_by(client_id=client_id).one_or_none()
            )
            if row is None:
                return None
            return CaseRaftClient(
                client_id=row.client_id,
                client_name=row.client_name,
                redirect_uris=[AnyUrl(u) for u in (row.redirect_uris or [])],
                token_endpoint_auth_method="none",
                grant_types=["authorization_code", "refresh_token"],
                response_types=["code"],
                scope=" ".join(SUPPORTED_SCOPES),
            )

    async def register_client(self, client_info):
        for uri in client_info.redirect_uris or []:
            if not redirect_uri_allowed(uri):
                raise RegistrationError(
                    "invalid_redirect_uri",
                    "Only the Claude callback "
                    f"({CLAUDE_CALLBACK}) and loopback redirect URIs "
                    "(http://localhost or http://127.0.0.1, any port) are allowed",
                )
        # Normalize to a PUBLIC client: PKCE is required, secrets are not
        # stored (mcp_clients holds no secret column by design). The mutated
        # object is what the SDK handler echoes back to the client.
        client_info.token_endpoint_auth_method = "none"
        client_info.client_secret = None
        client_info.client_secret_expires_at = None
        if not client_info.scope:
            client_info.scope = " ".join(SUPPORTED_SCOPES)
        with session_scope() as session:
            session.add(
                MCPClient(
                    client_id=client_info.client_id,
                    client_name=client_info.client_name,
                    redirect_uris=[str(u) for u in (client_info.redirect_uris or [])],
                )
            )
        logger.info(
            "Registered MCP client %s (%s)",
            client_info.client_id,
            client_info.client_name,
        )

    # ------------------------------------------------------------------
    # /authorize: relay the browser to the Flask consent surface
    # ------------------------------------------------------------------

    async def authorize(self, client, params: AuthorizationParams) -> str:
        """The Flask app owns sessions, Clio login, and the subscription gate,
        so /authorize forwards the whole request there. Flask mints the auth
        code (hash into mcp_auth_codes) and redirects to params.redirect_uri
        itself; this service sees the code again only at /token."""
        query = {
            "response_type": "code",
            "client_id": client.client_id,
            "redirect_uri": str(params.redirect_uri),
            "code_challenge": params.code_challenge,
            "code_challenge_method": "S256",
        }
        if params.state:
            query["state"] = params.state
        if params.scopes:
            query["scope"] = " ".join(params.scopes)
        if params.resource:
            query["resource"] = params.resource
        return f"{settings.consent_url}?{urlencode(query)}"

    # ------------------------------------------------------------------
    # /token: authorization_code + PKCE, refresh_token with rotation
    # ------------------------------------------------------------------

    async def load_authorization_code(self, client, authorization_code):
        code_hash = sha256_hex(authorization_code)
        with session_scope() as session:
            row = (
                session.query(MCPAuthCode)
                .filter_by(code_hash=code_hash, used=False)
                .one_or_none()
            )
            if row is None or row.client_id != client.client_id:
                return None
            return CaseRaftAuthorizationCode(
                code=authorization_code,
                scopes=row.scopes.split() if row.scopes else [],
                # Naive-UTC datetime -> epoch; SDK enforces expiry itself
                expires_at=row.expires_at.replace(tzinfo=timezone.utc).timestamp(),
                client_id=row.client_id,
                code_challenge=row.code_challenge,
                redirect_uri=AnyUrl(row.redirect_uri),
                redirect_uri_provided_explicitly=True,
                user_id=row.user_id,
            )

    async def exchange_authorization_code(self, client, authorization_code):
        code_hash = sha256_hex(authorization_code.code)
        failure = None
        with session_scope() as session:
            row = (
                session.query(MCPAuthCode)
                .filter_by(code_hash=code_hash)
                .one_or_none()
            )
            if row is None or row.used:
                failure = ("invalid_grant", "authorization code is not valid")
            else:
                row.used = True  # single-use, committed even if gating fails
                failure = _subscription_gate_failure(session, row.user_id)
                if failure is None:
                    access_token, refresh_token = _mint_token_pair(
                        session,
                        user_id=row.user_id,
                        client_id=client.client_id,
                        scopes=authorization_code.scopes,
                    )
        if failure is not None:
            raise TokenError(*failure)
        return OAuthToken(
            access_token=access_token,
            token_type="Bearer",
            expires_in=settings.access_token_ttl,
            scope=" ".join(authorization_code.scopes)
            if authorization_code.scopes
            else None,
            refresh_token=refresh_token,
        )

    async def load_refresh_token(self, client, refresh_token):
        token_hash = sha256_hex(refresh_token)
        with session_scope() as session:
            row = (
                session.query(MCPToken)
                .filter_by(refresh_token_hash=token_hash, revoked=False)
                .one_or_none()
            )
            if row is None or row.client_id != client.client_id:
                return None
            return CaseRaftRefreshToken(
                token=refresh_token,
                client_id=row.client_id,
                scopes=row.scopes.split() if row.scopes else [],
                expires_at=None,  # refresh tokens live until rotated/revoked
                user_id=row.user_id,
            )

    async def exchange_refresh_token(self, client, refresh_token, scopes):
        token_hash = sha256_hex(refresh_token.token)
        failure = None
        with session_scope() as session:
            row = (
                session.query(MCPToken)
                .filter_by(refresh_token_hash=token_hash, revoked=False)
                .one_or_none()
            )
            if row is None:
                # Rotated-away or revoked: the spec-mandated dead-token answer
                failure = ("invalid_grant", "refresh token is no longer valid")
            else:
                # ROTATION: retire the old pair (access token dies with row)
                row.revoked = True
                failure = _subscription_gate_failure(session, row.user_id)
                if failure is None:
                    new_scopes = scopes or (
                        row.scopes.split() if row.scopes else []
                    )
                    access_token, new_refresh_token = _mint_token_pair(
                        session,
                        user_id=row.user_id,
                        client_id=client.client_id,
                        scopes=new_scopes,
                    )
        if failure is not None:
            raise TokenError(*failure)
        return OAuthToken(
            access_token=access_token,
            token_type="Bearer",
            expires_in=settings.access_token_ttl,
            scope=" ".join(new_scopes) if new_scopes else None,
            refresh_token=new_refresh_token,
        )

    # ------------------------------------------------------------------
    # Bearer verification (RequireAuthMiddleware calls verify_token ->
    # load_access_token) and revocation
    # ------------------------------------------------------------------

    async def load_access_token(self, token):
        token_hash = sha256_hex(token)
        now = datetime.utcnow()
        with session_scope() as session:
            row = (
                session.query(MCPToken)
                .filter_by(token_hash=token_hash, revoked=False)
                .one_or_none()
            )
            if row is None or row.expires_at <= now:
                return None
            row.last_used_at = now
            return AccessToken(
                token=token,
                client_id=row.client_id,
                scopes=row.scopes.split() if row.scopes else [],
                expires_at=int(row.expires_at.replace(tzinfo=timezone.utc).timestamp()),
                resource=settings.canonical_mcp_url,
                subject=str(row.user_id),
                claims={"user_id": row.user_id},
            )

    async def revoke_token(self, token):
        """Revoke the whole token row (access + refresh die together)."""
        token_hash = sha256_hex(token.token)
        with session_scope() as session:
            row = (
                session.query(MCPToken)
                .filter(
                    (MCPToken.token_hash == token_hash)
                    | (MCPToken.refresh_token_hash == token_hash)
                )
                .one_or_none()
            )
            if row is not None:
                row.revoked = True

    # ------------------------------------------------------------------
    # Routes: add a root alias for the protected-resource metadata
    # ------------------------------------------------------------------

    def get_routes(self, mcp_path=None):
        """FastMCP publishes RFC 9728 path-scoped metadata at
        /.well-known/oauth-protected-resource/mcp. Also serve the same
        document at the root path, which is the URL our 401
        WWW-Authenticate header points at."""
        routes = super().get_routes(mcp_path)
        for route in list(routes):
            if isinstance(route, Route) and route.path.startswith(
                "/.well-known/oauth-protected-resource/"
            ):
                routes.append(
                    Route(
                        "/.well-known/oauth-protected-resource",
                        endpoint=route.endpoint,
                        methods=["GET", "OPTIONS"],
                    )
                )
        return routes
