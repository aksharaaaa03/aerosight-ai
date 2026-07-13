import pandas as pd
from app.pipelines.load_data import load_raw_scada

def diagnose_data_quality(df: pd.DataFrame) -> None:
    """
    Full diagnostic pass across ALL columns before any cleaning happens.
    """
    print("=== DUPLICATE CHECK ===")
    dupes = df.duplicated(subset=["Turbine_ID", "Timestamp"]).sum()
    print(f"Duplicate (Turbine_ID, Timestamp) rows: {dupes}")

    print("\n=== FULL MISSING VALUE SCAN (all 84 columns) ===")
    missing = df.isna().sum()
    missing_pct = (missing / len(df) * 100).round(2)
    report = pd.DataFrame({"missing_count": missing, "missing_pct": missing_pct})
    report = report[report["missing_count"] > 0].sort_values("missing_pct", ascending=False)
    if report.empty:
        print("No missing values found in any column.")
    else:
        print(report)

    print("\n=== SUSPECTED SENSOR-CEILING VALUES ===")
    # columns we flagged earlier as capping at 205
    suspect_cols = ["Gen_Bear_Temp_Avg", "Gen_Bear2_Temp_Avg",
                     "Gen_Phase1_Temp_Avg", "Gen_Phase2_Temp_Avg", "Gen_Phase3_Temp_Avg"]
    for col in suspect_cols:
        count_205 = (df[col] == 205).sum()
        pct_205 = count_205 / len(df) * 100
        print(f"  {col:25s} rows at exactly 205: {count_205} ({pct_205:.3f}%)")

SENSOR_CEILING_COLS = ["Gen_Bear_Temp_Avg", "Gen_Bear2_Temp_Avg",
                        "Gen_Phase1_Temp_Avg", "Gen_Phase2_Temp_Avg", "Gen_Phase3_Temp_Avg"]

