import pandas as pd
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"

def load_raw_scada() -> pd.DataFrame:
    """
    Loads both years of EDP SCADA signal data and combines them
    into a single continuous dataset, tagged by turbine.
    """
    df_2016 = pd.read_csv(RAW_DIR / "Wind-Turbine-SCADA-signals-2016.csv")
    df_2017 = pd.read_csv(RAW_DIR / "Wind-Turbine-SCADA-signals-2017_0.csv")

    combined = pd.concat([df_2016, df_2017], ignore_index=True)
    combined["Timestamp"] = pd.to_datetime(combined["Timestamp"])
    combined = combined.sort_values(["Turbine_ID", "Timestamp"]).reset_index(drop=True)

    return combined

REQUIRED_FIELDS = [
    "Turbine_ID", "Timestamp",
    "Amb_WindSpeed_Avg", "Amb_WindDir_Relative_Avg", "Amb_Temp_Avg",
    "Grd_Prod_Pwr_Avg", "Grd_Prod_PsblePwr_Avg", "Grd_Prod_ReactPwr_Avg",
    "Gen_RPM_Avg", "Rtr_RPM_Avg",
    "Gen_Bear_Temp_Avg", "Gen_Bear2_Temp_Avg", "Gear_Bear_Temp_Avg", "Gear_Oil_Temp_Avg", "Hyd_Oil_Temp_Avg",
    "Gen_Phase1_Temp_Avg", "Gen_Phase2_Temp_Avg", "Gen_Phase3_Temp_Avg",
    "Blds_PitchAngle_Avg",
    "Nac_Temp_Avg", "Nac_Direction_Avg",
    "HVTrafo_Phase1_Temp_Avg", "HVTrafo_Phase2_Temp_Avg", "HVTrafo_Phase3_Temp_Avg",
]

def validate_required_fields(df: pd.DataFrame) -> None:
    """
    Confirms all required sensor fields exist and are numeric
    (except Turbine_ID/Timestamp), and reports missing-value %.
    """
    missing_cols = [c for c in REQUIRED_FIELDS if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required fields: {missing_cols}")

    print("✅ All required fields present.\n")
    print("Field validation report:")
    for col in REQUIRED_FIELDS:
        if col in ("Turbine_ID", "Timestamp"):
            continue
        dtype = df[col].dtype
        missing_pct = df[col].isna().mean() * 100
        print(f"  {col:25s} dtype={str(dtype):10s} missing={missing_pct:.2f}%  "
              f"min={df[col].min():.2f}  max={df[col].max():.2f}")


if __name__ == "__main__":
    df = load_raw_scada()
    print("Total rows:", len(df))
    print("Turbines found:", sorted(df["Turbine_ID"].unique()))
    print("Date range:", df["Timestamp"].min(), "to", df["Timestamp"].max())
    print("Total columns:", len(df.columns))
    print("\nColumn list:\n", list(df.columns))
    print("\nFirst 3 rows:\n", df.head(3))
    validate_required_fields(df)