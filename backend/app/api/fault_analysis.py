from fastapi import APIRouter
import pandas as pd
from pathlib import Path

router = APIRouter(prefix="/api/epic4", tags=["Fault & Root Cause"])
PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"

TOP_SENSORS_FOR_TREND = [
    "Gear_Oil_Temp_Avg", "Hyd_Oil_Temp_Avg", "Gen_Bear_Temp_Avg", "Gen_Bear2_Temp_Avg",
    "HVTrafo_Phase1_Temp_Avg", "HVTrafo_Phase2_Temp_Avg", "HVTrafo_Phase3_Temp_Avg", "Blds_PitchAngle_Avg",
]


@router.get("/root-cause-summary")
def get_root_cause_summary():
    events = pd.read_parquet(PROCESSED_DIR / "fault_events.parquet")
    summary = events["probable_root_cause"].value_counts().reset_index()
    summary.columns = ["root_cause", "event_count"]
    return {"summary": summary.to_dict(orient="records"), "total_events": len(events)}

@router.get("/sensor-contribution/{event_index}")
def get_sensor_contribution(event_index: int):
    events = pd.read_parquet(PROCESSED_DIR / "fault_events.parquet")
    if event_index >= len(events):
        return {"error": "Event index out of range"}
    event = events.iloc[event_index]
    sensors = event["top_contributing_sensors"].split(", ")
    parsed = []
    for s in sensors:
        name, dev = s.rsplit(" (", 1)
        parsed.append({"sensor": name, "deviation": float(dev.replace(")", ""))})
    return {
        "turbine_id": event["turbine_id"],
        "start_time": event["start_time"],
        "probable_root_cause": event["probable_root_cause"],
        "contributing_sensors": parsed,
    }

@router.get("/sensor-trend-comparison/{event_index}")
def get_sensor_trend_comparison(event_index: int):
    events = pd.read_parquet(PROCESSED_DIR / "fault_events.parquet")
    if event_index >= len(events):
        return {"error": "Event index out of range"}
    event = events.iloc[event_index]
    if event["data_quality_flag"] != "OK":
        return {"error": "This event overlaps a long sensor-outage period. Underlying trend data is interpolated/fabricated across the gap and is not reliable for analysis."}
    turbine = event["turbine_id"]
    start = pd.to_datetime(event["start_time"])
    end = pd.to_datetime(event["end_time"])

    before_start = start - pd.Timedelta(hours=12)
    after_end = end + pd.Timedelta(hours=12)
    scada = pd.read_parquet(PROCESSED_DIR / "processed_scada_full.parquet")
    scada["Timestamp"] = pd.to_datetime(scada["Timestamp"])

    window = scada[
        (scada["Turbine_ID"] == turbine) &
        (scada["Timestamp"] >= before_start) &
        (scada["Timestamp"] <= after_end)
    ].sort_values("Timestamp")

    trend = window[["Timestamp"] + TOP_SENSORS_FOR_TREND].copy()
    trend["Timestamp"] = trend["Timestamp"].astype(str)
    trend["phase"] = ["Before" if pd.to_datetime(t) < start else ("During" if pd.to_datetime(t) <= end else "After") for t in trend["Timestamp"]]
    return {
        "turbine_id": turbine,
        "fault_start": str(start),
        "fault_end": str(end),
        "trend": trend.to_dict(orient="records"),
    }

@router.get("/fault-events")
def get_fault_events(turbine_id: str = None, limit: int = 20, include_flagged: bool = False):
    events = pd.read_parquet(PROCESSED_DIR / "fault_events.parquet")
    events["event_index"] = events.index
    if not include_flagged:
        events = events[events["data_quality_flag"] == "OK"]
    if turbine_id:
        events = events[events["turbine_id"] == turbine_id]
    events = events.sort_values("min_health_score").head(limit)
    return {"events": events.to_dict(orient="records")}

@router.get("/fault-timeline")
def get_fault_timeline(turbine_id: str = None):
    events = pd.read_parquet(PROCESSED_DIR / "fault_events.parquet")
    events["event_index"] = events.index
    events = events[events["data_quality_flag"] == "OK"]
    if turbine_id:
        events = events[events["turbine_id"] == turbine_id]
    events = events.sort_values("start_time")
    return {"timeline": events[["event_index", "turbine_id", "start_time", "end_time", "probable_root_cause", "min_health_score"]].to_dict(orient="records")}