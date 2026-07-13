from fastapi import APIRouter
import pandas as pd
from pathlib import Path

router = APIRouter(prefix="/api/epic3", tags=["Power Performance"])

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"

@router.get("/summary")
def get_summary():
    df = pd.read_parquet(PROCESSED_DIR / "power_performance.parquet")
    alerts = pd.read_parquet(PROCESSED_DIR / "performance_alerts.parquet")

    valid = df.dropna(subset=["power_ratio"])
    total_actual = valid["Grd_Prod_Pwr_Avg"].sum() / 6  # kW * 10min -> kWh
    total_expected = valid["Grd_Prod_PsblePwr_Avg"].sum() / 6
    total_loss_from_alerts = alerts["energy_loss_kwh"].sum()

    return {
        "total_actual_generation_kwh": round(total_actual, 1),
        "total_expected_generation_kwh": round(total_expected, 1),
        "total_energy_loss_from_sustained_underperformance_kwh": round(total_loss_from_alerts, 1),
        "underperforming_turbines_count": alerts["turbine_id"].nunique(),
        "total_alerts": len(alerts),
    }

@router.get("/power-curve/{turbine_id}")
def get_power_curve(turbine_id: str, sample_size: int = 2000):
    df = pd.read_parquet(PROCESSED_DIR / "power_performance.parquet")
    curve = pd.read_parquet(PROCESSED_DIR / "expected_power_curve.parquet")

    turbine_df = df[(df["Turbine_ID"] == turbine_id) & df["power_ratio"].notna()].copy()
    turbine_df["performance_category"] = turbine_df["is_continuous_underperformance"].map(
        {True: "Underperforming", False: "Normal"}
    )

    normal = turbine_df[turbine_df["performance_category"] == "Normal"]
    underperf = turbine_df[turbine_df["performance_category"] == "Underperforming"]
    n_sample = min(len(normal), sample_size)
    normal_sample = normal.sample(n=n_sample, random_state=42) if n_sample > 0 else normal

    scatter = pd.concat([normal_sample, underperf])[
        ["Amb_WindSpeed_Avg", "Grd_Prod_Pwr_Avg", "performance_category"]
    ]

    return {
        "turbine_id": turbine_id,
        "expected_curve": curve.to_dict(orient="records"),
        "scatter_points": scatter.to_dict(orient="records"),
    }

@router.get("/underperforming-turbines")
def get_underperforming_turbines():
    summary = pd.read_parquet(PROCESSED_DIR / "underperforming_turbines.parquet")
    return {"turbines": summary.to_dict(orient="records")}

@router.get("/alerts")
def get_alerts(turbine_id: str = None):
    alerts = pd.read_parquet(PROCESSED_DIR / "performance_alerts.parquet")
    if turbine_id:
        alerts = alerts[alerts["turbine_id"] == turbine_id]
    alerts = alerts.sort_values("energy_loss_kwh", ascending=False)
    alerts["start_time"] = alerts["start_time"].astype(str)
    alerts["end_time"] = alerts["end_time"].astype(str)
    return {"alerts": alerts.to_dict(orient="records")}

@router.get("/loss-trend")
def get_loss_trend(turbine_id: str = None):
    alerts = pd.read_parquet(PROCESSED_DIR / "performance_alerts.parquet")
    if turbine_id:
        alerts = alerts[alerts["turbine_id"] == turbine_id]

    alerts = alerts.copy()
    alerts["start_time"] = pd.to_datetime(alerts["start_time"])
    alerts = alerts.set_index("start_time")

    monthly = alerts.resample("ME")["energy_loss_kwh"].sum().reset_index()
    monthly["month"] = monthly["start_time"].dt.strftime("%Y-%m")

    return {
        "turbine_id": turbine_id or "All Turbines",
        "trend": [
            {"month": row["month"], "energy_loss_kwh": round(row["energy_loss_kwh"], 1)}
            for _, row in monthly.iterrows()
        ],
    }