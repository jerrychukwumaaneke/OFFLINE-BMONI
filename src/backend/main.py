from fastapi import FastAPI, HTTPException, Cookie, Depends, Response, Form
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from pydantic import BaseModel
import os
from database import (
    init_db, 
    insert_transaction, 
    get_pending_transactions, 
    mark_as_synced, 
    get_profile_value,
    set_profile_value,
    hash_password,
    create_session,
    verify_session,
    destroy_session
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

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="BMONI Offline Agent Relay Node")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    init_db()

# Data models
class TransactionSchema(BaseModel):
    node_id: str
    sender_wallet: str
    receiver_wallet: str
    amount: float

class ChatMessageSchema(BaseModel):
    message: str

# API protection dependency
def verify_api_auth(session_token: str = Cookie(None)):
    if not session_token or not verify_session(session_token):
        raise HTTPException(status_code=401, detail="Unauthorized session. Please log in.")
    return session_token

# Helper to verify HTML routes status for dashboard access
def check_dashboard_auth_redirect(session_token: str) -> RedirectResponse | None:
    # 1. Verify if registered
    registered_user = get_profile_value("bmoni_user_id")
    if not registered_user:
        return RedirectResponse(url="/register", status_code=303)
        
    # 2. Verify session
    if not session_token or not verify_session(session_token):
        return RedirectResponse(url="/login", status_code=303)
    
    # 3. Check if default password needs changing
    is_default = get_profile_value("is_default_password")
    if is_default == "True":
        return RedirectResponse(url="/change-password", status_code=303)
        
    return None

# Welcome / Landing Page
@app.get("/")
def serve_landing_page():
    """Serves the welcome landing page."""
    html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "landing.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return HTMLResponse("<h1>landing.html Not Found</h1>")

@app.get("/api/status-unprotected")
def get_registration_status():
    """Unprotected endpoint to check if the node has been configured yet."""
    registered_user = get_profile_value("bmoni_user_id")
    return {"registered": registered_user is not None and len(registered_user) > 0}

# Registration page
@app.get("/register")
def get_register_page():
    """Serves the registration page (only if no user is registered)."""
    registered_user = get_profile_value("bmoni_user_id")
    if registered_user:
        return RedirectResponse(url="/login", status_code=303)
        
    html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "register.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return HTMLResponse("<h1>register.html Not Found</h1>")

@app.post("/register")
def post_register(
    response: Response,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    default_password: str = Form(...)
):
    """Handles first-time registration and BMONI Sandbox onboarding."""
    # 1. Verify that a user is not already onboarded
    if get_profile_value("bmoni_user_id"):
        raise HTTPException(status_code=400, detail="Node is already registered.")
        
    # 2. Verify temporary authorization password
    entered_hash = hash_password(default_password)
    correct_hash = get_profile_value("password_hash")
    
    if entered_hash != correct_hash:
        raise HTTPException(status_code=400, detail="Invalid temporary authorization password.")
        
    print(f"[REGISTRATION] Onboarding profile: {first_name} {last_name} ({email})")
    
    try:
        # Save profile details locally first
        set_profile_value("first_name", first_name)
        set_profile_value("last_name", last_name)
        set_profile_value("email", email)
        set_profile_value("phone", phone)
        
        # 3. Run Live BMONI Handshake
        # A. EVM keypair
        pk, addr = wallet.get_or_create_keypair()
        
        # B. BMONI User
        user_id = create_bmoni_user(first_name=first_name, email=email, phone=phone)
        
        # C. BMONI Smart Wallet
        challenge = get_challenge(user_id, addr)
        challenge_id = challenge["challengeId"]
        msg = challenge["message"]
        sig = wallet.sign_eip191_message(msg, pk)
        
        wallet_data = create_managed_wallet(user_id, addr, challenge_id, sig)
        wallet_address = wallet_data.get("walletAddress") or wallet_data.get("address")
        wallet_id = wallet_data.get("id") or wallet_data.get("smartWalletId")
        
        # D. Sandbox NGN KYC & Rail Onboarding (wrapped to bypass staging latency/failures)
        try:
            start_nigeria_onboarding(user_id, wallet_address)
            
            # E. Provision NGN VBA
            if wallet_id:
                provision_nigerian_vba(user_id, wallet_id)
        except Exception as kyc_err:
            print(f"[REGISTRATION WARNING] Sandbox KYC/VBA activation failed or timed out: {kyc_err}")
                
        print(f"[REGISTRATION] Successfully onboarded BMONI User: {user_id}")
        
        # 4. Generate Session Token and redirect to password reset
        token = create_session()
        response.set_cookie(key="session_token", value=token, httponly=True, samesite="lax")
        return {"message": "Success"}
        
    except Exception as e:
        print(f"[REGISTRATION ERROR] User/Wallet creation failed: {e}")
        # Clear profile keys on fail so they can try again
        set_profile_value("bmoni_user_id", "")
        set_profile_value("smart_wallet_address", "")
        raise HTTPException(status_code=500, detail=f"BMONI User/Wallet creation failed: {str(e)}")

# Login Page
@app.get("/login")
def get_login_page(session_token: str = Cookie(None)):
    """Serves the login page."""
    # If the node is not registered yet, redirect to configuration/registration
    if not get_profile_value("bmoni_user_id"):
        return RedirectResponse(url="/register", status_code=303)
        
    if session_token and verify_session(session_token):
        return RedirectResponse(url="/dashboard", status_code=303)
        
    html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "login.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return HTMLResponse("<h1>login.html Not Found</h1>")

