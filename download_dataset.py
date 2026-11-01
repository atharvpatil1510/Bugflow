
from datasets import load_dataset
import os

print("Downloading BugFlow dataset...")

dataset = load_dataset(
    "AliArshad/Bugzilla_Eclipse_Bug_Reports_Dataset",
    split="train"
)

os.makedirs("data", exist_ok=True)

dataset.to_csv("data/bug_reports.csv", index=False)

print("Dataset downloaded successfully!")
print("Total records:", len(dataset))
print("Columns:", dataset.column_names)
print("Saved to: data/bug_reports.csv")
