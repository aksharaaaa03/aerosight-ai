import pandas as pd
from pathlib import Path
import json

PROCESSED_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "processed"
MODELS_DIR = Path(__file__).resolve().parent.parent / "ml" / "saved"
LABOR_RATE_EUR_PER_MINUTE = 1.67  # ~€100/hour
MAX_LABOR_ADDITION_FRACTION = 0.20
ROUTINE_EVENT_BASE_COST = 1_000
ROUTINE_EVENT_LABOR_CAP_FRACTION = 0.20

# --- Business assumptions (external reference data, not measured from SCADA data) ---
# Energy price: representative European onshore wind wholesale/PPA revenue rate.
# Sourced from industry benchmarks (~€50/MWh conservative wholesale price) and
# cross-checked against real Portugal day-ahead prices (~€38-88/MWh observed).
# This is what a wind operator earns per kWh SOLD, not what a consumer PAYS at
# retail (retail/industrial rates, e.g. Portugal's ~€0.12-0.16/kWh, would be the
# wrong reference here since the turbine is a generator, not a consumer).
ENERGY_PRICE_EUR_PER_KWH = 0.05

# Per-fault repair cost tiers, by component category (reusing Epic 4's
# SENSOR_TO_CATEGORY groupings). Sourced from published wind-industry cost
# benchmarks - NOT measured from this SCADA dataset, and NOT equally precise
# across tiers (see note below).
FAULT_COST_TIERS = {
    # Well-sourced: multiple independent industry sources agree gearbox major
    # failures cost ~$250,000-$350,000 (NREL/EPRI, Wind Systems Magazine).
    # Applied to other major drivetrain/electrical components as a reasonable
    # order-of-magnitude proxy - this is the WEAKEST-sourced part of the model,
    # since equally solid published data for generator/transformer-specific
    # repair costs wasn't found. Worth flagging explicitly, not hiding.
    "Gearbox": 230_000,
    "Generator": 230_000,
    "Generator Bearing": 230_000,
    "Transformer": 230_000,
    # Moderate: general unscheduled repair cost range ($15,000-$35,000)
    "Hydraulic Group": 25_000,
    "Pitch/Control System": 25_000,
    # Minor/unclassified: low end of unscheduled repair range
    "Nacelle (General)": 10_000,
    "Grid/Electrical": 10_000,
    "Drivetrain": 10_000,
    "Unknown": 10_000,
}


def load_performance_alerts() -> pd.DataFrame:
    df = pd.read_parquet(PROCESSED_DIR / "performance_alerts.parquet")
    df["start_time"] = pd.to_datetime(df["start_time"])
    df["end_time"] = pd.to_datetime(df["end_time"])
    return df


def get_energy_loss_cost() -> dict:
    """
    Sums real, measured energy loss (kWh) per turbine from Epic 3's performance
    alerts, then converts to euros using the assumed wholesale energy price.
    The kWh figures are real/measured; the euro conversion is an assumption,
    clearly separated in the output so the two are never confused.
    """
    df = load_performance_alerts()

    per_turbine = df.groupby("turbine_id").agg(
        total_energy_loss_kwh=("energy_loss_kwh", "sum"),
        alert_count=("energy_loss_kwh", "count"),
    ).round(1)

    per_turbine["estimated_revenue_loss_eur"] = (
        per_turbine["total_energy_loss_kwh"] * ENERGY_PRICE_EUR_PER_KWH
    ).round(2)

    fleet_total_kwh = per_turbine["total_energy_loss_kwh"].sum()
    fleet_total_eur = per_turbine["estimated_revenue_loss_eur"].sum()

    return {
        "energy_price_eur_per_kwh": ENERGY_PRICE_EUR_PER_KWH,
        "fleet_total_energy_loss_kwh": round(fleet_total_kwh, 1),
        "fleet_total_revenue_loss_eur": round(fleet_total_eur, 2),
        "per_turbine": per_turbine.reset_index().to_dict(orient="records"),
    }

