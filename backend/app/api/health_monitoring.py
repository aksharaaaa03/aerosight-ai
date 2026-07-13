from fastapi import APIRouter
import pandas as pd
from pathlib import Path
import json

router = APIRouter(prefix="/api/epic2", tags=["Health Monitoring"])

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
MODELS_DIR = Path(__file__).resolve().parents[2] / "app" / "ml" / "saved"

def load_health_data() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED_DIR / "health_scored.parquet")

def load_thresholds():
    with open(MODELS_DIR / "health_thresholds.json") as f:
        return json.load(f)

@router.get("/fleet-summary")
def get_fleet_summary():
    df = load_health_data()
    df = df.dropna(subset=["health_score"])  # exclude non-operational rows

    # Get each turbine's most recent operational reading
    latest = df.sort_values("Timestamp").groupby("Turbine_ID").tail(1)

    status_counts = latest["health_status"].value_counts().to_dict()

    return {
        "healthy_count": status_counts.get("Healthy", 0),
        "warning_count": status_counts.get("Warning", 0),
        "critical_count": status_counts.get("Critical", 0),
        "turbines": latest[["Turbine_ID", "health_score", "health_status"]].to_dict(orient="records"),
    }

@router.get("/trend/{turbine_id}")
def get_health_trend(turbine_id: str, start_date: str = None, end_date: str = None, days: int = 30):
    df = load_health_data()
    df = df.dropna(subset=["health_score"])
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])

    turbine_data = df[df["Turbine_ID"] == turbine_id].sort_values("Timestamp")
    if turbine_data.empty:
        return {"error": f"No data found for turbine {turbine_id}"}

    if start_date and end_date:
        start = pd.to_datetime(start_date, utc=True)
        end = pd.to_datetime(end_date, utc=True)
    else:
        end = turbine_data["Timestamp"].max()
        start = end - pd.Timedelta(days=days)

    recent = turbine_data[(turbine_data["Timestamp"] >= start) & (turbine_data["Timestamp"] <= end)]
    daily = recent.set_index("Timestamp").resample("D")["health_score"].mean().reset_index()

    thresholds = load_thresholds()
    def classify(score):
        if score >= thresholds["healthy_threshold"]:
            return "Healthy"
        elif score >= thresholds["critical_threshold"]:
            return "Warning"
        else:
            return "Critical"

    return {
        "turbine_id": turbine_id,
        "start_date": str(start.date()),
        "end_date": str(end.date()),
        "trend": [
            {
                "date": row["Timestamp"].strftime("%Y-%m-%d"),
                "health_score": round(row["health_score"], 1),
                "health_status": classify(row["health_score"]),
            }
            for _, row in daily.iterrows()
            if pd.notna(row["health_score"])
        ],
    }