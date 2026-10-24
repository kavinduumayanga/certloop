import threading
import time
import hashlib
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import case, func, select, update

from ..config import Settings
from ..database import SessionLocal
from ..models import Batch, DeliveryAttempt, DeliveryStatus, Participant, SendRecord
from .smtp import DefiniteSendError, SMTPClient, TransientSendError, UncertainSendError
from .templates import render_template
from .rendering import is_render_current


logger = logging.getLogger("certificate.delivery")


class SendPaused(Exception):
    """The batch was paused before this message entered SMTP submission."""


def _record_ref(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


class DeliveryManager:
    def __init__(self, settings: Settings, smtp_factory):
        self.settings = settings
        self.smtp_factory = smtp_factory
        self._threads: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()
        self._limit_lock = threading.Lock()
        self._rate_lock = threading.Lock()
        self._last_send = 0.0
        self._current_interval = max(settings.min_email_send_delay_seconds, settings.email_send_delay_seconds)
        self._healthy_streak = 0

    def recover(self) -> int:
        with SessionLocal() as db:
            rows = db.scalars(select(Participant).where(Participant.status == DeliveryStatus.SENDING)).all()
            sending_ids = {row.id for row in rows}
            for row in rows:
                row.status = DeliveryStatus.UNCERTAIN
                row.error_reason = "Backend restarted while this send was in progress; verify manually before retrying"
                if row.batch:
                    row.batch.is_paused = True
            reservations = db.scalars(select(SendRecord).where(SendRecord.status == "RESERVED")).all()
            for reservation in reservations:
                uncertain = reservation.participant_id in sending_ids
                reservation.status = "UNCERTAIN" if uncertain else "CANCELLED"
                reservation.counts_against_limit = uncertain
                reservation.finished_at = datetime.now(timezone.utc)
                reservation.error_reason = "Backend restarted during an active SMTP submission" if uncertain else "Backend restarted before SMTP submission"
            db.commit()
            if rows or reservations:
                logger.warning("delivery_event=recovered sending=%s reservations=%s action=marked_uncertain", len(rows), len(reservations))
            return len(rows)

    def is_running(self, batch_id: str) -> bool:
        with self._lock:
            thread = self._threads.get(batch_id)
            return bool(thread and thread.is_alive())

    def allowance(self) -> dict[str, int | bool | None | str]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        with SessionLocal() as db:
            base = SendRecord.reserved_at >= cutoff
            used, successful, failed, uncertain = db.execute(select(
                func.sum(case((SendRecord.counts_against_limit.is_(True), 1), else_=0)),
                func.sum(case((SendRecord.status == "SENT", 1), else_=0)),
                func.sum(case((SendRecord.status == "FAILED", 1), else_=0)),
                func.sum(case((SendRecord.status == "UNCERTAIN", 1), else_=0)),
            ).where(base)).one()
            used, successful, failed, uncertain = (used or 0, successful or 0, failed or 0, uncertain or 0)
        limit = self.settings.max_emails_per_day
        return {
            "enabled": limit is not None,
            "limit": limit,
            "used": used,
            "remaining": max(0, limit - used) if limit is not None else None,
            "successful": successful,
            "failed": failed,
            "uncertain": uncertain,
            "notice": "Email sending limits depend on your SMTP provider, account type, and current provider restrictions. The application monitors sending activity but cannot guarantee the provider's remaining allowance.",
        }

    def reserve_send(self, batch_id: str | None, participant_id: str | None, kind: str) -> str | None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        with self._limit_lock, SessionLocal() as db:
            used = db.scalar(select(func.count()).select_from(SendRecord).where(
                SendRecord.reserved_at >= cutoff, SendRecord.counts_against_limit.is_(True)
            )) or 0
            limit = self.settings.max_emails_per_day
            if limit is not None and used >= limit:
                return None
            record = SendRecord(batch_id=batch_id, participant_id=participant_id, kind=kind)
            db.add(record)
            db.commit()
            return record.id

    def finish_reservation(self, record_id: str, status: str, message_id: str | None = None, error: str | None = None):
        with SessionLocal() as db:
            record = db.get(SendRecord, record_id)
            if not record:
                return
            record.status = status
            record.finished_at = datetime.now(timezone.utc)
            record.smtp_message_id = message_id
            record.error_reason = error
            # Definite failures did not consume a Gmail accepted-message slot.
            record.counts_against_limit = status in {"RESERVED", "SENT", "UNCERTAIN"}
            db.commit()

    def start(self, batch_id: str) -> bool:
        with self._lock:
            existing = self._threads.get(batch_id)
            if existing and existing.is_alive():
                return False
            thread = threading.Thread(target=self._run, args=(batch_id,), daemon=True, name=f"delivery-{batch_id[:8]}")
            self._threads[batch_id] = thread
            thread.start()
            logger.info("delivery_event=worker_started batch=%s", _record_ref(batch_id))
            return True

    @contextmanager
    def submission_slot(self):
        """Serialize SMTP submissions and pace their start times."""
        with self._rate_lock:
            wait = self._last_send + self._current_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last_send = time.monotonic()
            yield

    def record_healthy_send(self) -> None:
        with self._rate_lock:
            self._healthy_streak += 1
            if self._healthy_streak >= max(1, self.settings.healthy_sends_before_speedup):
                self._current_interval = max(
                    self.settings.min_email_send_delay_seconds,
                    self._current_interval - 0.5,
                )
                self._healthy_streak = 0

    def record_temporary_failure(self, retry_after: int | None = None) -> None:
        with self._rate_lock:
            self._healthy_streak = 0
            increased = max(self._current_interval * 2, float(retry_after or 0))
            self._current_interval = min(self.settings.max_email_send_delay_seconds, increased)

    def _run(self, batch_id: str):
        with SessionLocal() as db:
            batch = db.get(Batch, batch_id)
            if not batch or not batch.send_confirmed:
                return
            rows = list(db.scalars(select(Participant).where(
                Participant.batch_id == batch_id,
                Participant.is_current_import.is_(True),
                Participant.status == DeliveryStatus.PENDING,
                Participant.is_valid.is_(True),
                Participant.is_excluded.is_(False),
                Participant.certificate_path.is_not(None),
            )).all())
            ids = [
                row.id for row in rows
                if row.certificate_revision == batch.certificate_revision
                and is_render_current(row.certificate_path)
            ]
        logger.info("delivery_event=batch_ready batch=%s recipients=%s workers=%s", _record_ref(batch_id), len(ids), self.settings.smtp_workers)
        client = None
        try:
            client = self.smtp_factory()
            for participant_id in ids:
                with SessionLocal() as db:
                    current = db.get(Batch, batch_id)
                    if not current or current.is_paused:
                        break
                try:
                    self._send_one(batch_id, participant_id, client)
                except Exception:
                    # _send_one persists all expected failures; a guard below catches programming faults.
                    logger.exception("delivery_event=unexpected_worker_error participant=%s", _record_ref(participant_id))
                    with SessionLocal() as db:
                        row = db.get(Participant, participant_id)
                        if row and row.status == DeliveryStatus.SENDING:
                            row.status = DeliveryStatus.UNCERTAIN
                            row.error_reason = "Unexpected worker interruption; outcome requires review"
                            reservation = db.scalars(select(SendRecord).where(
                                SendRecord.participant_id == row.id, SendRecord.status == "RESERVED"
                            ).order_by(SendRecord.reserved_at.desc())).first()
                            if reservation:
                                reservation.status = "UNCERTAIN"
                                reservation.finished_at = datetime.now(timezone.utc)
                                reservation.error_reason = row.error_reason
                            attempt = db.scalars(select(DeliveryAttempt).where(
                                DeliveryAttempt.participant_id == row.id,
                                DeliveryAttempt.outcome.is_(None),
                            ).order_by(DeliveryAttempt.id.desc())).first()
                            if attempt:
                                attempt.outcome = "UNCERTAIN"
                                attempt.error_code = "WORKER_INTERRUPTION"
                                attempt.error_reason = row.error_reason
                                attempt.finished_at = datetime.now(timezone.utc)
                            db.commit()
        finally:
            if client and hasattr(client, "close"):
                client.close()
            with SessionLocal() as db:
                batch = db.get(Batch, batch_id)
                if batch and not batch.is_paused:
                    batch.send_job_finished_at = datetime.now(timezone.utc)
                    db.commit()
            logger.info("delivery_event=worker_stopped batch=%s", _record_ref(batch_id))

    def _send_one(self, batch_id: str, participant_id: str, client: SMTPClient | None = None):
        attempt_started = time.perf_counter()
        with SessionLocal() as db:
            batch = db.get(Batch, batch_id)
            participant = db.get(Participant, participant_id)
            if not batch or not participant or batch.is_paused or participant.status != DeliveryStatus.PENDING:
                return
            if not batch.sender_email or not participant.certificate_path:
                participant.status = DeliveryStatus.FAILED
                participant.error_reason = "Email configuration or certificate is missing"
                db.commit()
                return
            if participant.certificate_revision != batch.certificate_revision or not is_render_current(participant.certificate_path):
                participant.error_reason = "Certificate styling changed; regenerate before sending"
                db.commit()
                logger.warning("delivery_event=skipped participant=%s reason=outdated_certificate", _record_ref(participant_id))
                return
            name, email, key = participant.name, participant.email, participant.idempotency_key
            sender, path = batch.sender_email, Path(participant.certificate_path)
            values = {"name": name}
            subject = render_template(batch.email_subject, values)
            body = render_template(batch.email_body, values)
        logger.info("delivery_event=profile participant=%s stage=prepare duration_ms=%s", _record_ref(participant_id), round((time.perf_counter() - attempt_started) * 1000, 1))

        reservation_started = time.perf_counter()
        reservation_id = self.reserve_send(batch_id, participant_id, "BULK")
        if not reservation_id:
            with SessionLocal() as db:
                participant = db.get(Participant, participant_id)
                if participant and participant.status == DeliveryStatus.PENDING:
                    participant.error_reason = "Rolling 24-hour application sending limit reached"
                    batch = db.get(Batch, batch_id)
                    if batch:
                        batch.is_paused = True
                    db.commit()
            return
        logger.info("delivery_event=profile participant=%s stage=quota_reservation duration_ms=%s", _record_ref(participant_id), round((time.perf_counter() - reservation_started) * 1000, 1))

        claim_started = time.perf_counter()
        with SessionLocal() as db:
            batch = db.get(Batch, batch_id)
            if not batch or batch.is_paused:
                self.finish_reservation(reservation_id, "CANCELLED", error="Send cancelled before SMTP submission")
                return
            claimed = db.execute(
                update(Participant).where(
                    Participant.id == participant_id,
                    Participant.status == DeliveryStatus.PENDING,
                ).values(status=DeliveryStatus.SENDING, error_reason=None, updated_at=datetime.now(timezone.utc))
            ).rowcount
            if claimed != 1:
                db.rollback()
                self.finish_reservation(reservation_id, "CANCELLED", error="Participant was already claimed")
                return
            participant = db.get(Participant, participant_id)
            attempt_count = db.scalar(select(func.count()).select_from(DeliveryAttempt).where(DeliveryAttempt.participant_id == participant.id)) or 0
            attempt = DeliveryAttempt(
                participant_id=participant.id,
                attempt_number=attempt_count + 1,
                certificate_path=participant.certificate_path,
                certificate_filename=participant.filename,
            )
            db.add(attempt)
            db.commit()
        logger.info("delivery_event=profile participant=%s stage=atomic_claim duration_ms=%s", _record_ref(participant_id), round((time.perf_counter() - claim_started) * 1000, 1))
        logger.info("delivery_event=status participant=%s status=SENDING", _record_ref(participant_id))
        try:
            client = client or self.smtp_factory()
        except Exception:
            with SessionLocal() as db:
                participant = db.get(Participant, participant_id)
                attempt = db.scalars(select(DeliveryAttempt).where(DeliveryAttempt.participant_id == participant_id).order_by(DeliveryAttempt.id.desc())).first()
                if participant:
                    participant.status = DeliveryStatus.FAILED
                    participant.error_reason = "SMTP backend configuration is unavailable"
                if attempt:
                    attempt.outcome = "FAILED"
                    attempt.error_code = "SMTP_CONFIGURATION"
                    attempt.error_reason = "SMTP backend configuration is unavailable"
                    attempt.finished_at = datetime.now(timezone.utc)
                db.commit()
            self.finish_reservation(reservation_id, "FAILED", error="SMTP backend configuration is unavailable")
            return
        last_error: Exception | None = None
        for retry in range(3):
            try:
                with self.submission_slot():
                    with SessionLocal() as db:
                        current_batch = db.get(Batch, batch_id)
                        if not current_batch or current_batch.is_paused:
                            raise SendPaused()
                    smtp_started = time.perf_counter()
                    message_id = client.send(sender, email, subject, body, path, key)
                smtp_duration = time.perf_counter() - smtp_started
                self.record_healthy_send()
                persist_started = time.perf_counter()
                with SessionLocal() as db:
                    participant = db.get(Participant, participant_id)
                    attempt = db.scalars(select(DeliveryAttempt).where(DeliveryAttempt.participant_id == participant_id).order_by(DeliveryAttempt.id.desc())).first()
                    participant.status = DeliveryStatus.SENT
                    participant.smtp_message_id = message_id
                    participant.sent_at = datetime.now(timezone.utc)
                    if attempt:
                        attempt.outcome, attempt.smtp_message_id, attempt.finished_at = "SENT", message_id, datetime.now(timezone.utc)
                    db.commit()
                self.finish_reservation(reservation_id, "SENT", message_id=message_id)
                logger.info(
                    "delivery_event=status participant=%s status=SENT smtp_ms=%s persist_ms=%s total_ms=%s",
                    _record_ref(participant_id), round(smtp_duration * 1000, 1),
                    round((time.perf_counter() - persist_started) * 1000, 1),
                    round((time.perf_counter() - attempt_started) * 1000, 1),
                )
                return
            except TransientSendError as exc:
                last_error = exc
                self.record_temporary_failure(exc.retry_after)
                logger.warning("delivery_event=transient participant=%s retry=%s", _record_ref(participant_id), retry + 1)
                if exc.rate_limited:
                    with SessionLocal() as db:
                        batch = db.get(Batch, batch_id)
                        if batch:
                            batch.is_paused = True
                            db.commit()
                    logger.warning("delivery_event=batch_paused batch=%s reason=rate_limit code=%s", _record_ref(batch_id), exc.smtp_code)
                    break
                if retry < 2:
                    time.sleep(exc.retry_after or 2**retry)
                    continue
            except (DefiniteSendError, UncertainSendError) as exc:
                last_error = exc
            except SendPaused:
                with SessionLocal() as db:
                    participant = db.get(Participant, participant_id)
                    attempt = db.scalars(select(DeliveryAttempt).where(DeliveryAttempt.participant_id == participant_id).order_by(DeliveryAttempt.id.desc())).first()
                    if participant and participant.status == DeliveryStatus.SENDING:
                        participant.status = DeliveryStatus.PENDING
                        participant.error_reason = "Sending paused before SMTP submission"
                    if attempt:
                        attempt.outcome = "PAUSED"
                        attempt.error_code = "PAUSED"
                        attempt.finished_at = datetime.now(timezone.utc)
                    db.commit()
                self.finish_reservation(reservation_id, "CANCELLED", error="Sending paused before SMTP submission")
                logger.info("delivery_event=status participant=%s status=PENDING reason=paused", _record_ref(participant_id))
                return
            break

        with SessionLocal() as db:
            participant = db.get(Participant, participant_id)
            attempt = db.scalars(select(DeliveryAttempt).where(DeliveryAttempt.participant_id == participant_id).order_by(DeliveryAttempt.id.desc())).first()
            uncertain = isinstance(last_error, UncertainSendError)
            participant.status = DeliveryStatus.UNCERTAIN if uncertain else DeliveryStatus.FAILED
            participant.error_reason = str(last_error)
            if attempt:
                attempt.outcome = participant.status.value
                attempt.error_code = "UNCERTAIN_SUBMISSION" if uncertain else "DEFINITE_FAILURE"
                attempt.error_reason = str(last_error)
                attempt.finished_at = datetime.now(timezone.utc)
            db.commit()
        self.finish_reservation(reservation_id, "UNCERTAIN" if uncertain else "FAILED", error=str(last_error))
        logger.warning("delivery_event=status participant=%s status=%s", _record_ref(participant_id), "UNCERTAIN" if uncertain else "FAILED")

