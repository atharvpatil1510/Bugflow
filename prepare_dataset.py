
import pandas as pd
import os

# Load the downloaded dataset
df = pd.read_csv("data/bug_reports.csv")

# Keep the columns needed for severity prediction
df = df[["Short Description", "Severity Label"]].copy()

# Remove any rows with missing values in these columns
df = df.dropna(subset=["Short Description", "Severity Label"])

# Remove empty descriptions
df["Short Description"] = df["Short Description"].astype(str).str.strip()
df = df[df["Short Description"] != ""]

# Save the prepared dataset
os.makedirs("data", exist_ok=True)
df.to_csv("data/bug_reports_clean.csv", index=False)

print("Dataset preparation completed!")
print("Total usable reports:", len(df))
print("\nSeverity categories:")
print(df["Severity Label"].value_counts())
print("\nSaved to: data/bug_reports_clean.csv")
