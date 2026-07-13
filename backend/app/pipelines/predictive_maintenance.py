import pandas as pd
import numpy as np
from pathlib import Path
import json

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
MODELS_DIR = Path(__file__).resolve().parents[2] / "app" / "ml" / "saved"

def load_health_data() -> pd.DataFrame:
    df = pd.read_parquet(PROCESSED_DIR / "health_scored.parquet")
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    df = df.dropna(subset=["health_score"])
    print(f"Loaded health data: {df.shape}")
    return df

def load_thresholds() -> dict:
    with open(MODELS_DIR / "health_thresholds.json") as f:
        return json.load(f)

def compute_health_trend(df: pd.DataFrame, turbine_id: str, as_of: pd.Timestamp, lookback_days: int = 30) -> dict:
    window_start = as_of - pd.Timedelta(days=lookback_days)
    subset = df[
        (df["Turbine_ID"] == turbine_id) &
        (df["Timestamp"] >= window_start) &
        (df["Timestamp"] <= as_of)
    ].sort_values("Timestamp")

    if len(subset) < 20:
        return {"status": "insufficient_data", "slope": None, "current_health": None}

    # Smooth to daily averages first - raw 10-min data is too noisy for stable regression
    daily = subset.set_index("Timestamp").resample("D")["health_score"].mean().dropna().reset_index()

    if len(daily) < 3:
        return {"status": "insufficient_data", "slope": None, "current_health": None}

    days = (daily["Timestamp"] - window_start).dt.total_seconds() / 86400
    scores = daily["health_score"].values

    slope, intercept = np.polyfit(days, scores, 1)
    current_health = slope * days.iloc[-1] + intercept

    return {
        "status": "ok",
        "slope_per_day": round(slope, 3),
        "current_health": round(current_health, 1),
        "data_points": len(daily),
        "window_start": str(window_start.date()),
        "window_end": str(as_of.date()),
    }

def estimate_remaining_useful_life(trend: dict, critical_threshold: float) -> dict:
    if trend["status"] != "ok":
        return {"rul_days": None, "reason": "insufficient_data"}

    slope = trend["slope_per_day"]
    current = trend["current_health"]

    if slope >= -0.05:  # not meaningfully declining (small negative noise allowed)
        return {"rul_days": None, "reason": "not_declining", "slope_per_day": slope}

    if current <= critical_threshold:
        return {"rul_days": 0, "reason": "already_critical"}

    days_to_critical = (current - critical_threshold) / abs(slope)
    return {
        "rul_days": round(days_to_critical, 1),
        "reason": "extrapolated",
        "slope_per_day": slope,
        "current_health": current,
    }

def diagnose_decline_shape(df: pd.DataFrame, turbine_id: str, as_of: pd.Timestamp) -> None:
    print(f"\n=== DECLINE SHAPE DIAGNOSIS: {turbine_id} as of {as_of.date()} ===")
    for lookback in [3, 5, 7, 10, 14, 21]:
        trend = compute_health_trend(df, turbine_id, as_of, lookback_days=lookback)
        if trend["status"] == "ok":
            print(f"  {lookback:2d}-day lookback: slope={trend['slope_per_day']:+.3f}/day, "
                  f"current_health={trend['current_health']}, points={trend['data_points']}")
            
def show_daily_health_values(df: pd.DataFrame, turbine_id: str, as_of: pd.Timestamp, lookback_days: int = 21) -> None:
    window_start = as_of - pd.Timedelta(days=lookback_days)
    subset = df[
        (df["Turbine_ID"] == turbine_id) &
        (df["Timestamp"] >= window_start) &
        (df["Timestamp"] <= as_of)
    ].sort_values("Timestamp")
    daily = subset.set_index("Timestamp").resample("D")["health_score"].mean().dropna()
    print(f"\n=== DAILY HEALTH VALUES: {turbine_id}, {window_start.date()} to {as_of.date()} ===")
    print(daily.to_string())

def compute_degradation_risk(df: pd.DataFrame, turbine_id: str, as_of: pd.Timestamp,
                               lookback_days: int, thresholds: dict) -> dict:
    window_start = as_of - pd.Timedelta(days=lookback_days)
    subset = df[
        (df["Turbine_ID"] == turbine_id) &
        (df["Timestamp"] >= window_start) &
        (df["Timestamp"] <= as_of)
    ]

    if len(subset) < 20:
        return {"status": "insufficient_data"}

    healthy_thresh = thresholds["healthy_threshold"]
    critical_thresh = thresholds["critical_threshold"]

    pct_below_healthy = (subset["health_score"] < healthy_thresh).mean() * 100
    pct_critical = (subset["health_score"] < critical_thresh).mean() * 100
    min_health_in_window = subset["health_score"].quantile(0.05)

    # Recent baseline: last 3 days average (short window, "where is it right now")
    recent = subset[subset["Timestamp"] >= as_of - pd.Timedelta(days=3)]
    recent_avg = recent["health_score"].mean() if len(recent) > 0 else subset["health_score"].mean()

    return {
        "status": "ok",
        "pct_time_below_healthy": round(pct_below_healthy, 1),
        "pct_time_critical": round(pct_critical, 1),
        "min_health_in_window": round(min_health_in_window, 1),
        "recent_avg_health": round(recent_avg, 1),
    }

