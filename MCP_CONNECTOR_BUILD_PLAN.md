# CaseRaft MCP Connector: Build Plan

Goal: ship "CaseRaft for Claude", a hosted remote MCP connector that lets any lawyer
connect their Clio Manage account to Claude (claude.ai, Desktop, Cowork, Claude Code)
in one click. No npm, no self-hosting, no API keys. CaseRaft hosts the server,
holds the Clio OAuth relationship, and gates access behind the existing Stripe plans.

Positioning: the safe, listed, one-click Claude to Clio bridge for non-technical
lawyers. Community MCP servers (oktopeak/clio-mcp, lawyered0/clio-mcp) exist but
require self-hosting. There is no official Clio MCP as of July 2026. Window is open.

Demand evidence (Clio Users FB group, "Has anyone used Claude with CLIO", May 17,
52 comments): multiple lawyers failing to DIY the connection, one non-technical
lawyer running 20 Claude skills against Clio daily, requests for daily digests,
status-update drafting, intake summaries, probate accounting, immigration packets.
Shameka Rhoades (already a CaseRaft whitelisted user, srhoades@trustice.us) posted
"I have been trying to do this, but failing."

---

## Architecture

Two services, one database.

1. Existing Flask app (caseraft.com): unchanged except a small consent surface
   and a settings card. Keeps owning Clio OAuth, users table, Stripe, audit log.
2. New MCP service (mcp.caseraft.com): separate Railway service. Python MCP SDK
   (FastMCP) on uvicorn (ASGI). Speaks streamable HTTP (the current transport;
   legacy SSE is deprecated). Reads the same Postgres: users table for Fernet
   encrypted Clio tokens, new tables for MCP clients/tokens, audit_logs for
   tool-call logging.

Why a separate service: the Flask app runs sync gunicorn (2 workers, 120s hard
timeout, per-worker memory). Streamable HTTP wants ASGI and no aggressive
timeout. claude.ai allows tool calls up to 300s. Do not retrofit Flask.

Auth model (two OAuth hops, distinct roles):
- Hop 1 (exists): CaseRaft is an OAuth CLIENT of Clio. User signs in, we hold
  encrypted access/refresh tokens per user.
- Hop 2 (new): CaseRaft is an OAuth 2.1 SERVER for Claude. Claude discovers our
  metadata, registers via Dynamic Client Registration, runs authorization code +
  PKCE, and receives a CaseRaft-issued token bound to one user row. Claude's
  callback URL: https://claude.ai/api/mcp/auth_callback (plus loopback for
  Claude Code).

Request path: Claude -> mcp.caseraft.com (CaseRaft MCP token) -> resolve user ->
decrypt Clio token (auto-refresh if near expiry, logic already in ClioAPIClient)
-> Clio API v4 -> compute -> JSON tool result (cap ~150k chars) -> audit log.

Rate limits: Clio limits are per user access token (~50 req/min peak), so load
scales per user. Existing 429/Retry-After handling in clio_client.py carries over.

Cost model: inference runs on the user's own Claude subscription. CaseRaft pays
only for the proxy service. Custom connectors are available on every Claude plan
(Free limited to one connector), so any Clio lawyer with any Claude account is
addressable.

---

## Phase 0: Spikes (half a day) — DONE 2026-07-24

- [x] 0.1 Hello-world FastMCP 3.4.4 streamable HTTP server verified locally
      (uv venv, python 3.12). Programmatic client probe: initialize ->
      tools/list -> tools/call all pass, structured JSON results confirmed.
      Spike code kept in session scratchpad (mcp-spike/hello.py + probe.py);
      port into mcp-service/ in Phase 1.
- [x] 0.2 DECIDED: FastMCP's built-in `OAuthProvider` base class (full OAuth
      server: DCR, PKCE, metadata endpoints) — no Authlib. Key facts from the
      claude.com authentication doc that shape Phase 1:
      - Discovery: return 401 with `WWW-Authenticate: Bearer
        resource_metadata="https://mcp.caseraft.com/.well-known/
        oauth-protected-resource"`. Claude does NOT honor the header on 200s.
      - Protected resource metadata `resource` field must match the MCP URL
        exactly as users type it (decide canonical URL: with or without
        trailing path, and publish only that).
      - PKCE S256 mandatory; advertise `code_challenge_methods_supported:
        ["S256"]`.
      - `/token` must accept application/x-www-form-urlencoded (register a
        form parser; /register uses JSON — different parsers).
      - Rotate refresh tokens (public client), return `invalid_grant` on dead
        refresh tokens, include `offline_access` in scopes_supported to get
        refresh-token behavior.
      - Callbacks: `https://claude.ai/api/mcp/auth_callback` + Claude Code
        loopback (`localhost`/`127.0.0.1` any port — port-agnostic match).
      - Latency budget: 10s on discovery/registration/token, 30s on refresh.
      - Anthropic egress: 160.79.104.0/21 (for any WAF/allowlist).
      - At directory scale later, prefer CIMD or Anthropic-held creds over
        DCR (DCR registers a new client per connection). DCR fine for MVP.
