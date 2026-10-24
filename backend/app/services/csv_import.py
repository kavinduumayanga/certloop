import csv
import io
import re
from dataclasses import dataclass

from email_validator import EmailNotValidError, validate_email


@dataclass
class ImportedRow:
    row_number: int
    name: str
    email: str
    normalized_email: str
    is_valid: bool
    error: str | None = None


def validate_participant(name: str, email: str) -> tuple[str, str, list[str]]:
    """Return cleaned name, canonical email, and user-facing validation errors."""
    clean_name = " ".join(name.strip().split())
    clean_email = email.strip()
    errors: list[str] = []
    if not clean_name:
        errors.append("Name is required")
    canonical = clean_email.casefold()
    if not clean_email:
        errors.append("Email is required")
    else:
        try:
            canonical = validate_email(clean_email, check_deliverability=False).normalized.casefold()
        except EmailNotValidError as exc:
            errors.append(str(exc))
    return clean_name, canonical, errors


NAME_ALIASES = {
    "name", "participant", "participant name", "participant's name", "full name",
    "fullname", "attendee name", "student name", "certificate name", "name on certificate",
}
EMAIL_ALIASES = {
    "email", "email address", "e-mail", "e-mail address", "mail", "participant email",
    "participant email address", "email address (to send the e-certificate)",
    "email address (to send the e-certificate )", "email address for certificate",
}


def normalize_header(value: str) -> str:
    """Canonicalize untrusted CSV headings without changing the displayed heading."""
    return " ".join(value.lstrip("\ufeff").strip().split()).casefold()


def _header_match(headers: list[str], requested: str | None, aliases: set[str], kind: str) -> str | None:
    normalized = [(header, normalize_header(header)) for header in headers]
    if requested:
        requested_normalized = normalize_header(requested)
        return next((header for header, canonical in normalized if canonical == requested_normalized), None)
    exact = next((header for header, canonical in normalized if canonical in aliases), None)
    if exact:
        return exact
    if kind == "email":
        return next((header for header, canonical in normalized if re.search(r"\be-?mail\b", canonical)), None)
    return next((header for header, canonical in normalized if "name" in canonical and any(word in canonical for word in ("participant", "attendee", "student", "certificate", "full"))), None)


def resolve_columns(headers: list[str], name_column: str | None = None, email_column: str | None = None) -> tuple[str | None, str | None]:
    return (
        _header_match(headers, name_column, NAME_ALIASES, "name"),
        _header_match(headers, email_column, EMAIL_ALIASES, "email"),
    )


def parse_participants(data: bytes, name_column: str | None = None, email_column: str | None = None) -> tuple[list[ImportedRow], list[str]]:
    if b"\x00" in data:
        raise ValueError("CSV contains NUL bytes")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8 encoded") from exc
    reader = csv.DictReader(io.StringIO(text, newline=""))
    headers = reader.fieldnames or []
    name_key, email_key = resolve_columns(headers, name_column, email_column)
    if not name_key or not email_key:
        return [], headers
    result: list[ImportedRow] = []
    seen: set[str] = set()
    for row_number, row in enumerate(reader, start=2):
        email = (row.get(email_key) or "").strip()
        name, normalized, errors = validate_participant(row.get(name_key) or "", email)
        if normalized and normalized in seen:
            errors.append("Duplicate email in this import")
        elif normalized:
            seen.add(normalized)
        result.append(ImportedRow(row_number, name, email, normalized, not errors, "; ".join(errors) or None))
    return result, headers


def csv_safe(value: object) -> str:
    text = "" if value is None else str(value)
    if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text
