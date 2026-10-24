import re
import unicodedata
from pathlib import Path


def safe_filename(value: str, fallback: str = "certificate") -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode()
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", ascii_value).strip("-._")
    return (stem[:120] or fallback)


def contained_path(root: Path, *parts: str) -> Path:
    root = root.resolve()
    candidate = root.joinpath(*parts).resolve()
    if root != candidate and root not in candidate.parents:
        raise ValueError("Unsafe path")
    return candidate

