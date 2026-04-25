from werkzeug.security import generate_password_hash
from db import get_connection

conn = get_connection()
cursor = conn.cursor(dictionary=True)

email = "admin@momentsmaker.com"
password = "Admin@123"

# Check already exists
cursor.execute("SELECT id FROM users WHERE is_admin=TRUE")
if cursor.fetchone():
    print("⚠ Admin already exists")
else:
    hash_pass = generate_password_hash(password)
    cursor.execute("""
        INSERT INTO users (name, email, password_hash, is_admin)
        VALUES (%s,%s,%s,TRUE)
    """, ("Super Admin", email, hash_pass))
    conn.commit()
    print("✅ Admin created successfully")

cursor.close()
conn.close()
