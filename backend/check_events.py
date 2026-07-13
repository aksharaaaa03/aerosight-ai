import pandas as pd
df = pd.read_parquet('data/processed/maintenance_forecast.parquet')
print(df['risk_level'].unique())