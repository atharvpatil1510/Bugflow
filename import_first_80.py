
import pandas as pd
from db import get_connection

CSV_FILE = "data/bug_reports.csv"

df = pd.read_csv(CSV_FILE, nrows=80)
df = df.dropna(subset=["Short Description"])

conn = get_connection()

try:
    cur = conn.cursor()
    updated = 0
    inserted = 0

    for _, row in df.iterrows():
        project = str(row["Project"]).strip()
        bug_id = str(row["Bug ID"]).strip()
        title = str(row["Short Description"]).strip()
        severity = str(row["Severity Label"]).strip().lower()
        resolution = str(row["Resolution Status"]).strip().upper()

        if not title or title.lower() == "nan":
            continue

        # Convert dataset resolution to BugFlow status
        status = "Resolved" if resolution == "FIXED" else "Open"

        # Check whether this bug was already imported
        cur.execute(
            """
            SELECT id
            FROM public.bug_reports
            WHERE title = %s
            ORDER BY id
            LIMIT 1
            """,
            (title[:200],)
        )

        existing = cur.fetchone()

        if existing:
            # Correct the existing record with real dataset values
            cur.execute(
                """
                UPDATE public.bug_reports
                SET project = %s,
                    title = %s,
                    description = %s,
                    severity = %s,
                    status = %s
                WHERE id = %s
                """,
                (
                    project[:150],
                    title[:200],
                    f"Source Bug ID: {bug_id}\n\n{title}",
                    severity[:30],
                    status,
                    existing[0]
                )
            )
            updated += 1
        else:
            cur.execute(
                """
                INSERT INTO public.bug_reports
                    (project, title, description, severity, status)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    project[:150],
                    title[:200],
                    f"Source Bug ID: {bug_id}\n\n{title}",
                    severity[:30],
                    status
                )
            )
            inserted += 1

    conn.commit()

    print("Dataset processing completed!")
    print("Existing records updated:", updated)
    print("New records inserted:", inserted)
    print("Source rows processed:", len(df))

except Exception as e:
    conn.rollback()
    print("Import failed:", e)

finally:
    conn.close()