def calibrate_against_real_failures(df: pd.DataFrame, thresholds: dict) -> None:
    failures = pd.read_excel(Path(__file__).resolve().parents[2] / "data" / "raw" / "Historical-Failure-Logbook-2016.xlsx")
    failures["Timestamp"] = pd.to_datetime(failures["Timestamp"])
    known_turbines = df["Turbine_ID"].unique()
    usable = failures[failures["Turbine_ID"].isin(known_turbines)]

    print(f"\n=== CALIBRATION: Degradation risk 7 days before each real failure ===")
    for _, fail in usable.iterrows():
        turbine, fail_time, component = fail["Turbine_ID"], fail["Timestamp"], fail["Component"]
        check_point = fail_time - pd.Timedelta(days=7)
        risk = compute_degradation_risk(df, turbine, check_point, lookback_days=14, thresholds=thresholds)
        print(f"{turbine} — {component} (failed {fail_time.date()}), checked 7 days prior: {risk}")

def compute_fleet_baseline_critical_rate(df: pd.DataFrame, thresholds: dict) -> float:
    critical_thresh = thresholds["critical_threshold"]
    return (df["health_score"] < critical_thresh).mean() * 100

def classify_risk_level(pct_time_critical: float, baseline: float) -> str:
    if pct_time_critical > baseline * 2:
        return "High"
    elif pct_time_critical > baseline:
        return "Medium"
    else:
        return "Low"

def calibrate_against_real_failures(df: pd.DataFrame, thresholds: dict) -> None:
    baseline = compute_fleet_baseline_critical_rate(df, thresholds)
    print(f"\nFleet-wide baseline critical-time rate: {baseline:.2f}%")
    print(f"Risk bands: Low <= {baseline:.1f}% | Medium {baseline:.1f}-{baseline*2:.1f}% | High > {baseline*2:.1f}%")

    failures = pd.read_excel(Path(__file__).resolve().parents[2] / "data" / "raw" / "Historical-Failure-Logbook-2016.xlsx")
    failures["Timestamp"] = pd.to_datetime(failures["Timestamp"])
    known_turbines = df["Turbine_ID"].unique()
    usable = failures[failures["Turbine_ID"].isin(known_turbines)]

    print(f"\n=== CALIBRATION: Risk level 7 days before each real failure ===")
    risk_counts = {"High": 0, "Medium": 0, "Low": 0}
    for _, fail in usable.iterrows():
        turbine, fail_time, component = fail["Turbine_ID"], fail["Timestamp"], fail["Component"]
        check_point = fail_time - pd.Timedelta(days=7)
        risk = compute_degradation_risk(df, turbine, check_point, lookback_days=14, thresholds=thresholds)
        if risk["status"] != "ok":
            continue
        level = classify_risk_level(risk["pct_time_critical"], baseline)
        risk_counts[level] += 1
        print(f"{turbine} — {component} (failed {fail_time.date()}): "
              f"pct_critical={risk['pct_time_critical']}%, risk_level={level}")

    print(f"\n=== SUMMARY: {risk_counts['High']}/12 High, {risk_counts['Medium']}/12 Medium, {risk_counts['Low']}/12 Low ===")
    print(f"(High + Medium = {risk_counts['High']+risk_counts['Medium']}/12 would have shown ELEVATED risk 7 days out)")

def calibrate_rul_lead_time(df: pd.DataFrame, thresholds: dict) -> None:
    baseline = compute_fleet_baseline_critical_rate(df, thresholds)
    failures = pd.read_excel(Path(__file__).resolve().parents[2] / "data" / "raw" / "Historical-Failure-Logbook-2016.xlsx")
    failures["Timestamp"] = pd.to_datetime(failures["Timestamp"])
    known_turbines = df["Turbine_ID"].unique()
    usable = failures[failures["Turbine_ID"].isin(known_turbines)]

    print(f"\n=== HOW FAR IN ADVANCE DOES 'HIGH RISK' APPEAR? ===")
    for _, fail in usable.iterrows():
        turbine, fail_time, component = fail["Turbine_ID"], fail["Timestamp"], fail["Component"]
        row = f"{turbine} — {component} ({fail_time.date()}): "
        for days_before in [3, 7, 14, 21, 30]:
            check_point = fail_time - pd.Timedelta(days=days_before)
            risk = compute_degradation_risk(df, turbine, check_point, lookback_days=14, thresholds=thresholds)
            if risk["status"] == "ok":
                level = classify_risk_level(risk["pct_time_critical"], baseline)
                row += f"[{days_before}d:{level[0]}] "
            else:
                row += f"[{days_before}d:-] "
        print(row)

