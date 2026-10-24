from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from .database import clean_session_name

from .models import DeliveryStatus


class BatchCreate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return clean_session_name(value)


class RegionUpdate(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)
    font_size: int = Field(ge=8, le=1000)
    min_font_size: int = Field(ge=8, le=500)
    auto_fit: bool = True
    vertical_offset: int = Field(ge=-1000, le=1000)

    @model_validator(mode="after")
    def minimum_does_not_exceed_maximum(self):
        if self.min_font_size > self.font_size:
            raise ValueError("Minimum font size cannot exceed font size")
        return self


class PreviewRequest(RegionUpdate):
    participant_id: str


class EmailConfig(BaseModel):
    sender_email: EmailStr
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=100_000)


class ParticipantPatch(BaseModel):
    # Accept draft strings here so the row can persist and show precise
    # validation feedback instead of losing the edit at request parsing time.
    name: str | None = Field(default=None, max_length=500)
    email: str | None = Field(default=None, max_length=320)
    is_excluded: bool | None = None


class ParticipantOut(BaseModel):
    id: str
    row_number: int
    name: str
    email: str
    is_valid: bool
    is_excluded: bool
    validation_error: str | None
    status: DeliveryStatus
    filename: str | None
    certificate_current: bool = False
    legibility_warning: str | None
    smtp_message_id: str | None
    sent_at: datetime | None
    updated_at: datetime | None
    error_reason: str | None
    model_config = {"from_attributes": True}


class BatchOut(BaseModel):
    id: str
    name: str
    template_path: str | None
    font_path: str | None
    sender_email: str | None
    email_subject: str
    email_body: str
    is_paused: bool
    send_confirmed: bool
    region: dict
    counts: dict[str, int]
    ready_count: int = 0
    outdated_certificate_count: int = 0
    allowance: dict[str, int]
    participants: list[ParticipantOut] = []


class StartSendRequest(BaseModel):
    confirmation: str


class ReconcileRequest(BaseModel):
    action: Literal["CONFIRM_SENT", "CONFIRM_NOT_SENT"]
    confirmation: str
    note: str = Field(default="", max_length=1000)

