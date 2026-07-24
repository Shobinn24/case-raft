# Phase 1 implementation notes (MCP service skeleton + OAuth server)

Status: Phase 1 tasks 1.1 through 1.7 implemented. Nothing deployed; no
commits made. Both test suites green (backend: 59 = 52 existing + 7 new
consent tests; mcp-service: 19).

## What exists

```
mcp-service/
  pyproject.toml            python 3.12; fastmcp, sqlalchemy, psycopg2-binary,
                            cryptography, requests, uvicorn
  Dockerfile                python:3.12-slim, uvicorn, PORT env
  caseraft_mcp/
    config.py               env settings; postgres:// -> postgresql:// fixup
    crypto.py               Fernet encrypt/decrypt ported from Flask
                            (byte-compatible, verified cross-service),
                            EncryptedText column type, sha256_hex helper
    db.py                   users table (subset, read-write) + mcp_clients /
                            mcp_auth_codes / mcp_tokens; engine per process,
                            session per unit of work
    clio_client.py          ClioAPIClient port: 429/Retry-After, retries,
                            refresh with encrypted write-back to users
    oauth.py                CaseRaftOAuthProvider (FastMCP OAuthProvider
                            subclass): DCR, authorize-relay, token, refresh
                            rotation, revoke, bearer verification
    server.py               FastMCP "CaseRaft" app, /mcp streamable HTTP
                            (stateless + JSON responses), whoami tool,
                            unauthenticated /health
  tests/                    19 tests, sqlite, Clio HTTP mocked

backend/ (Flask, additive only)
  app/models/mcp.py                     mirror models for the three tables
  app/routes/connect.py                 /connect/authorize consent surface
  app/__init__.py                       + connect_bp registration (only
                                        existing file touched)
  migrations/versions/c4d8f1a92e57_...  the three tables (head after
                                        b7e2c1a4f9d0); verified with
                                        flask db upgrade on a scratch DB
  tests/test_connect.py                 7 consent tests
```

## Canonical URL decision

The canonical MCP URL is exactly `https://mcp.caseraft.com/mcp` (no trailing
slash). It is the `resource` value in the protected-resource metadata and the
only form that may appear in docs/onboarding/listing copy, because Claude
matches metadata `resource` against the URL as the user typed it.

Protected-resource metadata is served at BOTH:

* `/.well-known/oauth-protected-resource` (root; this is the URL the 401
  `WWW-Authenticate` header carries, per the Phase 0 requirement)
* `/.well-known/oauth-protected-resource/mcp` (RFC 9728 path-scoped form
  that FastMCP emits natively)

Both return the same document. FastMCP's built-in 401 header points at the
path-scoped URL, so `server.py` wraps the app in a tiny ASGI middleware that
rewrites the header on 401s from `/mcp` to the exact required value:

    WWW-Authenticate: Bearer resource_metadata="https://mcp.caseraft.com/.well-known/oauth-protected-resource"

## How the consent relay works (no deviation from the two-service design)

FastMCP's `OAuthProvider.authorize()` returns a URL that the SDK 302s the
browser to, which fits the relay design directly: it returns
`CONSENT_URL?response_type=code&client_id=...&redirect_uri=...&code_challenge=...
&code_challenge_method=S256&state=...&scope=...` and the Flask app does
login + subscription gate + consent, mints the code into `mcp_auth_codes`
(SHA-256 hash only), and 302s straight to Claude's callback with
`code` + `state`. The MCP service sees the code again only at `/token`,
where the SDK handler does the PKCE S256 verification against the stored
`code_challenge`.

## Decisions and small deviations

1. **Public clients only.** `mcp_clients` intentionally stores no client
   secret (spec'd columns: id, client_id, client_name, redirect_uris,
   created_at). `register_client` therefore normalizes every registration to
   `token_endpoint_auth_method: "none"` and returns no secret. PKCE is the
   security boundary; this matches how Claude registers anyway.
   `get_client` reconstructs the client with fixed grant/response types and
   the full supported scope set.

2. **`redirect_uri_provided_explicitly` is always treated as True.** The
   auth-codes table has no column for it and the relay always forwards a
   resolved redirect_uri. Consequence: a client that omits redirect_uri at
   /authorize AND at /token would fail the exchange. Claude always sends it;
   acceptable.

