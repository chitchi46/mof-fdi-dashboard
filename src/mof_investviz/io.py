from __future__ import annotations

import csv
import os
from typing import Dict, Iterable, List, Tuple


TRIAL_ENCODINGS = ["utf-8", "utf-8-sig", "cp932", "shift_jis"]


def detect_encoding(path: str, trial_encodings: Iterable[str] = TRIAL_ENCODINGS) -> str:
    """Return the first encoding that can decode the file without error.

    This is a lightweight heuristic suitable for MVP. It does not guarantee
    semantic correctness, only successful decoding.
    """
    with open(path, "rb") as f:
        head = f.read(65536)
    for enc in trial_encodings:
        try:
            head.decode(enc)
            return enc
        except Exception:
            continue
    # Fallback to UTF-8 if none succeeded
    return "utf-8"


def sniff_dialect(sample_text: str) -> csv.Dialect:
    try:
        return csv.Sniffer().sniff(sample_text)
    except Exception:
        # Default to comma separated
        class _Default(csv.Dialect):
            delimiter = ","
            quotechar = '"'
            escapechar = None
            doublequote = True
            skipinitialspace = False
            lineterminator = "\n"
            quoting = csv.QUOTE_MINIMAL

        return _Default()


def read_csv_rows(path: str, encoding: str | None = None) -> Tuple[List[Dict[str, str]], List[str], Dict[str, str]]:
    """Read a CSV file into a list of dict rows.

    Returns (rows, headers, meta) where meta includes encoding and dialect info.
    """
    enc = encoding or detect_encoding(path)
    with open(path, "r", encoding=enc, errors="strict", newline="") as f:
        sample = f.read(8192)
        f.seek(0)
        dialect = sniff_dialect(sample)
        reader = csv.DictReader(f, dialect=dialect)
        headers = reader.fieldnames or []
        rows: List[Dict[str, str]] = [dict(r) for r in reader]
    meta = {
        "encoding": enc,
        "delimiter": getattr(dialect, "delimiter", ","),
        "quotechar": getattr(dialect, "quotechar", '"'),
        "path": os.path.abspath(path),
    }
    return rows, headers, meta


def write_csv(path: str, rows: Iterable[Dict[str, object]], headers: List[str]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in headers})


def read_csv_matrix(path: str, encoding: str | None = None) -> Tuple[List[List[str]], Dict[str, str]]:
    """Read a CSV into a list-of-lists (raw matrix) with dialect sniffing.

    Returns (matrix, meta)
    """
    enc = encoding or detect_encoding(path)
    with open(path, "r", encoding=enc, errors="strict", newline="") as f:
        sample = f.read(8192)
        f.seek(0)
        dialect = sniff_dialect(sample)
        reader = csv.reader(f, dialect=dialect)
        matrix: List[List[str]] = [list(map(lambda x: x.strip(), row)) for row in reader]
    meta = {
        "encoding": enc,
        "delimiter": getattr(dialect, "delimiter", ","),
        "quotechar": getattr(dialect, "quotechar", '"'),
        "path": os.path.abspath(path),
    }
    return matrix, meta
