import pandas as pd
import numpy as np
from pathlib import Path

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"

def load_health_and_sensor_data() -> pd.DataFrame:
    health = pd.read_parquet(PROCESSED_DIR / "health_scored.parquet")
    scada = pd.read_parquet(PROCESSED_DIR / "processed_scada_full.parquet")

    df = scada.merge(health[["Turbine_ID", "Timestamp", "health_score", "health_status"]],
                      on=["Turbine_ID", "Timestamp"], how="left")
    print(f"Merged shape: {df.shape}")
    return df

def detect_fault_events(df: pd.DataFrame, min_duration_intervals: int = 3) -> pd.DataFrame:
    df = df.copy()
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    df = df.sort_values(["Turbine_ID", "Timestamp"]).reset_index(drop=True)

    events = []
    for turbine, group in df[df["health_status"] == "Critical"].groupby("Turbine_ID"):
        group = group.sort_values("Timestamp")
        gaps = group["Timestamp"].diff() > pd.Timedelta(minutes=10)
        episode_id = gaps.cumsum()

        for _, episode in group.groupby(episode_id):
            if len(episode) >= min_duration_intervals:
                events.append({
                    "turbine_id": turbine,
                    "start_time": episode["Timestamp"].min(),
                    "end_time": episode["Timestamp"].max(),
                    "duration_minutes": len(episode) * 10,
                    "min_health_score": episode["health_score"].min(),
                    "avg_health_score": round(episode["health_score"].mean(), 1),
                })

    events_df = pd.DataFrame(events).sort_values("min_health_score")
    print(f"\nTotal fault events detected (>= {min_duration_intervals*10} min of sustained Critical status): {len(events_df)}")
    print(f"\nBy turbine:\n{events_df['turbine_id'].value_counts()}")
    print(f"\nTop 10 most severe events:\n{events_df.head(10).to_string(index=False)}")

    return events_df

from app.pipelines.health_model import HEALTH_FEATURES_NORM

def identify_contributing_sensors(df: pd.DataFrame, events_df: pd.DataFrame, top_n: int = 3) -> pd.DataFrame:
    events_df = events_df.copy()
    contributing_sensors_list = []

    # Exclude both external-condition features from being "blamed" for a fault
    fault_candidate_features = [c for c in HEALTH_FEATURES_NORM if c != "Amb_WindSpeed_Avg_norm"]

    for _, event in events_df.iterrows():
        turbine = event["turbine_id"]
        event_data = df[
            (df["Turbine_ID"] == turbine) &
            (df["Timestamp"] >= event["start_time"]) &
            (df["Timestamp"] <= event["end_time"])
        ]
        event_wind = event_data["Amb_WindSpeed_Avg"].mean()
        event_temp = event_data["Amb_Temp_Avg"].mean()

        # Match on BOTH wind speed and ambient temperature now
        similar_condition = df[
            (df["Turbine_ID"] == turbine) &
            (df["is_operational"]) &
            (df["health_status"] == "Healthy") &
            (df["Amb_WindSpeed_Avg"].between(event_wind - 1, event_wind + 1)) &
            (df["Amb_Temp_Avg"].between(event_temp - 3, event_temp + 3))
        ]
        if len(similar_condition) < 20:
            contributing_sensors_list.append("Insufficient comparable data")
            continue

        baseline_matched = similar_condition[fault_candidate_features].mean()
        event_means = event_data[fault_candidate_features].mean()
        deviation = (event_means - baseline_matched).abs().sort_values(ascending=False)

        top_sensors = deviation.head(top_n)
        contributing_sensors_list.append(
            ", ".join([f"{sensor.replace('_norm','')} ({dev:.2f})" for sensor, dev in top_sensors.items()])
        )

    events_df["top_contributing_sensors"] = contributing_sensors_list
    return events_df

SENSOR_TO_CATEGORY = {
    "Gen_Bear_Temp_Avg": "Generator Bearing", "Gen_Bear2_Temp_Avg": "Generator Bearing",
    "Gen_Phase1_Temp_Avg": "Generator", "Gen_Phase2_Temp_Avg": "Generator", "Gen_Phase3_Temp_Avg": "Generator",
    "Gear_Bear_Temp_Avg": "Gearbox", "Gear_Oil_Temp_Avg": "Gearbox",
    "Hyd_Oil_Temp_Avg": "Hydraulic Group",
    "HVTrafo_Phase1_Temp_Avg": "Transformer", "HVTrafo_Phase2_Temp_Avg": "Transformer", "HVTrafo_Phase3_Temp_Avg": "Transformer",
    "Blds_PitchAngle_Avg": "Pitch/Control System",
    "Nac_Temp_Avg": "Nacelle (General)",
    "Grd_Prod_ReactPwr_Avg": "Grid/Electrical",
    "Gen_RPM_Avg": "Drivetrain", "Rtr_RPM_Avg": "Drivetrain",
    "Amb_WindSpeed_Avg": "EXTERNAL CONDITION (not a fault)",
}
def diagnose_sensor_selection_frequency(events_df: pd.DataFrame) -> None:
    print("\n=== HOW OFTEN EACH SENSOR IS THE #1 CONTRIBUTOR ACROSS ALL EVENTS ===")
    top_sensor_only = events_df["top_contributing_sensors"].str.split(",").str[0].str.split(" \(").str[0]
    print(top_sensor_only.value_counts())

