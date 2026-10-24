# Certificate Dispatch

A local-first FastAPI + React application for producing personalized, full-resolution participation certificates and individually delivering them through personal Gmail SMTP with an App Password. It persists every state transition in SQLite and never sends as a side effect of import, generation, preview, or automated tests.

## What is included

- Five-step responsive Material UI workflow with persistent session creation/selection on the import step, followed by template/font, generation, email composition, and a combined send/live-dashboard page.
- UTF-8/BOM/quoted CSV parsing, flexible header mapping, atomic active-dataset replacement, immutable historical delivery snapshots, normalized email validation, duplicate blocking, row correction/exclusion, and formula-safe CSV reports.
- Original-resolution JPG/PNG processing with a user-supplied TTF/OTF font, normalized drag/resize coordinates, solid-black participant names, centering, long-name auto-fit, legibility warnings, PDF/PNG output, and ZIP export.
- Gmail SMTP with explicit EHLO/STARTTLS/authentication/envelope/DATA checks, persistent authenticated-session reuse, controlled connection recycling, environment-only App Password storage, configured-account/alias checks, individual messages, safe plain-text placeholders, stable audit headers, and privacy-safe stage diagnostics.
- Durable `PENDING`, `SENDING`, `SENT`, `FAILED`, and `UNCERTAIN` states; background certificate-generation progress; one sequential background SMTP worker; adaptive pacing and optional rolling application cap; exponential retry for definite transient responses; pause/resume; safe failure retry; restart recovery; SSE updates; audit attempts and reports.
- Backend pytest and frontend Vitest coverage. SMTP is mocked in tests; tests never make a real submission.

## Requirements

- Python 3.12 or later
- Node.js 20 or later and npm
- A licensed Citadel Script `.ttf` or `.otf` file (not included)
- For sending only: a personal Gmail account with 2-Step Verification and a Google App Password

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'

cp .env.example .env
# Add SMTP_USERNAME, SMTP_APP_PASSWORD, and SMTP_SENDER_EMAIL to .env

cd frontend
npm install
cd ..
```

Start the backend and frontend in separate terminals from the repository root:

```bash
source .venv/bin/activate
uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

```bash
cd frontend
npm run dev
```

Open <http://127.0.0.1:5173>. Both servers bind to localhost by default. Do not change the host to `0.0.0.0` unless you have added network-level access control and understand that participant data would become reachable from your network.

## Personal Gmail App Password setup

1. Enable 2-Step Verification on the personal Gmail account. App Passwords may be unavailable for Advanced Protection accounts or accounts configured for security-key-only sign-in.
2. While signed into the sending account, open Google Account → Security → App passwords and create a dedicated password for this local certificate tool. Revoke it after the workshop if it is no longer needed.
3. Put the account and the generated 16-character password in the root `.env` file:

   ```dotenv
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USERNAME=your.name@gmail.com
   SMTP_APP_PASSWORD=xxxx xxxx xxxx xxxx
   SMTP_SENDER_EMAIL=your.name@gmail.com
   SMTP_ALLOWED_ALIASES=
   SMTP_TIMEOUT_SECONDS=30
   SMTP_CONNECTION_REUSE=true
   SMTP_MAX_MESSAGES_PER_CONNECTION=25
   SMTP_WORKERS=1
   ```

4. Restart FastAPI after changing `.env`. The UI shows only whether SMTP is configured and the permitted sender identity; it never receives the App Password.

The App Password, database files, uploads, generated certificates, and `.env` are git-ignored. Credentials are read only by the backend, are never placed in messages or logs, and are not exposed through frontend APIs. `SMTP_SENDER_EMAIL` should normally match the Gmail account. Only list aliases already configured and verified under Gmail's “Send mail as” settings in `SMTP_ALLOWED_ALIASES`.

## Operating the workflow safely

