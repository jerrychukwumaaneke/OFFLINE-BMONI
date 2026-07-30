import os
import requests
import random
import time
from database import get_profile_value, set_profile_value

BASE_URL = "https://embedded-dev.bmoni.com"
API_KEY = "pk_a025cacbf33a_76fb864113f3540909de5b1da39cc146906e35b1c6d4d1e4"

def get_headers():
    return {
        "x-api-key": API_KEY,
        "Content-Type": "application/json"
    }

def create_bmoni_user(first_name="TestAgent", email=None, phone=None):
    """
    Creates a new user in the BMONI sandbox.
    Generates unique random email and phone number if not provided.
    """
    if not email:
        email = f"agent-{random.randint(100000, 999999)}@example.com"
    if not phone:
        phone = f"+2348{random.randint(100000000, 999999999)}"
        
    url = f"{BASE_URL}/v1/users"
    payload = {
        "firstName": first_name,
        "email": email,
        "phoneNumber": phone
    }
    
    print(f"[BMONI] Creating user: {payload}")
    res = requests.post(url, json=payload, headers=get_headers())
    if res.status_code == 200 or res.status_code == 201:
        data = res.json()
        user_obj = data.get("user", {}) if "user" in data else data
        user_id = user_obj.get("bmoniUserId") or user_obj.get("id") or user_obj.get("userId")
        if user_id:
            set_profile_value("bmoni_user_id", user_id)
            set_profile_value("email", email)
            set_profile_value("phone", phone)
            return user_id
    raise Exception(f"Failed to create BMONI user: {res.text}")

def get_challenge(user_id, eth_address):
    """Requests an owner-proof challenge for CNGN."""
    url = f"{BASE_URL}/v1/users/{user_id}/smart-wallets/owner-proof-challenges"
    payload = {
        "currency": "CNGN",
        "userOwnerAddress": eth_address
    }
    print(f"[BMONI] Requesting challenge for address: {eth_address}")
    res = requests.post(url, json=payload, headers=get_headers())
    if res.status_code in [200, 201]:
        return res.json()  # Contains challengeId and message
    raise Exception(f"Failed to get owner-proof challenge: {res.text}")

def create_managed_wallet(user_id, eth_address, challenge_id, signature):
    """Deploys/creates the managed smart wallet on BMONI."""
    url = f"{BASE_URL}/v1/users/{user_id}/smart-wallets/create-managed"
    payload = {
        "currency": "CNGN",
        "userOwnerAddress": eth_address,
        "ownerProofChallengeId": challenge_id,
        "ownerProofSignature": signature
    }
    print(f"[BMONI] Deploying smart wallet...")
    res = requests.post(url, json=payload, headers=get_headers())
    if res.status_code in [200, 201]:
        data = res.json()
        print(f"[BMONI] Smart wallet deployed: {data}")
        wallet_address = data.get("walletAddress") or data.get("address")
        wallet_id = data.get("id") or data.get("smartWalletId")
        if wallet_address:
            set_profile_value("smart_wallet_address", wallet_address)
        if wallet_id:
            set_profile_value("smart_wallet_id", wallet_id)
        return data
    raise Exception(f"Failed to create managed smart wallet: {res.text}")

def start_nigeria_onboarding(user_id, wallet_address, bvn="22222222222"):
    """Starts Nigerian KYC onboarding and rail activation using Sandbox BVN."""
    url = f"{BASE_URL}/v1/users/{user_id}/onboarding/start-nigeria"
    payload = {
        "bvn": bvn,
        "ngnWalletAddress": wallet_address,
        "ngnWalletIndex": 0
    }
    print(f"[BMONI] Submitting sandbox NGN KYC onboarding...")
    res = requests.post(url, json=payload, headers=get_headers())
    if res.status_code in [200, 201]:
        print(f"[BMONI] Onboarding result: {res.json()}")
        return res.json()
    raise Exception(f"Failed to start Nigeria onboarding: {res.text}")

def get_onboarding_status(user_id):
    """Checks onboarding status for the user."""
    url = f"{BASE_URL}/v1/users/{user_id}/onboarding/status"
    res = requests.get(url, headers=get_headers())
    if res.status_code == 200:
        return res.json()
    raise Exception(f"Failed to get onboarding status: {res.text}")

