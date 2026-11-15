from flask import Blueprint, jsonify, request
import pandas as pd
from services.data_loader import load_jobs
from services.analytics import summary, charts, salary_by, effective_categories, salary_outlier_count
from database.db import get_source, get_source_columns, get_refreshed_at

api=Blueprint("api", __name__, url_prefix="/api")

@api.get("/health")
def health(): return jsonify(status="ok", service="CareerPulse")

@api.get("/dashboard")
def dashboard():
    df=load_jobs()
    country=request.args.get("country","").strip()
    category=request.args.get("category","").strip()
    search=request.args.get("search","").strip().lower()
    start=request.args.get("start","").strip()
    end=request.args.get("end","").strip()
    if country: df=df[df.country.astype(str).str.casefold().eq(country.casefold())]
    if category: df=df.loc[effective_categories(df).str.casefold().eq(category.casefold())]
    if search: df=df[df.job_title.astype(str).str.lower().str.contains(search, regex=False) | df.company.fillna("").astype(str).str.lower().str.contains(search, regex=False)]
    try:
        start_date = pd.Timestamp(start).normalize() if start else None
        end_date = pd.Timestamp(end).normalize() if end else None
        if start_date is not None and end_date is not None and start_date > end_date:
            return jsonify(error="The start date must be on or before the end date."), 400
        if start_date is not None: df=df[df.date_posted.ge(start_date)]
        if end_date is not None: df=df[df.date_posted.lt(end_date+pd.Timedelta(days=1))]
    except (ValueError, TypeError): return jsonify(error="Dates must use YYYY-MM-DD format."),400
    return jsonify(metrics=summary(df), charts=charts(df), source=get_source(), refreshed_at=get_refreshed_at(), rows=len(df))

@api.get("/filters")
def filters():
    df=load_jobs()
    countries=sorted(df.loc[df.country.ne("Unknown"),"country"].dropna().astype(str).unique().tolist())
    categories=sorted(effective_categories(df).dropna().astype(str).unique().tolist())
    return jsonify(countries=countries,categories=categories)

@api.get("/analytics/jobs")
def jobs():
    df=load_jobs(); return jsonify(total=len(df), by_role=df.job_title.value_counts().head(30).to_dict(), by_category=effective_categories(df).value_counts().to_dict())

@api.get("/analytics/salary")
def salaries():
    df=load_jobs(); values=df.dropna(subset=["salary"]).copy()
    return jsonify(records=salary_by(df, "job_title"), experience=salary_by(df, "experience"), countries=salary_by(df, "country"), available=int(df.salary.notna().sum()), outlier_count=salary_outlier_count(df), outlier_method="1.5?IQR within comparable pay-period and currency groups", currencies=sorted(values.currency.dropna().astype(str).unique().tolist()) if "currency" in values else [])

@api.get("/salaries/countries")
def countries():
    df=load_jobs()
    hourly=df.loc[df.salary_period.fillna("").astype(str).str.casefold().eq("hourly")].copy()
    hourly["currency"] = hourly.currency.fillna("Unavailable").replace("", "Unavailable") if "currency" in hourly else "Unavailable"
    currencies=hourly.currency.value_counts()
    selected_currency=currencies.index[0] if not currencies.empty else None
    if selected_currency is not None:
        hourly=hourly.loc[hourly.currency.eq(selected_currency)]
    hourly=hourly.loc[hourly.country.fillna("Unknown").astype(str).str.casefold().ne("unknown")]
    records=salary_by(hourly, "country")
    return jsonify(records=records, available=int(hourly.salary.notna().sum()), currency=selected_currency or "Unavailable", excluded_mixed_currency=bool(len(currencies)>1))

@api.get("/dataset")
def dataset_info():
    df=load_jobs(); columns=get_source_columns()
    if not columns and get_source()=="jobs.csv":
        import csv
        from config import DATA_DIR
        with (DATA_DIR/"jobs.csv").open(encoding="utf-8-sig", newline="") as f: columns=next(csv.reader(f), [])
    checks={"company":df.company,"description":df.description,"skills":df.skills,"experience":df.experience,"employment_type":df.employment_type,"remote_status":df.remote_status,"currency":df.currency,"salary_period":df.salary_period,"country":df.country}
    missing=[name for name,series in checks.items() if not series.fillna("").astype(str).str.strip().ne("").any() or (name == "country" and series.astype(str).str.casefold().eq("unknown").all())]
    source=get_source()
    scope="Upwork job-posting extract; not a complete representation of the global employment market." if source and (source.casefold()=="jobs.csv" or "upwork" in source.casefold()) else "Imported job-posting dataset; not a complete representation of the global employment market."
    return jsonify(name=source or "Data unavailable", records=len(df), columns=columns, missing_fields=missing, refreshed_at=get_refreshed_at(), scope=scope)

@api.get("/trends/monthly")
def monthly(): return jsonify(charts(load_jobs())["monthly"])

@api.get("/analytics/remote-work")
def remote():
    df=load_jobs(); counts=df.remote_status.value_counts().to_dict()
    remote_df=df[df.remote_status.fillna("").str.contains("remote",case=False)]
    dated=remote_df.dropna(subset=["date_posted"])
    monthly=dated.set_index("date_posted").resample("MS").size() if not dated.empty else pd.Series(dtype=int)
    return jsonify(distribution=counts, by_country=remote_df.country.value_counts().head(15).to_dict(), monthly={"labels":[d.strftime("%b %Y") for d in monthly.index],"values":[int(x) for x in monthly.values]})

@api.get("/predictions/demand")
def demand():
    from models.demand_prediction import forecast
    try: return jsonify(forecast(load_jobs(), max(1,min(24,int(request.args.get("months",6))))))
    except ValueError: return jsonify(error="months must be an integer"), 400

@api.post("/recommendations")
def recommendations():
    from models.recommendation import recommend, source_capabilities
    if not request.is_json: return jsonify(error="Send a JSON object."), 400
    profile=request.get_json(silent=True)
    if not isinstance(profile, dict): return jsonify(error="The recommendation profile must be a JSON object."), 400
    for key in ("skills", "job_title", "experience", "location", "employment_type", "work_mode"):
        if isinstance(profile.get(key), str) and len(profile[key]) > 300:
            return jsonify(error=f"{key} must be 300 characters or fewer."), 400
    try:
        df=load_jobs()
        return jsonify(results=recommend(df, profile), capabilities=source_capabilities(df))
    except ValueError as exc: return jsonify(error=str(exc)), 400