- [x] 0.3 Clio OAuth app verified ALIVE (2026-07-24): GET /oauth/authorize
      with the configured client_id + redirect_uri issues a real
      login_challenge and lands on account.clio.com/login — an invalid/dead
      client_id errors before that. No new scopes needed for the endpoints
      clio_client.py already uses (prod reports prove them). FOLLOW-UPS for
      live testing, not blockers: (a) confirm the dev trial ACCOUNT still
      accepts sign-in (memory says trial->free-dev conversion was due ~June 5);
      (b) daily_digest adds tasks.json + calendar_entries.json — if those 403
      on first live call, add task/calendar scopes to the app registration in
      the Clio developer portal (portal login required, Shobinn action).

Exit: met — transport verified, auth approach chosen, Clio app confirmed live.

## Phase 1: MCP service skeleton + OAuth server (2-3 days)

- [ ] 1.1 New top-level dir `mcp-service/` in this repo (own pyproject, own
      Dockerfile, python:3.11-slim, uvicorn). Shares nothing with Flask at
      import time; talks only to Postgres.
- [ ] 1.2 Port the minimum shared code: a thin read-only copy of the User lookup
      + crypto.decrypt_token + ClioAPIClient (import via a small `caseraft_core`
      package or straight copy; do not import the Flask app). Token refresh must
      WRITE BACK to the users table exactly like the Flask path does.
- [ ] 1.3 Schema additions (alembic migration lives with the Flask app since it
      owns migrations):
      - `mcp_clients` (id, client_id, client_name, redirect_uris JSON,
        created_at) for DCR registrations.
      - `mcp_auth_codes` (code hash, user_id, client_id, PKCE challenge,
        expires_at, used bool).
      - `mcp_tokens` (token hash, user_id, client_id, scopes, expires_at,
        revoked bool, last_used_at). Store only hashes.
- [ ] 1.4 OAuth 2.1 server endpoints on mcp.caseraft.com:
      - `/.well-known/oauth-protected-resource` (points at the AS)
      - `/.well-known/oauth-authorization-server` (metadata)
      - `POST /register` (DCR)
      - `GET /authorize` (redirects into caseraft.com consent, below)
      - `POST /token` (code + PKCE exchange, refresh grant)
      - `POST /revoke`
- [ ] 1.5 Consent surface on the FLASK app (it owns sessions and Clio login):
      `GET /connect/authorize?...` renders "Claude wants to access your Clio
      data through CaseRaft" with the tool list. If not signed in, run the
      existing Clio OAuth login first. On approve, mint an auth code in
      mcp_auth_codes and redirect to Claude's callback. Subscription gate here:
      require is_paid or is_whitelisted (reuse existing helpers).
- [ ] 1.6 Bearer auth middleware in the MCP service: hash lookup in mcp_tokens,
      reject expired/revoked, stamp last_used_at, attach user to request ctx.
- [ ] 1.7 Tests: DCR happy path, PKCE verify failure, expired code, revoked
      token, subscription-lapsed user gets 403 with a clear message.

Exit: `claude mcp add` and claude.ai Settings > Connectors both complete the
OAuth dance against staging and list zero tools without erroring.

## Phase 2: Tools v1, read-only (2 days)

All tools reuse ClioAPIClient methods and the existing computation classes
(firm_data.py, case.py). Return compact JSON, never PDFs. Every call writes
record_audit-equivalent rows (user_id, tool, args hash, timestamp, status).
Truncate any list beyond a sane cap and say so in the result.

- [ ] 2.1 `whoami` : current Clio user, firm, plan tier. (Trivial, proves auth.)
- [ ] 2.2 `list_matters(status?, query?, limit=25)` : id, display_number,
      description, client name, status, practice area.
- [ ] 2.3 `get_matter(matter_id)` : matter detail + related contacts + billing
      summary (reuse Case/BillingSummary from services/case.py).
- [ ] 2.4 `search_contacts(query)` and `get_contact(contact_id)`.
- [ ] 2.5 `firm_productivity(start, end)` : per-employee hours, billable split,
      realization/collection/utilization, invoice aging (FirmProductivityData).
- [ ] 2.6 `outstanding_revenue(start, end)` : collected vs outstanding AR by
      practice area + aging bucket (RevenueByPracticeAreaData).
- [ ] 2.7 `trust_balances()` : balances vs thresholds, per-client deficits
      (TrustManagementData). Remove the single-email hard allowlist for this
      path; gate by plan tier instead.
