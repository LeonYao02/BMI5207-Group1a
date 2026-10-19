"""Shared, versioned identity/date rules. Reuse the SAME key across all domains.

This provides pseudonymisation, not an anonymity guarantee. Keep key and registries
private. Never use the demonstration/test keys for the actual group dataset.
"""
from __future__ import annotations

import csv
import hashlib
import hmac
import os
import secrets
from datetime import date, datetime, timedelta
from pathlib import Path

# Fits the signed INTEGER identifiers in the stock CDM 5.4 DDL and is exact in Excel.
# This small coursework dataset is checked for collisions before export.
ID_MAX = 2**31 - 1
ID_SCHEME = "hmac-sha256-int31-v2"


def clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def load_key(path: Path, *, create: bool = False) -> bytes:
    if not path.exists():
        if not create:
            raise ValueError(f"Missing group key: {path}. Run the init-key command once.")
        path.parent.mkdir(parents=True, exist_ok=True)
        # O_EXCL prevents accidentally replacing another member's group key.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as stream:
            stream.write(secrets.token_hex(32) + "\n")
    key = bytes.fromhex(path.read_text(encoding="ascii").strip())
    if len(key) != 32:
        raise ValueError("Group key must contain exactly 32 random bytes, encoded as hex.")
    return key


def digest(key: bytes, namespace: str, *parts: str) -> bytes:
    # Length-prefix components: ('ab','c') must never collide with ('a','bc').
    message = b"BMI5207-v1"
    for part in (namespace, *parts):
        value = clean(part).encode("utf-8")
        message += len(value).to_bytes(4, "big") + value
    return hmac.new(key, message, hashlib.sha256).digest()


def person_id(key: bytes, patient_no: str) -> int:
    if not clean(patient_no):
        raise ValueError("Patient_No is missing.")
    return int.from_bytes(digest(key, "person", patient_no)[:8], "big") % ID_MAX + 1


def visit_id(key: bytes, patient_no: str, case_no: str) -> int:
    if not clean(case_no):
        raise ValueError("Case_No is missing.")
    return int.from_bytes(digest(key, "visit", patient_no, case_no)[:8], "big") % ID_MAX + 1


def event_id(key: bytes, patient_no: str, source_key: str) -> int:
    return int.from_bytes(digest(key, "drug-event", patient_no, source_key)[:8], "big") % ID_MAX + 1


def date_offset(key: bytes, patient_no: str, max_days: int = 180) -> int:
    if not clean(patient_no) or max_days < 1:
        raise ValueError("A patient number and a positive shift range are required.")
    value = int.from_bytes(digest(key, "date-shift", patient_no)[:8], "big") % (2 * max_days)
    # Uniform in [-max_days,-1] U [1,max_days]. No unshifted patients.
    return value - max_days if value < max_days else value - max_days + 1


def parse_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    text = clean(value)
    if not text:
        raise ValueError("Missing date/time.")
    return datetime.fromisoformat(text)


def shift_datetime(key: bytes, patient_no: str, value: object, max_days: int = 180) -> datetime:
    return parse_datetime(value) + timedelta(days=date_offset(key, patient_no, max_days))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="raise", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))
