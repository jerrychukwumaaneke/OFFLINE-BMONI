from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
from database import init_db, insert_transaction, get_pending_transactions, mark_as_synced

app = FastAPI(title="BMONI Offline Agent Relay Node")

# Ensure DB is created on startup
@app.on_event("startup")
def startup_event():
    init_db()

# Data model for incoming offline transactions
class TransactionSchema(BaseModel):
    node_id: str
    sender_wallet: str
    receiver_wallet: str
    amount: float

@app.get("/")
def root():
    return {
        "system": "BMONI Offline Relay Server",
        "status": "ONLINE",
        "mode": "OFFLINE_ESCROW_READY"
    }

@app.post("/transaction/offline-receive")
def receive_offline_transaction(tx: TransactionSchema):
    """
    Endpoint used by the ESP32 (or serial bridge) to save an 
    offline escrow payload directly into local SQLite.
    """
    tx_id = insert_transaction(
        node_id=tx.node_id,
        sender=tx.sender_wallet,
        receiver=tx.receiver_wallet,
        amount=tx.amount
    )
    return {
        "message": "Transaction held safely in local escrow",
        "db_record_id": tx_id,
        "status": "PENDING_LOCAL_SYNC"
    }

@app.get("/transactions/pending")
def list_pending_transactions():
    """
    Retrieves all offline transactions currently waiting in local SQLite.
    """
    pending = get_pending_transactions()
    formatted = []
    for row in pending:
        formatted.append({
            "id": row[0],
            "node_id": row[1],
            "sender_wallet": row[2],
            "receiver_wallet": row[3],
            "amount": row[4]
        })
    return {"pending_count": len(formatted), "transactions": formatted}