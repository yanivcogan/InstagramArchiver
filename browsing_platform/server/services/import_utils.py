import csv
import io
from typing import Optional

from fastapi import HTTPException


def parse_import_file(file_bytes: bytes, filename: str, expected_columns: list[str],
                      required_columns: Optional[list[str]] = None) -> list[dict]:
    """
    Parses a CSV (utf-8-sig) or XLSX (first sheet) file.
    Returns a list of row dicts with lowercase, stripped keys.
    Raises HTTPException(400) if required columns are missing.
    Enforces a 5MB file size limit.
    """
    if len(file_bytes) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 5 MB)")

    lower_expected = [c.lower() for c in expected_columns]
    lower_required = [c.lower() for c in (required_columns or [])]

    if filename.lower().endswith(".xlsx"):
        rows = _parse_xlsx(file_bytes, lower_expected)
    else:
        rows = _parse_csv(file_bytes, lower_expected)

    if rows and lower_required:
        actual_keys = set(rows[0].keys())
        missing = [c for c in lower_required if c not in actual_keys]
        if missing:
            raise HTTPException(status_code=400, detail=f"Missing required columns: {', '.join(missing)}")

    return rows


def _parse_csv(file_bytes: bytes, expected_columns: list[str]) -> list[dict]:
    text = file_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return []
    # Normalize headers to lowercase
    normalized_headers = [h.strip().lower() for h in reader.fieldnames]
    rows = []
    for row in reader:
        normalized = {}
        for orig_key, value in row.items():
            key = orig_key.strip().lower() if orig_key else orig_key
            if key in expected_columns:
                normalized[key] = (value or "").strip()
        # Fill missing expected columns with empty string
        for col in expected_columns:
            if col not in normalized:
                normalized[col] = ""
        rows.append(normalized)
    return rows


def _parse_xlsx(file_bytes: bytes, expected_columns: list[str]) -> list[dict]:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    ws = wb.worksheets[0]

    headers: list[str] = []
    rows = []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            headers = [str(c).strip().lower() if c is not None else "" for c in row]
            continue
        # Skip completely empty rows
        if all(c is None for c in row):
            continue
        normalized = {}
        for j, col in enumerate(headers):
            if col in expected_columns:
                cell_val = row[j] if j < len(row) else None
                normalized[col] = str(cell_val).strip() if cell_val is not None else ""
        # Fill missing expected columns
        for col in expected_columns:
            if col not in normalized:
                normalized[col] = ""
        rows.append(normalized)
    wb.close()
    return rows