- [ ] 2.8 `daily_digest(date?)` : today's tasks + calendar entries + unpaid
      bills + recent activity, one call. This is the marquee demo tool (the FB
      thread's most repeated want). Needs two small ClioAPIClient additions:
      `tasks.json` and `calendar_entries.json` (GET only).
- [ ] 2.9 MCP prompts (starter skill pack, ships with the server):
      "morning-digest", "status-update-email", "intake-summary". Prompts are
      supported by claude.ai connectors and cost nothing to serve.
- [ ] 2.10 Tests: each tool against the existing mock Clio data path
      (mock_clio_data.py), plus one live smoke against the dev Clio account.

Deliberately NOT in v1: any write tool. Read-only means zero malpractice
surface while validating. v0.2 candidates behind a per-user toggle:
create_task, create_note, log_time_entry.

## Phase 3: Deploy + wire-up (1 day)

- [ ] 3.1 Second Railway service from `mcp-service/Dockerfile`. Env:
      DATABASE_URL (same Postgres), TOKEN_ENCRYPTION_KEY, CLIO_* (for refresh),
      SENTRY_DSN. No 120s timeout; uvicorn defaults.
- [ ] 3.2 DNS: mcp.caseraft.com -> Railway. TLS automatic.
- [ ] 3.3 CORS/origin: MCP streamable HTTP is server-to-server from Anthropic
      infra; no browser CORS needed on the MCP host. The consent page lives on
      caseraft.com so existing CORS config is untouched.
- [ ] 3.4 Monitoring: Sentry in the MCP service, Better Stack check on
      mcp.caseraft.com/health, Slack #caseraft-alerts on OAuth failures and
      tool error spikes (reuse alert conventions).
- [ ] 3.5 End-to-end on prod: connect from claude.ai (personal account), run
      whoami + daily_digest + outstanding_revenue against the dev Clio account.

## Phase 4: Product wrapper + beta (2-3 days, overlaps 3)

- [ ] 4.1 caseraft.com/connect : onboarding page written for the non-technical
      persona. Three steps with screenshots: copy URL, paste in Claude Settings
      > Connectors, sign in with Clio. Include Claude Desktop + mobile notes.
- [ ] 4.2 caseraft.com/security : answers the exact questions from the thread.
      Encrypted tokens at rest, every access audit-logged, read-only tools,
      Anthropic does not train on paid-plan data, revoke anytime (button in
      settings kills mcp_tokens rows).
- [ ] 4.3 Settings card in the app: connection status, last used, revoke.
- [ ] 4.4 Pricing decision: fold into existing tiers as the headline feature
      (recommended: connector included in Solo $29 and up; raw reports remain
      the free hook) OR a new AI tier. Decide before public launch, not before
      beta.
- [ ] 4.5 Private beta: Shameka first (she is whitelisted, already demoed
      CaseRaft, and publicly asked for this). Then 3-5 volunteers from the
      thread (Becca BC hit Claude usage limits, Ashley McDuffie could not
      connect at all, Mark Montanaro asked "how").
- [ ] 4.6 Launch posts: reply in the original FB thread (group allows product
      mentions; mirror Andrew Stein's ask-first etiquette), founder post on
      LinkedIn Page, update the Clio App Directory listing copy to mention
      Claude connectivity (factual wording only, no Clio endorsement implied,
      keep the existing compliance playbook).
- [ ] 4.7 Submit to the Anthropic connectors directory (claude.com/docs/
      connectors/building/submission) once 10+ active users and stable.

---

## Testing matrix

- MCP inspector: auth flow + every tool schema.
- Claude Code (`claude mcp add`): fastest iteration loop.
- claude.ai web + Desktop: the real customer surface, verify OAuth + prompts UI.
- Token refresh: force-expire a Clio token, confirm mid-conversation refresh.
- Limits: matter list on a 1000-matter account stays under the 150k char cap.
- Revocation: revoke in settings, confirm Claude gets a clean auth error.

## Risks and mitigations

- Clio ships an official MCP: moat becomes curated legal workflows, computed
  reports (productivity, AR, trust), audit trail, and support. Ship fast, own
  the workflows, keep the report tools that a raw pipe will not have.
- Clio TOS sensitivity (FasterLaw precedent): per-user OAuth through a listed
  App Directory app is the sanctioned model. No bulk scraping, no shared
  tokens, respect rate limits. Optionally give partnerships a heads-up note
  through the existing contact once beta works.
- OAuth is the known stumbling block (Anthropic says so): Phase 0 spike +
  inspector-first development. Do not build tools until the dance passes.
- Confidentiality optics: read-only v1, security page, audit log export on
  request. Never store Clio response bodies beyond request lifetime.
- Dead Clio dev trial account risk (existing issue): confirm the dev account
  used for testing is the fresh Manage app from 5/30, not App 211.

## Open decisions (answer during Phase 0/1)

1. FastMCP built-in auth vs Authlib custom AS. Default FastMCP unless blocked.
2. Package sharing between Flask and MCP service: extract `caseraft_core` vs
   copy the 3 files. Copy is fine for MVP; extract when it hurts.
3. Pricing placement (4.4).
4. Name: "CaseRaft for Claude" vs "CaseRaft Connect". Listing copy needs it by
   Phase 4.

## Effort summary

Phase 0: 0.5 day. Phase 1: 2-3 days. Phase 2: 2 days. Phase 3: 1 day.
Phase 4: 2-3 days (partly parallel). Total: 8-10 working days part-time,
about a week focused. First live end-to-end demo possible after Phase 3,
roughly day 5.
