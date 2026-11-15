# CareerPulse

CareerPulse is a Flask application for exploring job listings, salary signals, remote-work patterns, and job recommendations. It uses the supplied Upwork dataset and keeps all reported figures grounded in that source. SQLite stores imported job records; CSV and Excel files can be imported from Settings.

## Dataset included

`dataset/jobs.csv` is the supplied `all_upwork_jobs_2024-02-07-2024-03-24.csv` dataset (244,828 rows, 8 source columns). It is loaded into SQLite the first time the app starts. The inspected file has no exact duplicate rows, 212 distinct non-empty country values, and posting dates from 2023-11-02 through 2024-03-24. One row is missing its title and country is blank for 5,077 rows.

The source contains title, link, published date, an hourly flag, hourly low/high bounds, project budget, and country. It does not provide company, skills, description, experience, employment type, or remote status. CareerPulse leaves those fields unspecified and derives clearly marked weak role and task hints from titles for matching. It does not treat fixed project budgets as salaries or invent currencies and exchange rates. Salary summaries keep pay periods and currency labels in separate groups. The global salary view includes only hourly records and visibly warns that this extract does not identify currency; no conversion is performed. When an hourly rate is derived from a low/high range, the source bounds are retained. Short-history demand forecasts are shown as exploratory trend estimates without fabricated accuracy metrics.

## Run locally

Python 3.10+ is recommended.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5000>. The app listens on `0.0.0.0:5000`, including for container use. Set `CAREERPULSE_SECRET_KEY` before deployment. `CAREERPULSE_DATABASE` and `CAREERPULSE_DATA_DIR` can override the SQLite file and bundled dataset directory.

## Docker deployment

Docker packages an application and its runtime dependencies into a repeatable image. Docker Compose runs that image with its network and persistent storage configuration. CareerPulse uses Docker so the same Python/Flask environment can run consistently on a laptop, in an academic demo, or on a Linux server.

### Architecture

- **`careerpulse` service:** one Flask application container. Gunicorn serves `app:app` on `0.0.0.0:5000`; the image runs as an unprivileged user. The dashboard, API, recommendation logic, forecasting code, templates, static assets, and bundled CSV live in this service.
- **SQLite:** remains the application's database. There is no separate database container. The `careerpulse-data` named volume stores `/data/careerpulse.sqlite3` across restarts and image rebuilds, separate from the Python `database` package.
- **Network and port:** Compose creates a private bridge network. The web service is published only on `127.0.0.1:5000` on the host.
- **Health and logs:** Compose checks `/api/health`, restarts the service unless stopped, and rotates container logs.

The local SQLite file is excluded from the image. On a new volume, CareerPulse creates the database and seeds it from `dataset/jobs.csv`. Uploaded data is then persisted in the volume. The dataset is included in the image; change it before building to seed a different initial dataset. Existing local SQLite data is not automatically copied into a new Docker volume.

### Prerequisites

- Docker Desktop (Windows/macOS) or Docker Engine with the Docker Compose plugin (Linux).
- At least 2 GB of free memory and disk space for the Python/scikit-learn image and dataset.

### Configure and build

Copy `.env.example` to `.env` and replace the placeholder with a private random Flask secret. Keep `.env` local; it is ignored by Git and Docker build context.

PowerShell:

```powershell
Copy-Item .env.example .env
```

Then edit `.env` and build the image:

```sh
docker compose build
```

### Start and verify

```sh
docker compose up -d
docker compose ps
docker compose logs -f
```

Open <http://localhost:5000>. The first startup can take a few minutes while the bundled dataset is loaded into SQLite; wait for the health status to become `healthy`. Stop following logs with `Ctrl+C` (the container keeps running).

### Stop, restart, and persistence

```sh
docker compose stop
docker compose start
docker compose restart
docker compose down
```

`docker compose down` stops and removes the container and network but preserves `careerpulse-data`. `docker compose down -v` also removes the SQLite volume and permanently deletes the imported database; use it only when you intend to reset container data. Rebuilding the image does not remove the volume.

### Logs and debugging

```sh
docker compose logs --tail=100 careerpulse
docker compose ps
docker compose exec careerpulse python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:5000/api/health').read().decode())"
```

If port 5000 is already in use, change the host side of the Compose mapping, for example `127.0.0.1:5001:5000`, then open <http://localhost:5001>. Check `.env` if Compose reports a missing `CAREERPULSE_SECRET_KEY`. The first start's database import is intentionally included in the health-check start period.

