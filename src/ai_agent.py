import os
import google.generativeai as genai
from database import get_pending_transactions
from bmoni_client import get_balances

def get_ai_response(user_message: str, bmoni_user_id: str = None) -> str:
    """
    Assembles system state (local pending txs + live balances) and calls
    Gemini 1.5 Flash to provide context-aware financial answers.
    """
    # 1. Retrieve current state
    pending_txs = get_pending_transactions()
    balances_info = None
    if bmoni_user_id:
        try:
            balances_info = get_balances(bmoni_user_id)
        except Exception:
            pass

    # 2. Build system context for the LLM
    context = (
        "You are the BMONI Financial AI Assistant running on an Offline Agent Relay Node.\n"
        "This node collects transactions from offline ESP32 terminals and holds them in a local SQLite escrow.\n"
        "When internet is restored, the agent can sync these transactions to the live BMONI CNGN network.\n\n"
        "Current System State:\n"
    )
    
    context += "--- Local SQLite Pending Offline Queue ---\n"
    if pending_txs:
        for tx in pending_txs:
            context += f"- Record ID: {tx[0]} | Terminal: {tx[1]} | Sender: {tx[2]} | Recipient: {tx[3]} | Amount: {tx[4]} CNGN\n"
    else:
        context += "No pending transactions in local SQLite escrow.\n"
        
    context += "\n--- Live BMONI Blockchain Account State ---\n"
    if balances_info:
        context += f"Smart Wallet Address: {balances_info.get('smartAccountAddress')}\n"
        for bal in balances_info.get("balances", []):
            context += f"- Asset: {bal.get('currency')} | Live Balance: {bal.get('balance')}\n"
    else:
        context += "No active live BMONI smart wallet found/onboarded yet.\n"
        
    context += (
        "\nInstruction: Use the system state above to answer the user's question. "
        "Keep your response friendly, clear, professional, and under 3-4 sentences. "
        "Provide helpful explanations about NGN/CNGN conversion or sync status if queried."
    )

    # 3. Call Gemini API
    # Check both standard names
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        # Graceful fallback for mock demo
        tx_count = len(pending_txs)
        live_balance_str = "0"
        if balances_info and balances_info.get("balances"):
            live_balance_str = balances_info["balances"][0].get("balance", "0")
            
        return (
            f"🤖 [AI Demo Mode] I received your question: \"{user_message}\".\n\n"
            f"Here is your status:\n"
            f"- You have **{tx_count}** offline transaction(s) pending sync.\n"
            f"- Your live wallet balance is **{live_balance_str} CNGN**.\n\n"
            f"💡 *Tip: To enable the full Gemini LLM, set a `GEMINI_API_KEY` in your `.env` file and restart the server.*"
        )
        
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"{context}\n\nUser: {user_message}\nAssistant:"
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"⚠️ Error generating response from Gemini: {str(e)}"

if __name__ == "__main__":
    from database import init_db
    init_db()
    print(get_ai_response("Explain my current balance and if I have any pending syncs."))
