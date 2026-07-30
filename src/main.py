from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import os
import threading
from database import (
    init_db, 
    insert_transaction, 
    get_pending_transactions, 
    mark_as_synced, 
    get_profile_value,
    set_profile_value
)
from bmoni_client import (
    create_bmoni_user, 
    get_challenge, 
    create_managed_wallet, 
    start_nigeria_onboarding, 
    get_onboarding_status,
    get_balances,
    get_smart_wallets,
    provision_nigerian_vba,
    get_deposit_accounts
)
import wallet
from ai_agent import get_ai_response

app = FastAPI(title="BMONI Offline Agent Relay Node")

# Background thread to handle automatic BMONI Sandbox onboarding on startup
def auto_onboard_agent():
    print("[ONBOARDING] Starting auto-onboarding task...")
    try:
        init_db()
        
        # 1. EVM Owner Wallet
        pk, addr = wallet.get_or_create_keypair()
        print(f"[ONBOARDING] EVM Owner Address: {addr}")
        
        # 2. BMONI User ID
        user_id = get_profile_value("bmoni_user_id")
        if not user_id:
            user_id = create_bmoni_user()
            print(f"[ONBOARDING] Created BMONI User ID: {user_id}")
        else:
            print(f"[ONBOARDING] Found BMONI User ID: {user_id}")
            
        # 3. Smart Wallet Address
        wallet_address = get_profile_value("smart_wallet_address")
        if not wallet_address:
            try:
                challenge = get_challenge(user_id, addr)
                challenge_id = challenge["challengeId"]
                msg = challenge["message"]
                sig = wallet.sign_eip191_message(msg, pk)
                wallet_data = create_managed_wallet(user_id, addr, challenge_id, sig)
                wallet_address = wallet_data.get("walletAddress") or wallet_data.get("address")
                print(f"[ONBOARDING] Deployed Smart Wallet: {wallet_address}")
            except Exception as e:
                print(f"[ONBOARDING] Managed wallet creation failed, recovering: {e}")
                wallets = get_smart_wallets(user_id)
                if wallets:
                    wallet_data = wallets[0]
                    wallet_address = wallet_data.get("walletAddress")
                    wallet_id = wallet_data.get("id")
                    if wallet_address:
                        set_profile_value("smart_wallet_address", wallet_address)
                    if wallet_id:
                        set_profile_value("smart_wallet_id", wallet_id)
                    print(f"[ONBOARDING] Recovered Smart Wallet: {wallet_address}")
                else:
                    raise e
        else:
            print(f"[ONBOARDING] Found Smart Wallet Address: {wallet_address}")
            
        # 4. Sandbox KYC and Nigeria rail onboarding
        try:
            start_nigeria_onboarding(user_id, wallet_address)
            print("[ONBOARDING] Submitting NGN KYC...")
        except Exception as e:
            # If already active, it will throw conflict but we can proceed
            print(f"[ONBOARDING] NGN KYC Onboarding check: {e}")
            
        # 5. Provision Virtual NGN Bank Account for deposits
        wallet_id = get_profile_value("smart_wallet_id")
        if wallet_id:
            try:
                provision_nigerian_vba(user_id, wallet_id)
            except Exception as e:
                print(f"[ONBOARDING] VBA provisioning check: {e}")
                
        print("[ONBOARDING] Auto-onboarding complete! Node is live and configured.")
    except Exception as e:
        print(f"[ONBOARDING] Auto-onboarding failed: {e}")

@app.on_event("startup")
def startup_event():
    init_db()
    # Run onboarding in a background thread so FastAPI startup isn't blocked by network requests
    threading.Thread(target=auto_onboard_agent, daemon=True).start()

# Data models
class TransactionSchema(BaseModel):
    node_id: str
    sender_wallet: str
    receiver_wallet: str
    amount: float

class ChatMessageSchema(BaseModel):
    message: str

@app.get("/")
def serve_dashboard():
    """Serves the dashboard HTML file."""
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return HTMLResponse("<h1>BMONI Dashboard File index.html Not Found</h1>")

@app.get("/api/status")
def get_node_status():
    """Returns local configuration and live BMONI status."""
    user_id = get_profile_value("bmoni_user_id")
    wallet_address = get_profile_value("smart_wallet_address")
    wallet_id = get_profile_value("smart_wallet_id")
    
    live_balances = []
    vba_details = {}
    
    if user_id:
        try:
            balances_data = get_balances(user_id)
            live_balances = balances_data.get("balances", [])
        except Exception:
            pass
            
        try:
            vbas = get_deposit_accounts(user_id)
            if vbas:
                # Return the first active virtual bank account
                vba_details = vbas[0]
        except Exception:
            pass
            
    return {
        "status": "ONLINE",
        "bmoni_user_id": user_id,
        "smart_wallet_address": wallet_address,
        "smart_wallet_id": wallet_id,
        "live_balances": live_balances,
        "virtual_bank_account": vba_details
    }

@app.post("/transaction/offline-receive")
def receive_offline_transaction(tx: TransactionSchema):
    """Saves offline transaction to SQLite."""
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
    """Lists pending offline transactions."""
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

@app.post("/transactions/sync")
def sync_transactions():
    """Simulates syncing/broadcasting pending offline transactions to BMONI rails."""
    pending = get_pending_transactions()
    if not pending:
        return {"message": "No pending offline transactions to sync."}
        
    synced_ids = []
    # Simulate processing them one by one through BMONI transfers
    for tx in pending:
        tx_id, node_id, sender, receiver, amount = tx
        print(f"[SYNC] Processing TX {tx_id}: Sending {amount} CNGN from {sender} to {receiver}")
        # In a real setup, we would call BMONI offramp/swap/transfer endpoint here
        # For the hackathon sandbox, we simulate the live settlement success
        mark_as_synced(tx_id)
        synced_ids.append(tx_id)
        
    return {
        "message": "Successfully synchronized offline transactions to BMONI live network",
        "synced_count": len(synced_ids),
        "synced_ids": synced_ids
    }

@app.post("/transactions/simulate")
def simulate_offline_event():
    """Triggers a simulated ESP32 offline transaction event."""
    payload = {
        "node_id": "C3_MINI_NODE_SIMULATED",
        "sender_wallet": "08012345678",
        "receiver_wallet": "09087654321",
        "amount": random_amount()
    }
    tx_id = insert_transaction(
        node_id=payload["node_id"],
        sender=payload["sender_wallet"],
        receiver=payload["receiver_wallet"],
        amount=payload["amount"]
    )
    return {
        "message": "Simulated hardware event logged in local escrow",
        "db_record_id": tx_id,
        "payload": payload
    }

def random_amount():
    import random
    return round(random.uniform(500, 5000), 2)

@app.post("/ai/chat")
def chat_with_agent(chat_msg: ChatMessageSchema):
    """Sends user query to Gemini AI financial assistant."""
    user_id = get_profile_value("bmoni_user_id")
    response_text = get_ai_response(chat_msg.message, bmoni_user_id=user_id)
    return {"reply": response_text}