1. On **Import Participants**, create a **New Session** for a separate certificate-distribution workflow or select a previous session. The selected session is restored after refresh. Import a CSV such as [`samples/participants.csv`](samples/participants.csv); `Name,Email` is detected automatically. Re-importing replaces only that session's active dataset, with confirmation when generated certificates or delivery activity already exist. Correct/exclude invalid rows before generation.
2. Upload the original certificate image and the exact licensed Citadel Script font. The first valid participant appears immediately in solid black; search for another participant or use the short/medium/longest quick checks. Drag and resize the live name box, tune size/offset/auto-fit, inspect the full-resolution backend-rendered preview, and save placement. Unsaved edits remain visible but are not used by generation until saved.
3. Generate and inspect individual previews or download the ZIP. Generation is local and cannot send mail.
4. Confirm SMTP is configured, enter the configured sender/allowed alias, subject, and plain-text body. Available placeholders are `{{name}}` and `{{workshop_name}}`.
5. Open **Send Certificates**. Review the sender, imported/valid/generated/ready counts, status totals, and allowance. Bulk submission begins only after clicking **Send All Certificates** and typing the exact `SEND N` confirmation. The same page updates through SSE, supports Pause/Resume, and requires a second explicit confirmation before Retry Failed changes definite `FAILED` rows back to `PENDING`. `UNCERTAIN` entries are never retried automatically. Check Gmail Sent, the recipient, timestamp, and delivery reference shown in the table. Use **Found in Sent** only after confirming the message exists, or **Not sent** to convert it to a definite failure; actual resending still requires the separate Retry Failed confirmation. For a controlled test, import a small test CSV and use this same standard workflow.

`SENT` means Gmail's SMTP server accepted the message submission without reporting refused recipients. It does not prove inbox placement, reading, or non-bounce.

## Configuration

See [`.env.example`](.env.example). Important controls:

| Variable | Default | Purpose |
|---|---:|---|
| `APP_HOST` | `127.0.0.1` | Documented local bind address |
| `MAX_UPLOAD_MB` | `25` | Per-upload hard limit |
| `DELIVERY_CONCURRENCY` | `1` | Compatibility setting; delivery intentionally uses one sequential SMTP worker |
| `MAX_EMAILS_PER_DAY` | disabled | Optional conservative application submission cap in any rolling 24-hour period; leave blank to monitor without an app cap |
| `EMAIL_SEND_DELAY_SECONDS` | `5` | Conservative starting interval between SMTP submissions |
| `MIN_EMAIL_SEND_DELAY_SECONDS` | `5` | Lowest interval between SMTP submission start times |
| `MAX_EMAIL_SEND_DELAY_SECONDS` | `120` | Upper bound for adaptive backoff |
| `HEALTHY_SENDS_BEFORE_SPEEDUP` | `5` | Healthy acknowledgments required before reducing the interval by 0.5 seconds |
| `DATABASE_URL` | `sqlite:///./data/certificates.db` | Durable SQLAlchemy database |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | Sole allowed CORS origin |
| `SMTP_HOST` / `SMTP_PORT` | `smtp.gmail.com` / `587` | Gmail SMTP STARTTLS endpoint |
| `SMTP_USERNAME` | — | Personal Gmail account owning the App Password |
| `SMTP_APP_PASSWORD` | — | Google-generated App Password; backend only |
| `SMTP_SENDER_EMAIL` | — | Primary permitted From identity |
| `SMTP_ALLOWED_ALIASES` | empty | Optional comma-separated permitted aliases |
| `SMTP_TIMEOUT_SECONDS` | `30` | Connection and ordinary SMTP command timeout |
| `SMTP_DATA_TIMEOUT_SECONDS` | `300` | DATA upload/final-ack timeout for large certificate attachments |
| `SMTP_CONNECTION_REUSE` | `true` | Reuse the authenticated STARTTLS session for sequential messages |
| `SMTP_MAX_MESSAGES_PER_CONNECTION` | `25` | Reauthenticate on a fresh connection after this many accepted messages |
| `SMTP_WORKERS` | `1` | SMTP workers; intentionally constrained to one for Gmail safety |

