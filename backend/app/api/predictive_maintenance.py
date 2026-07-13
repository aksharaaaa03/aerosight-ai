from fastapi import APIRouter
import pandas as pd
from pathlib import Path

router = APIRouter(prefix="/api/epic5", tags=["Predictive Maintenance"])
PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"

@router.get("/fleet-forecast")
def get_fleet_forecast():
    df = pd.read_parquet(PROCESSED_DIR / "maintenance_forecast.parquet")
    return {"forecast": df.to_dict(orient="records")}

@router.get("/turbine-forecast-history/{turbine_id}")
def get_turbine_forecast_history(turbine_id: str, start_date: str = None, end_date: str = None, days: int = 60):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from app.pipelines.predictive_maintenance import (
        load_health_data, load_thresholds, compute_degradation_risk,
        compute_fleet_baseline_critical_rate, classify_risk_level,
    )

    health_df = load_health_data()
    thresholds = load_thresholds()
    baseline = compute_fleet_baseline_critical_rate(health_df, thresholds)

    turbine_data = health_df[health_df["Turbine_ID"] == turbine_id]
    if turbine_data.empty:
        return {"error": f"No data for turbine {turbine_id}"}

    if start_date and end_date:
        start = pd.to_datetime(start_date, utc=True)
        end = pd.to_datetime(end_date, utc=True)
    else:
        end = turbine_data["Timestamp"].max()
        start = end - pd.Timedelta(days=days)

    history = []
    check_date = start
    while check_date <= end:
        risk = compute_degradation_risk(health_df, turbine_id, check_date, lookback_days=14, thresholds=thresholds)
        if risk["status"] == "ok":
            history.append({
                "date": str(check_date.date()),
                "pct_time_critical": risk["pct_time_critical"],
                "recent_avg_health": risk["recent_avg_health"],
                "risk_level": classify_risk_level(risk["pct_time_critical"], baseline),
            })
        check_date += pd.Timedelta(days=3)

    return {"turbine_id": turbine_id, "start_date": str(start.date()), "end_date": str(end.date()), "history": history}

@router.get("/prioritized-maintenance")
def get_prioritized_maintenance():
    df = pd.read_parquet(PROCESSED_DIR / "maintenance_forecast.parquet")
    df = df.sort_values("priority_rank")
    return {"prioritized_list": df.to_dict(orient="records")}