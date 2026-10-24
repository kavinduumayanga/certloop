import os
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///./data/test-certificates.db")
os.environ.setdefault("DATA_DIR", "./data/test-data")

import pytest
from PIL import ImageFont

from app.config import get_settings
from app.database import Base, engine


@pytest.fixture(autouse=True)
def clean_database():
    settings = get_settings()
    settings.max_emails_per_day = 200
    settings.email_send_delay_seconds = 0
    settings.min_email_send_delay_seconds = 0
    settings.max_email_send_delay_seconds = 120
    settings.healthy_sends_before_speedup = 5
    settings.smtp_connection_reuse = True
    settings.smtp_max_messages_per_connection = 25
    settings.smtp_workers = 1
    settings.smtp_timeout_seconds = 30
    settings.smtp_data_timeout_seconds = 300
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def font_path() -> Path:
    candidates = [
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    path = next((candidate for candidate in candidates if candidate.exists()), None)
    if path is None:
        pytest.skip("No system TrueType font is available for rendering tests")
    ImageFont.truetype(str(path), 12)
    return path

