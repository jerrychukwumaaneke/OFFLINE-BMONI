import time
import json
from database import init_db, insert_transaction

# Initialize DB first
init_db()

def simulate_esp32_button_press():
    print("\n[SIMULATOR] Pressing ESP32 BOOT button...")
    
    payload = {
        "node_id": "C3_MINI_NODE_SIMULATED",
        "sender_wallet": "08012345678",
        "receiver_wallet": "09087654321",
        "amount": 5000.00
    }
    
    tx_id = insert_transaction(
        node_id=payload["node_id"],
        sender=payload["sender_wallet"],
        receiver=payload["receiver_wallet"],
        amount=payload["amount"]
    )
    
    print(f"[SIMULATOR] Transaction saved to local escrow! Database Record ID: {tx_id}")

if __name__ == "__main__":
    simulate_esp32_button_press()