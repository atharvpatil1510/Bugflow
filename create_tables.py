
from db import get_connection

connection = get_connection()
cursor = connection.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS bug_reports (
        id SERIAL PRIMARY KEY,
        project VARCHAR(150) NOT NULL,
        title VARCHAR(200) NOT NULL,
        description TEXT NOT NULL,
        severity VARCHAR(30) NOT NULL,
        status VARCHAR(30) NOT NULL DEFAULT 'Open',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
""")

connection.commit()

cursor.close()
connection.close()

print("Bug reports table created successfully!")