3. **Subscription-lapsed users at /token get `invalid_grant`** (HTTP 401 via
   FastMCP's spec-compliant token handler) with an error_description that
   names the upgrade URL. The "403 with a clear message" from plan task 1.7
   is not possible on the token endpoint without violating RFC 6749 error
   codes; the human-readable 403 upgrade page lives on the Flask consent
   surface instead, which is where a human actually sees it.

4. **Refresh tokens rotate by revoking the whole old row**, so the old
   access token dies together with the old refresh token. Dead refresh
   tokens produce `invalid_grant` (SDK path when `load_refresh_token`
   returns None). Refresh tokens have no expiry in Phase 1 (rows live until
   rotation or revocation; the Phase 4 settings kill switch flips `revoked`).

5. **Loopback redirect matching** (Claude Code): `http://localhost` and
   `http://127.0.0.1` are interchangeable, ANY port matches (RFC 8252 7.3),
   path must match the registered path. Registration itself only accepts
   Claude's callback (`https://claude.ai/api/mcp/auth_callback`) and
   loopback URIs. The Flask consent page enforces the identical policy.

6. **Stateless streamable HTTP with JSON responses.** No sticky sessions
   needed under multiple uvicorn workers or Railway replicas; matches the
   session-per-request DB design. Revisit only if server-initiated
   notifications/sampling are ever needed.

7. **Signed-out bounce is one-way in Phase 1.** `/connect/authorize` stashes
   the authorization request in the session and redirects to `/auth/login`.
   The existing `/auth/callback` redirects to `/cases` (that file was NOT
   modified per the phase constraints), so after login the user is not
   automatically returned to the consent page (revisiting the consent URL
   resumes via the stash). Before the claude.ai end-to-end test, add a
   two-line change to `auth.callback`: if `session["mcp_authorize_params"]`
   exists, redirect to `/connect/authorize` instead of `/cases`.

8. **DB calls in async provider methods are synchronous.** Each is a few
   indexed lookups; acceptable at Phase 1 scale. If tool traffic grows,
   move to `anyio.to_thread` or async SQLAlchemy.

9. **Frozen-dataclass gotcha (SDK).** `TokenError` is a frozen dataclass and
   contextlib assigns `__traceback__` on exceptions raised through a
   `@contextmanager`, so TokenErrors must be raised OUTSIDE `session_scope()`
   blocks. `oauth.py` collects failures inside the session and raises after.

10. **`/revoke` requires the `client_secret` KEY** in the form (SDK pydantic
    model quirk); public clients can send it empty. Harmless, noted in case
    a client ever 400s on revocation.

11. **Repo venv is broken.** `venv/bin/python3` at the repo root is
    SIGKILLed by macOS (stale binary, likely from an OS/python upgrade).
    Backend tests were run in a fresh python 3.12 venv installed from
    `backend/requirements.txt`. Recreate the repo venv when convenient.

## Running locally

```bash
cd mcp-service
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e . pytest httpx
DATABASE_URL=... TOKEN_ENCRYPTION_KEY=... CLIO_CLIENT_ID=... CLIO_CLIENT_SECRET=... \
MCP_ISSUER_URL=http://localhost:8300 CONSENT_URL=http://localhost:5000/connect/authorize \
.venv/bin/uvicorn caseraft_mcp.server:app --port 8300

.venv/bin/python -m pytest tests -q     # 19 tests
```

## Open items for the claude.ai end-to-end test (Phase 1 exit / Phase 3)

- [ ] Apply the migration to staging/prod Postgres (`flask db upgrade`).
- [ ] Auth-callback return hop for signed-out users (note 7 above).
- [ ] Deploy mcp-service to Railway, DNS mcp.caseraft.com, then
      `claude mcp add` and claude.ai Settings > Connectors against staging:
      the dance must complete and list the whoami tool without erroring.
- [ ] Confirm the Clio dev trial ACCOUNT still accepts sign-in (Phase 0
      follow-up (a)) so whoami can be exercised live.
- [ ] Verify discovery latency budget (10s) once behind Railway TLS.
- [ ] Decide whether to periodically purge expired/used mcp_auth_codes and
      expired revoked mcp_tokens (cron or opportunistic delete).

---

# Phase 2 implementation notes (Tools v1, read-only)

Status: plan tasks 2.1 through 2.10 implemented (2.10's live smoke against
the dev Clio account is deferred to deployment, matching the Phase 3 E2E
item). File renamed from PHASE1_NOTES.md.

## Tools shipped (all read-only, all bearer-resolved, all audit-logged)

| Tool | Notes |
|---|---|
| whoami | Phase 1 tool, now audit-logged like the rest |
| list_matters(status, query, limit=25) | compact rows, cap 100, truncated flag |
| get_matter(matter_id) | detail + related contacts grouped by role + billing summary (Case/BillingSummary port) |
| search_contacts(query, limit=10) | cap 25, truncated flag; new Clio client method (contacts.json query param) |
| get_contact(contact_id) | full contact detail |
| firm_productivity(start, end) | FirmProductivityData port: per-employee + firm totals, realization/collection/utilization, invoice aging |
| outstanding_revenue(start, end) | RevenueByPracticeArea port, BOTH collected and outstanding views by practice area x aging bucket |
| trust_balances() | TrustManagementData port. The Flask app's single-email allowlist was NOT carried over: any paid or whitelisted user may call it (plan task 2.7) |
| daily_digest(date=None) | tasks due/overdue + calendar + unpaid bills (trailing 365 days) + summary counts; date defaults to today in the user's timezone |

Prompts (FastMCP @mcp.prompt): morning_digest, status_update_email(matter),
intake_summary(matter).

## New/changed modules

```
caseraft_mcp/computations.py  ports of case.py + firm_data.py classes
                              (Flask-free; format_currency helpers dropped,
                              raw numbers in JSON instead)
caseraft_mcp/tools.py         all tools + prompts + shared plumbing
caseraft_mcp/audit.py         record_audit mirroring app/services/audit.py
                              (best-effort, never raises into the tool)
caseraft_mcp/db.py            + AuditLog mirror model, + users.timezone
caseraft_mcp/clio_client.py   + query param on get_matters,
                              + search_contacts, list_tasks,
                              + list_calendar_entries
caseraft_mcp/server.py        thin now; registers tools/prompts
tests/clio_fixtures.py        realistic Clio v4 shapes (mirrors
                              mock_clio_data.py plus tasks/calendar/firm data)
tests/test_tools.py           18 new tests
```

## Decisions and notable details

1. **Audit rows** land in the SAME audit_logs table the Flask app owns,
   action "mcp.tool.<name>", resource_type "mcp_tool", user_agent
   "caseraft-mcp", ip_address NULL (calls arrive server-to-server from
   Anthropic infra). Detail carries argument SHAPES only: limits, statuses,
   dates, id references, and query LENGTHS. Search text and any client
   names never reach the audit table. Status (ok/error) is appended to the
   detail string. Tool result payloads are never persisted (confidentiality
   rule from the plan).

2. **Caps**: matters 100, contacts 25, digest lists 50; every capped list
   has a truncated flag and counts in summaries reflect pre-cap totals.
   With these caps outputs are a few KB, far below the 150k char budget.

3. **Timezones**: users.timezone stores Rails-style names from Clio
   ("Eastern Time (US & Canada)"). A small map covers the common US/Canada
   zones -> IANA; unmapped values are tried as IANA names and fall back to
   UTC. daily_digest reports which timezone it used.

4. **New Clio endpoints** (tasks.json, calendar_entries.json, contacts.json
   query search) follow Clio v4 index-filter conventions
   (assignee_id/assignee_type, complete, due_at_from/due_at_to, from/to).
   Clio HTTP is mocked in tests, so the param names and any missing task or
   calendar scopes must be confirmed on the first live call (this is
   exactly Phase 0 follow-up (b); add scopes in the Clio developer portal
   if those endpoints 403).

5. **Error hygiene**: unexpected exceptions inside a tool are logged
   server-side and surfaced to the model as a generic ToolError (type name
   only), because Clio error bodies can echo request contents.

6. **daily_digest unpaid bills** look back 365 days from the target date
   (get_all_bills_simple filter), excluding paid/void/deleted states.

## Test counts after Phase 2

- mcp-service: 37 passed (19 Phase 1 + 18 Phase 2)
- backend Flask: 59 passed (unchanged; no Flask files touched in Phase 2)

## Open items (carried + new)

- [ ] All Phase 1 open items (migration to prod, auth-callback return hop,
      Railway deploy + DNS, discovery latency, code/token purging).
- [ ] Live-verify tasks.json + calendar_entries.json param names and scopes
      against the dev Clio account; add scopes in the portal if 403.
- [ ] Live smoke of each tool against the dev Clio account after deploy
      (plan 2.10), including the 1000-matter cap behavior.
- [ ] Consent page tool list (Flask connect.py) still shows only whoami with
      a "coming soon" note; update TOOL_DESCRIPTIONS when Phase 2 deploys
      (deliberately not touched now to keep Flask frozen this phase).
