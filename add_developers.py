
from db import get_connection
from werkzeug.security import generate_password_hash
import secrets

# 20 new developers, 20 testers, 2 project managers, 1 admin
users = [
    # Developers
    ("Vikram Singh", "vikram.singh@bugflow.com", "Developer"),
    ("Meera Desai", "meera.desai@bugflow.com", "Developer"),
    ("Arjun Nair", "arjun.nair@bugflow.com", "Developer"),
    ("Kavya Rao", "kavya.rao@bugflow.com", "Developer"),
    ("Siddharth Verma", "siddharth.verma@bugflow.com", "Developer"),
    ("Pooja Shinde", "pooja.shinde@bugflow.com", "Developer"),
    ("Nikhil Gupta", "nikhil.gupta@bugflow.com", "Developer"),
    ("Tanvi Joshi", "tanvi.joshi@bugflow.com", "Developer"),
    ("Omkar Pawar", "omkar.pawar@bugflow.com", "Developer"),
    ("Riya Kapoor", "riya.kapoor@bugflow.com", "Developer"),
    ("Saurabh Mishra", "saurabh.mishra@bugflow.com", "Developer"),
    ("Aditi Chavan", "aditi.chavan@bugflow.com", "Developer"),
    ("Manish Yadav", "manish.yadav@bugflow.com", "Developer"),
    ("Shreya Kulkarni", "shreya.kulkarni@bugflow.com", "Developer"),
    ("Akash Thakur", "akash.thakur@bugflow.com", "Developer"),
    ("Nisha Soni", "nisha.soni@bugflow.com", "Developer"),
    ("Varun Malhotra", "varun.malhotra@bugflow.com", "Developer"),
    ("Mitali Pawar", "mitali.pawar@bugflow.com", "Developer"),
    ("Devendra Patil", "devendra.patil@bugflow.com", "Developer"),
    ("Simran Kaur", "simran.kaur@bugflow.com", "Developer"),

    # Testers
    ("Aniket Bhosale", "aniket.bhosale@bugflow.com", "Tester"),
    ("Sakshi Jadhav", "sakshi.jadhav@bugflow.com", "Tester"),
    ("Harsh Vardhan", "harsh.vardhan@bugflow.com", "Tester"),
    ("Komal Rathod", "komal.rathod@bugflow.com", "Tester"),
    ("Yash Agrawal", "yash.agrawal@bugflow.com", "Tester"),
    ("Divya Naik", "divya.naik@bugflow.com", "Tester"),
    ("Pranav Shukla", "pranav.shukla@bugflow.com", "Tester"),
    ("Mansi Thombre", "mansi.thombre@bugflow.com", "Tester"),
    ("Abhishek Sahu", "abhishek.sahu@bugflow.com", "Tester"),
    ("Rutuja Gawande", "rutuja.gawande@bugflow.com", "Tester"),
    ("Kunal Saxena", "kunal.saxena@bugflow.com", "Tester"),
    ("Pallavi More", "pallavi.more@bugflow.com", "Tester"),
    ("Deepak Rane", "deepak.rane@bugflow.com", "Tester"),
    ("Ishita Jain", "ishita.jain@bugflow.com", "Tester"),
    ("Pratik Salunkhe", "pratik.salunkhe@bugflow.com", "Tester"),
    ("Swati Kamat", "swati.kamat@bugflow.com", "Tester"),
    ("Nitin Choudhary", "nitin.choudhary@bugflow.com", "Tester"),
    ("Gauri Wagh", "gauri.wagh@bugflow.com", "Tester"),
    ("Mohit Arora", "mohit.arora@bugflow.com", "Tester"),
    ("Priti Sawant", "priti.sawant@bugflow.com", "Tester"),

    # Project Managers
    ("Rajiv Malhotra", "rajiv.malhotra@bugflow.com", "Project Manager"),
    ("Shalini Deshmukh", "shalini.deshmukh@bugflow.com", "Project Manager"),

    # Admin
    ("Amitabh Kulkarni", "amitabh.kulkarni@bugflow.com", "Admin"),
]

conn = get_connection()
cur = conn.cursor()

try:
    created = 0
    skipped = 0

    for name, email, role in users:
        password = secrets.token_urlsafe(12)
        password_hash = generate_password_hash(password)

        cur.execute(
            """
            INSERT INTO public.users (name, role, email, password_hash)
            SELECT %s, %s, %s, %s
            WHERE NOT EXISTS (
                SELECT 1 FROM public.users WHERE email = %s
            )
            RETURNING user_id
            """,
            (name, role, email, password_hash, email)
        )

        result = cur.fetchone()

        if result:
            created += 1
            print(f"Created: {name} | {role} | {email}")
            print(f"Temporary password: {password}\n")
        else:
            skipped += 1
            print(f"Skipped existing account: {email}")

    conn.commit()

    print("=" * 45)
    print("ACCOUNT CREATION COMPLETED")
    print(f"New accounts created: {created}")
    print(f"Existing accounts skipped: {skipped}")
    print(f"Total accounts processed: {len(users)}")

except Exception as error:
    conn.rollback()
    print("Error:", error)
    print("Database changes rolled back.")

finally:
    cur.close()
    conn.close()
