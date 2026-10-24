import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


DEFAULT_EMAIL_SUBJECT = "Your Certificate – Introduction to DevOps Workshop"
DEFAULT_EMAIL_BODY = """Hi {name},

Thank you for joining the Introduction to DevOps Workshop, organized by MS Club of SLIIT with Sysco LABS. Your certificate of participation is attached.

Keep learning and building!

Best regards,
MS Club of SLIIT"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DeliveryStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENDING = "SENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    UNCERTAIN = "UNCERTAIN"


class Batch(Base):
    __tablename__ = "batches"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200), default="Certificate batch")
    name_normalized: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
    workshop_name: Mapped[str] = mapped_column(String(300), default="Workshop")
    template_path: Mapped[str | None] = mapped_column(Text)
    font_path: Mapped[str | None] = mapped_column(Text)
    region_x: Mapped[float] = mapped_column(Float, default=0.2)
    region_y: Mapped[float] = mapped_column(Float, default=0.45)
    region_w: Mapped[float] = mapped_column(Float, default=0.6)
    region_h: Mapped[float] = mapped_column(Float, default=0.12)
    font_size: Mapped[int] = mapped_column(Integer, default=110)
    min_font_size: Mapped[int] = mapped_column(Integer, default=38)
    auto_fit: Mapped[bool] = mapped_column(Boolean, default=True)
    vertical_offset: Mapped[int] = mapped_column(Integer, default=0)
    sender_email: Mapped[str | None] = mapped_column(String(320))
    email_subject: Mapped[str] = mapped_column(String(500), default=DEFAULT_EMAIL_SUBJECT)
    email_body: Mapped[str] = mapped_column(Text, default=DEFAULT_EMAIL_BODY)
    is_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    send_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    send_job_total: Mapped[int] = mapped_column(Integer, default=0)
    send_job_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    send_job_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active_import_id: Mapped[str | None] = mapped_column(String(36), index=True)
    generation_job_id: Mapped[str | None] = mapped_column(String(36))
    generation_status: Mapped[str] = mapped_column(String(20), default="IDLE")
    generation_total: Mapped[int] = mapped_column(Integer, default=0)
    generation_succeeded: Mapped[int] = mapped_column(Integer, default=0)
    generation_failed: Mapped[int] = mapped_column(Integer, default=0)
    generation_current_name: Mapped[str | None] = mapped_column(String(500))
    generation_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    generation_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    participants: Mapped[list["Participant"]] = relationship(back_populates="batch", cascade="all, delete-orphan")


class Participant(Base):
    __tablename__ = "participants"
    __table_args__ = (UniqueConstraint("batch_id", "normalized_email"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id"), index=True)
    row_number: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(500))
    email: Mapped[str] = mapped_column(String(320))
    normalized_email: Mapped[str] = mapped_column(String(320))
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    is_excluded: Mapped[bool] = mapped_column(Boolean, default=False)
    validation_error: Mapped[str | None] = mapped_column(Text)
    # Imports are snapshots. Older rows remain in SQLite for delivery/audit
    # history, while only the latest snapshot is shown or eligible to send.
    is_current_import: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    import_id: Mapped[str | None] = mapped_column(String(36), index=True)
    canonical_email: Mapped[str | None] = mapped_column(String(320), index=True)
    previous_delivery_id: Mapped[str | None] = mapped_column(String, index=True)
    certificate_path: Mapped[str | None] = mapped_column(Text)
    preview_path: Mapped[str | None] = mapped_column(Text)
    filename: Mapped[str | None] = mapped_column(String(600))
    legibility_warning: Mapped[str | None] = mapped_column(Text)
    generation_error: Mapped[str | None] = mapped_column(Text)
    status: Mapped[DeliveryStatus] = mapped_column(Enum(DeliveryStatus), default=DeliveryStatus.PENDING, index=True)
    # Keep the legacy SQLite column name for in-place compatibility with existing batches.
    smtp_message_id: Mapped[str | None] = mapped_column("gmail_message_id", String(300))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_reason: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    batch: Mapped[Batch] = relationship(back_populates="participants")
    attempts: Mapped[list["DeliveryAttempt"]] = relationship(back_populates="participant", cascade="all, delete-orphan")


class DeliveryAttempt(Base):
    __tablename__ = "delivery_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str | None] = mapped_column(String(40))
    smtp_message_id: Mapped[str | None] = mapped_column("gmail_message_id", String(300))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_reason: Mapped[str | None] = mapped_column(Text)
    reconciliation_action: Mapped[str | None] = mapped_column(String(40))
    reconciliation_note: Mapped[str | None] = mapped_column(Text)
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    participant: Mapped[Participant] = relationship(back_populates="attempts")


class SendRecord(Base):
    """Persistent rolling-limit reservation for bulk and test SMTP submissions."""
    __tablename__ = "send_records"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_id: Mapped[str | None] = mapped_column(String, index=True)
    participant_id: Mapped[str | None] = mapped_column(String, index=True)
    kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="RESERVED", index=True)
    counts_against_limit: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    reserved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    smtp_message_id: Mapped[str | None] = mapped_column(String(300))
    error_reason: Mapped[str | None] = mapped_column(Text)

