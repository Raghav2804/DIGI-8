"""Normalize common job-data schemas into a consistent dataframe."""
import re
import json
import pandas as pd
from services.inference import infer_title_metadata

ALIASES = {
    "job_title": ["job_title", "title", "job role", "role", "position"],
    "company": ["company", "company_name", "employer"],
    "location": ["location", "city", "job_location"],
    "country": ["country", "country_name"],
    "salary": ["salary", "salary_amount", "annual_salary", "average_salary"],
    "salary_min": ["salary_min", "min_salary", "salary_from"],
    "salary_max": ["salary_max", "max_salary", "salary_to"],
    "hourly_low": ["hourly_low", "hourly_min", "hourly_rate_min"],
    "hourly_high": ["hourly_high", "hourly_max", "hourly_rate_max"],
    "budget_amount": ["budget_amount", "budget", "project_budget"],
    "salary_period": ["salary_period", "pay_period", "salary_unit"],
    "currency": ["currency", "salary_currency"],
    "experience": ["experience", "experience_level", "seniority"],
    "category": ["category", "job_category", "industry", "job_family"],
    "skills": ["skills", "required_skills", "skill_set"],
    "inferred_category": ["inferred_category", "predicted_category"],
    "inferred_skills": ["inferred_skills", "title_inferred_skills"],
    "employment_type": ["employment_type", "type", "job_type"],
    "remote_status": ["remote_status", "workplace_type", "remote", "work_mode"],
    "date_posted": ["date_posted", "posted_date", "published_date", "date", "created_at", "posting_date"],
    "description": ["description", "job_description"],
    "apply_url": ["apply_url", "url", "link", "job_url", "application_url"],
    "is_hourly": ["is_hourly", "hourly"],
}

def normalize(frame):
    if frame is None:
        return pd.DataFrame()
    df = frame.copy()
    df.columns = [re.sub(r"\s+", "_", str(c).strip().lower()) for c in df.columns]
    rename = {}
    for target, aliases in ALIASES.items():
        for alias in aliases:
            key = alias.replace(" ", "_")
            if key in df.columns:
                rename[key] = target
                break
    df = df.rename(columns=rename)
    # Keep the source's salary representation alongside any numeric value used
    # for aggregation (for example, currency-formatted strings).
    if "salary_original" not in df:
        df["salary_original"] = df["salary"].copy() if "salary" in df else None
    has_salary = "salary" in df.columns
    for col in ALIASES:
        if col not in df:
            df[col] = None
    if not has_salary and (df["salary_min"].notna().any() or df["salary_max"].notna().any()):
        lo, hi = pd.to_numeric(df["salary_min"], errors="coerce"), pd.to_numeric(df["salary_max"], errors="coerce")
        df["salary"] = (lo.fillna(hi) + hi.fillna(lo)) / 2
    df["salary"] = pd.to_numeric(df["salary"].astype(str).str.replace(r"[^0-9.]", "", regex=True), errors="coerce")
    for col in ("hourly_low", "hourly_high", "budget_amount"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    hourly_flag = df["is_hourly"].astype(str).str.lower().isin(["true", "1", "yes", "hourly"])
    if df["is_hourly"].notna().any():
        low = df["hourly_low"].fillna(df["hourly_high"])
        high = df["hourly_high"].fillna(df["hourly_low"])
        df["salary"] = ((low + high) / 2).where(hourly_flag)
        df["salary_period"] = "hourly"
        df.loc[~hourly_flag, "salary_period"] = None
    elif df["salary_period"].isna().all():
        df["salary_period"] = "unspecified"
    published = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    if "published_date" in df:
        published = pd.to_datetime(df["published_date"], errors="coerce", utc=True).dt.tz_localize(None)
    df["date_posted"] = df["date_posted"].where(df["date_posted"].notna(), published)
    df["date_posted"] = pd.to_datetime(df["date_posted"], errors="coerce", utc=True).dt.tz_localize(None)
    for c in df.select_dtypes(include="object"):
        df[c] = df[c].map(lambda x: x.strip() if isinstance(x, str) else x)
    # Imported database rows may already contain list-valued tag columns.
    # pandas duplicate detection cannot hash lists, so create a shallow helper
    # with canonical JSON keys while retaining the original values in df.
    duplicate_keys = df.copy(deep=False)
    for column in df.select_dtypes(include="object").columns:
        if df[column].map(lambda value: isinstance(value, (list, tuple, set, dict))).any():
            duplicate_keys[column] = df[column].map(
                lambda value: json.dumps(sorted(value) if isinstance(value, set) else value, sort_keys=True, default=str)
                if isinstance(value, (list, tuple, set, dict)) else value
            )
    df = df.loc[~duplicate_keys.duplicated()].reset_index(drop=True)
    df["job_title"] = df["job_title"].fillna("Unspecified role")
    df["country"] = df["country"].fillna("Unknown")
    df["remote_status"] = df["remote_status"].fillna("Unknown")
    df["category"] = df["category"].fillna("Uncategorized")
    # Keep weak, title-derived hints separate from source-provided labels.
    inferred = df["job_title"].map(infer_title_metadata)
    missing_category = df["inferred_category"].isna() | df["inferred_category"].astype(str).str.strip().eq("")
    df.loc[missing_category, "inferred_category"] = inferred.loc[missing_category].map(lambda item: item[0])
    def infer_skills(row):
        value = row["inferred_skills"]
        if isinstance(value, (list, tuple, set)):
            return list(value)
        if isinstance(value, str) and value.strip():
            return [part.strip() for part in re.split(r"[,;|]", value) if part.strip()]
        return infer_title_metadata(row["job_title"])[1]
    df["inferred_skills"] = df.apply(infer_skills, axis=1)
    return df
