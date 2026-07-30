import sqlite3
import os

DB_NAME = "offline_relay.db"

def init_db():
    """Creates the local escrow database table and settings table if they don't exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Existing transactions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT NOT NULL,
            sender_wallet TEXT NOT NULL,
            receiver_wallet TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT DEFAULT 'PENDING_LOCAL_SYNC',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Key-value store for agent profile / BMONI credentials
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agent_profile (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Local Escrow SQLite DB Initialized successfully.")

def insert_transaction(node_id, sender, receiver, amount):
    """Saves a new offline transaction payload locally."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO transactions (node_id, sender_wallet, receiver_wallet, amount)
        VALUES (?, ?, ?, ?)
    ''', (node_id, sender, receiver, amount))
    conn.commit()
    tx_id = cursor.lastrowid
    conn.close()
    return tx_id

def get_pending_transactions():
    """Retrieves all transactions waiting to be synced to BMONI."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, node_id, sender_wallet, receiver_wallet, amount FROM transactions WHERE status = 'PENDING_LOCAL_SYNC'")
    rows = cursor.fetchall()
    conn.close()
    return rows

def mark_as_synced(tx_id):
    """Updates status once synced to BMONI Sandbox."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE transactions SET status = 'SYNCED_TO_BMONI' WHERE id = ?", (tx_id,))
    conn.commit()
    conn.close()

def get_profile_value(key):
    """Retrieves a configuration value from the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM agent_profile WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def set_profile_value(key, value):
    """Saves/updates a configuration value in the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO agent_profile (key, value)
        VALUES (?, ?)
    ''', (key, str(value)))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
