import csv
import asyncio
import io
import json
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from PIL import Image, ImageFont, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .config import get_settings
from .database import Base, SessionLocal, clean_session_name, engine, ensure_schema, get_db, normalized_session_name
from .models import Batch, DeliveryAttempt, DeliveryStatus, Participant, SendRecord
from .schemas import BatchCreate, EmailConfig, ParticipantPatch, PreviewRequest, ReconcileRequest, RegionUpdate, StartSendRequest
from .services.csv_import import csv_safe, parse_participants, resolve_columns, validate_participant
from .services.delivery import DeliveryManager
from .services.generation import GenerationManager
from .services.files import safe_filename
from .services.rendering import is_render_current, make_zip, render_certificate, render_preview_png
from .services.smtp import DefiniteSendError, SMTPClient, message_id_for

settings = get_settings()
Base.metadata.create_all(bind=engine)
ensure_schema()


def smtp_configured() -> bool:
    return bool(settings.smtp_username and settings.smtp_app_password and settings.smtp_sender_email)


def smtp_client() -> SMTPClient:
    if not smtp_configured():
        raise DefiniteSendError("Configure SMTP_USERNAME, SMTP_APP_PASSWORD, and SMTP_SENDER_EMAIL first")
    return SMTPClient(
        settings.smtp_host, settings.smtp_port, settings.smtp_username or "",
        settings.smtp_app_password or "", settings.smtp_sender_email or "",
        settings.smtp_aliases, settings.smtp_timeout_seconds,
        data_timeout=settings.smtp_data_timeout_seconds,
        connection_reuse=settings.smtp_connection_reuse,
        max_messages_per_connection=settings.smtp_max_messages_per_connection,
    )


def allowed_senders() -> set[str]:
    if not settings.smtp_sender_email:
        return set()
    return {settings.smtp_sender_email.casefold(), *settings.smtp_aliases}


delivery = DeliveryManager(settings, smtp_client)
generation = GenerationManager(settings)


@asynccontextmanager
async def lifespan(_: FastAPI):
    delivery.recover()
    generation.recover()
    yield


