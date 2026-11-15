"""Chronological demand forecast; reports errors only when a holdout exists."""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

def forecast(df, horizon=6):
    dated = df.dropna(subset=["date_posted"]).copy()
    if dated.empty: return {"available": False, "reason": "Import records with posting dates to forecast demand."}
    monthly = dated.set_index("date_posted").resample("MS").size().astype(float)
    if len(monthly) < 3: return {"available": False, "reason": "At least 3 months of dated records are needed to draw an exploratory forecast."}
    values = monthly.values
    if len(values) < 8:
        # Very short histories cannot support a meaningful train/test evaluation.
        # Use a simple damped trend so a forecast is visible, while labelling it
        # exploratory and withholding fabricated accuracy metrics.
        x = np.arange(len(values), dtype=float)
        slope = float(np.polyfit(x, values, 1)[0]) if len(values) >= 2 else 0.0
        damping = 0.65
        future = []
        accumulated = 0.0
        for step in range(1, horizon + 1):
            accumulated += damping ** step
            future.append(max(0.0, float(values[-1]) + slope * accumulated))
        dates = pd.date_range(monthly.index[-1] + pd.offsets.MonthBegin(1), periods=horizon, freq="MS")
        return {
            "available": True,
            "historical": {"labels": [d.strftime("%b %Y") for d in monthly.index], "values": [int(v) for v in values]},
            "future": {"labels": [d.strftime("%b %Y") for d in dates], "values": [round(v, 1) for v in future]},
            "metrics": None,
            "confidence": "low",
            "historical_end": dated.date_posted.max().strftime("%Y-%m-%d"),
            "warning": "Exploratory trend only: fewer than 8 monthly observations, so no holdout accuracy metrics are reported. The forecast extends this dataset's short historical pattern; it is not a current labor-market outlook.",
            "model": "Damped linear trend (exploratory; short history)",
        }
    def features(i): return [i, values[i-1], values[i-2] if i >= 2 else values[0], values[i-3] if i >= 3 else values[0]]
    X = np.array([features(i) for i in range(3, len(values))]); y = values[3:]
    split = max(1, int(len(y) * .8)); model = RandomForestRegressor(n_estimators=150, random_state=42, min_samples_leaf=1)
    model.fit(X[:split], y[:split]); test_pred = model.predict(X[split:]) if split < len(y) else np.array([])
    metrics = None
    if len(test_pred): metrics = {"mae": round(float(mean_absolute_error(y[split:], test_pred)), 2), "rmse": round(float(np.sqrt(mean_squared_error(y[split:], test_pred))), 2), "r2": round(float(r2_score(y[split:], test_pred)), 3) if len(test_pred)>1 else None}
    all_model = RandomForestRegressor(n_estimators=150, random_state=42).fit(X, y)
    hist = list(values); future=[]
    for step in range(horizon):
        i=len(hist); row=[i, hist[-1], hist[-2] if len(hist)>1 else hist[-1], hist[-3] if len(hist)>2 else hist[-1]]
        value=max(0, float(all_model.predict([row])[0])); future.append(value); hist.append(value)
    dates = pd.date_range(monthly.index[-1] + pd.offsets.MonthBegin(1), periods=horizon, freq="MS")
    return {"available": True, "historical": {"labels": [d.strftime("%b %Y") for d in monthly.index], "values": [int(v) for v in values]}, "future": {"labels": [d.strftime("%b %Y") for d in dates], "values": [round(v, 1) for v in future]}, "metrics": metrics, "confidence": "low" if len(monthly) < 18 else "moderate", "historical_end": dated.date_posted.max().strftime("%Y-%m-%d"), "warning": "This forecast is based only on the imported historical postings and may not represent current market demand.", "model": "RandomForestRegressor (lag features; chronological 80/20 holdout)"}
