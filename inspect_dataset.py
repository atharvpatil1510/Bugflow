
import pandas as pd

df = pd.read_csv("data/bug_reports.csv")

print("\n--- DATASET INFORMATION ---")
print("Total records:", len(df))
print("Total columns:", len(df.columns))

print("\n--- COLUMN NAMES ---")
print(df.columns.tolist())

print("\n--- FIRST 5 BUG REPORTS ---")
print(df.head().to_string(index=False))

print("\n--- SEVERITY DISTRIBUTION ---")
print(df["Severity Label"].value_counts())

print("\n--- MISSING VALUES ---")
print(df.isnull().sum())
