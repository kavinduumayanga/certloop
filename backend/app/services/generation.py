import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from ..config import Settings
from ..database import SessionLocal
from ..models import Batch, Participant
from .fonts import resolve_font_path
from .rendering import render_certificate


logger = logging.getLogger("certificate.generation")


class GenerationManager:
    """Runs one durable, observable certificate-generation job per batch."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._threads: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    def recover(self) -> int:
        with SessionLocal() as db:
            rows = db.scalars(select(Batch).where(Batch.generation_status == "RUNNING")).all()
            for batch in rows:
                batch.generation_status = "INTERRUPTED"
                batch.generation_current_name = None
                batch.generation_finished_at = datetime.now(timezone.utc)
            db.commit()
            return len(rows)

    def is_running(self, batch_id: str) -> bool:
        with self._lock:
            thread = self._threads.get(batch_id)
            return bool(thread and thread.is_alive())

    def start(self, batch_id: str, participant_id: str | None = None) -> bool:
        with self._lock:
            existing = self._threads.get(batch_id)
            if existing and existing.is_alive():
                return False
            thread = threading.Thread(target=self._run, args=(batch_id, participant_id), daemon=True, name=f"generation-{batch_id[:8]}")
            self._threads[batch_id] = thread
            thread.start()
            return True

    def _run(self, batch_id: str, participant_id: str | None = None) -> None:
        job_id = str(uuid.uuid4())
        with SessionLocal() as db:
            batch = db.get(Batch, batch_id)
            if not batch or not batch.template_path:
                return
            active_import_id = batch.active_import_id
            query = select(Participant).where(
                Participant.batch_id == batch_id,
                Participant.is_current_import.is_(True),
                Participant.is_valid.is_(True),
                Participant.is_excluded.is_(False),
            )
            if participant_id:
                query = query.where(Participant.id == participant_id)
            rows = db.scalars(query.order_by(Participant.row_number)).all()
            ids = [row.id for row in rows]
            batch.generation_job_id = job_id
            batch.generation_status = "RUNNING"
            batch.generation_total = len(ids)
            batch.generation_succeeded = 0
            batch.generation_failed = 0
            batch.generation_current_name = None
            batch.generation_started_at = datetime.now(timezone.utc)
            batch.generation_finished_at = None
            template_path = Path(batch.template_path)
            font_path = resolve_font_path(batch.font_path)
            certificate_revision = batch.certificate_revision
            region = {
                "x": batch.region_x, "y": batch.region_y, "w": batch.region_w, "h": batch.region_h,
                "font_size": batch.font_size, "min_font_size": batch.min_font_size,
                "auto_fit": batch.auto_fit, "vertical_offset": batch.vertical_offset,
            }
            db.commit()

        output = self.settings.generated_dir / batch_id
        for participant_id in ids:
            with SessionLocal() as db:
                batch = db.get(Batch, batch_id)
                row = db.get(Participant, participant_id)
                if not batch or batch.generation_job_id != job_id:
                    return
                # An import/edit during a job cannot attach an old result to the
                # replacement dataset. The endpoint blocks those mutations, and
                # this check is a final integrity guard.
                if not row or not row.is_current_import or row.import_id != active_import_id:
                    batch.generation_failed += 1
                    db.commit()
                    continue
                batch.generation_current_name = row.name
                row.generation_error = None
                name = row.name
                db.commit()
            try:
                result = render_certificate(template_path, font_path, output, participant_id, name, region)
                with SessionLocal() as db:
                    batch = db.get(Batch, batch_id)
                    row = db.get(Participant, participant_id)
                    if not batch or batch.generation_job_id != job_id or not row or not row.is_current_import or row.import_id != active_import_id:
                        continue
                    row.certificate_path = str(result.pdf_path.resolve())
                    row.preview_path = str(result.preview_path.resolve())
                    row.filename = result.filename
                    row.legibility_warning = result.warning
                    row.generation_error = None
                    row.certificate_revision = certificate_revision
                    batch.generation_succeeded += 1
                    db.commit()
            except Exception as exc:  # preserve the rest of a bulk generation job
                logger.exception("certificate generation failed participant=%s", participant_id[:12])
                with SessionLocal() as db:
                    batch = db.get(Batch, batch_id)
                    row = db.get(Participant, participant_id)
                    if not batch or batch.generation_job_id != job_id:
                        return
                    if row:
                        row.generation_error = f"{type(exc).__name__}: {exc}"
                    batch.generation_failed += 1
                    db.commit()

        with SessionLocal() as db:
            batch = db.get(Batch, batch_id)
            if batch and batch.generation_job_id == job_id:
                batch.generation_status = "COMPLETED" if batch.generation_failed == 0 else "COMPLETED_WITH_ERRORS"
                batch.generation_current_name = None
                batch.generation_finished_at = datetime.now(timezone.utc)
                db.commit()
