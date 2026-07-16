import pandas as pd
from pathlib import Path
import json
from app.pipelines.fault_analysis import SENSOR_TO_CATEGORY
from app.pipelines.health_model import HEALTH_FEATURES
from functools import lru_cache

PROCESSED_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "processed"
MODELS_DIR = Path(__file__).resolve().parent.parent / "ml" / "saved"

# Global "now" anchor - the dataset's true latest timestamp, used consistently
# across all Epic 6 aggregations so every alert type agrees on what "recent" means
GLOBAL_NOW = pd.Timestamp("2017-12-31 23:50:00", tz="UTC")
ACTIVE_WINDOW_DAYS = 14

@lru_cache(maxsize=1)
def load_health_data() -> pd.DataFrame:
    df = pd.read_parquet(PROCESSED_DIR / "health_scored.parquet")
    df = df.rename(columns={"Turbine_ID": "turbine_id", "Timestamp": "timestamp"})
    return df
@lru_cache(maxsize=1)
def load_thresholds() -> dict:
    with open(MODELS_DIR / "health_thresholds.json") as f:
        return json.load(f)


def get_fleet_overview() -> dict:
    df = load_health_data()
    thresholds = load_thresholds()

    recent_cutoff = GLOBAL_NOW - pd.Timedelta(days=3)
    recent = df[df["timestamp"] >= recent_cutoff]

    per_turbine_health = recent.groupby("turbine_id")["health_score"].mean().round(1)

    def status_from_score(score):
        if score >= thresholds["healthy_threshold"]:
            return "Healthy"
        elif score < thresholds["critical_threshold"]:
            return "Critical"
        else:
            return "Warning"

    per_turbine_status = per_turbine_health.apply(status_from_score)
    status_counts = per_turbine_status.value_counts().to_dict()

    total_turbines = per_turbine_health.shape[0]
    avg_fleet_health = round(per_turbine_health.mean(), 1)

    return {
        "as_of": str(GLOBAL_NOW),
        "total_turbines": int(total_turbines),
        "avg_fleet_health": float(avg_fleet_health),
        "status_breakdown": status_counts,
        "per_turbine_health": per_turbine_health.to_dict(),
        "per_turbine_status": per_turbine_status.to_dict(),
    }

def load_fault_events() -> pd.DataFrame:
    df = pd.read_parquet(PROCESSED_DIR / "fault_events.parquet")
    df["start_time"] = pd.to_datetime(df["start_time"])
    df["end_time"] = pd.to_datetime(df["end_time"])
    return df

@lru_cache(maxsize=1)
def load_performance_alerts() -> pd.DataFrame:
    df = pd.read_parquet(PROCESSED_DIR / "performance_alerts.parquet")
    df["start_time"] = pd.to_datetime(df["start_time"])
    df["end_time"] = pd.to_datetime(df["end_time"])
    return df

@lru_cache(maxsize=1)
def load_maintenance_forecast() -> pd.DataFrame:
    return pd.read_parquet(PROCESSED_DIR / "maintenance_forecast.parquet")


def get_prediction_summary() -> list[dict]:
    """
    Surfaces Epic 5's prediction results directly, satisfying the spec's
    'prediction results' requirement as its own dashboard section - distinct
    from active_alerts (which only shows HIGH_RISK_FORECAST when risk_level
    is High). This shows every turbine's current forecast regardless of
    urgency, so predictions are visible even when the whole fleet is Low risk
    (as it currently is) rather than only appearing once something's already
    urgent enough to be an alert.

    No new logic here - reuses Epic 5's maintenance_forecast.parquet as-is,
    the single source of truth for prediction results already established
    and validated in Epic 5.
    """
    df = load_maintenance_forecast()
    df = df.sort_values("priority_rank")
    return df.to_dict(orient="records")

