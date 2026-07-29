import sqlite3

DB_NAME = "offline_relay.db"

def init_db():
    """Creates the local escrow database table if it doesn't exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
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

if __name__ == "__main__":
    init_db()