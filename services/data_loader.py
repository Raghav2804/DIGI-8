"""CSV/Excel import and database-backed dataset access."""
from io import BytesIO
from functools import lru_cache
from pathlib import Path
import csv
import pandas as pd
from database import db
from config import DATA_DIR
from services.preprocessing import normalize

def load_upload(file):
    data = file.read()
    name = file.filename or "uploaded file"
    if not data:
        raise ValueError("The selected file is empty. Choose a CSV or Excel file with job records.")
    if name.lower().endswith(".csv"):
        sample = data[:65536].decode("utf-8-sig", errors="replace")
        try:
            delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
        except csv.Error:
            delimiter = ","
        try:
            frame = pd.read_csv(BytesIO(data), encoding="utf-8-sig", sep=delimiter)
        except UnicodeDecodeError:
            try:
                frame = pd.read_csv(BytesIO(data), encoding="cp1252", sep=delimiter)
            except Exception as exc:
                raise ValueError("Could not read this CSV. Save it as UTF-8 CSV and try again.") from exc
        except pd.errors.ParserError as exc:
            raise ValueError("Could not parse this CSV. Check that each row has the same columns, then try again.") from exc
    elif name.lower().endswith((".xlsx", ".xls")):
        try:
            frame = pd.read_excel(BytesIO(data))
        except ImportError as exc:
            raise ValueError("Excel support is missing. Install the project's requirements and retry.") from exc
        except Exception as exc:
            raise ValueError("Could not read this Excel file. Check that it is a valid .xlsx or .xls workbook.") from exc
    else:
        raise ValueError("Upload a CSV or Excel file (.csv, .xlsx, .xls).")
    if frame.empty:
        raise ValueError("The uploaded file has no job records.")
    clean = normalize(frame)
    if clean.empty or clean.job_title.eq("Unspecified role").all():
        raise ValueError("No job-title column was found. Include a column named title, job_title, job role, role, or position.")
    db.replace_jobs(clean.where(pd.notna(clean), None).to_dict(orient="records"), name, list(frame.columns))
    load_jobs.cache_clear()
    return {"source": name, "rows": len(clean), "duplicates_removed": len(frame) - len(clean), "columns": list(frame.columns)}

def load_bundled_dataset():
    path = DATA_DIR / "jobs.csv"
    if not path.exists() or db.job_count():
        return False
    frame = pd.read_csv(path)
    clean = normalize(frame)
    db.replace_jobs(clean.where(pd.notna(clean), None).to_dict(orient="records"), path.name, list(frame.columns))
    return True

@lru_cache(maxsize=1)
def load_jobs():
    return normalize(pd.DataFrame(db.get_jobs()))
