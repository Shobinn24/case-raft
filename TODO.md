# Case Raft — Architectural TODOs

These were identified during the 2026-04-09 security/quality review but
were intentionally deferred from the fix pass because they require user
decisions on infra, migration strategy, or third-party providers. Each
one is a real gap — not a nice-to-have — and should be picked up as its
own scoped piece of work.

## 1. Encrypt Clio OAuth tokens at rest (review #6)

**Where:** `backend/app/models/user.py:11-12` — `clio_access_token` and
`clio_refresh_token` are stored as plaintext `db.Column(db.Text)`.

**Why it matters:** A database dump leaks live Clio credentials for every
connected firm. An attacker with those tokens can read every case,
contact, invoice, and trust balance in the affected tenants.

**What's needed before doing it:**
- Pick an encryption key strategy (suggested: Fernet, with key in
  `TOKEN_ENCRYPTION_KEY` env var, rotatable via `MultiFernet`).
- Design the migration: add new `clio_access_token_encrypted` /
  `clio_refresh_token_encrypted` columns → backfill encrypted values →
  switch reads to the new columns → drop the old columns in a second
  migration. Needs a maintenance window or a dual-read fallback.
- Decide key rotation policy — who holds the key, how it's rotated, and
  what happens to rows encrypted under retired keys.

**Suggested library:** `cryptography.fernet.Fernet` with getter/setter
properties on the `User` model.

## 2. Move generated PDFs off ephemeral disk (review #15)

**Where:** `backend/app/services/report.py:73` writes PDFs to
`generated_reports/` and `backend/app/routes/reports.py:379` serves them
from that path.

**Why it matters:** Railway containers have ephemeral filesystems, so
every deploy wipes the generated-reports directory. Users who try to
re-download a report after a deploy get a 404.

**Options to choose from:**
- **S3 (or Railway Volume-less equivalent):** store PDF bytes on S3,
  keep only the object key in `report_history.file_path`. Most scalable.
  Adds boto3 dependency and an AWS bill.
- **Railway Volumes:** persistent disk addon. Least code change — just
  mount a volume and point `generated_reports/` at it. Cheap but
  Railway-specific.
- **Regenerate on download:** store the report source data as JSON in
  the DB and re-run the renderer when the user clicks download. No
  object store needed, but doubles compute on downloads and means a
  schema change to the Clio API breaks historical reports.

**Recommended:** S3 for clean separation; Volumes if we want to ship
quickly.

## 3. Background queue for PDF generation (review #19)

**Where:** `backend/app/routes/reports.py:generate_report` and
`generate_batch_reports`. Both block the request thread on
`report.generate()` which fans out multiple Clio calls plus WeasyPrint.

**Why it matters:** Batch reports (up to 20 matters) routinely take 60–
180 seconds. With the two-worker gunicorn config applied in the recent
security pass, this is tolerable but still pins one worker per batch.
With any more traffic it's a DoS against ourselves.

**Options:**
- **Celery + Redis:** most conventional. Heavier infra — needs a worker
  process on Railway and a Redis addon.
- **RQ (Redis Queue):** lighter than Celery, same Redis dependency.
- **ThreadPoolExecutor in-process:** no new infra; loses work on worker
  restarts and doesn't survive multi-instance scale-out.

This also unblocks doing things like "email the user when the batch is
done."

## 4. Email notification on payment failed (review #24)

**Where:** `backend/app/services/stripe_service.py:handle_payment_failed`
marks the user as `past_due` but doesn't notify them.

**Why it matters:** Users whose cards fail silently get a degraded
dashboard until they stumble onto the billing page. For a B2B SaaS
billing users monthly, that's the largest preventable churn cause.

**What's needed:**
- Pick an email provider: Postmark (best deliverability for
  transactional), SendGrid (cheapest), or Mailgun (middle ground).
- Add an `EMAIL_FROM` env var and API key.
- Build a simple `send_email(to, subject, body)` helper so we can also
  use it for welcome emails and report-ready notifications later.

---

## Not in this list

The review covered 40+ findings; everything that could be safely fixed
in code without needing user sign-off was done in the batches above (see
`SESSION_HANDOFF.md` for the breakdown, which is gitignored intentionally).

The only other architectural call that was deferred is test coverage
beyond the critical-path tests added in the last batch. Raising coverage
is a continuous effort rather than a single TODO, so it's tracked in the
CI story, not here.