def clean_dataset(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    before = len(df)

    # 1. Remove duplicate (Turbine_ID, Timestamp) rows
    df = df.drop_duplicates(subset=["Turbine_ID", "Timestamp"], keep="first")
    df = df.reset_index(drop=True)   # <-- close the index gaps NOW, before anything else
    print(f"Dropped {before - len(df)} duplicate rows.")

    # 2. Replace sensor-ceiling error values with NaN
    for col in SENSOR_CEILING_COLS:
        bad_count = (df[col] == 205).sum()
        df.loc[df[col] == 205, col] = pd.NA
        print(f"Flagged {bad_count} sensor-ceiling values in {col} as missing.")
        # Grd_Prod_ReactPwr_Avg: only 2 exact-1000.0 readings, likely instrument ceiling saturation
    reactpwr_ceiling_count = (df["Grd_Prod_ReactPwr_Avg"] == 1000.0).sum()
    df.loc[df["Grd_Prod_ReactPwr_Avg"] == 1000.0, "Grd_Prod_ReactPwr_Avg"] = pd.NA
    print(f"Flagged {reactpwr_ceiling_count} sensor-ceiling values in Grd_Prod_ReactPwr_Avg as missing.")

    # 3. Interpolate missing values per turbine, using time order
    df = df.sort_values(["Turbine_ID", "Timestamp"]).reset_index(drop=True)
    numeric_cols = df.select_dtypes(include="number").columns

    interpolated = (
        df.groupby("Turbine_ID")[numeric_cols]
          .apply(lambda g: g.interpolate(method="linear", limit_direction="both"))
    )
    interpolated = interpolated.droplevel(0)  # drop the Turbine_ID level, keep original row index
    df[numeric_cols] = interpolated

    remaining_na = df[numeric_cols].isna().sum().sum()
    print(f"Remaining missing values after interpolation: {remaining_na}")

    return df.reset_index(drop=True)

def locate_remaining_nulls(df: pd.DataFrame) -> None:
    print("\n=== LOCATING REMAINING NULLS AFTER CLEANING ===")
    numeric_cols = df.select_dtypes(include="number").columns
    null_counts = df[numeric_cols].isna().sum()
    null_counts = null_counts[null_counts > 0]
    print("By column:\n", null_counts)

    for col in null_counts.index:
        by_turbine = df[df[col].isna()]["Turbine_ID"].value_counts()
        print(f"\n{col} — nulls by turbine:\n{by_turbine}")

def diagnose_non_operational(df: pd.DataFrame) -> None:
    print("\n=== NON-OPERATIONAL DATA DIAGNOSIS ===")
    condition = (df["Grd_Prod_Pwr_Avg"] <= 0) & (df["Amb_WindSpeed_Avg"] >= 3.5)
    flagged = condition.sum()
    pct = flagged / len(df) * 100
    print(f"Rows flagged as non-operational: {flagged} ({pct:.2f}% of data)")

    print("\nBy turbine:")
    print(df[condition]["Turbine_ID"].value_counts())

    print("\nSample flagged rows (wind speed, power):")
    print(df[condition][["Turbine_ID", "Timestamp", "Amb_WindSpeed_Avg", "Grd_Prod_Pwr_Avg"]].head(10))

def flag_operational_status(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    non_operational = (df["Grd_Prod_Pwr_Avg"] <= 0) & (df["Amb_WindSpeed_Avg"] >= 3.5)
    df["is_operational"] = ~non_operational
    print(f"\nis_operational flag added. Operational: {df['is_operational'].sum()}, "
          f"Non-operational: {(~df['is_operational']).sum()}")
    return df

from sklearn.preprocessing import StandardScaler
import joblib
from pathlib import Path

NORMALIZE_COLS = [
    "Amb_WindSpeed_Avg", "Amb_WindDir_Relative_Avg", "Amb_Temp_Avg",
    "Grd_Prod_Pwr_Avg", "Grd_Prod_PsblePwr_Avg", "Grd_Prod_ReactPwr_Avg",
    "Gen_RPM_Avg", "Rtr_RPM_Avg",
    "Gen_Bear_Temp_Avg", "Gen_Bear2_Temp_Avg", "Gear_Bear_Temp_Avg", "Gear_Oil_Temp_Avg", "Hyd_Oil_Temp_Avg",
    "Gen_Phase1_Temp_Avg", "Gen_Phase2_Temp_Avg", "Gen_Phase3_Temp_Avg",
    "Blds_PitchAngle_Avg",
    "Nac_Temp_Avg", "Nac_Direction_Avg",
    "HVTrafo_Phase1_Temp_Avg", "HVTrafo_Phase2_Temp_Avg", "HVTrafo_Phase3_Temp_Avg",
]

MODELS_DIR = Path(__file__).resolve().parents[2] / "app" / "ml" / "saved"

def normalize_sensors(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    scaler = StandardScaler()
    operational_data = df[df["is_operational"]]
    scaler.fit(operational_data[NORMALIZE_COLS])

    normalized_values = scaler.transform(df[NORMALIZE_COLS])
    norm_cols = [f"{c}_norm" for c in NORMALIZE_COLS]
    df[norm_cols] = normalized_values

    joblib.dump(scaler, MODELS_DIR / "scaler.pkl")
    print(f"\nNormalization complete. Added {len(norm_cols)} normalized columns.")
    print(f"Scaler saved to {MODELS_DIR / 'scaler.pkl'}")

    return df

def check_timestamp_continuity(df: pd.DataFrame) -> None:
    print("\n=== TIMESTAMP CONTINUITY CHECK ===")
    for turbine in sorted(df["Turbine_ID"].unique()):
        sub = df[df["Turbine_ID"] == turbine].sort_values("Timestamp")
        full_range = pd.date_range(sub["Timestamp"].min(), sub["Timestamp"].max(), freq="10min")
        expected = len(full_range)
        actual = len(sub)
        missing = expected - actual
        pct = missing / expected * 100
        print(f"  {turbine}: expected {expected} intervals, have {actual}, missing {missing} ({pct:.2f}%)")

def check_normalized_sanity(df: pd.DataFrame) -> None:
    print("\n=== NORMALIZED COLUMN SANITY CHECK ===")
    norm_cols = [c for c in df.columns if c.endswith("_norm")]
    bad = df[norm_cols].isin([float("inf"), float("-inf")]).sum().sum()
    nan_count = df[norm_cols].isna().sum().sum()
    print(f"Infinite values in normalized columns: {bad}")
    print(f"NaN values in normalized columns: {nan_count}")
    print(f"Normalized value ranges (min to max across all norm columns): "
          f"{df[norm_cols].min().min():.2f} to {df[norm_cols].max().max():.2f}")
    
def find_extreme_outlier(df: pd.DataFrame) -> None:
    print("\n=== LOCATING EXTREME NORMALIZED OUTLIER ===")
    norm_cols = [c for c in df.columns if c.endswith("_norm")]
    max_per_col = df[norm_cols].max()
    worst_col = max_per_col.idxmax()
    worst_value = max_per_col.max()
    raw_col = worst_col.replace("_norm", "")
    print(f"Worst column: {worst_col} (z-score = {worst_value:.2f})")

    worst_row = df.loc[df[worst_col].idxmax()]
    print(f"\nRaw value in that row: {raw_col} = {worst_row[raw_col]}")
    print(f"Turbine: {worst_row['Turbine_ID']}, Timestamp: {worst_row['Timestamp']}")
    print(f"is_operational: {worst_row['is_operational']}")

    print(f"\nOverall stats for {raw_col} (operational rows only):")
    print(df[df["is_operational"]][raw_col].describe())

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"

def save_training_ready(df: pd.DataFrame) -> None:
    df = df.copy()
    df = df.drop(columns=["Unnamed: 0"], errors="ignore")
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # Full dataset — for dashboards
    full_path = PROCESSED_DIR / "processed_scada_full.parquet"
    df.to_parquet(full_path, index=False)
    print(f"\nSaved full processed dataset: {full_path} — shape {df.shape}")

    # Training-ready subset — operational only, normalized columns only
    norm_cols = [c for c in df.columns if c.endswith("_norm")]
    training_df = df[df["is_operational"]][["Turbine_ID", "Timestamp"] + norm_cols]
    training_path = PROCESSED_DIR / "training_ready.parquet"
    training_df.to_parquet(training_path, index=False)
    print(f"Saved training-ready dataset: {training_path} — shape {training_df.shape}")

if __name__ == "__main__":
    df = load_raw_scada()
    diagnose_data_quality(df)
    print("\n=== APPLYING CLEANING ===")
    df_clean = clean_dataset(df)
    print(f"\nFinal shape after cleaning: {df_clean.shape}")
    locate_remaining_nulls(df_clean)
    diagnose_non_operational(df_clean)
    df_flagged = flag_operational_status(df_clean)
    df_normalized = normalize_sensors(df_flagged)
    print(f"\nFinal dataset shape (with normalized columns): {df_normalized.shape}")
    print(df_normalized[["Turbine_ID", "Amb_WindSpeed_Avg", "Amb_WindSpeed_Avg_norm"]].head())
    check_timestamp_continuity(df_normalized)
    check_normalized_sanity(df_normalized)
    find_extreme_outlier(df_normalized)
    save_training_ready(df_normalized)