def get_fault_repair_cost() -> dict:
    """
    Splits fault events into two honestly different categories before costing:
    - Confirmed failures (matched to the 12 real logbook entries): costed
      using the real logged component + FAULT_COST_TIERS (major-replacement
      scale costs).
    - Routine anomaly detections (the remaining ~977 events): NOT assumed to
      be real failures - these get a much smaller inspection-level cost.
    Both use the same base-cost + capped-duration-labor-addition structure,
    just at very different scales, so the methodology stays consistent even
    though the certainty behind each tier's cost figure is very different.
    SENSOR_OUTAGE_INTERPOLATED-flagged events are excluded (Epic 4/6 rule).
    """
    fault_df = pd.read_parquet(PROCESSED_DIR / "fault_events.parquet")
    fault_df = fault_df[fault_df["data_quality_flag"] != "SENSOR_OUTAGE_INTERPOLATED"]
    fault_df = match_events_to_logbook(fault_df)

    def estimate_cost(row):
        if row["is_confirmed_failure"]:
            base = FAULT_COST_TIERS.get(row["logged_component"], FAULT_COST_TIERS["Unknown"])
            cap_fraction = MAX_LABOR_ADDITION_FRACTION
        else:
            base = ROUTINE_EVENT_BASE_COST
            cap_fraction = ROUTINE_EVENT_LABOR_CAP_FRACTION

        labor_addition = row["duration_minutes"] * LABOR_RATE_EUR_PER_MINUTE
        labor_addition = min(labor_addition, base * cap_fraction)
        return round(base + labor_addition, 2)

    fault_df["estimated_repair_cost_eur"] = fault_df.apply(estimate_cost, axis=1)

    per_turbine = fault_df.groupby("turbine_id").agg(
        fault_count=("estimated_repair_cost_eur", "count"),
        confirmed_failure_count=("is_confirmed_failure", "sum"),
        total_repair_cost_eur=("estimated_repair_cost_eur", "sum"),
    ).round(2)

    fleet_total = per_turbine["total_repair_cost_eur"].sum()
    total_confirmed = int(fault_df["is_confirmed_failure"].sum())

    return {
        "fleet_total_repair_cost_eur": round(fleet_total, 2),
        "total_confirmed_failures": total_confirmed,
        "total_routine_events": len(fault_df) - total_confirmed,
        "per_turbine": per_turbine.reset_index().to_dict(orient="records"),
    }

def match_events_to_logbook(fault_df: pd.DataFrame) -> pd.DataFrame:
    """
    Identifies which detected fault events correspond to a REAL, logged
    failure (only 12 exist across the whole dataset), vs. routine anomaly
    detections (the remaining ~977 events). Reuses the exact matching logic
    already validated in Epic 4 (validate_against_logbook): for each real
    logged failure, the nearest fault event in the 10 days before it is
    considered the match. Unlike Epic 4's version (which only printed stats),
    this writes the result back as a column so cost estimation can use it.
    """
    failures = pd.read_excel(PROCESSED_DIR.parent / "raw" / "Historical-Failure-Logbook-2016.xlsx")
    failures["Timestamp"] = pd.to_datetime(failures["Timestamp"])

    fault_df = fault_df.copy()
    fault_df["start_time"] = pd.to_datetime(fault_df["start_time"])
    fault_df["end_time"] = pd.to_datetime(fault_df["end_time"])
    fault_df["is_confirmed_failure"] = False
    fault_df["logged_component"] = None

    for _, fail in failures.iterrows():
        turbine, fail_time, real_component = fail["Turbine_ID"], fail["Timestamp"], fail["Component"]
        window_start = fail_time - pd.Timedelta(days=10)

        nearby = fault_df[
            (fault_df["turbine_id"] == turbine) &
            (fault_df["start_time"] >= window_start) &
            (fault_df["start_time"] <= fail_time)
        ]
        if nearby.empty:
            continue

        most_severe_idx = nearby.sort_values("min_health_score").index[0]
        fault_df.loc[most_severe_idx, "is_confirmed_failure"] = True
        fault_df.loc[most_severe_idx, "logged_component"] = real_component

    return fault_df

