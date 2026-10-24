from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def clean_session_name(value: str | None) -> str:
    """Normalize display whitespace and enforce the public session-name contract."""
    cleaned = " ".join((value or "").strip().split())
    if not cleaned:
        raise ValueError("Session name is required")
    if len(cleaned) > 100:
        raise ValueError("Session name must be 100 characters or fewer")
    return cleaned


def normalized_session_name(value: str) -> str:
    return clean_session_name(value).casefold()


def ensure_unique_session_names(connection) -> None:
    """Backfill unique readable names for legacy blank/duplicate sessions."""
    rows = connection.execute(text("SELECT id, name FROM batches ORDER BY created_at, id")).all()
    used: set[str] = set()
    unnamed = 0
    for session_id, stored_name in rows:
        raw = " ".join((stored_name or "").strip().split())
        if not raw:
            unnamed += 1
            raw = f"Session {unnamed}"
        raw = raw[:100].rstrip() or "Session"
        candidate = raw
        suffix = 2
        while candidate.casefold() in used:
            ending = f" {suffix}"
            candidate = f"{raw[:100-len(ending)].rstrip()}{ending}"
            suffix += 1
        canonical = candidate.casefold()
        used.add(canonical)
        connection.execute(text("UPDATE batches SET name=:name, name_normalized=:normalized WHERE id=:id"), {
            "name": candidate, "normalized": canonical, "id": session_id,
        })
    connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_batches_name_normalized ON batches(name_normalized)"))


def relocated_path(stored: str | None, root: Path, batch_id: str | None = None) -> str | None:
    """Resolve a stale absolute runtime path after the project directory moves."""
    if not stored or Path(stored).exists():
        return stored
    candidate = root / batch_id / Path(stored).name if batch_id else root / Path(stored).name
    return str(candidate.resolve()) if candidate.exists() else stored


def ensure_schema() -> None:
    """Apply the small additive migration needed by existing local SQLite installs."""
    if engine.dialect.name != "sqlite" or "batches" not in inspect(engine).get_table_names():
        return
    additions = {
        "batches": {
            "name_normalized": "VARCHAR(100)",
            "send_job_total": "INTEGER NOT NULL DEFAULT 0",
            "send_job_started_at": "DATETIME",
            "send_job_finished_at": "DATETIME",
            "active_import_id": "VARCHAR(36)",
            "generation_job_id": "VARCHAR(36)",
            "generation_status": "VARCHAR(20) NOT NULL DEFAULT 'IDLE'",
            "generation_total": "INTEGER NOT NULL DEFAULT 0",
            "generation_succeeded": "INTEGER NOT NULL DEFAULT 0",
            "generation_failed": "INTEGER NOT NULL DEFAULT 0",
            "generation_current_name": "VARCHAR(500)",
            "generation_started_at": "DATETIME",
            "generation_finished_at": "DATETIME",
        },
        "delivery_attempts": {
            "reconciliation_action": "VARCHAR(40)",
            "reconciliation_note": "TEXT",
            "reconciled_at": "DATETIME",
        },
        "participants": {
            "is_current_import": "BOOLEAN NOT NULL DEFAULT 1",
            "import_id": "VARCHAR(36)",
            "canonical_email": "VARCHAR(320)",
            "previous_delivery_id": "VARCHAR",
            "generation_error": "TEXT",
        },
    }
    with engine.begin() as connection:
        for table, columns in additions.items():
            if table not in inspect(engine).get_table_names():
                continue
            existing = {column["name"] for column in inspect(engine).get_columns(table)}
            for name, definition in columns.items():
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
        # Give legacy active rows an explicit immutable import identity without
        # changing any participant, certificate, delivery, or attempt record.
        batches = connection.execute(text("SELECT id, active_import_id FROM batches")).all()
        for batch_id, active_import_id in batches:
            import_id = active_import_id or f"legacy-{batch_id[:29]}"
            if not active_import_id:
                connection.execute(text("UPDATE batches SET active_import_id=:import_id WHERE id=:batch_id"), {"import_id": import_id, "batch_id": batch_id})
            connection.execute(text("UPDATE participants SET import_id=:import_id WHERE batch_id=:batch_id AND is_current_import=1 AND import_id IS NULL"), {"import_id": import_id, "batch_id": batch_id})
        connection.execute(text("UPDATE participants SET canonical_email=lower(email) WHERE canonical_email IS NULL AND normalized_email NOT LIKE '__invalid__:%'"))
        ensure_unique_session_names(connection)
        # Runtime files were historically stored as absolute paths. Repair only
        # paths whose old target is missing and whose basename exists in the
        # configured data directory; delivery state and audit rows are untouched.
        for batch_id, template_path, font_path in connection.execute(text("SELECT id, template_path, font_path FROM batches")).all():
            repaired_template = relocated_path(template_path, settings.upload_dir)
            repaired_font = relocated_path(font_path, settings.upload_dir)
            if repaired_template != template_path or repaired_font != font_path:
                connection.execute(text("UPDATE batches SET template_path=:template_path, font_path=:font_path WHERE id=:batch_id"), {
                    "template_path": repaired_template, "font_path": repaired_font, "batch_id": batch_id,
                })
        for participant_id, batch_id, certificate_path, preview_path in connection.execute(text("SELECT id, batch_id, certificate_path, preview_path FROM participants WHERE certificate_path IS NOT NULL OR preview_path IS NOT NULL")).all():
            repaired_certificate = relocated_path(certificate_path, settings.generated_dir, batch_id)
            repaired_preview = relocated_path(preview_path, settings.generated_dir, batch_id)
            if repaired_certificate != certificate_path or repaired_preview != preview_path:
                connection.execute(text("UPDATE participants SET certificate_path=:certificate_path, preview_path=:preview_path WHERE id=:participant_id"), {
                    "certificate_path": repaired_certificate, "preview_path": repaired_preview, "participant_id": participant_id,
                })


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

