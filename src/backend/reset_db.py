import sqlite3
import hashlib

DB_NAME = "offline_relay.db"

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def reset_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Clear transactions
    try:
        cursor.execute("DELETE FROM transactions")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='transactions'")
        print("[DB] Cleared transactions table successfully.")
    except Exception as e:
        print(f"[DB] Note on clearing transactions: {e}")
        
    # 2. Clear agent profile
    try:
        cursor.execute("DELETE FROM agent_profile")
        print("[DB] Cleared agent profile settings successfully.")
    except Exception as e:
        print(f"[DB] Note on clearing profile: {e}")
        
    # 3. Insert default temporary credentials
    cursor.execute("INSERT OR REPLACE INTO agent_profile (key, value) VALUES ('password_hash', ?)", (hash_password("BMONI_TEMP_2026"),))
    cursor.execute("INSERT OR REPLACE INTO agent_profile (key, value) VALUES ('is_default_password', 'True')")
    print("[DB] Reset temporary credentials to default ('BMONI_TEMP_2026').")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    reset_database()
