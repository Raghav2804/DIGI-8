from flask import Blueprint, render_template, request, redirect, url_for, flash
from services.data_loader import load_jobs, load_upload
from services.analytics import summary, charts, salary_by, salary_outlier_count
from database.db import get_source, get_refreshed_at, get_source_columns
from config import DATA_DIR

pages = Blueprint("pages", __name__)

@pages.app_context_processor
def shared_context():
    df = load_jobs()
    columns = get_source_columns()
    if not columns and get_source() == "jobs.csv":
        import csv
        with (DATA_DIR / "jobs.csv").open(encoding="utf-8-sig", newline="") as source_file: columns = next(csv.reader(source_file), [])
    checks={"company":df.company,"description":df.description,"skills":df.skills,"experience":df.experience,"employment_type":df.employment_type,"remote_status":df.remote_status,"currency":df.currency,"salary_period":df.salary_period,"country":df.country}
    missing_fields=[name for name,series in checks.items() if not series.fillna("").astype(str).str.strip().ne("").any() or (name == "country" and series.astype(str).str.casefold().eq("unknown").all())]
    source = get_source()
    scope = "Upwork job-posting extract; not a complete representation of the global employment market." if source and (source.casefold() == "jobs.csv" or "upwork" in source.casefold()) else "Imported job-posting dataset; not a complete representation of the global employment market."
    return {"nav_summary": summary(df), "data_source": source, "dataset_scope": scope, "job_count": len(df), "data_refreshed_at": get_refreshed_at(), "source_columns": columns, "missing_fields": missing_fields}

@pages.route("/")
def dashboard():
    df=load_jobs()
    return render_template("dashboard.html", metrics=summary(df), chart_data=charts(df), dataset_columns=get_source_columns())

@pages.route("/analytics")
def analytics():
    df=load_jobs()
    return render_template("analytics.html", df=df, salary_groups=salary_by(df, "job_title", 25), outlier_count=salary_outlier_count(df))

@pages.route("/predictions")
def predictions(): return render_template("predictions.html")

@pages.route("/salaries")
def salaries():
    df=load_jobs()
    hourly=df.loc[df.salary_period.fillna("").astype(str).str.casefold().eq("hourly")]
    return render_template("salaries.html", df=df, hourly=hourly, salary_groups=salary_by(hourly, "country", 30))

@pages.route("/recommendations", methods=["GET", "POST"])
def recommendations():
    results=[]
    from models.recommendation import source_capabilities
    df=load_jobs()
    if request.method == "POST":
        from models.recommendation import recommend
        try: results=recommend(df, request.form.to_dict())
        except ValueError as exc: flash(str(exc), "error")
    return render_template("recommendations.html", results=results, capabilities=source_capabilities(df))

@pages.route("/trends")
def trends():
    df=load_jobs()
    return render_template("trends.html", dated_count=int(df.date_posted.notna().sum()), total_count=len(df))

@pages.route("/remote-work")
def remote_work(): return render_template("remote_work.html", chart_data=charts(load_jobs()))

@pages.route("/about")
def about(): return render_template("about.html")

@pages.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        f=request.files.get("dataset")
        if not f or not f.filename: flash("Choose a CSV or Excel dataset first.", "error")
        else:
            try:
                info=load_upload(f); flash(f"Imported {info['rows']:,} rows from {info['source']}; removed {info['duplicates_removed']} duplicate rows.", "success")
            except Exception as exc: flash(str(exc), "error")
        return redirect(url_for("pages.settings"))
    return render_template("settings.html", source=get_source())

@pages.post("/refresh")
def refresh():
    flash("Analytics refreshed from the current dataset.", "success")
    return redirect(request.referrer or url_for("pages.dashboard"))