### Deployment notes

For a private server, use a TLS reverse proxy in front of Gunicorn, set a unique secret through the deployment environment, restrict inbound access, and back up the `careerpulse-data` volume. The supplied Compose file binds to localhost by default; change the host binding only when remote access is intended. This starter setup does not add authentication or a managed database.

### Screenshots checklist

- `docker compose ps` showing the service healthy.
- CareerPulse overview at `http://localhost:5000`.
- Settings page showing the active dataset and record count.
- Demand forecast and job recommendation pages running in the container.
- Container logs showing a clean Gunicorn startup and `/api/health` check.

## Pages and API

- Overview: actual dataset statistics and interactive Plotly charts, functional country/category/text/date filters, dataset refresh date, and a dataset transparency disclosure. Values are descriptive calculations, not live analytics; inferred role families and title hints are labelled.
- Market Analytics: salary groups by title, pay period, and currency with record counts and 1.5?IQR outlier counts within comparable groups.
- Demand Prediction: monthly forecast with chronological holdout metrics when enough history exists; short histories show an exploratory damped trend with clear caveats and no accuracy claims.
- Global Salary Insights: hourly records only, record counts in chart tooltips, source country labels, and a persistent currency/cross-country comparability disclaimer.
- Job Recommendations: dataset-aware TF-IDF cosine similarity, with score weights renormalized to fields that exist. Unsupported preferences are reported, hourly-rate floors exclude fixed project budgets, and recommendations only link to imported listings. Browser-local favorites can be saved and filtered. Because this source has titles but no descriptions or skills, broad role families and task hints are inferred from titles and used as weak matching signals; they are not verified requirements or ground-truth labels.
- Monthly Trends and Remote Work Analysis: source date and workplace fields with clear empty/unknown states.
- About Project and Settings: project methodology, dataset import, and runtime information.

JSON endpoints are under `/api`: `/health`, `/dashboard` (supports country, category, search, start, and end filters), `/dataset` (source columns, record count, missing fields, and refresh timestamp), `/filters`, `/analytics/jobs`, `/analytics/salary`, `/predictions/demand`, `/salaries/countries`, `/recommendations`, `/trends/monthly`, and `/analytics/remote-work`.

## Importing a different dataset

Open Settings and upload a CSV or Excel file up to 64 MB. Import replaces the active dataset. The preprocessor recognizes common variants of job title, posting date, salary, hourly bounds, budget, country, skills, category, experience, work arrangement, and application URL. Salary records keep their supplied unit and period; data with incompatible units should not be interpreted as a direct comparison.

## Architecture

```text
app.py               Flask application factory and error handlers
routes/              Page and JSON API blueprints
services/             Data import, preprocessing, and analytics
models/               Recommendation and demand prediction logic
database/db.py         SQLite repository
templates/             Jinja pages
static/css, static/js  Responsive dark UI and Plotly charts
dataset/jobs.csv       Supplied source dataset
```

## Notes

- No authentication or user accounts are implemented.
- No scheduled data collection is implemented. Results update after a dataset import or refresh.
- Plots use Plotly.js from its CDN; an internet connection is needed for chart rendering in the browser.
- Do not interpret hourly rates as annual compensation. The dataset does not include a currency field.

## Data quality and interpretation

- Dashboard statistics are calculated from the current imported SQLite dataset. They do not update from a live job-market feed. The refresh timestamp is stored when a dataset is loaded or replaced; if an older database has no recorded timestamp, the UI says it is unavailable rather than inventing one.
- The bundled source fields are title, link, published date, hourly flag, hourly low/high values, project budget, and country. Company names, descriptions, skills, experience, employment type, remote status, salary currency, and dependable salary period labels are not supplied.
- Pay summaries are separated by period and currency. Outlier counts use the 1.5?IQR rule inside those groups; outliers are flags for review, not assumed errors. Hourly range bounds remain available alongside the numeric midpoint used for grouping. Project budgets are not salary.
- Recommendations use the available title text and explicitly labelled title-inferred hints where structured skill/description data is missing. Match scores are weighted, normalized relevance scores, not probabilities or skill verification. Application links appear only when the source contains a URL.
- The supplied date history is short. Forecasts use the method named in the page and warn when confidence is low; accuracy metrics are omitted unless a chronological holdout evaluation exists. This posting extract is not representative of the full global employment market.
