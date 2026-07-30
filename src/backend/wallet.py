from eth_account import Account
from eth_account.messages import encode_defunct
from database import get_profile_value, set_profile_value

def get_or_create_keypair():
    """
    Retrieves the agent's EVM private key from SQLite agent_profile,
    or generates and saves a new one if none exists.
    Returns:
        private_key (str), eth_address (str)
    """
    private_key = get_profile_value("private_key")
    if not private_key:
        print("[WALLET] Generating a new EVM owner keypair...")
        new_account = Account.create()
        private_key = new_account.key.hex()
        eth_address = new_account.address
        set_profile_value("private_key", private_key)
        set_profile_value("eth_address", eth_address)
        print(f"[WALLET] New keypair created. Address: {eth_address}")
    else:
        # derive address from existing key
        account = Account.from_key(private_key)
        eth_address = account.address
        set_profile_value("eth_address", eth_address)
    
    return private_key, eth_address

def sign_eip191_message(message: str, private_key: str) -> str:
    """
    Signs a plain-text challenge message using EIP-191 standard.
    Returns the hex signature (starting with 0x).
    """
    encoded_message = encode_defunct(text=message)
    signed = Account.sign_message(encoded_message, private_key=private_key)
    return "0x" + signed.signature.hex()

if __name__ == "__main__":
    from database import init_db
    init_db()
    pk, addr = get_or_create_keypair()
    print(f"Address: {addr}")
    
    # Test signing
    challenge = "Verify ownership of this wallet for BMONI CNGN onboarding."
    sig = sign_eip191_message(challenge, pk)
    print(f"Signed challenge signature: {sig}")
