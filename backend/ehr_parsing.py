"""
EHR file parsing — handles two genuinely different input shapes:

1. Our own clean CSV templates (art_number, sample_date, ... — one header
   row, nothing else) — what /ehr/templates hands out.
2. Real MOHCC/OpenMRS report exports (Art Appointments List, HTS Register,
   etc.) — these arrive as XLSX-format files (regardless of .xls/.xlsx
   extension — `file` command confirms OOXML zip structure either way),
   with several metadata rows (facility name, report title, year/month,
   totals) BEFORE the actual column header row, and report-specific
   column names with numbered prefixes ("2) OI/ART Number", "5)Sex", etc.
   rather than our simple flat names.

Both are real inputs this system needs to accept — clinics running actual
DHIS2/OpenMRS-based systems export type (2), and internal tooling/manual
entry uses type (1).
"""
import csv
import io
import pandas as pd


def load_rows(filename: str, content: bytes) -> list[dict]:
    """
    Returns a list of plain dict rows with stripped string column names,
    regardless of whether the upload was a clean CSV or a messy MOHCC
    XLSX/XLS export. Blank/all-NaN rows are dropped.
    """
    lower = (filename or "").lower()
    if lower.endswith(".csv"):
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        return [dict(row) for row in reader]

    # XLSX/XLS — MOHCC systems export genuine OOXML zip files even when
    # the filename ends in .xls, so pandas/openpyxl reads either cleanly.
    df_raw = pd.read_excel(io.BytesIO(content), header=None, nrows=30)
    header_row = _find_header_row(df_raw)
    df = pd.read_excel(io.BytesIO(content), header=header_row)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all")
    # NaN -> None so downstream `.get()`/truthiness checks behave like CSV rows
    return df.where(pd.notna(df), None).to_dict(orient="records")


def _find_header_row(df_raw: pd.DataFrame) -> int:
    """
    MOHCC/OpenMRS exports put the real column header several rows down,
    after facility name / report title / year-month / totals metadata.
    That metadata is sparse (a handful of populated cells per row); the
    real header row has one populated cell per actual column, so it's
    reliably the row with the most non-null cells in the first ~30 rows.
    Verified against two real exports (Art Appointments List, HTS
    Register) — correctly finds row 9 and row 14 respectively, despite
    their very different metadata block shapes.
    """
    counts = df_raw.notna().sum(axis=1)
    return int(counts.idxmax())


def clean_str(v) -> str:
    """Normalize a cell value to a stripped string, treating None/NaN as ''."""
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s.lower() == "nan" else s