def build_active_alerts() -> list[dict]:
    """
    Aggregates 4 distinct alert types into one list. Each type keeps its own
    honest meaning rather than being collapsed into a single fake-unified severity.
    'Active' = within ACTIVE_WINDOW_DAYS of GLOBAL_NOW (the dataset's latest
    timestamp, treated as "now" since this is historical, not live, data).
    Window size (14 days) chosen via direct evidence: gave 5 fault events + 2
    performance alerts near the data's end, and matches Epic 5's own 14-day
    trend window, keeping "recent" consistent across epics.
    """
    alerts = []
    window_start = GLOBAL_NOW - pd.Timedelta(days=ACTIVE_WINDOW_DAYS)
    thresholds = load_thresholds()

    # --- HEALTH_CRITICAL: turbine's 3-day-avg health is below Critical threshold ---
    health_df = load_health_data()
    recent_health = health_df[health_df["timestamp"] >= GLOBAL_NOW - pd.Timedelta(days=3)]
    per_turbine_health = recent_health.groupby("turbine_id")["health_score"].mean()

    for turbine_id, score in per_turbine_health.items():
        if score < thresholds["critical_threshold"]:
            alerts.append({
                "type": "HEALTH_CRITICAL",
                "turbine_id": turbine_id,
                "detail": f"3-day avg health score {round(score, 1)} below critical threshold",
                "timestamp": str(GLOBAL_NOW),
            })

    # --- FAULT_EVENT: sustained fault episodes ending within the active window ---
    fault_df = load_fault_events()
    recent_faults = fault_df[
        (fault_df["end_time"] >= window_start) &
        (fault_df["data_quality_flag"] != "SENSOR_OUTAGE_INTERPOLATED")
    ]
    for _, row in recent_faults.iterrows():
        alerts.append({
            "type": "FAULT_EVENT",
            "turbine_id": row["turbine_id"],
            "detail": f"{row['probable_root_cause']} fault, {row['duration_minutes']} min",
            "timestamp": str(row["end_time"]),
        })

    # --- PERFORMANCE_ALERT: sustained underperformance episodes ---
    perf_df = load_performance_alerts()
    recent_perf = perf_df[perf_df["end_time"] >= window_start]
    for _, row in recent_perf.iterrows():
        alerts.append({
            "type": "PERFORMANCE_ALERT",
            "turbine_id": row["turbine_id"],
            "detail": f"Underperformance, {row['duration_minutes']} min, {row['energy_loss_kwh']:.1f} kWh lost",
            "timestamp": str(row["end_time"]),
        })

    # --- HIGH_RISK_FORECAST: forward-looking risk, not a live fault - labeled distinctly ---
    forecast_df = load_maintenance_forecast()
    high_risk = forecast_df[forecast_df["risk_level"] == "High"]  # confirm exact label before trusting this
    for _, row in high_risk.iterrows():
        alerts.append({
            "type": "HIGH_RISK_FORECAST",
            "turbine_id": row["turbine_id"],
            "detail": f"{row['likely_component']} — {row['recommended_action']}",
            "timestamp": str(row["as_of"]),
        })

    return alerts

def get_recent_events(turbine_id: str = None, start_date: str = None,
                       end_date: str = None, limit: int = 20) -> list[dict]:
    """
    Combines fault events and performance alerts into one operational history
    timeline, sorted most-recent-first. Unlike active_alerts, this isn't bounded
    by ACTIVE_WINDOW_DAYS - it's meant to be browsable history, filtered by the
    caller via turbine_id / date range / limit rather than a fixed cutoff.

    SENSOR_OUTAGE_INTERPOLATED fault events are still excluded by default here,
    same rule as Epic 4 and build_active_alerts - a flagged event isn't a real
    fault worth surfacing in operational history either.
    """
    events = []

    fault_df = load_fault_events()
    fault_df = fault_df[fault_df["data_quality_flag"] != "SENSOR_OUTAGE_INTERPOLATED"]
    for _, row in fault_df.iterrows():
        events.append({
            "type": "FAULT_EVENT",
            "turbine_id": row["turbine_id"],
            "detail": f"{row['probable_root_cause']} fault, {row['duration_minutes']} min",
            "start_time": row["start_time"],
            "end_time": row["end_time"],
        })

    perf_df = load_performance_alerts()
    for _, row in perf_df.iterrows():
        events.append({
            "type": "PERFORMANCE_ALERT",
            "turbine_id": row["turbine_id"],
            "detail": f"Underperformance, {row['duration_minutes']} min, {row['energy_loss_kwh']:.1f} kWh lost",
            "start_time": row["start_time"],
            "end_time": row["end_time"],
        })

    events_df = pd.DataFrame(events)

    if turbine_id:
        events_df = events_df[events_df["turbine_id"] == turbine_id]
    if start_date:
        events_df = events_df[events_df["end_time"] >= pd.Timestamp(start_date, tz="UTC")]
    if end_date:
        events_df = events_df[events_df["end_time"] <= pd.Timestamp(end_date, tz="UTC")]

    events_df = events_df.sort_values("end_time", ascending=False).head(limit)

    events_df["start_time"] = events_df["start_time"].astype(str)
    events_df["end_time"] = events_df["end_time"].astype(str)

    return events_df.to_dict(orient="records")


