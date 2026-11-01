
from db import get_connection

connection = get_connection()
cursor = connection.cursor()

cursor.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_name = 'bug_reports';
""")

result = cursor.fetchall()

print("Tables found:", result)

cursor.close()
connection.close()
