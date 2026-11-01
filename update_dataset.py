
import csv
from datetime import datetime
from pathlib import Path

from db import get_connection


# --------------------------------------------------
# BugFlow dataset update
# Updates existing bugs first and inserts if needed.
# Does not delete any records or user accounts.
# --------------------------------------------------

TARGET_COUNT = 200

PROJECTS = [
    "Online Shopping Application",
    "Banking Management System",
    "College Management System",
    "Hospital Management System",
    "Library Management System",
    "Employee Payroll System",
    "Hotel Booking System",
    "Inventory Management System",
    "Food Delivery Application",
    "Vehicle Rental System",
]

BUGS = [
    ("Login button does not respond", "Clicking Login does not submit valid credentials.", "High"),
    ("Password reset email is not sent", "The password recovery email is not received.", "Medium"),
    ("Invalid password is accepted", "Authentication does not reject an incorrect password.", "Critical"),
    ("Dashboard data loads slowly", "Dashboard information takes too long to appear.", "Medium"),
    ("Search returns incorrect results", "Search results do not match the entered keywords.", "Medium"),
    ("Form accepts missing required fields", "The form can be submitted without required values.", "High"),
    ("Logout does not clear the session", "The previous session remains accessible after logout.", "Critical"),
    ("Mobile layout overlaps buttons", "Some controls overlap on narrow screens.", "Low"),
    ("Report export creates an empty file", "Exported reports contain no expected data.", "Medium"),
    ("Duplicate records are created", "Submitting the same request twice creates duplicates.", "High"),
    ("Date filter shows incorrect records", "The date filter returns results outside the selected range.", "Medium"),
    ("Error message is not displayed", "The application fails without showing a helpful message.", "Low"),
    ("User profile changes are not saved", "Updated profile information is not persisted.", "Medium"),
    ("Pagination skips records", "Moving between pages skips some records.", "Medium"),
    ("File upload rejects valid documents", "Supported files are incorrectly rejected.", "High"),
    ("Notification count is incorrect", "The notification badge shows the wrong count.", "Low"),
    ("Application crashes on empty input", "Submitting empty input causes an unexpected error.", "Critical"),
    ("Role permissions are not enforced", "A user can access a restricted action.", "Critical"),
    ("Sorting order is incorrect", "The table does not sort records as selected.", "Low"),
    ("Confirmation message is missing", "Successful operations do not show confirmation.", "Low"),
]

STATUSES = ["Open", "In Progress", "Resolved"]


def main():
    connection = get_connection()
    cursor = connection.cursor()

    try:
        # Read current data and create a backup before changes.
        cursor.execute("""
            SELECT id, project, title, description, severity, status,
                   created_at, assigned_to_user_id
            FROM public.bug_reports
            ORDER BY id;
        """)
        old_rows = cursor.fetchall()
        column_names = [item[0] for item in cursor.description]

        backup_file = Path(__file__).resolve().parent / (
            "bug_reports_backup_" +
            datetime.now().strftime("%Y%m%d_%H%M%S") + ".csv"
        )

        with backup_file.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file)
            writer.writerow(column_names)
            writer.writerows(old_rows)

        print(f"Backup created: {backup_file}")
        print(f"Existing bug records: {len(old_rows)}")

        # Use real user IDs already present in the database.
        cursor.execute("""
            SELECT user_id
            FROM public.users
            ORDER BY user_id;
        """)
        user_ids = [row[0] for row in cursor.fetchall()]

        if not user_ids:
            print(
                "No users found. Bug reports will remain unassigned."
            )

        # Use the first 200 existing rows, if available.
        # Extra records are preserved; nothing is deleted.
        rows_to_update = old_rows[:TARGET_COUNT]
        updated = 0
        inserted = 0

        for i in range(TARGET_COUNT):
            project = PROJECTS[i % len(PROJECTS)]
            title, description, severity = BUGS[i % len(BUGS)]
            status = STATUSES[(i // 2) % len(STATUSES)]

            # Make each title distinct.
            title = f"{title} - Case {i + 1:03d}"

            # Assign only existing users.
            assigned_user_id = (
                user_ids[i % len(user_ids)] if user_ids else None
            )

            if i < len(rows_to_update):
                bug_id = rows_to_update[i][0]

                cursor.execute("""
                    UPDATE public.bug_reports
                    SET project = %s,
                        title = %s,
                        description = %s,
                        severity = %s,
                        status = %s,
                        assigned_to_user_id = %s
                    WHERE id = %s;
                """, (
                    project,
                    title,
                    description,
                    severity,
                    status,
                    assigned_user_id,
                    bug_id,
                ))
                updated += cursor.rowcount

            else:
                cursor.execute("""
                    INSERT INTO public.bug_reports
                        (project, title, description, severity,
                         status, assigned_to_user_id)
                    VALUES (%s, %s, %s, %s, %s, %s);
                """, (
                    project,
                    title,
                    description,
                    severity,
                    status,
                    assigned_user_id,
                ))
                inserted += 1

        # Verify the changes before committing.
        cursor.execute("""
            SELECT COUNT(*), COUNT(DISTINCT project)
            FROM public.bug_reports
            WHERE title LIKE '% - Case %';
        """)
        generated_count, project_count = cursor.fetchone()

        if generated_count != TARGET_COUNT or project_count != len(PROJECTS):
            raise RuntimeError(
                "Verification failed. Changes will be rolled back."
            )

        connection.commit()

        print("\nDataset update completed successfully!")
        print(f"Records updated: {updated}")
        print(f"Records inserted: {inserted}")
        print(f"Generated records verified: {generated_count}")
        print(f"Distinct projects verified: {project_count}")
        print("Existing users were not changed.")

    except Exception as error:
        connection.rollback()
        print("\nUpdate failed. Database changes were rolled back.")
        print("Error:", error)

    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":
    main()