Rolling activity is persisted in SQLite and includes accepted messages, active reservations, uncertain submissions, and any preserved legacy test-send records from the preceding 24 hours. Definite failures and sends cancelled before SMTP submission release their reservation. Set `MAX_EMAILS_PER_DAY` only when an administrator wants an additional conservative application cap. Email sending limits depend on the SMTP provider, account type, and current provider restrictions; the application cannot determine or guarantee the provider's remaining allowance. One worker reuses an authenticated STARTTLS session and recycles it after the configured message count. It does not add a redundant `NOOP` round trip before every message: a confirmed failure during `MAIL FROM` or `RCPT TO` discards the session and reconnects safely. Definite temporary SMTP 4xx rejections increase the adaptive delay and are retried with bounded exponential backoff; recognized rate-limit responses pause the batch. A connection loss during DATA, where the provider may already have accepted the payload, becomes `UNCERTAIN` and is never retried automatically.

Five-second pacing is an application target, not a promise that the provider will accept that rate. The interval is measured between submission start times, so a fast SMTP result waits only for the remainder instead of adding the full interval after completion. Temporary failures increase the interval automatically, recognized provider restrictions pause the batch, and provider account restrictions remain authoritative. The dashboard shows the current recipient, job-local processed outcomes, elapsed time, and a rolling estimate based on actual completed attempts.

SMTP diagnostics use structured stage names such as `connect`, `ehlo`, `starttls`, `authentication`, attachment loading, MIME assembly, `mail_from`, `recipient`, and `data`. Each stage records elapsed milliseconds. Logs include only a one-way short job reference, response code, byte count, timings, and exception class—never the App Password, participant address, subject, body, or attachment contents.

### DATA timeout diagnosis

Generated certificates can be large because the original full-resolution template is preserved. A 9.4 MB PDF becomes roughly 12–13 MB after MIME/base64 encoding. Connection setup and ordinary SMTP commands use the short `SMTP_TIMEOUT_SECONDS`, while DATA upload and Gmail's final acknowledgment use `SMTP_DATA_TIMEOUT_SECONDS`. If DATA still ends without a final `250` response, the result remains `UNCERTAIN`; increasing a timeout never changes that safety rule. Use the structured `attachment_loaded`, `mime_ready`, `connection_ready`, and `accepted` timing events to distinguish local file work, TLS/authentication, upload time, and Gmail acknowledgment time.

## Tests and production checks

```bash
source .venv/bin/activate
pytest

cd frontend
npm test
npm run build
```

Tests cover CSV validation and duplicates, report formula defense, solid-black name rendering with the exact supplied font, long/impossible names, placement clipping, pixel-identical live/generated previews, all-recipient PDF validation, outdated-certificate protection, delivery transitions, atomic duplicate prevention, pause/resume safety, explicit failed-only retry, rolling quota accounting, restart recovery, persistent SMTP reuse/recycling, adaptive pacing, mocked STARTTLS/App Password stages, Gmail rate-limit pausing, privacy-safe diagnostics, definite/transient/uncertain outcomes, a 200-recipient mocked performance run, API import/report behavior, and dashboard rendering.

Before a real workshop run, back up the `data/` directory, perform a small controlled test batch, confirm the Gmail account and any verified alias, and retain the exported report. SQLite is appropriate for this single-operator local application; do not run multiple backend processes against the same batch.

## Project layout

```text
backend/app/            FastAPI routes, SQLAlchemy models, services, worker
backend/tests/          Unit and integration tests (mocked delivery)
frontend/src/           React/TypeScript Material UI wizard and dashboard
frontend/public/        Browser-accessible sample CSV
samples/                Repository sample CSV
data/                   Runtime SQLite/uploads/generated output (ignored)
```

## API notes

Interactive OpenAPI documentation is available at <http://127.0.0.1:8000/docs>. Header mapping for unusual CSVs is exposed as `name_column` and `email_column` multipart fields on the import endpoint. This makes it possible to map arbitrary columns even though the streamlined UI auto-detects common headings.