def load_raw_sensor_data(turbine_id: str, columns: list[str]) -> pd.DataFrame:
    needed_columns = ["Turbine_ID", "Timestamp"] + columns
    df = pd.read_parquet(
        PROCESSED_DIR / "processed_scada_full.parquet",
        columns=needed_columns,
        filters=[("Turbine_ID", "==", turbine_id)],
    )
    df = df.rename(columns={"Turbine_ID": "turbine_id", "Timestamp": "timestamp"})
    return df

def get_sensor_trends(turbine_id: str, sensors: list[str] = None,
                       start_date: str = None, end_date: str = None,
                       resample: str = "h") -> dict:
    if sensors is None:
        sensors = HEALTH_FEATURES
    else:
        invalid = [s for s in sensors if s not in HEALTH_FEATURES and s != "Grd_Prod_Pwr_Avg"]
        if invalid:
            raise ValueError(f"Unknown sensor(s) requested: {invalid}")

    df = load_raw_sensor_data(turbine_id, sensors)

    if start_date:
        df = df[df["timestamp"] >= pd.Timestamp(start_date, tz="UTC")]
    if end_date:
        df = df[df["timestamp"] <= pd.Timestamp(end_date, tz="UTC")]
    if sensors is None:
        sensors = HEALTH_FEATURES
    else:
        invalid = [s for s in sensors if s not in HEALTH_FEATURES and s != "Grd_Prod_Pwr_Avg"]
        if invalid:
            raise ValueError(f"Unknown sensor(s) requested: {invalid}")

    missing = [s for s in sensors if s not in df.columns]
    if missing:
        raise ValueError(f"Sensors not found in processed data: {missing}")

    if df.empty:
        return {"turbine_id": turbine_id, "sensors": {}, "resample": resample, "row_count": 0}

    if resample == "raw":
        series_df = df[["timestamp"] + sensors].sort_values("timestamp")
    else:
        series_df = (
            df.set_index("timestamp")[sensors]
            .resample(resample)
            .mean()
            .dropna(how="all")
            .reset_index()
        )

    result = {
        "turbine_id": turbine_id,
        "resample": resample,
        "row_count": len(series_df),
        "sensors": {},
    }
    for sensor in sensors:
        category = SENSOR_TO_CATEGORY.get(sensor, "Power Output" if sensor == "Grd_Prod_Pwr_Avg" else "Uncategorized")
        result["sensors"][sensor] = {
            "category": category,
            "timestamps": series_df["timestamp"].astype(str).tolist(),
            "values": series_df[sensor].round(3).tolist(),
        }

    return result


if __name__ == "__main__":
    overview = get_fleet_overview()
    print("=== FLEET OVERVIEW ===")
    print(overview)

    alerts = build_active_alerts()
    print(f"\n=== ACTIVE ALERTS ({len(alerts)} total) ===")
    for a in alerts:
        print(a)

    events = get_recent_events(limit=10)
    print(f"\n=== RECENT EVENTS (top 10, unfiltered) ===")
    for e in events:
        print(e)

    t01_events = get_recent_events(turbine_id="T01", limit=10)
    print(f"\n=== RECENT EVENTS (T01 only) ===")
    for e in t01_events:
        print(e)

    trend = get_sensor_trends(
        turbine_id="T01",
        sensors=["Gear_Bear_Temp_Avg", "Gear_Oil_Temp_Avg"],
        start_date="2016-07-01",
        end_date="2016-07-18",
    )
    print(f"\n=== SENSOR TRENDS: T01, Gearbox sensors, 2016-07-01 to 2016-07-18 ===")
    print(f"Row count: {trend['row_count']}, resample: {trend['resample']}")
    for sensor, data in trend["sensors"].items():
        print(f"\n{sensor} ({data['category']}):")
        print(f"  First 3 points: {list(zip(data['timestamps'][:3], data['values'][:3]))}")
        print(f"  Last 3 points: {list(zip(data['timestamps'][-3:], data['values'][-3:]))}")

    predictions = get_prediction_summary()
    print(f"\n=== PREDICTION SUMMARY ({len(predictions)} turbines) ===")
    for p in predictions:
        print(p)