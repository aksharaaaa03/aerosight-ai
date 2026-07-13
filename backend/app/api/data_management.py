from fastapi import APIRouter
import pandas as pd
from pathlib import Path

router = APIRouter(prefix="/api/epic1", tags=["Data Management"])

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"

@router.get("/summary")
def get_data_summary():
    df = pd.read_parquet(PROCESSED_DIR / "processed_scada_full.parquet")

    total_records = len(df)
    non_operational = int((~df["is_operational"]).sum())

    # Data completeness: % of raw sensor cells that were originally valid
    # (we know 48 dupes + 523 ceiling values + 8 originally-missing = "imputed" count)
    imputed_values = 48 + 523 + 8  # duplicates + sensor-ceiling fixes + original NaNs
    completeness_pct = round((1 - imputed_values / (total_records * 84)) * 100, 3)

    return {
        "total_records": total_records,
        "data_completeness_pct": completeness_pct,
        "imputed_values": imputed_values,
        "non_operational_records": non_operational,
        "non_operational_pct": round(non_operational / total_records * 100, 2),
    }

@router.get("/missing-data-analysis")
def get_missing_data_analysis():
    return {
        "duplicates_removed": 48,
        "sensor_ceiling_values_fixed": 523,
        "originally_missing": 8,
        "total_imputed": 579,
        "breakdown": [
            {"issue": "Duplicate records", "count": 48},
            {"issue": "Sensor ceiling errors (205°C temp cap)", "count": 521},
            {"issue": "Sensor ceiling errors (1000 reactive power cap)", "count": 2},
            {"issue": "Originally missing values", "count": 8},
        ],
    }

@router.get("/sensor-distribution")
def get_sensor_distribution():
    df = pd.read_parquet(PROCESSED_DIR / "processed_scada_full.parquet")
    wind_speed = df["Amb_WindSpeed_Avg"]

    bins = [0, 4, 8, 12, 16, 20, 25, 100]
    labels = ["0-4", "4-8", "8-12", "12-16", "16-20", "20-25", "25+"]
    binned = pd.cut(wind_speed, bins=bins, labels=labels, right=False)
    distribution = binned.value_counts().sort_index()

    return {
        "bins": labels,
        "counts": [int(distribution[label]) for label in labels],
    }

@router.get("/processed-summary")
def get_processed_summary():
    df = pd.read_parquet(PROCESSED_DIR / "processed_scada_full.parquet")
    training_df = pd.read_parquet(PROCESSED_DIR / "training_ready.parquet")

    per_turbine = df.groupby("Turbine_ID").size().to_dict()

    return {
        "full_dataset": {
            "rows": len(df),
            "columns": len(df.columns),
            "date_range_start": str(df["Timestamp"].min()),
            "date_range_end": str(df["Timestamp"].max()),
        },
        "training_ready_dataset": {
            "rows": len(training_df),
            "columns": len(training_df.columns),
        },
        "records_per_turbine": per_turbine,
    }