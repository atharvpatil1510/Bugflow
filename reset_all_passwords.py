
from db import get_connection
from werkzeug.security import generate_password_hash
import secrets
import csv
from pathlib import Path
from datetime import datetime

# Ask for confirmation before resetting every account
confirmation = input(
    "WARNING: This resets passwords for ALL users. "
    "Type RESET ALL to continue: "
)

if confirmation != "RESET ALL":
    print("Cancelled. No passwords were changed.")
    raise SystemExit

conn = get_connection()
cur = conn.cursor()

# Save the credentials in a separate CSV file
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_file = Path(__file__).parent / f"user_temporary_passwords_{timestamp}.csv"
temp_file = output_file.with_suffix(".tmp")

try:
    # Fetch all accounts
    cur.execute("""
        SELECT user_id, name, email, role
        FROM public.users
        ORDER BY user_id
    """)
    users = cur.fetchall()

    if not users:
        print("No users found. Nothing to reset.")
        raise SystemExit

    credentials = []

    # Generate a unique password for every user
    for user_id, name, email, role in users:
        temporary_password = secrets.token_urlsafe(16)
        password_hash = generate_password_hash(temporary_password)

        cur.execute("""
            UPDATE public.users
            SET password_hash = %s
            WHERE user_id = %s
        """, (password_hash, user_id))

        credentials.append({
            "user_id": user_id,
            "name": name or "",
            "email": email or "",
            "role": role or "",
            "temporary_password": temporary_password
        })

    # Write the credential file before committing database changes
    with open(temp_file, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "user_id", "name", "email", "role",
                "temporary_password"
            ]
        )
        writer.writeheader()
        writer.writerows(credentials)

    # Commit all password changes together
    conn.commit()
    temp_file.replace(output_file)

    print("\nPassword reset completed successfully!")
    print(f"Accounts updated: {len(credentials)}")
    print(f"Credential file: {output_file}")
    print("Keep this file private and secure.")

except SystemExit:
    conn.rollback()
    raise

except Exception as error:
    conn.rollback()
    if temp_file.exists():
        temp_file.unlink()
    print("Password reset failed. Database changes were rolled back.")
    print("Error:", error)

finally:
    cur.close()
    conn.close()