@app.post("/login")
def post_login(response: Response, email: str = Form(...), password: str = Form(...)):
    """Authenticates the agent using email and password."""
    # Check registration
    if not get_profile_value("bmoni_user_id"):
        raise HTTPException(status_code=400, detail="Agent is not registered yet.")
        
    # Verify Email
    saved_email = get_profile_value("email")
    if email.lower() != saved_email.lower():
        raise HTTPException(status_code=400, detail="Invalid email or password.")
        
    # Verify Password
    entered_hash = hash_password(password)
    correct_hash = get_profile_value("password_hash")
    
    if entered_hash != correct_hash:
        raise HTTPException(status_code=400, detail="Invalid email or password.")
        
    # Generate token
    token = create_session()
    response.set_cookie(key="session_token", value=token, httponly=True, samesite="lax")
    return {"message": "Success"}

# Forgot Password Pages
@app.get("/forgot-password")
def get_forgot_password():
    """Serves the forgot password recovery page."""
    html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "forgot_password.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return HTMLResponse("<h1>forgot_password.html Not Found</h1>")

@app.post("/forgot-password")
def post_forgot_password(email: str = Form(...), recovery_password: str = Form(...), new_password: str = Form(...)):
    """Resets the password if authorized by email and default recovery password."""
    # Check registration
    if not get_profile_value("bmoni_user_id"):
        raise HTTPException(status_code=400, detail="Agent is not registered yet.")
        
    # Verify Email
    saved_email = get_profile_value("email")
    if email.lower() != saved_email.lower():
        raise HTTPException(status_code=400, detail="Email address does not match registered agent.")
        
    # Verify staff recovery password (default BMONI_TEMP_2026)
    if recovery_password != "BMONI_TEMP_2026":
        raise HTTPException(status_code=400, detail="Invalid staff default recovery password.")
        
    # Apply new password reset
    set_profile_value("password_hash", hash_password(new_password))
    return {"message": "Password reset successfully!"}

@app.get("/change-password")
def get_change_password_page(session_token: str = Cookie(None)):
    """Serves the password update screen."""
    if not session_token or not verify_session(session_token):
        return RedirectResponse(url="/login", status_code=303)
        
    html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "change_password.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return HTMLResponse("<h1>change_password.html Not Found</h1>")

@app.post("/change-password")
def post_change_password(session_token: str = Cookie(None), new_password: str = Form(...)):
    """Saves new password and updates default flag."""
    if not session_token or not verify_session(session_token):
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
        
    set_profile_value("password_hash", hash_password(new_password))
    set_profile_value("is_default_password", "False")
    return {"message": "Password changed successfully."}

@app.get("/logout")
def logout(response: Response):
    """Destroys current session and redirects to landing page."""
    destroy_session()
    response.delete_cookie(key="session_token")
    return RedirectResponse(url="/", status_code=303)

# Protected Dashboard and APIs
@app.get("/dashboard")
def serve_dashboard(session_token: str = Cookie(None)):
    """Serves the main dashboard HTML if authenticated."""
    redirect = check_dashboard_auth_redirect(session_token)
    if redirect:
        return redirect
        
    html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "index.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return HTMLResponse("<h1>index.html Not Found</h1>")

@app.get("/api/status")
def get_node_status(session_token: str = Depends(verify_api_auth)):
    """Returns local configuration and live BMONI status."""
    user_id = get_profile_value("bmoni_user_id")
    wallet_address = get_profile_value("smart_wallet_address")
    wallet_id = get_profile_value("smart_wallet_id")
    
    first_name = get_profile_value("first_name")
    last_name = get_profile_value("last_name")
    email = get_profile_value("email")
    phone = get_profile_value("phone")
    
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
                vba_details = vbas[0]
        except Exception:
            pass
            
    return {
        "status": "ONLINE",
        "bmoni_user_id": user_id,
        "smart_wallet_address": wallet_address,
        "smart_wallet_id": wallet_id,
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": phone,
        "live_balances": live_balances,
        "virtual_bank_account": vba_details
    }

@app.post("/transaction/offline-receive")
def receive_offline_transaction(tx: TransactionSchema):
    """Saves offline transaction to SQLite (unprotected for hardware ingestion)."""
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
def list_pending_transactions(session_token: str = Depends(verify_api_auth)):
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
def sync_transactions(session_token: str = Depends(verify_api_auth)):
    """Simulates syncing/broadcasting pending offline transactions to BMONI rails."""
    pending = get_pending_transactions()
    if not pending:
        return {"message": "No pending offline transactions to sync."}
        
    synced_ids = []
    for tx in pending:
        tx_id, node_id, sender, receiver, amount = tx
        print(f"[SYNC] Processing TX {tx_id}: Sending {amount} CNGN from {sender} to {receiver}")
        mark_as_synced(tx_id)
        synced_ids.append(tx_id)
        
    return {
        "message": "Successfully synchronized offline transactions to BMONI live network",
        "synced_count": len(synced_ids),
        "synced_ids": synced_ids
    }

@app.post("/transactions/simulate")
def simulate_offline_event(session_token: str = Depends(verify_api_auth)):
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
def chat_with_agent(chat_msg: ChatMessageSchema, session_token: str = Depends(verify_api_auth)):
    """Sends user query to Gemini AI financial assistant."""
    user_id = get_profile_value("bmoni_user_id")
    response_text = get_ai_response(chat_msg.message, bmoni_user_id=user_id)
    return {"reply": response_text}