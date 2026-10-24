<div align="center">
  <img src="frontend/public/branding/certloop-logo.png" alt="CertLoop" width="520">
  <h1>CertLoop</h1>
  <p><strong>Generate. Personalize. Deliver.</strong></p>
  <p>A local-first application for generating personalized PDF certificates and distributing them through Gmail SMTP.</p>

  <p>
    <img alt="Python 3.12+" src="https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white">
    <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white">
    <img alt="React 19" src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=20232A">
    <img alt="TypeScript 5.8" src="https://img.shields.io/badge/TypeScript-5.8-3178C6?logo=typescript&logoColor=white">
  </p>
</div>

## Overview

CertLoop provides a five-step workflow for importing participants, designing certificates, generating personalized PDFs, composing messages, and monitoring delivery. Named sessions keep participant lists, certificate settings, email templates, generated files, and delivery history separate.

Certificate work does not send email. Delivery begins only after an operator explicitly confirms a bulk send.

## Features

- Create uniquely named sessions with backend-generated IDs and isolated data.
- Import CSV participant lists, map columns, validate names and email syntax, detect duplicates, and edit or exclude rows.
- Upload JPG or PNG certificate templates and position a draggable, resizable participant-name area.
- Use the included Bitstream Vera Sans default or upload a licensed TTF/OTF font, including Citadel Script, per session.
- Adjust font size, minimum size, vertical offset, and long-name auto-fit with an immediate full-resolution preview.
- Generate personalized PDF certificates in a batch with live progress updates.
- Search participants to preview and download individual certificates or download current certificates as a ZIP archive.
- Regenerate certificates for valid participants—including previously `SENT` participants—without resending email or changing delivery status.
- Preserve versioned certificate files and historical delivery-attempt attachment references.
- Edit the email sender, subject, and plain-text body with the `{name}` personalization placeholder.
- Send PDF attachments through Gmail SMTP with App Password authentication and verified sender aliases.
- Monitor `PENDING`, `SENDING`, `SENT`, `FAILED`, and `UNCERTAIN` states in real time.
- Pause and resume delivery, retry definite failures, and reconcile uncertain outcomes without automatic duplicate sends.
- Export a CSV delivery report containing recipient status and attempt information.

Certificate regeneration only creates a newer certificate artifact. It never automatically sends email, resets delivery states, or makes a previously sent participant eligible for the normal bulk-send queue.

## Screenshots

Application screenshots are not currently included in the repository.

<!-- Add sanitized screenshots here after placing them in docs/screenshots/. -->

## Tech Stack

| Area | Technology |
|---|---|
| Frontend | React 19, TypeScript 5.8, Vite 6, Material UI 7 |
| Backend | FastAPI, Pydantic, Uvicorn |
| Persistence | SQLAlchemy, SQLite |
| Certificates | Pillow, ReportLab |
| Live updates | Server-sent events (SSE) |
| Email | Gmail SMTP with STARTTLS and App Password authentication |
| Testing | pytest, Vitest, Testing Library |

## Getting Started

### Prerequisites

- Python 3.12 or later
- Node.js 18, 20, or 22+ and npm, matching the Vite 6 runtime requirement
- A JPG or PNG certificate template
- A Gmail account with 2-Step Verification and an App Password only when email delivery is needed
- Bash and `lsof` when using the included helper scripts on macOS or Linux

A custom font is optional. CertLoop uses Bitstream Vera Sans from ReportLab by default. Only upload fonts and certificate artwork you are permitted to use.

### Install

Run these commands from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'

cp .env.example .env

cd frontend
npm ci
cd ..
```

### Start the application

Start both development servers:

```bash
./start-dev.sh
```

Or start them in separate terminals:

```bash
./start-backend.sh
```

```bash
./start-frontend.sh
```

Manual equivalents are:

```bash
.venv/bin/python -m uvicorn app.main:app \
  --app-dir backend --reload --host 127.0.0.1 --port 8000
