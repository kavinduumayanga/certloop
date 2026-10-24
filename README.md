<div align="center">
  <h1>CertLoop</h1>
  <p><strong>Generate. Personalize. Deliver.</strong></p>
  <p>A local-first web application for creating personalized certificates and delivering them through Gmail SMTP.</p>

  <p>
    <img alt="Python 3.12+" src="https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white">
    <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white">
    <img alt="React 19" src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=20232A">
    <img alt="TypeScript 5.8" src="https://img.shields.io/badge/TypeScript-5.8-3178C6?logo=typescript&logoColor=white">
  </p>
</div>

## Overview

CertLoop guides a local operator through a five-step workflow: import participants, customize a certificate template, generate personalized PDFs, prepare an email, and track delivery. Sessions keep separate workshops and their history organized, while SQLite stores progress locally.

Email delivery is explicit and operator-controlled. Importing, previewing, and generating certificates never sends email.

## Features

- Import participants from CSV, map common columns, validate required values and email syntax, detect duplicates, and edit or exclude rows.
- Create named sessions with isolated participants, certificate settings, and delivery progress.
- Upload a JPG or PNG certificate template and position the participant name visually.
- Generate with the included Bitstream Vera Sans default, or select a custom licensed TTF or OTF font per session.
- Preview generated certificates as PNG and download individual PDFs or a ZIP archive.
- Customize the email sender, subject, and body with the `{name}` participant placeholder.
- Deliver individual certificate attachments through Gmail SMTP using an App Password.
- Follow generation and delivery progress in real time through server-sent events.
- Pause or resume sending, retry definite failures, and safely review uncertain outcomes.
- Export a CSV delivery report with participant status and attempt history.

## Screenshots

Screenshots are not currently included in the repository.

<!-- Add sanitized application screenshots here after placing them in docs/screenshots/. -->

## Tech Stack

| Area | Technology |
|---|---|
| Frontend | React 19, TypeScript, Vite, Material UI |
| Backend | FastAPI, Pydantic, Uvicorn |
| Data | SQLAlchemy, SQLite |
| Certificates | Pillow, ReportLab |
| Live updates | Server-sent events (SSE) |
| Testing | pytest, Vitest, Testing Library |

## Getting Started

### Prerequisites

- Python 3.12 or later
- Node.js 20 LTS or 22+ and npm
- macOS or Linux for the included shell helper scripts
- A JPG or PNG certificate template
- A licensed TTF or OTF font only when you want to replace the included default
- A Gmail account with 2-Step Verification and an App Password, only if email delivery is needed

### Install

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'

cp .env.example .env

cd frontend
npm ci
cd ..
```

### Run locally

Start both development servers:

```bash
./start-dev.sh
```

Alternatively, run them in separate terminals:

```bash
./start-backend.sh
```

```bash
./start-frontend.sh
```

Open <http://127.0.0.1:5173>. FastAPI documentation is available at <http://127.0.0.1:8000/docs>.

The servers bind to localhost by default. Avoid exposing CertLoop to a network without adding appropriate authentication and access controls.

## Environment Configuration

Copy [`.env.example`](.env.example) to `.env`. The example contains every supported setting and safe local defaults. The `.env` file is ignored by Git and should never be committed.

Certificate creation works without SMTP credentials. Email delivery requires these values:

| Variable | Purpose |
|---|---|
| `SMTP_USERNAME` | Gmail account that owns the App Password |
| `SMTP_APP_PASSWORD` | Google-generated App Password |
| `SMTP_SENDER_EMAIL` | Primary address used in the `From` header |

Common optional settings include:

| Variable | Default | Purpose |
|---|---:|---|
| `DATABASE_URL` | `sqlite:///./data/certificates.db` | Local SQLAlchemy database |
| `DATA_DIR` | `./data` | Upload and generated-file directory |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | Allowed frontend origin |
| `MAX_UPLOAD_MB` | `25` | Maximum upload size |
| `MAX_EMAILS_PER_DAY` | Disabled | Optional rolling application-level cap |
| `SMTP_ALLOWED_ALIASES` | Empty | Comma-separated Gmail aliases already verified for the account |
| `SMTP_TIMEOUT_SECONDS` | `30` | Connection and SMTP command timeout |
| `SMTP_DATA_TIMEOUT_SECONDS` | `300` | Attachment upload and final acknowledgment timeout |

The remaining pacing and connection settings are documented directly in [`.env.example`](.env.example). The application intentionally uses one sequential SMTP worker.

### Gmail App Password

1. Enable 2-Step Verification for the Gmail account.
2. In Google Account security settings, create an App Password for CertLoop.
3. Add the Gmail address and generated password to `.env`.
4. Set `SMTP_SENDER_EMAIL` to the same address, or use an address already configured in Gmail as a verified “Send mail as” alias.
5. Restart the backend after changing `.env`.

Do not use a normal Gmail password. Provider limits and policies remain authoritative, and SMTP acceptance does not guarantee inbox placement or that a message will be read.

## How to Use

1. **Import Participants** — Create or select a session, then import a CSV containing participant names and email addresses. Review validation results and fix or exclude invalid rows.
2. **Template & Font** — Upload the certificate image, optionally select a custom font, then position and resize the participant-name area.
3. **Generate & Preview** — Generate personalized certificates, inspect previews, and optionally download PDFs or a ZIP archive.
4. **Configure Email** — Confirm the SMTP sender and customize the subject and plain-text body. Use `{name}` to insert each participant's saved name.
5. **Send Certificates** — Review the ready count, complete the explicit confirmation, and monitor delivery. Pause, resume, retry definite failures, or export the delivery report as needed.

Delivery states are preserved as `PENDING`, `SENDING`, `SENT`, `FAILED`, or `UNCERTAIN`. An uncertain message is never retried automatically because the provider may already have accepted it.

CertLoop uses **Bitstream Vera Sans** from the required ReportLab package as its offline default certificate font. Google Sans is not bundled or represented as the default because it is a Google brand typeface without general redistribution terms. Uploaded custom fonts remain the user's responsibility and are stored per session.

## Contributing

Contributions are welcome. A typical workflow is:

1. Fork the repository and create a focused branch.
2. Make the change without committing credentials, participant data, generated certificates, or databases.
3. Run the checks:

   ```bash
   source .venv/bin/activate
   python -m pytest

   cd frontend
   npm test
   npm run build
   ```

4. Commit with a clear message and open a pull request describing the change and how it was tested.

Please keep pull requests small and avoid sending real email from automated tests.

## License

This repository does not currently include a license file. Until a license is added, no open-source license permissions are granted. Add an appropriate `LICENSE` file before presenting CertLoop as licensed open-source software.