app = FastAPI(title="Certificate Dispatch API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin], allow_credentials=True, allow_methods=["*"] , allow_headers=["*"])


def batch_or_404(db: Session, batch_id: str) -> Batch:
    batch = db.get(Batch, batch_id)
    if not batch:
        raise HTTPException(404, "Batch not found")
    return batch


def revalidate_active_participants(batch: Batch) -> None:
    """Revalidate the active import as a set so duplicate corrections resolve immediately."""
    seen: set[str] = set()
    for row in sorted((p for p in batch.participants if p.is_current_import), key=lambda item: item.row_number):
        clean_name, canonical, errors = validate_participant(row.name, row.email)
        row.name = clean_name
        row.canonical_email = canonical or None
        if canonical and canonical in seen:
            errors.append("Duplicate email in this import")
        elif canonical:
            seen.add(canonical)
        row.is_valid = not errors
        row.validation_error = "; ".join(errors) or None


def serialize_batch(batch: Batch, include_participants: bool = True) -> dict:
    counts = {status.value: 0 for status in DeliveryStatus}
    imported = [p for p in batch.participants if p.is_current_import]
    active = [p for p in imported if p.is_valid and not p.is_excluded]
    for participant in active:
        counts[participant.status.value] += 1
    current = {p.id: is_render_current(p.certificate_path) for p in imported}
    ready_count = sum(p.status == DeliveryStatus.PENDING and current[p.id] for p in active)
    outdated_count = sum(bool(p.certificate_path) and not current[p.id] for p in active)
    started_at = batch.send_job_started_at
    finished_at = batch.send_job_finished_at
    progress_total = batch.send_job_total or 0
    progress_counts = {"SENT": 0, "FAILED": 0, "UNCERTAIN": 0}
    if started_at:
        with SessionLocal() as progress_db:
            rows = progress_db.execute(select(SendRecord.status, func.count()).where(
                SendRecord.batch_id == batch.id,
                SendRecord.kind == "BULK",
                SendRecord.reserved_at >= started_at,
            ).group_by(SendRecord.status)).all()
        for status, count in rows:
            if status in progress_counts:
                progress_counts[status] = count
    processed = sum(progress_counts.values())
    sending_count = counts[DeliveryStatus.SENDING.value]
    job_pending = max(0, progress_total - processed - sending_count)
    current_recipient = next((p.name for p in active if p.status == DeliveryStatus.SENDING), None)
    end = finished_at or datetime.now(timezone.utc)
    if started_at:
        start = started_at if started_at.tzinfo else started_at.replace(tzinfo=timezone.utc)
        end_aware = end if end.tzinfo else end.replace(tzinfo=timezone.utc)
        elapsed_seconds = max(0, int((end_aware - start).total_seconds()))
    else:
        elapsed_seconds = 0
    eta_seconds = int(elapsed_seconds / processed * job_pending) if processed and job_pending else 0
    invalid_count = sum(not p.is_valid for p in imported)
    duplicate_count = sum(bool(p.validation_error and "Duplicate email" in p.validation_error) for p in imported)
    generation_done = batch.generation_succeeded + batch.generation_failed
    participant_by_id = {participant.id: participant for participant in batch.participants}
    return {
        "id": batch.id, "name": batch.name, "workshop_name": batch.workshop_name,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "updated_at": batch.updated_at.isoformat() if batch.updated_at else None,
        "template_path": bool(batch.template_path), "font_path": bool(batch.font_path),
        "sender_email": batch.sender_email, "email_subject": batch.email_subject, "email_body": batch.email_body,
        "is_paused": batch.is_paused, "send_confirmed": batch.send_confirmed,
        "region": {"x": batch.region_x, "y": batch.region_y, "w": batch.region_w, "h": batch.region_h, "font_size": batch.font_size, "min_font_size": batch.min_font_size, "auto_fit": batch.auto_fit, "vertical_offset": batch.vertical_offset},
        "counts": {"TOTAL": len(active), **counts},
        "ready_count": ready_count,
        "outdated_certificate_count": outdated_count,
        "import_counts": {
            "total": len(imported), "valid": len(imported) - invalid_count,
            "invalid": invalid_count, "duplicates": duplicate_count, "preserved": 0,
        },
        "allowance": delivery.allowance(),
        "generation": {
            "job_id": batch.generation_job_id,
            "status": batch.generation_status,
            "total": batch.generation_total,
            "succeeded": batch.generation_succeeded,
            "failed": batch.generation_failed,
            "remaining": max(0, batch.generation_total - generation_done),
            "percent": round(generation_done / batch.generation_total * 100, 1) if batch.generation_total else 0,
            "current_name": batch.generation_current_name,
            "started_at": batch.generation_started_at.isoformat() if batch.generation_started_at else None,
            "finished_at": batch.generation_finished_at.isoformat() if batch.generation_finished_at else None,
        },
        "progress": {
            "total": progress_total,
            "processed": processed,
            "pending": job_pending,
            "sending": sending_count,
            "sent": progress_counts["SENT"],
            "failed": progress_counts["FAILED"],
            "uncertain": progress_counts["UNCERTAIN"],
            "percent": round(processed / progress_total * 100, 1) if progress_total else 0,
            "current_recipient": current_recipient,
            "elapsed_seconds": elapsed_seconds,
            "eta_seconds": eta_seconds,
            "started_at": started_at.isoformat() if started_at else None,
            "finished_at": finished_at.isoformat() if finished_at else None,
        },
        "participants": [{"id": p.id, "row_number": p.row_number, "name": p.name, "email": p.email, "is_valid": p.is_valid, "is_excluded": p.is_excluded, "validation_error": p.validation_error, "status": p.status.value, "filename": p.filename, "certificate_current": current[p.id], "legibility_warning": p.legibility_warning, "generation_error": p.generation_error, "smtp_message_id": p.smtp_message_id, "sent_at": p.sent_at.isoformat() if p.sent_at else None, "updated_at": p.updated_at.isoformat() if p.updated_at else None, "error_reason": p.error_reason, "delivery_reference": p.idempotency_key, "previous_delivery": ({"participant_id": p.previous_delivery_id, "name": participant_by_id[p.previous_delivery_id].name, "email": participant_by_id[p.previous_delivery_id].email, "sent_at": participant_by_id[p.previous_delivery_id].sent_at.isoformat() if participant_by_id[p.previous_delivery_id].sent_at else None, "smtp_message_id": participant_by_id[p.previous_delivery_id].smtp_message_id, "filename": participant_by_id[p.previous_delivery_id].filename} if p.previous_delivery_id and p.previous_delivery_id in participant_by_id else None), "attempts": [{"attempt_number": a.attempt_number, "started_at": a.started_at.isoformat() if a.started_at else None, "finished_at": a.finished_at.isoformat() if a.finished_at else None, "outcome": a.outcome, "error_code": a.error_code, "error_reason": a.error_reason, "reconciliation_action": a.reconciliation_action, "reconciliation_note": a.reconciliation_note, "reconciled_at": a.reconciled_at.isoformat() if a.reconciled_at else None} for a in sorted(p.attempts, key=lambda item: item.attempt_number, reverse=True)]} for p in sorted(imported, key=lambda item: item.row_number)] if include_participants else [],
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/batches")
def create_batch(payload: BatchCreate, db: Session = Depends(get_db)):
    name = clean_session_name(payload.name)
    batch = Batch(name=name, name_normalized=normalized_session_name(name), workshop_name=payload.workshop_name.strip())
    db.add(batch)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, f'A session named "{name}" already exists') from exc
    db.refresh(batch)
    return serialize_batch(batch)


@app.get("/api/batches")
def list_batches(db: Session = Depends(get_db)):
    return [serialize_batch(row, False) for row in db.scalars(select(Batch).order_by(Batch.created_at.desc())).all()]


@app.get("/api/batches/{batch_id}")
def get_batch(batch_id: str, db: Session = Depends(get_db)):
    return serialize_batch(batch_or_404(db, batch_id))


async def read_limited(file: UploadFile) -> bytes:
    data = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB")
    return data


@app.post("/api/batches/{batch_id}/participants/import")
async def import_csv(batch_id: str, file: UploadFile = File(...), name_column: str | None = Form(None), email_column: str | None = Form(None), confirm_replace: bool = Form(False), db: Session = Depends(get_db)):
    batch = batch_or_404(db, batch_id)
    if generation.is_running(batch_id) or batch.generation_status == "RUNNING":
        raise HTTPException(409, "Wait for certificate generation to finish before replacing the participant list")
    if delivery.is_running(batch_id) or any(p.status == DeliveryStatus.SENDING for p in batch.participants):
        raise HTTPException(409, "Pause sending and wait for the current SMTP submission to finish before importing a new CSV")
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(400, "Only .csv files are accepted")
    data = await read_limited(file)
    try:
        rows, headers = parse_participants(data, name_column, email_column)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    resolved_name, resolved_email = resolve_columns(headers, name_column, email_column)
    if not resolved_name or not resolved_email:
        raise HTTPException(422, {
            "code": "column_mapping_required",
            "message": "We could not identify both participant columns. Choose the Name and Email columns below.",
            "headers": headers,
            "detected": {"name": resolved_name, "email": resolved_email},
        })
    if not rows:
        raise HTTPException(422, "The CSV has headers but contains no participant rows")
    current_rows = [participant for participant in batch.participants if participant.is_current_import]
    replacement_has_history = any(
        participant.certificate_path or participant.attempts or participant.status != DeliveryStatus.PENDING
        for participant in current_rows
    ) or bool(batch.send_job_total or batch.send_job_started_at)
    if current_rows and replacement_has_history and not confirm_replace:
        raise HTTPException(409, {
            "code": "replace_confirmation_required",
            "message": "This session already has generated certificates or delivery activity. Confirm replacement to archive the active participant list without deleting its history.",
        })
    # Every successful import gets a new identity. Previous participants remain
    # untouched as immutable delivery/audit snapshots.
    import_id = str(uuid.uuid4())
    sent_by_email: dict[str, Participant] = {}
    for participant in sorted(batch.participants, key=lambda item: (item.sent_at or datetime.min).replace(tzinfo=None), reverse=True):
        canonical = participant.canonical_email or (participant.email.casefold() if participant.email else "")
        if participant.status == DeliveryStatus.SENT and canonical and canonical not in sent_by_email:
            sent_by_email[canonical] = participant
    try:
        for old in batch.participants:
            old.is_current_import = False
        for row in rows:
            previous = sent_by_email.get(row.normalized_email) if row.is_valid else None
            db.add(Participant(
                batch_id=batch.id, row_number=row.row_number, name=row.name,
                email=row.email, normalized_email=f"__participant__:{uuid.uuid4()}",
                canonical_email=row.normalized_email or None,
                is_valid=row.is_valid, validation_error=row.error,
                is_current_import=True, import_id=import_id,
                # A re-imported sent address is visible but cannot silently
                # become a new pending delivery.
                is_excluded=bool(previous),
                status=DeliveryStatus.PENDING,
                previous_delivery_id=previous.id if previous else None,
                error_reason="Previously sent in an earlier import; excluded to prevent duplicate delivery" if previous else None,
                idempotency_key=f"cert-{batch.id}-{uuid.uuid4()}",
            ))
        batch.active_import_id = import_id
        batch.generation_status = "IDLE"
        batch.generation_total = batch.generation_succeeded = batch.generation_failed = 0
        batch.generation_current_name = None
        # The imported dataset begins a fresh delivery job inside this session.
        # Historical participants, attempts, and account-level SendRecords stay intact.
        batch.send_confirmed = False
        batch.is_paused = False
        batch.send_job_total = 0
        batch.send_job_started_at = None
        batch.send_job_finished_at = None
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(409, "The CSV conflicts with existing participant data. No rows were imported; review duplicate email addresses and try again.") from exc
    db.refresh(batch)
    result = serialize_batch(batch)
    result["import_counts"] = {
        "total": len(rows),
        "valid": sum(row.is_valid for row in rows),
        "invalid": sum(not row.is_valid for row in rows),
        "duplicates": sum(bool(row.error and "Duplicate email" in row.error) for row in rows),
        "preserved": sum(1 for row in rows if row.is_valid and row.normalized_email in sent_by_email),
    }
    return result


@app.patch("/api/participants/{participant_id}")
def update_participant(participant_id: str, payload: ParticipantPatch, db: Session = Depends(get_db)):
    row = db.get(Participant, participant_id)
    if not row: raise HTTPException(404, "Participant not found")
    if not row.is_current_import:
        raise HTTPException(409, "Historical participant snapshots cannot be edited")
    if generation.is_running(row.batch_id) or row.batch.generation_status == "RUNNING":
        raise HTTPException(409, "Wait for certificate generation to finish before editing participants")
    content_changed = payload.name is not None or payload.email is not None
    if content_changed and row.status in {DeliveryStatus.SENT, DeliveryStatus.SENDING, DeliveryStatus.UNCERTAIN}:
        raise HTTPException(409, "Recipient details are locked after delivery starts; historical delivery snapshots cannot be changed")
    if payload.name is not None: row.name = payload.name.strip()
    if payload.email is not None: row.email = payload.email.strip()
    if payload.is_excluded is not None: row.is_excluded = payload.is_excluded
    revalidate_active_participants(row.batch)
    if content_changed and row.status != DeliveryStatus.SENT:
        row.certificate_path = row.preview_path = row.filename = row.legibility_warning = row.generation_error = None
    try: db.commit()
    except Exception as exc:
        db.rollback(); raise HTTPException(409, "Participant changes could not be saved") from exc
    return serialize_batch(row.batch)


@app.post("/api/participants/{participant_id}/reconcile")
def reconcile_uncertain(participant_id: str, payload: ReconcileRequest, db: Session = Depends(get_db)):
    participant = db.get(Participant, participant_id)
    if not participant:
        raise HTTPException(404, "Participant not found")
    if participant.status != DeliveryStatus.UNCERTAIN:
        raise HTTPException(409, "Only an UNCERTAIN submission can be reconciled")
    expected = "CONFIRM SENT" if payload.action == "CONFIRM_SENT" else "CONFIRM NOT SENT"
    if payload.confirmation != expected:
        raise HTTPException(400, f"Confirmation must exactly match: {expected}")
    attempt = db.scalars(select(DeliveryAttempt).where(
        DeliveryAttempt.participant_id == participant.id,
        DeliveryAttempt.outcome == "UNCERTAIN",
    ).order_by(DeliveryAttempt.id.desc())).first()
    if not attempt:
        raise HTTPException(409, "No uncertain delivery attempt is available to reconcile")
    record = db.scalars(select(SendRecord).where(
        SendRecord.participant_id == participant.id,
        SendRecord.status == "UNCERTAIN",
    ).order_by(SendRecord.reserved_at.desc())).first()
    now = datetime.now(timezone.utc)
    attempt.reconciliation_action = payload.action
    attempt.reconciliation_note = payload.note.strip() or None
    attempt.reconciled_at = now
    if payload.action == "CONFIRM_SENT":
        sender = settings.smtp_sender_email or participant.batch.sender_email or "localhost"
        message_id = message_id_for(participant.idempotency_key, sender)
        participant.status = DeliveryStatus.SENT
        participant.smtp_message_id = message_id
        participant.sent_at = now
        participant.error_reason = "Manually reconciled after confirming the message in Gmail Sent"
        if record:
            record.status = "SENT"
            record.smtp_message_id = message_id
            record.error_reason = "Manually reconciled as accepted"
    else:
        participant.status = DeliveryStatus.FAILED
        participant.error_reason = "Manually reconciled as not sent; Retry Failed still requires explicit confirmation"
        if record:
            record.status = "FAILED"
            # Preserve conservative quota accounting because the original SMTP
            # outcome was indeterminate even after operator reconciliation.
            record.counts_against_limit = True
            record.error_reason = "Manually reconciled as not sent"
    db.commit()
    db.refresh(participant)
    return serialize_batch(participant.batch)


@app.post("/api/batches/{batch_id}/template")
async def upload_template(batch_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    batch = batch_or_404(db, batch_id)
    if generation.is_running(batch_id): raise HTTPException(409, "Wait for certificate generation to finish")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg"}: raise HTTPException(400, "Template must be PNG or JPEG")
    data = await read_limited(file)
    try:
        image = Image.open(io.BytesIO(data)); image.verify()
    except (UnidentifiedImageError, OSError) as exc: raise HTTPException(400, "Invalid image content") from exc
    path = settings.upload_dir / f"{batch_id}-template{suffix}"
    path.write_bytes(data); batch.template_path = str(path.resolve())
    for row in batch.participants:
        if row.is_current_import and row.status not in {DeliveryStatus.SENT, DeliveryStatus.SENDING, DeliveryStatus.UNCERTAIN}:
            row.certificate_path = row.preview_path = row.filename = row.legibility_warning = None
    db.commit()
    return serialize_batch(batch)


@app.post("/api/batches/{batch_id}/font")
async def upload_font(batch_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    batch = batch_or_404(db, batch_id)
    if generation.is_running(batch_id): raise HTTPException(409, "Wait for certificate generation to finish")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".ttf", ".otf"}: raise HTTPException(400, "Font must be TTF or OTF")
    data = await read_limited(file)
    path = settings.upload_dir / f"{batch_id}-font{suffix}"; path.write_bytes(data)
    try: ImageFont.truetype(str(path), 32)
    except OSError as exc:
        path.unlink(missing_ok=True); raise HTTPException(400, "Invalid or unsupported font file") from exc
    batch.font_path = str(path.resolve())
    for row in batch.participants:
        if row.is_current_import and row.status not in {DeliveryStatus.SENT, DeliveryStatus.SENDING, DeliveryStatus.UNCERTAIN}:
            row.certificate_path = row.preview_path = row.filename = row.legibility_warning = None
    db.commit()
    return serialize_batch(batch)


@app.get("/api/batches/{batch_id}/template-file")
def template_file(batch_id: str, db: Session = Depends(get_db)):
    batch = batch_or_404(db, batch_id)
    if not batch.template_path:
        raise HTTPException(404, "Template not uploaded")
    suffix = Path(batch.template_path).suffix.lower()
    return FileResponse(batch.template_path, media_type="image/png" if suffix == ".png" else "image/jpeg")


@app.post("/api/batches/{batch_id}/render-preview")
def render_live_preview(batch_id: str, payload: PreviewRequest, db: Session = Depends(get_db)):
    batch = batch_or_404(db, batch_id)
    if not batch.template_path or not batch.font_path:
        raise HTTPException(409, "Upload the certificate template and Citadel Script font first")
    participant = db.get(Participant, payload.participant_id)
    if not participant or participant.batch_id != batch.id or not participant.is_current_import or not participant.is_valid or participant.is_excluded:
        raise HTTPException(404, "Preview participant is not available")
    if payload.x + payload.w > 1 or payload.y + payload.h > 1:
        raise HTTPException(422, "Name region must stay inside the image")
    png, actual_size, warning = render_preview_png(
        Path(batch.template_path), Path(batch.font_path), participant.name,
        payload.model_dump(exclude={"participant_id"}),
    )
    return Response(
        png,
        media_type="image/png",
        headers={
            "Cache-Control": "no-store",
            "X-Actual-Font-Size": str(actual_size),
            "X-Legibility-Warning": "1" if warning else "0",
        },
    )


@app.put("/api/batches/{batch_id}/region")
def update_region(batch_id: str, payload: RegionUpdate, db: Session = Depends(get_db)):
    if payload.x + payload.w > 1 or payload.y + payload.h > 1: raise HTTPException(422, "Name region must stay inside the image")
    batch = batch_or_404(db, batch_id)
    if generation.is_running(batch_id): raise HTTPException(409, "Wait for certificate generation to finish")
    for key, value in payload.model_dump().items(): setattr(batch, f"region_{key}" if key in {"x", "y", "w", "h"} else key, value)
    for row in batch.participants:
        if row.is_current_import and row.status not in {DeliveryStatus.SENT, DeliveryStatus.SENDING, DeliveryStatus.UNCERTAIN}:
            row.certificate_path = row.preview_path = row.filename = row.legibility_warning = None
    db.commit(); return serialize_batch(batch)


@app.post("/api/batches/{batch_id}/generate")
def generate(batch_id: str, db: Session = Depends(get_db)):
    batch = batch_or_404(db, batch_id)
    if not batch.template_path or not batch.font_path: raise HTTPException(409, "Upload a template and exact licensed font first")
    eligible = [row for row in batch.participants if row.is_current_import and row.is_valid and not row.is_excluded and row.status in {DeliveryStatus.PENDING, DeliveryStatus.FAILED}]
    if not eligible: raise HTTPException(409, "No valid unsent participants are eligible for generation")
    if generation.is_running(batch_id) or batch.generation_status == "RUNNING":
        raise HTTPException(409, "Certificate generation is already running for this batch")
    if not generation.start(batch_id):
        raise HTTPException(409, "Certificate generation is already running for this batch")
    return {"started": True, "total": len(eligible)}


@app.get("/api/participants/{participant_id}/preview")
def preview(participant_id: str, db: Session = Depends(get_db)):
    row = db.get(Participant, participant_id)
    if not row or not row.preview_path: raise HTTPException(404, "Preview not generated")
    if not is_render_current(row.certificate_path): raise HTTPException(409, "Certificate styling changed; regenerate this certificate")
    return FileResponse(row.preview_path, media_type="image/png")


@app.get("/api/participants/{participant_id}/certificate")
def certificate(participant_id: str, db: Session = Depends(get_db)):
    row = db.get(Participant, participant_id)
    if not row or not row.certificate_path: raise HTTPException(404, "Certificate not generated")
    if not is_render_current(row.certificate_path): raise HTTPException(409, "Certificate styling changed; regenerate this certificate")
    return FileResponse(row.certificate_path, media_type="application/pdf", filename=row.filename)


@app.get("/api/batches/{batch_id}/zip")
def download_zip(batch_id: str, db: Session = Depends(get_db)):
    batch = batch_or_404(db, batch_id)
    files = [(Path(p.certificate_path), p.filename or "certificate.pdf") for p in batch.participants if p.is_current_import and p.certificate_path and not p.is_excluded and is_render_current(p.certificate_path)]
    if not files: raise HTTPException(409, "Generate certificates first")
    path = make_zip(files, settings.generated_dir / f"{batch.id}-certificates.zip")
    return FileResponse(path, media_type="application/zip", filename=f"{safe_filename(batch.name)}-certificates.zip")


@app.put("/api/batches/{batch_id}/email")
def configure_email(batch_id: str, payload: EmailConfig, db: Session = Depends(get_db)):
    batch = batch_or_404(db, batch_id)
    if str(payload.sender_email).casefold() not in allowed_senders():
        raise HTTPException(400, "Sender must match SMTP_SENDER_EMAIL or an address in SMTP_ALLOWED_ALIASES")
    batch.sender_email, batch.email_subject, batch.email_body, batch.workshop_name = str(payload.sender_email), payload.subject, payload.body, payload.workshop_name
    db.commit(); return serialize_batch(batch)


@app.get("/api/smtp/status")
def smtp_status():
    return {
        "configured": smtp_configured(),
        "sender_email": settings.smtp_sender_email if smtp_configured() else None,
        "aliases": settings.smtp_aliases if smtp_configured() else [],
        "host": settings.smtp_host,
        "port": settings.smtp_port,
        "provider": "Gmail" if "gmail" in settings.smtp_host.casefold() else settings.smtp_host,
        "application_cap": settings.max_emails_per_day,
    }


@app.get("/api/sending-allowance")
def sending_allowance():
    return delivery.allowance()


@app.post("/api/batches/{batch_id}/send")
def start_send(batch_id: str, payload: StartSendRequest, db: Session = Depends(get_db)):
    batch = batch_or_404(db, batch_id)
    if delivery.is_running(batch_id):
        raise HTTPException(409, "A sending worker is already active for this batch")
    pending_eligible = [p for p in batch.participants if p.is_current_import and p.is_valid and not p.is_excluded and p.status == DeliveryStatus.PENDING]
    ready = sum(1 for p in pending_eligible if is_render_current(p.certificate_path))
    expected = f"SEND {ready}"
    if payload.confirmation != expected: raise HTTPException(400, f"Confirmation must exactly match: {expected}")
    if ready == 0: raise HTTPException(409, "No pending participants have a current generated certificate")
    if ready != len(pending_eligible): raise HTTPException(409, f"Generate current PDFs for all {len(pending_eligible)} pending eligible participants before sending")
    if not batch.sender_email or not batch.email_subject.strip() or not batch.email_body.strip(): raise HTTPException(409, "Configure sender, subject, and email body first")
    if not smtp_configured():
        raise HTTPException(503, "SMTP App Password is not configured")
    if batch.sender_email.casefold() not in allowed_senders():
        raise HTTPException(400, "Sender is not the configured Gmail account or an allowed alias")
    remaining = delivery.allowance()["remaining"]
    if remaining is not None and remaining <= 0:
        raise HTTPException(429, "Rolling 24-hour application sending limit reached")
    batch.send_confirmed = True
    batch.is_paused = False
    batch.send_job_total = ready
    batch.send_job_started_at = datetime.now(timezone.utc)
    batch.send_job_finished_at = None
    db.commit()
    if not delivery.start(batch.id):
        raise HTTPException(409, "A sending worker is already active for this batch")
    return {"started": True}


@app.post("/api/batches/{batch_id}/pause")
def pause(batch_id: str, db: Session = Depends(get_db)):
    batch = batch_or_404(db, batch_id); batch.is_paused = True; db.commit(); return {"paused": True}


@app.post("/api/batches/{batch_id}/resume")
def resume(batch_id: str, db: Session = Depends(get_db)):
    batch = batch_or_404(db, batch_id); batch.is_paused = False; db.commit(); delivery.start(batch.id); return {"resumed": True}


@app.post("/api/batches/{batch_id}/retry-failed")
def retry_failed(batch_id: str, db: Session = Depends(get_db)):
    batch = batch_or_404(db, batch_id); count = 0
    for row in batch.participants:
        if row.is_current_import and row.status == DeliveryStatus.FAILED: row.status = DeliveryStatus.PENDING; row.error_reason = None; count += 1
    db.commit(); return {"reset": count}


@app.get("/api/batches/{batch_id}/events")
async def events(batch_id: str, request: Request):
    async def stream():
        previous = None
        while not await request.is_disconnected():
            with SessionLocal() as db:
                batch = db.get(Batch, batch_id)
                if not batch: yield "event: error\ndata: Batch not found\n\n"; return
                payload = json.dumps(serialize_batch(batch))
            if payload != previous: yield f"data: {payload}\n\n"; previous = payload
            await asyncio.sleep(1)
    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/api/batches/{batch_id}/report")
def report(batch_id: str, db: Session = Depends(get_db)):
    batch = batch_or_404(db, batch_id); buffer = io.StringIO(); writer = csv.writer(buffer)
    writer.writerow(["Recipient", "Name", "Included", "Status", "Timestamp", "SMTP Message ID", "Delivery Reference", "Previous Delivery ID", "Last Attempt", "Reconciliation", "Error Reason"])
    for p in sorted((row for row in batch.participants if row.is_current_import), key=lambda item: item.row_number):
        timestamp = p.sent_at or (p.updated_at if p.status != DeliveryStatus.PENDING else None)
        attempt = max(p.attempts, key=lambda item: item.attempt_number, default=None)
        writer.writerow([csv_safe(p.email), csv_safe(p.name), "No" if p.is_excluded else "Yes", p.status.value, timestamp.isoformat() if timestamp else "", csv_safe(p.smtp_message_id), csv_safe(p.idempotency_key), csv_safe(p.previous_delivery_id), csv_safe(attempt.outcome if attempt else None), csv_safe(attempt.reconciliation_action if attempt else None), csv_safe(p.error_reason)])
    data = buffer.getvalue().encode("utf-8-sig")
    return StreamingResponse(iter([data]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{safe_filename(batch.name)}-delivery-report.csv"'})

