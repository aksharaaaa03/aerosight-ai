import pandas as pd
from pathlib import Path
from sklearn.ensemble import IsolationForest
import joblib
import numpy as np
import json

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
MODELS_DIR = Path(__file__).resolve().parents[2] / "app" / "ml" / "saved"
FAILURE_LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "raw" / "Historical-Failure-Logbook-2016.xlsx"


HEALTH_FEATURES = [
    "Gen_RPM_Avg", "Rtr_RPM_Avg",
    "Gen_Bear_Temp_Avg", "Gen_Bear2_Temp_Avg", "Gear_Bear_Temp_Avg",
    "Gear_Oil_Temp_Avg", "Hyd_Oil_Temp_Avg",
    "Gen_Phase1_Temp_Avg", "Gen_Phase2_Temp_Avg", "Gen_Phase3_Temp_Avg",
    "HVTrafo_Phase1_Temp_Avg", "HVTrafo_Phase2_Temp_Avg", "HVTrafo_Phase3_Temp_Avg",
    "Blds_PitchAngle_Avg", "Nac_Temp_Avg", "Grd_Prod_ReactPwr_Avg",
    "Amb_WindSpeed_Avg",
]
HEALTH_FEATURES_NORM = [f"{c}_norm" for c in HEALTH_FEATURES]

def load_processed_data() -> pd.DataFrame:
    df = pd.read_parquet(PROCESSED_DIR / "processed_scada_full.parquet")
    print(f"Loaded processed data: {df.shape}")
    missing = [c for c in HEALTH_FEATURES_NORM if c not in df.columns]
    if missing:
        raise ValueError(f"Missing expected normalized health features: {missing}")
    print(f"All {len(HEALTH_FEATURES_NORM)} health features confirmed present.")
    return df

def train_health_model(df: pd.DataFrame):
    operational = df[df["is_operational"]]
    X_train = operational[HEALTH_FEATURES_NORM]

    print(f"Training Isolation Forest on {len(X_train)} operational rows, {len(HEALTH_FEATURES_NORM)} features...")

    model = IsolationForest(
        n_estimators=200,
        contamination=0.05,   # assume ~5% of operational data still looks "unusually rough"
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODELS_DIR / "health_model.pkl")
    print(f"Model saved to {MODELS_DIR / 'health_model.pkl'}")

    return model

def generate_health_scores(df: pd.DataFrame, model) -> pd.DataFrame:
    df = df.copy()
    operational_mask = df["is_operational"]

    X = df.loc[operational_mask, HEALTH_FEATURES_NORM]
    raw_scores = model.score_samples(X)  # higher = more normal, lower = more anomalous

    # Rescale raw scores to 0-100 using min-max across this dataset
    min_score, max_score = raw_scores.min(), raw_scores.max()
    health_scores = (raw_scores - min_score) / (max_score - min_score) * 100

    df["health_score"] = np.nan  # non-operational rows get no score
    df.loc[operational_mask, "health_score"] = health_scores

    print("\nHealth score distribution (operational rows only):")
    print(df.loc[operational_mask, "health_score"].describe())
    return df

def calculate_dynamic_thresholds(df: pd.DataFrame):
    scores = df["health_score"].dropna()
    mean, std = scores.mean(), scores.std()

    healthy_threshold = mean - 1 * std
    critical_threshold = mean - 2 * std

    print(f"\nMean: {mean:.2f}, Std Dev: {std:.2f}")
    print(f"Healthy threshold (mean - 1*std): {healthy_threshold:.2f}")
    print(f"Critical threshold (mean - 2*std): {critical_threshold:.2f}")

    healthy_pct = (scores >= healthy_threshold).mean() * 100
    warning_pct = ((scores < healthy_threshold) & (scores >= critical_threshold)).mean() * 100
    critical_pct = (scores < critical_threshold).mean() * 100

    print(f"\nResulting distribution:")
    print(f"  Healthy:  {healthy_pct:.2f}%")
    print(f"  Warning:  {warning_pct:.2f}%")
    print(f"  Critical: {critical_pct:.2f}%")

    return healthy_threshold, critical_threshold

