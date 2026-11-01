
from db import get_connection

try:
    connection = get_connection()
    print("PostgreSQL connected successfully!")

    cursor = connection.cursor()
    cursor.execute("SELECT version();")
    print(cursor.fetchone()[0])

    cursor.close()
    connection.close()

except Exception as error:
    print("Database connection failed:", error)
