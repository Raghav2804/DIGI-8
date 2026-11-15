"""Dataset-grounded analytics used by pages and API routes."""
import pandas as pd
import numpy as np
import re
from services.inference import infer_title_metadata

def effective_categories(df):
    source = df["category"].fillna("").astype(str).str.strip()
    inferred = df["inferred_category"].fillna("Other").astype(str).str.strip() if "inferred_category" in df else df["job_title"].map(lambda title: infer_title_metadata(title)[0])
    return source.where(source.ne("") & source.ne("Uncategorized"), inferred)

def effective_skill_tags(df):
    rows = []
    for _, row in df.iterrows():
        raw = row.get("skills")
        if isinstance(raw, (list, tuple, set)):
            tags = list(raw)
        elif pd.notna(raw) and str(raw).strip():
            tags = re.split(r"[,;|]", str(raw))
        else:
            inferred = row.get("inferred_skills", [])
            tags = inferred if isinstance(inferred, (list, tuple, set)) else []
        rows.extend(str(tag).strip() for tag in tags if str(tag).strip())
    return pd.Series(rows, dtype="object")

def summary(df):
    if df.empty:
        return {"total_jobs": 0, "average_salary": None, "salary_count": 0, "salary_period": None, "salary_currency": "Unavailable", "top_role": "Data unavailable", "remote_percent": None, "remote_count": 0, "categories": 0, "countries": 0}
    valid = df.loc[df.salary.notna()].copy()
    normalized_periods = valid.salary_period.fillna("Unavailable").astype(str).str.strip().replace("", "Unavailable").replace("unspecified", "Unavailable")
    normalized_currencies = valid.currency.fillna("Unavailable").astype(str).str.strip().replace("", "Unavailable") if "currency" in valid else pd.Series("Unavailable", index=valid.index)
    pairs = pd.DataFrame({"period": normalized_periods, "currency": normalized_currencies}).value_counts()
    selected_period, selected_currency = sorted(pairs[pairs.eq(pairs.max())].index.tolist())[0] if not pairs.empty else (None, "Unavailable")
    comparable_mask = normalized_periods.eq(selected_period) & normalized_currencies.eq(selected_currency)
    comparable = valid.loc[comparable_mask, "salary"] if selected_period else pd.Series(dtype=float)
    currency = selected_currency
    labels = df["remote_status"].fillna("").astype(str)
    remote = labels.str.contains("remote", case=False)
    labeled = labels.str.lower().ne("unknown") & labels.ne("")
    return {"total_jobs": int(len(df)), "average_salary": round(float(comparable.mean()), 2) if len(comparable) else None,
            "salary_period": selected_period, "salary_count": int(comparable.count()), "salary_currency": currency,
            "top_role": str(df["job_title"].mode().iloc[0]) if not df["job_title"].mode().empty else "—",
            "remote_percent": round(float(remote[labeled].mean() * 100), 1) if labeled.any() else None, "remote_count": int(labeled.sum()),
            "categories": int(effective_categories(df).nunique()), "countries": int(df.loc[df.country.ne("Unknown"), "country"].nunique())}

def charts(df):
    def counts(series, n=10): return {"labels": [str(x) for x in series.value_counts().head(n).index], "values": [int(x) for x in series.value_counts().head(n).values]}
    dated = df.dropna(subset=["date_posted"])
    monthly = dated.set_index("date_posted").resample("MS").size() if not dated.empty else pd.Series(dtype=int)
    hourly = df.loc[df.salary_period.fillna("").astype(str).str.casefold().eq("hourly")].copy()
    hourly_currency = hourly.currency.fillna("Unavailable").astype(str).str.strip().replace("", "Unavailable") if "currency" in hourly else pd.Series("Unavailable", index=hourly.index)
    currency_counts = hourly_currency.value_counts()
    salary_currency = sorted(currency_counts[currency_counts.eq(currency_counts.max())].index.tolist())[0] if not currency_counts.empty else "Unavailable"
    salaries = hourly.loc[hourly_currency.eq(salary_currency), "salary"].dropna().astype(float) if not hourly.empty else pd.Series(dtype=float)
    hist = np.histogram(salaries, bins=min(24, max(1, int(np.sqrt(len(salaries)))))) if len(salaries) else ([], [])
    hist_labels = [round(float((hist[1][i] + hist[1][i+1]) / 2), 2) for i in range(len(hist[0]))]
    category_values = effective_categories(df)
    skill_values = effective_skill_tags(df)
    raw_categories = df["category"].fillna("").astype(str).str.strip().ne("").any() and not df["category"].fillna("").astype(str).str.strip().eq("Uncategorized").all() if "category" in df else False
    raw_skills = df["skills"].fillna("").astype(str).str.strip().ne("").any() if "skills" in df else False
    return {"roles": counts(df.job_title), "categories": counts(category_values, 12), "categories_inferred": not raw_categories, "remote": counts(df.remote_status, 6),
            "skills": counts(skill_values), "skills_inferred": not raw_skills,
            "monthly": {"labels": [x.strftime("%b %Y") for x in monthly.index], "values": [int(x) for x in monthly.values]},
            "salary_histogram": {"labels": hist_labels, "values": [int(x) for x in hist[0]], "currency": salary_currency, "records": int(len(salaries)), "multiple_currencies": bool(len(currency_counts) > 1)}}

def salary_by(df, field, limit=20):
    valid = df.dropna(subset=["salary"]).copy()
    if valid.empty: return []
    valid["salary_period"] = valid.salary_period.fillna("Unavailable").replace("", "Unavailable")
    if "currency" not in valid: valid["currency"] = "Unavailable"
    valid["currency"] = valid.currency.fillna("Unavailable").replace("", "Unavailable")
    return valid.groupby([field, "salary_period", "currency"], dropna=True).salary.agg(["mean", "median", "count"]).sort_values("mean", ascending=False).head(limit).reset_index().to_dict(orient="records")

def salary_outlier_count(df):
    valid = df.dropna(subset=["salary"]).copy()
    if valid.empty: return 0
    valid["salary_period"] = valid.salary_period.fillna("Unavailable").replace("", "Unavailable")
    if "currency" not in valid: valid["currency"] = "Unavailable"
    valid["currency"] = valid.currency.fillna("Unavailable").replace("", "Unavailable")
    count = 0
    for _, group in valid.groupby(["salary_period", "currency"]):
        if len(group) < 4: continue
        q1, q3 = group.salary.quantile([.25, .75]); spread = q3 - q1
        if spread:
            count += int(((group.salary < q1 - 1.5 * spread) | (group.salary > q3 + 1.5 * spread)).sum())
    return count