def provision_nigerian_vba(user_id, wallet_id):
    """Provisions a virtual bank account for NGN bank transfers (onramp)."""
    url = f"{BASE_URL}/v1/users/{user_id}/smart-wallets/{wallet_id}/onramp/vba/nigeria"
    print(f"[BMONI] Provisioning virtual NGN bank account for wallet {wallet_id}...")
    res = requests.post(url, json={}, headers=get_headers())
    if res.status_code in [200, 201]:
        print(f"[BMONI] Virtual account provisioned: {res.json()}")
        return res.json()
    # If already provisioned, it might fail or return a success message.
    print(f"[BMONI] VBA provisioning response: {res.text}")
    return {"message": "Requested VBA provisioning"}

def get_deposit_accounts(user_id):
    """Retrieves deposit bank accounts (virtual accounts) for NGN."""
    url = f"{BASE_URL}/v1/users/{user_id}/bank-accounts/deposit-accounts/NGN"
    res = requests.get(url, headers=get_headers())
    if res.status_code == 200:
        return res.json()
    return []

def get_smart_wallets(user_id):
    """Retrieves all smart wallets associated with the user."""
    url = f"{BASE_URL}/v1/users/{user_id}/smart-wallets/account/wallets"
    res = requests.get(url, headers=get_headers())
    if res.status_code == 200:
        return res.json()
    raise Exception(f"Failed to fetch smart wallets: {res.text}")

def get_balances(user_id):
    """Retrieves live smart wallet balances."""
    url = f"{BASE_URL}/v1/users/{user_id}/smart-wallets/account/balances"
    res = requests.get(url, headers=get_headers())
    if res.status_code == 200:
        return res.json()
    raise Exception(f"Failed to get balances: {res.text}")

def get_transactions(user_id):
    """Retrieves live smart wallet transactions."""
    url = f"{BASE_URL}/v1/users/{user_id}/smart-wallets/account/transactions"
    res = requests.get(url, headers=get_headers())
    if res.status_code == 200:
        return res.json()
    # It might be that the endpoint is /v1/users/{userId}/smart-wallets/account/transactions or per-wallet
    # If it fails, return empty list
    return []

def get_nigerian_banks(user_id):
    """Retrieves the list of supported Nigerian banks with code."""
    url = f"{BASE_URL}/v1/users/{user_id}/bank-accounts/nigerian-banks"
    res = requests.get(url, headers=get_headers())
    if res.status_code == 200:
        return res.json()
    return []

def verify_bank_account(user_id, account_number, bank_code):
    """Verifies a Nigerian bank account number."""
    url = f"{BASE_URL}/v1/users/{user_id}/bank-accounts/verify-nigerian-account"
    payload = {
        "accountNumber": account_number,
        "bankCode": bank_code
    }
    res = requests.post(url, json=payload, headers=get_headers())
    if res.status_code == 200:
        return res.json() # Returns accountHolderName
    raise Exception(f"Verification failed: {res.text}")

if __name__ == "__main__":
    # Test file
    from database import init_db
    init_db()
    
    import wallet
    print("Testing BMONI Client...")
    try:
        user_id = get_profile_value("bmoni_user_id")
        if not user_id:
            user_id = create_bmoni_user()
        print(f"BMONI User ID: {user_id}")
        
        # Get Keypair
        pk, addr = wallet.get_or_create_keypair()
        
        # Challenge & Wallet creation
        wallet_address = get_profile_value("smart_wallet_address")
        if not wallet_address:
            try:
                challenge = get_challenge(user_id, addr)
                challenge_id = challenge["challengeId"]
                msg = challenge["message"]
                sig = wallet.sign_eip191_message(msg, pk)
                wallet_data = create_managed_wallet(user_id, addr, challenge_id, sig)
                wallet_address = wallet_data.get("walletAddress") or wallet_data.get("address")
            except Exception as e:
                print(f"[BMONI] Creation failed, attempting to recover existing wallet: {e}")
                wallets = get_smart_wallets(user_id)
                if wallets:
                    wallet_data = wallets[0]
                    wallet_address = wallet_data.get("walletAddress")
                    wallet_id = wallet_data.get("id")
                    if wallet_address:
                        set_profile_value("smart_wallet_address", wallet_address)
                    if wallet_id:
                        set_profile_value("smart_wallet_id", wallet_id)
                else:
                    raise e
            
        print(f"Smart Wallet Address: {wallet_address}")
        
        # Check onboarding
        status = get_onboarding_status(user_id)
        print(f"Onboarding status: {status}")
        
        # Try onboarding if not active
        # (Status response is usually a dictionary with rails active, e.g. {"nigeria": {"status": "ACTIVE"}})
        try:
            start_nigeria_onboarding(user_id, wallet_address)
        except Exception as e:
            print(f"Onboarding submission note: {e}")
            
        # Balances
        balances = get_balances(user_id)
        print(f"Balances: {balances}")
        
    except Exception as e:
        print(f"Test failed with error: {e}")