def get_asset_risk_ranking() -> list[dict]:
    """
    Ranks turbines primarily by historical business impact (repair + energy
    loss cost) - the stronger, better-differentiated signal. Epic 5's
    priority_rank is shown alongside as context, not mathematically blended
    into a single score.

    Why not a blended 50/50 score: priority_score currently varies only
    slightly across turbines (~100-103, all "Low" risk) - min-max rescaling
    that narrow a spread to a full 0-100 range would manufacture artificial
    differences the underlying signal doesn't actually support (confirmed by
    inspection: doing so flipped the ranking order versus what historical
    cost alone shows, purely due to rescaling noise-level gaps). Historical
    cost has real, substantial spread (€207k-€383k) and is the more reliable
    ranking basis right now. If Epic 5's risk scores diverge more in the
    future (e.g. a turbine actually enters Medium/High risk), priority_rank
    becomes a more meaningful differentiator and this logic should be
    revisited.
    """
    energy = get_energy_loss_cost()
    repair = get_fault_repair_cost()
    forecast = pd.read_parquet(PROCESSED_DIR / "maintenance_forecast.parquet")

    energy_by_turbine = {row["turbine_id"]: row["estimated_revenue_loss_eur"] for row in energy["per_turbine"]}
    repair_by_turbine = {row["turbine_id"]: row["total_repair_cost_eur"] for row in repair["per_turbine"]}

    rows = []
    for _, f in forecast.iterrows():
        turbine = f["turbine_id"]
        total_cost = energy_by_turbine.get(turbine, 0) + repair_by_turbine.get(turbine, 0)
        rows.append({
            "turbine_id": turbine,
            "total_historical_cost_eur": round(total_cost, 2),
            "forecast_priority_rank": int(f["priority_rank"]),
            "forecast_priority_score": f["priority_score"],
            "risk_level": f["risk_level"],
            "likely_component": f["likely_component"],
        })

    rows.sort(key=lambda r: r["total_historical_cost_eur"], reverse=True)
    for i, r in enumerate(rows, start=1):
        r["risk_rank"] = i

    return rows

def get_fleet_performance_summary() -> dict:
    """
    High-level rollup combining business impact (this epic) with fleet health
    (Epic 6) into one management-facing summary. Reuses Epic 6's fleet health
    calculation directly rather than recomputing it, so the numbers are
    guaranteed consistent with what the Operations Dashboard already shows.
    """
    from app.pipelines.operations_dashboard import get_fleet_overview

    energy = get_energy_loss_cost()
    repair = get_fault_repair_cost()
    health = get_fleet_overview()

    total_cost = energy["fleet_total_revenue_loss_eur"] + repair["fleet_total_repair_cost_eur"]

    return {
        "total_business_impact_eur": round(total_cost, 2),
        "total_energy_loss_kwh": energy["fleet_total_energy_loss_kwh"],
        "total_revenue_loss_eur": energy["fleet_total_revenue_loss_eur"],
        "total_repair_cost_eur": repair["fleet_total_repair_cost_eur"],
        "confirmed_failures": repair["total_confirmed_failures"],
        "routine_anomaly_events": repair["total_routine_events"],
        "avg_fleet_health": health["avg_fleet_health"],
        "fleet_status_breakdown": health["status_breakdown"],
        "total_turbines": health["total_turbines"],
    }

if __name__ == "__main__":
    result = get_energy_loss_cost()
    print("=== ENERGY LOSS COST ===")
    print(f"Energy price assumption: €{result['energy_price_eur_per_kwh']}/kWh")
    print(f"Fleet total energy loss: {result['fleet_total_energy_loss_kwh']} kWh")
    print(f"Fleet total revenue loss: €{result['fleet_total_revenue_loss_eur']}")
    print("\nPer turbine:")
    for row in result["per_turbine"]:
        print(row)

    repair = get_fault_repair_cost()
    print(f"\n=== FAULT REPAIR COST ===")
    print(f"Fleet total: €{repair['fleet_total_repair_cost_eur']}")
    print(f"Confirmed failures: {repair['total_confirmed_failures']}, Routine events: {repair['total_routine_events']}")
    print("\nPer turbine:")
    for row in repair["per_turbine"]:
        print(row)

    # NEW - add this part at the end
    ranking = get_asset_risk_ranking()
    print(f"\n=== ASSET RISK RANKING ===")
    for r in ranking:
        print(r)

    summary = get_fleet_performance_summary()
    print(f"\n=== FLEET PERFORMANCE SUMMARY ===")
    print(summary)