import pandas as pd
import numpy as np
from pathlib import Path

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"

def load_merged_data() -> pd.DataFrame:
    scada = pd.read_parquet(PROCESSED_DIR / "processed_scada_full.parquet")
    health = pd.read_parquet(PROCESSED_DIR / "health_scored.parquet")

    df = scada.merge(health[["Turbine_ID", "Timestamp", "health_score", "health_status"]],
                      on=["Turbine_ID", "Timestamp"], how="left")

    print(f"Merged dataset shape: {df.shape}")
    print(f"Rows with health_status assigned: {df['health_status'].notna().sum()}")
    return df

def compute_power_ratio(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Empirically chosen threshold (see find_psble_pwr_threshold diagnostic):
    # ratio std drops sharply and stabilizes above ~50 kW possible power,
    # avoiding division-by-near-zero instability seen at low PsblePwr values
    valid_psble = df["Grd_Prod_PsblePwr_Avg"] > 50

    df["power_ratio"] = np.nan
    df.loc[valid_psble, "power_ratio"] = (
        df.loc[valid_psble, "Grd_Prod_Pwr_Avg"] / df.loc[valid_psble, "Grd_Prod_PsblePwr_Avg"]
    )

    print(f"\nRows with valid power_ratio (PsblePwr > 50 kW): {df['power_ratio'].notna().sum()}")
    print(f"Rows excluded (PsblePwr <= 50 kW): {(~valid_psble).sum()}")
    print("\nPower ratio distribution (operational rows only):")
    print(df.loc[df["is_operational"], "power_ratio"].describe())

    return df

def diagnose_power_ratio_issues(df: pd.DataFrame) -> None:
    print("\n=== DIAGNOSING PsblePwr <= 0 EXCLUSIONS ===")
    excluded = df[df["Grd_Prod_PsblePwr_Avg"] <= 0]
    print(f"Total excluded: {len(excluded)}")
    print(f"Of those, is_operational=True: {excluded['is_operational'].sum()}")
    print(f"Wind speed stats for excluded rows:\n{excluded['Amb_WindSpeed_Avg'].describe()}")

    print("\n=== DIAGNOSING EXTREME POWER RATIO OUTLIERS ===")
    op = df[df["is_operational"]].dropna(subset=["power_ratio"])
    extreme = op[op["power_ratio"] < -1]
    print(f"Rows with power_ratio < -1: {len(extreme)}")
    print(extreme[["Turbine_ID", "Timestamp", "Amb_WindSpeed_Avg", "Grd_Prod_Pwr_Avg", "Grd_Prod_PsblePwr_Avg", "power_ratio"]].sort_values("power_ratio").head(10))

def find_psble_pwr_threshold(df: pd.DataFrame) -> None:
    op = df[df["is_operational"]].copy()
    print("\n=== FINDING SENSIBLE PsblePwr THRESHOLD ===")
    for threshold in [0.1, 1, 5, 10, 20, 50, 100]:
        subset = op[op["Grd_Prod_PsblePwr_Avg"] > threshold]
        ratio = subset["Grd_Prod_Pwr_Avg"] / subset["Grd_Prod_PsblePwr_Avg"]
        print(f"Threshold > {threshold:>5}: {len(subset):>7} rows | "
              f"ratio mean={ratio.mean():.3f} std={ratio.std():.3f} min={ratio.min():.1f} max={ratio.max():.1f}")
        
def diagnose_underperformance_threshold(df: pd.DataFrame) -> None:
    op = df[df["is_operational"] & df["power_ratio"].notna()].copy()
    print("\n=== UNDERPERFORMANCE THRESHOLD CHECK ===")
    for cutoff in [0.9, 0.8, 0.7, 0.6, 0.5]:
        pct = (op["power_ratio"] < cutoff).mean() * 100
        print(f"power_ratio < {cutoff}: {pct:.2f}% of valid operational readings")

def diagnose_underperformance_duration(df: pd.DataFrame) -> None:
    df = df.copy()
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    df = df.sort_values(["Turbine_ID", "Timestamp"])

    op = df[df["is_operational"] & df["power_ratio"].notna()].copy()
    op["is_underperforming"] = op["power_ratio"] < 0.8

    print("\n=== UNDERPERFORMANCE RUN-LENGTH CHECK ===")
    run_lengths = []
    for turbine, group in op.groupby("Turbine_ID"):
        flags = group["is_underperforming"].values
        current_run = 0
        for flag in flags:
            if flag:
                current_run += 1
            else:
                if current_run > 0:
                    run_lengths.append(current_run)
                current_run = 0
        if current_run > 0:
            run_lengths.append(current_run)

    run_lengths = pd.Series(run_lengths)
    print(f"Total underperformance episodes: {len(run_lengths)}")
    print(f"Run length stats (in 10-min intervals):\n{run_lengths.describe()}")
    print(f"\nEpisodes lasting >= 6 intervals (1hr+): {(run_lengths >= 6).sum()} ({(run_lengths>=6).mean()*100:.1f}%)")
    print(f"Episodes lasting >= 3 intervals (30min+): {(run_lengths >= 3).sum()} ({(run_lengths>=3).mean()*100:.1f}%)")
    print(f"Episodes lasting only 1 interval (10min): {(run_lengths == 1).sum()} ({(run_lengths==1).mean()*100:.1f}%)")


def flag_continuous_underperformance(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    df = df.sort_values(["Turbine_ID", "Timestamp"]).reset_index(drop=True)

    df["is_underperforming_raw"] = (df["is_operational"]) & (df["power_ratio"] < 0.8)
    df["is_continuous_underperformance"] = False

    for turbine, group in df.groupby("Turbine_ID"):
        idx = group.index
        flags = group["is_underperforming_raw"].values
        run_start = None
        for i, flag in enumerate(flags):
            if flag and run_start is None:
                run_start = i
            elif not flag and run_start is not None:
                if i - run_start >= 3:
                    df.loc[idx[run_start:i], "is_continuous_underperformance"] = True
                run_start = None
        if run_start is not None and len(flags) - run_start >= 3:
            df.loc[idx[run_start:], "is_continuous_underperformance"] = True

    total_flagged = df["is_continuous_underperformance"].sum()
    print(f"\nRows flagged as CONTINUOUS underperformance (30+ min episodes): {total_flagged}")
    print(f"As % of valid operational readings: {total_flagged / df['power_ratio'].notna().sum() * 100:.2f}%")
    print("\nBy turbine:")
    print(df[df["is_continuous_underperformance"]]["Turbine_ID"].value_counts())

    return df

def calculate_energy_loss(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Each row = 10 minutes = 1/6 hour. Energy (kWh) = Power (kW) * time (hours)
    df["energy_loss_kwh"] = np.nan
    mask = df["power_ratio"].notna()
    shortfall_kw = (df.loc[mask, "Grd_Prod_PsblePwr_Avg"] - df.loc[mask, "Grd_Prod_Pwr_Avg"]).clip(lower=0)
    df.loc[mask, "energy_loss_kwh"] = shortfall_kw * (10 / 60)

    total_loss = df["energy_loss_kwh"].sum()
    continuous_loss = df.loc[df["is_continuous_underperformance"], "energy_loss_kwh"].sum()

    print(f"\nTotal energy loss across all valid readings: {total_loss:,.1f} kWh")
    print(f"Energy loss specifically from CONTINUOUS underperformance episodes: {continuous_loss:,.1f} kWh")
    print(f"As % of total loss: {continuous_loss/total_loss*100:.2f}%")

    print("\nEnergy loss by turbine (continuous underperformance only):")
    print(df[df["is_continuous_underperformance"]].groupby("Turbine_ID")["energy_loss_kwh"].sum().round(1))

    return df

def generate_performance_alerts(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["Turbine_ID", "Timestamp"]).reset_index(drop=True)
    alerts = []

    for turbine, group in df[df["is_continuous_underperformance"]].groupby("Turbine_ID"):
        group = group.sort_values("Timestamp")
        gaps = group["Timestamp"].diff() > pd.Timedelta(minutes=10)
        episode_id = gaps.cumsum()

        for _, episode in group.groupby(episode_id):
            alerts.append({
                "turbine_id": turbine,
                "start_time": episode["Timestamp"].min(),
                "end_time": episode["Timestamp"].max(),
                "duration_minutes": len(episode) * 10,
                "avg_power_ratio": round(episode["power_ratio"].mean(), 3),
                "min_power_ratio": round(episode["power_ratio"].min(), 3),
                "energy_loss_kwh": round(episode["energy_loss_kwh"].sum(), 1),
            })

    alerts_df = pd.DataFrame(alerts).sort_values("energy_loss_kwh", ascending=False)
    print(f"\nTotal performance alerts generated: {len(alerts_df)}")
    print("\nTop 10 alerts by energy loss:")
    print(alerts_df.head(10).to_string(index=False))

    return alerts_df

def build_power_curve_data(df: pd.DataFrame, turbine_id: str, sample_size: int = 2000) -> pd.DataFrame:
    turbine_df = df[(df["Turbine_ID"] == turbine_id) & df["power_ratio"].notna()].copy()

    # Category for coloring: keep this consistent with our verified definitions
    turbine_df["performance_category"] = "Normal"
    turbine_df.loc[turbine_df["is_continuous_underperformance"], "performance_category"] = "Underperforming"

    normal = turbine_df[turbine_df["performance_category"] == "Normal"]
    underperf = turbine_df[turbine_df["performance_category"] == "Underperforming"]

    # Sample normal points (there are many), but KEEP ALL underperforming points (rare, must not lose them)
    n_normal_sample = min(len(normal), sample_size)
    normal_sample = normal.sample(n=n_normal_sample, random_state=42)

    combined = pd.concat([normal_sample, underperf])
    print(f"\n{turbine_id} power curve data: {len(normal_sample)} normal (sampled) + {len(underperf)} underperforming (kept all) = {len(combined)} total points")

    return combined[["Amb_WindSpeed_Avg", "Grd_Prod_Pwr_Avg", "performance_category", "Timestamp"]]

def build_expected_curve_line(df: pd.DataFrame) -> pd.DataFrame:
    # Use only Healthy + operational readings to define what "expected" looks like
    clean = df[(df["is_operational"]) & (df["health_status"] == "Healthy")].copy()

    bins = np.arange(0, 26, 1)  # 1 m/s bins, 0 to 25
    clean["wind_bin"] = pd.cut(clean["Amb_WindSpeed_Avg"], bins=bins)
    curve = clean.groupby("wind_bin", observed=True)["Grd_Prod_Pwr_Avg"].median().reset_index()
    curve["wind_speed_mid"] = curve["wind_bin"].apply(lambda b: b.mid)

    print(f"\nExpected power curve computed across {len(curve)} wind-speed bins")
    print(curve[["wind_speed_mid", "Grd_Prod_Pwr_Avg"]].to_string(index=False))

    return curve[["wind_speed_mid", "Grd_Prod_Pwr_Avg"]].rename(columns={"Grd_Prod_Pwr_Avg": "expected_power"})

def build_underperforming_turbines_list(alerts_df: pd.DataFrame) -> pd.DataFrame:
    summary = alerts_df.groupby("turbine_id").agg(
        total_alerts=("turbine_id", "count"),
        total_energy_loss_kwh=("energy_loss_kwh", "sum"),
        avg_power_ratio_during_alerts=("avg_power_ratio", "mean"),
        worst_power_ratio=("min_power_ratio", "min"),
        total_downtime_minutes=("duration_minutes", "sum"),
    ).reset_index()

    summary["total_energy_loss_kwh"] = summary["total_energy_loss_kwh"].round(1)
    summary["avg_power_ratio_during_alerts"] = summary["avg_power_ratio_during_alerts"].round(3)
    summary = summary.sort_values("total_energy_loss_kwh", ascending=False)

    print("\n=== UNDERPERFORMING TURBINES SUMMARY ===")
    print(summary.to_string(index=False))

    return summary

def save_power_performance_results(df: pd.DataFrame, alerts_df: pd.DataFrame,
                                     underperforming_summary: pd.DataFrame, curve_line: pd.DataFrame) -> None:
    output_cols = ["Turbine_ID", "Timestamp", "Amb_WindSpeed_Avg", "Grd_Prod_Pwr_Avg",
                   "Grd_Prod_PsblePwr_Avg", "power_ratio", "is_continuous_underperformance", "energy_loss_kwh"]
    df[output_cols].to_parquet(PROCESSED_DIR / "power_performance.parquet", index=False)
    alerts_df.to_parquet(PROCESSED_DIR / "performance_alerts.parquet", index=False)
    underperforming_summary.to_parquet(PROCESSED_DIR / "underperforming_turbines.parquet", index=False)
    curve_line.to_parquet(PROCESSED_DIR / "expected_power_curve.parquet", index=False)

    print(f"\nSaved: power_performance.parquet — {df[output_cols].shape}")
    print(f"Saved: performance_alerts.parquet — {alerts_df.shape}")
    print(f"Saved: underperforming_turbines.parquet — {underperforming_summary.shape}")
    print(f"Saved: expected_power_curve.parquet — {curve_line.shape}")


if __name__ == "__main__":
    df = load_merged_data()
    df = compute_power_ratio(df)
    diagnose_underperformance_threshold(df)
    diagnose_underperformance_duration(df)
    df = flag_continuous_underperformance(df)
    df = calculate_energy_loss(df)
    alerts_df = generate_performance_alerts(df)
    curve_line = build_expected_curve_line(df)
    scatter_data = build_power_curve_data(df, turbine_id="T07")  # T07: our most underperformance-flagged turbine
    underperforming_summary = build_underperforming_turbines_list(alerts_df)
    save_power_performance_results(df, alerts_df, underperforming_summary, curve_line)