MAINTENANCE_ACTIONS = {
    "Gearbox": "Schedule gearbox inspection; check oil condition and bearing wear.",
    "Generator Bearing": "Inspect generator bearing; check for vibration/temperature anomalies.",
    "Generator": "Inspect generator windings and electrical connections.",
    "Transformer": "Inspect transformer cooling system and insulation; check for overheating.",
    "Hydraulic Group": "Check hydraulic fluid levels and pump/valve condition.",
    "Pitch/Control System": "Inspect pitch actuator and control system calibration.",
    "Nacelle (General)": "General nacelle inspection recommended.",
    "Grid/Electrical": "Inspect grid-side electrical connections and protection systems.",
}

def generate_recommendation(risk_level: str, likely_component: str = None) -> dict:
    rul_bands = {
        "High": "Elevated risk — recommend inspection within 3-14 days",
        "Medium": "Monitor closely — potential issue within 1-3 weeks",
        "Low": "No immediate concern based on current trend",
    }
    action = MAINTENANCE_ACTIONS.get(likely_component, "General inspection recommended") if risk_level in ("High", "Medium") else "Routine monitoring — no action needed"

    return {
        "risk_level": risk_level,
        "rul_estimate": rul_bands[risk_level],
        "recommended_action": action,
    }

def forecast_turbine(df: pd.DataFrame, turbine_id: str, as_of: pd.Timestamp,
                       thresholds: dict, baseline: float, latest_root_causes: dict = None) -> dict:
    risk = compute_degradation_risk(df, turbine_id, as_of, lookback_days=14, thresholds=thresholds)
    if risk["status"] != "ok":
        return {"turbine_id": turbine_id, "status": "insufficient_data"}

    risk_level = classify_risk_level(risk["pct_time_critical"], baseline)
    likely_component = latest_root_causes.get(turbine_id) if latest_root_causes else None
    recommendation = generate_recommendation(risk_level, likely_component)

    return {
        "turbine_id": turbine_id,
        "as_of": str(as_of.date()),
        "current_health": risk["recent_avg_health"],
        "pct_time_critical_14d": risk["pct_time_critical"],
        "pct_time_below_healthy_14d": risk["pct_time_below_healthy"],
        "min_health_5th_pct": risk["min_health_in_window"],
        "risk_level": risk_level,
        "likely_component": likely_component,
        **recommendation,
    }

def forecast_fleet(df: pd.DataFrame, thresholds: dict) -> pd.DataFrame:
    baseline = compute_fleet_baseline_critical_rate(df, thresholds)
    as_of = df["Timestamp"].max()

    # Pull each turbine's most recent (unflagged) root cause from Epic 4, as a hint for recommendations
    fault_events = pd.read_parquet(PROCESSED_DIR / "fault_events.parquet")
    fault_events = fault_events[fault_events["data_quality_flag"] == "OK"]
    fault_events["start_time"] = pd.to_datetime(fault_events["start_time"])
    latest_causes = {}
    for turbine, group in fault_events.groupby("turbine_id"):
        latest = group.sort_values("start_time").iloc[-1]
        latest_causes[turbine] = latest["probable_root_cause"]

    results = []
    for turbine in sorted(df["Turbine_ID"].unique()):
        result = forecast_turbine(df, turbine, as_of, thresholds, baseline, latest_causes)
        results.append(result)

    fleet_df = pd.DataFrame(results)
    print(f"\n=== FLEET FORECAST as of {as_of.date()} ===")
    print(fleet_df.to_string(index=False))
    return fleet_df

def save_forecast(fleet_df: pd.DataFrame) -> None:
    fleet_df.to_parquet(PROCESSED_DIR / "maintenance_forecast.parquet", index=False)
    print(f"\nSaved maintenance_forecast.parquet — shape {fleet_df.shape}")

def prioritize_maintenance(fleet_df: pd.DataFrame) -> pd.DataFrame:
    risk_rank = {"High": 3, "Medium": 2, "Low": 1}
    fleet_df = fleet_df.copy()
    fleet_df["priority_score"] = (
        fleet_df["risk_level"].map(risk_rank) * 100 +
        fleet_df["pct_time_critical_14d"]
    )
    fleet_df = fleet_df.sort_values("priority_score", ascending=False).reset_index(drop=True)
    fleet_df["priority_rank"] = fleet_df.index + 1

    print(f"\n=== MAINTENANCE PRIORITY RANKING ===")
    print(fleet_df[["priority_rank", "turbine_id", "risk_level", "pct_time_critical_14d", "likely_component", "recommended_action"]].to_string(index=False))
    return fleet_df


if __name__ == "__main__":
    df = load_health_data()
    thresholds = load_thresholds()
    fleet_df = forecast_fleet(df, thresholds)
    fleet_df = prioritize_maintenance(fleet_df)
    save_forecast(fleet_df)