def classify_health(df: pd.DataFrame, healthy_thresh: float, critical_thresh: float) -> pd.DataFrame:
    df = df.copy()

    def classify(score):
        if pd.isna(score):
            return None
        elif score >= healthy_thresh:
            return "Healthy"
        elif score >= critical_thresh:
            return "Warning"
        else:
            return "Critical"

    df["health_status"] = df["health_score"].apply(classify)

    print("\nHealth status distribution (operational rows only):")
    print(df["health_status"].value_counts())
    print("\nAs percentage:")
    print((df["health_status"].value_counts(normalize=True) * 100).round(2))

    return df

def validate_against_failures(df: pd.DataFrame) -> None:
    failures = pd.read_excel(FAILURE_LOG_PATH)
    failures["Timestamp"] = pd.to_datetime(failures["Timestamp"])
    known_turbines = df["Turbine_ID"].unique()
    usable_failures = failures[failures["Turbine_ID"].isin(known_turbines)].reset_index(drop=True)

    print(f"\nTotal logged failures: {len(failures)}")
    print(f"Usable (turbine present in our data): {len(usable_failures)}")

    print("\n=== VALIDATION (clean baseline, excludes all failure-adjacent periods) ===")
    results = []
    for _, row in usable_failures.iterrows():
        turbine, fail_time, component = row["Turbine_ID"], row["Timestamp"], row["Component"]
        turbine_data = df[df["Turbine_ID"] == turbine].copy()

        # Exclude any timestamp within 14 days of ANY known failure for this turbine, to get a clean baseline
        turbine_failures = usable_failures[usable_failures["Turbine_ID"] == turbine]["Timestamp"]
        clean_mask = pd.Series(True, index=turbine_data.index)
        for ft in turbine_failures:
            clean_mask &= ~turbine_data["Timestamp"].between(ft - pd.Timedelta(days=14), ft + pd.Timedelta(days=14))
        clean_baseline = turbine_data.loc[clean_mask, "health_score"].mean()

        window_start = fail_time - pd.Timedelta(days=7)
        before_window = turbine_data[(turbine_data["Timestamp"] >= window_start) & (turbine_data["Timestamp"] < fail_time)]
        pre_failure_avg = before_window["health_score"].mean()

        drop = clean_baseline - pre_failure_avg if pd.notna(pre_failure_avg) else None
        results.append(drop)

        print(f"\n{turbine} — {component} — failed {fail_time.date()}")
        print(f"  Clean baseline (excl. all failure periods): {clean_baseline:.1f}")
        print(f"  Avg health in 7 days BEFORE failure: {pre_failure_avg:.1f}" if pd.notna(pre_failure_avg) else "  No data")
        if drop is not None:
            print(f"  Drop: {drop:.1f} points {'✅ detected' if drop > 5 else '⚠️ weak/no signal'}")

    valid_drops = [d for d in results if d is not None]
    detected = sum(1 for d in valid_drops if d > 5)
    print(f"\n=== SUMMARY ===")
    print(f"Events with meaningful pre-failure health drop (>5 pts): {detected}/{len(valid_drops)} ({detected/len(valid_drops)*100:.1f}%)")


def save_health_results(df: pd.DataFrame) -> None:
    output_cols = ["Turbine_ID", "Timestamp", "health_score", "health_status"]
    health_df = df[output_cols].copy()

    output_path = PROCESSED_DIR / "health_scored.parquet"
    health_df.to_parquet(output_path, index=False)
    print(f"\nSaved health results: {output_path} — shape {health_df.shape}")


def save_thresholds(healthy_thresh: float, critical_thresh: float) -> None:
    thresholds = {"healthy_threshold": healthy_thresh, "critical_threshold": critical_thresh}
    path = MODELS_DIR / "health_thresholds.json"
    with open(path, "w") as f:
        json.dump(thresholds, f)
    print(f"Saved thresholds to {path}: {thresholds}")

if __name__ == "__main__":
    df = load_processed_data()
    model = train_health_model(df)
    df_scored = generate_health_scores(df, model)
    healthy_thresh, critical_thresh = calculate_dynamic_thresholds(df_scored)
    save_thresholds(healthy_thresh, critical_thresh)
    df_classified = classify_health(df_scored, healthy_thresh, critical_thresh)
    validate_against_failures(df_classified)
    save_health_results(df_classified)