import sqlite3

def init_db():
    # This connects to (or creates) clinical_portal.db in your project folder
    conn = sqlite3.connect('clinical_portal.db')
    cursor = conn.cursor()

    # Create the users table for registration and login
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            assigned_doctor_id INTEGER
        )
    ''')

    conn.commit()
    conn.close()
    print("Database 'clinical_portal.db' and 'users' table created successfully!")

if __name__ == '__main__':
    init_db()