def generate_root_cause(events_df: pd.DataFrame) -> pd.DataFrame:
    events_df = events_df.copy()
    top_sensor_name = events_df["top_contributing_sensors"].str.split(" \(").str[0]
    events_df["probable_root_cause"] = top_sensor_name.map(SENSOR_TO_CATEGORY).fillna("Unknown")
    return events_df

def validate_against_logbook(events_df: pd.DataFrame) -> None:
    failures = pd.read_excel(Path(__file__).resolve().parents[2] / "data" / "raw" / "Historical-Failure-Logbook-2016.xlsx")
    failures["Timestamp"] = pd.to_datetime(failures["Timestamp"])

    print("\n=== ROOT CAUSE VALIDATION (nearest, most severe event) ===")
    matches = 0
    total_checked = 0
    for _, fail in failures.iterrows():
        turbine, fail_time, real_component = fail["Turbine_ID"], fail["Timestamp"], fail["Component"]
        window_start = fail_time - pd.Timedelta(days=10)

        nearby = events_df[
            (events_df["turbine_id"] == turbine) &
            (events_df["start_time"] >= window_start) &
            (events_df["start_time"] <= fail_time)
        ]
        if nearby.empty:
            print(f"\n{turbine} — {real_component} ({fail_time.date()}) — no events detected")
            continue

        total_checked += 1
        most_severe = nearby.sort_values("min_health_score").iloc[0]
        predicted = most_severe["probable_root_cause"]
        norm_predicted = predicted.upper().replace(" ", "_")
        norm_real = real_component.upper().replace(" ", "_")
        match = norm_predicted in norm_real or norm_real in norm_predicted
        if match:
            matches += 1
        print(f"\n{turbine} — {real_component} ({fail_time.date()})")
        print(f"  Most severe nearby event: {most_severe['start_time'].date()}, predicted: {predicted}  [{'✅ MATCH' if match else '❌ no match'}]")

    print(f"\n=== SUMMARY: {matches}/{total_checked} matches (excluding events with no data) ===")

def diagnose_sensor_selection_frequency(events_df: pd.DataFrame) -> None:
    print("\n=== HOW OFTEN EACH SENSOR IS THE #1 CONTRIBUTOR ACROSS ALL 989 EVENTS ===")
    top_sensor_only = events_df["top_contributing_sensors"].str.split(",").str[0].str.split(" \(").str[0]
    print(top_sensor_only.value_counts())

def save_fault_events(events_df: pd.DataFrame) -> None:
    events_df = events_df.copy()
    events_df["start_time"] = events_df["start_time"].astype(str)
    events_df["end_time"] = events_df["end_time"].astype(str)
    events_df.to_parquet(PROCESSED_DIR / "fault_events.parquet", index=False)
    print(f"\nSaved fault_events.parquet — shape {events_df.shape}")

def flag_sensor_outage_events(events_df: pd.DataFrame) -> pd.DataFrame:
    """
    Some 205-degree sensor faults (Gen_Bear_Temp_Avg / Gen_Bear2_Temp_Avg) lasted
    1+ hours continuously. Our Epic 1 cleaning interpolates across gaps, which is
    correct for brief gaps but creates a FABRICATED smooth trend across long outages.
    This flags any fault event overlapping a known long sensor-outage window, so we
    never present interpolated fiction as a real fault trend.
    """
    known_outage_windows = [
        ("T06", "2016-07-20 14:30:00+00:00", "2016-07-21 09:10:00+00:00"),
        ("T06", "2016-11-02 12:00:00+00:00", "2016-11-04 09:30:00+00:00"),
        ("T07", "2017-08-28 11:30:00+00:00", "2017-08-28 14:00:00+00:00"),
    ]

    events_df = events_df.copy()
    events_df["data_quality_flag"] = "OK"

    for turbine, w_start, w_end in known_outage_windows:
        w_start, w_end = pd.to_datetime(w_start), pd.to_datetime(w_end)
        overlap = (
            (events_df["turbine_id"] == turbine) &
            (pd.to_datetime(events_df["start_time"]) <= w_end) &
            (pd.to_datetime(events_df["end_time"]) >= w_start)
        )
        events_df.loc[overlap, "data_quality_flag"] = "SENSOR_OUTAGE_INTERPOLATED"

    flagged = (events_df["data_quality_flag"] != "OK").sum()
    print(f"\nFlagged {flagged} fault event(s) as built on long sensor-outage interpolation (excluded from reliable analysis).")
    print(events_df[events_df["data_quality_flag"] != "OK"][["turbine_id", "start_time", "end_time", "min_health_score"]].to_string(index=False))

    return events_df

if __name__ == "__main__":
    df = load_health_and_sensor_data()
    events_df = detect_fault_events(df)
    events_df = identify_contributing_sensors(df, events_df)
    diagnose_sensor_selection_frequency(events_df)
    events_df = generate_root_cause(events_df)
    events_df = flag_sensor_outage_events(events_df)
    validate_against_logbook(events_df)
    save_fault_events(events_df)