```

```bash
cd frontend
npm run dev -- --host 127.0.0.1
```

Open the application at <http://127.0.0.1:5173>. FastAPI documentation is available at <http://127.0.0.1:8000/docs>.

SQLite tables and safe additive migrations are applied automatically when the backend starts. Runtime data is stored under `./data` by default; the database is not recreated during normal startup.

CertLoop binds to localhost by default. Add authentication and appropriate access controls before exposing it to a network.

## Environment Configuration

Copy [`.env.example`](.env.example) to `.env`. The example file contains every supported setting and safe local defaults. `.env` is ignored by Git and must not be committed.

Certificate import, preview, generation, and download work without SMTP credentials. Sending email requires:

| Variable | Purpose |
|---|---|
| `SMTP_USERNAME` | Gmail account that owns the App Password |
| `SMTP_APP_PASSWORD` | Google-generated App Password |
| `SMTP_SENDER_EMAIL` | Primary address used in the `From` header |

Other supported settings are:

| Variable | Default | Purpose |
|---|---:|---|
| `APP_HOST` | `127.0.0.1` | Application host setting |
| `APP_PORT` | `8000` | Backend port setting |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | Allowed browser origin |
| `DATABASE_URL` | `sqlite:///./data/certificates.db` | SQLAlchemy database URL |
| `DATA_DIR` | `./data` | Upload and generated-file directory |
| `MAX_UPLOAD_MB` | `25` | Maximum accepted upload size |
| `DELIVERY_CONCURRENCY` | `1` | Sequential delivery worker count |
| `MAX_EMAILS_PER_DAY` | Disabled | Optional rolling 24-hour application cap |
| `EMAIL_SEND_DELAY_SECONDS` | `5` | Initial delay between submissions |
| `MIN_EMAIL_SEND_DELAY_SECONDS` | `5` | Minimum adaptive delay |
| `MAX_EMAIL_SEND_DELAY_SECONDS` | `120` | Maximum adaptive delay |
| `HEALTHY_SENDS_BEFORE_SPEEDUP` | `5` | Successful sends before reducing delay |
| `SMTP_HOST` | `smtp.gmail.com` | SMTP server |
| `SMTP_PORT` | `587` | STARTTLS SMTP port |
| `SMTP_ALLOWED_ALIASES` | Empty | Comma-separated verified Gmail aliases |
| `SMTP_TIMEOUT_SECONDS` | `30` | Connection and command timeout |
| `SMTP_DATA_TIMEOUT_SECONDS` | `300` | Attachment submission timeout |
| `SMTP_CONNECTION_REUSE` | `true` | Reuse an SMTP connection when possible |
| `SMTP_MAX_MESSAGES_PER_CONNECTION` | `25` | Reconnect after this many messages |
| `SMTP_WORKERS` | `1` | Enforced sequential SMTP worker count |

### Gmail App Password

1. Enable 2-Step Verification for the Gmail account.
2. Create an App Password in the Google Account security settings.
3. Add the Gmail address and generated App Password to `.env`.
4. Set `SMTP_SENDER_EMAIL` to that account or to a verified Gmail “Send mail as” alias listed in `SMTP_ALLOWED_ALIASES`.
5. Restart the backend after changing `.env`.

Do not use a normal Gmail password. SMTP acceptance confirms that the provider accepted the submission; it does not guarantee inbox placement or that the recipient read the message.

## How to Use

1. **Import Participants** — Create or select a session, upload a CSV, map the name and email columns when needed, then review and correct invalid or duplicate rows.
2. **Template & Font** — Upload a certificate background, keep the default font or select a custom font, then position and style the participant name.
3. **Generate & Preview** — Generate certificates, monitor progress, search participants, preview or download individual PDFs, and regenerate outdated certificates when needed.
4. **Configure Email** — Select the SMTP sender and edit the subject and plain-text body. Use `{name}` to insert each participant's saved name.
5. **Send Certificates** — Review readiness, enter the required confirmation, start delivery, and monitor or export the results.

The included sanitized CSV examples are available at [`samples/participants.csv`](samples/participants.csv) and [`frontend/public/samples/participants.csv`](frontend/public/samples/participants.csv).

## Contributing

Contributions are welcome:

1. Fork the repository and create a focused branch.
2. Make the change without committing `.env`, participant data, databases, uploaded assets, generated certificates, or credentials.
3. Run the checks:

   ```bash
   source .venv/bin/activate
   python -m pytest

   cd frontend
   npm test
   npm run build
   ```

4. Commit with a clear message and open a pull request describing the change and verification performed.

Tests must use fake SMTP clients and must never send real email. Keep copyrighted fonts, certificate templates, participant lists, and production delivery records out of pull requests.

## License

This repository does not currently contain a `LICENSE` file. No open-source license permissions are granted until the project owner adds one. The included Bitstream Vera font is supplied through ReportLab under its own font license; uploaded fonts and templates remain subject to their respective licenses.
