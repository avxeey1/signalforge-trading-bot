import os
import base58
import requests
import time
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams
from solana.rpc.async_api import AsyncClient

SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"
JUPITER_API = "https://quote-api.jup.ag/v4/quote"

# Cache for SOL price
_last_price = 0
_last_fetch = 0

def initialize_wallet(private_key_str):
    """Initialize Solana wallet from private key (hex, base58, or array)"""
    if not private_key_str:
        return None
    private_key_str = private_key_str.strip().strip('"\'').strip()
    try:
        if private_key_str.startswith('['):
            private_key = bytes(map(int, private_key_str.strip('[]').split(',')))
        elif len(private_key_str) == 64:
            private_key = bytes.fromhex(private_key_str)
        else:
            private_key = base58.b58decode(private_key_str)
        return Keypair.from_bytes(private_key)
    except Exception as e:
        print(f"❌ Wallet init error: {e}")
        return None

async def get_wallet_balance(pubkey):
    """Get SOL balance in SOL"""
    try:
        async with AsyncClient(SOLANA_RPC_URL) as client:
            if isinstance(pubkey, str):
                pubkey = Pubkey.from_string(pubkey)
            resp = await client.get_balance(pubkey)
            return resp.value / 1e9 if resp.value else 0
    except Exception as e:
        print(f"⚠️ Balance error: {e}")
        return 0

async def get_token_balances(wallet_address):
    """Get token balances from Solscan"""
    url = f"https://public-api.solscan.io/account/tokens?account={wallet_address}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            tokens = []
            total_usd = 0
            for token in data:
                if token.get("tokenAmount", {}).get("uiAmount", 0) > 0:
                    tokens.append({
                        "symbol": token.get("tokenSymbol", "Unknown"),
                        "balance": token["tokenAmount"]["uiAmount"],
                        "address": token["tokenAddress"],
                        "price": token.get("tokenPrice", 0),
                    })
                    total_usd += token["tokenAmount"]["uiAmount"] * token.get("tokenPrice", 0)
            return tokens, total_usd
        return [], 0
    except Exception as e:
        print(f"⚠️ Token balance error: {e}")
        return [], 0

def get_sol_price():
    """Get current SOL price from CoinGecko with caching"""
    global _last_price, _last_fetch
    now = time.time()
    if now - _last_fetch < 60:
        return _last_price
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            price = data.get("solana", {}).get("usd", 0)
            if price:
                _last_price = price
                _last_fetch = now
                return price
        # fallback to Jupiter
        jup = requests.get("https://price.jup.ag/v4/price?ids=SOL", timeout=10)
        if jup.status_code == 200:
            price = jup.json().get("data", {}).get("SOL", {}).get("price", 0)
            if price:
                _last_price = price
                _last_fetch = now
                return price
    except Exception as e:
        print(f"⚠️ SOL price error: {e}")
    return _last_price or 0

def get_token_price(token_address, amount_sol=0.0215):
    """Get token price in SOL via Jupiter"""
    params = {
        "inputMint": token_address,
        "outputMint": "So11111111111111111111111111111111111111112",
        "amount": int(amount_sol * 1e9),
        "slippageBps": 50
    }
    try:
        resp = requests.get(JUPITER_API, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("data") and len(data["data"]) > 0:
                return float(data["data"][0]["outAmount"]) / 1e9
    except Exception as e:
        print(f"⚠️ Token price error: {e}")
    return None

async def send_sol(wallet, receiver, amount):
    """Send SOL (simulated or real)"""
    try:
        async with AsyncClient(SOLANA_RPC_URL) as client:
            _ix = transfer(
                TransferParams(
                    from_pubkey=wallet.pubkey(),
                    to_pubkey=Pubkey.from_string(receiver),
                    lamports=int(amount * 1e9)
                )
            )
            # In real implementation, you'd sign and send.
            # Here we simulate.
            return True, "simulated_tx_hash"
    except Exception as e:
        return False, str(e)
