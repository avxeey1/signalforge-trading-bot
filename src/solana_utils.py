"""
Solana blockchain utilities for SignalForge Trading Bot
"""
import os
import base58
import requests
import asyncio
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams
from solana.transaction import Transaction
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
from datetime import datetime

# Constants
SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"
JUPITER_API = "https://quote-api.jup.ag/v4/quote"

def initialize_wallet(private_key_str):
    """
    Initialize Solana wallet from private key
    
    Args:
        private_key_str: Private key in various formats
    
    Returns:
        Keypair object or None
    """
    try:
        if not private_key_str:
            return None
            
        # Handle different private key formats
        if private_key_str.startswith('['):
            # Handle array format [1,2,3,...]
            private_key = bytes(map(int, private_key_str.strip('[]').split(',')))
        else:
            # Try to decode as base58 (Phantom export format)
            try:
                private_key = base58.b58decode(private_key_str)
            except:
                # Try as hex string
                private_key = bytes.fromhex(private_key_str)
        
        wallet = Keypair.from_bytes(private_key)
        return wallet
    except Exception as e:
        print(f"Wallet initialization error: {e}")
        return None

async def get_wallet_balance(wallet_pubkey):
    """
    Get SOL balance for a wallet
    
    Args:
        wallet_pubkey: Public key as string or Pubkey object
    
    Returns:
        SOL balance as float
    """
    try:
        async with AsyncClient(SOLANA_RPC_URL) as client:
            if isinstance(wallet_pubkey, str):
                pubkey = Pubkey.from_string(wallet_pubkey)
            else:
                pubkey = wallet_pubkey
                
            resp = await client.get_balance(pubkey)
            if resp.value:
                return resp.value / 1e9  # Convert lamports to SOL
            return 0
    except Exception as e:
        print(f"Balance check error: {e}")
        return 0

async def get_token_balances(wallet_address):
    """
    Get token balances for a wallet using Solscan API
    
    Args:
        wallet_address: Wallet public key as string
    
    Returns:
        Tuple of (tokens list, total USD value)
    """
    url = f"https://public-api.solscan.io/account/tokens?account={wallet_address}"
    headers = {"accept": "application/json"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            tokens = []
            total_usd_value = 0
            
            for token in data:
                if token.get("tokenAmount", {}).get("uiAmount", 0) > 0:
                    token_info = {
                        "symbol": token.get("tokenSymbol", "Unknown"),
                        "name": token.get("tokenName", "Unknown"),
                        "balance": token.get("tokenAmount", {}).get("uiAmount", 0),
                        "address": token.get("tokenAddress"),
                        "price": token.get("tokenPrice", 0),
                        "decimals": token.get("tokenAmount", {}).get("decimals", 9),
                        "value": token.get("tokenAmount", {}).get("uiAmount", 0) * token.get("tokenPrice", 0)
                    }
                    tokens.append(token_info)
                    total_usd_value += token_info["value"]
            
            return tokens, total_usd_value
        else:
            return [], 0
    except Exception as e:
        print(f"Token balance error: {e}")
        return [], 0


def get_sol_price():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "solana" in data and "usd" in data["solana"]:
                return data["solana"]["usd"]
            else:
                print("⚠️ Unexpected API response format:", data)
        else:
            print(f"⚠️ CoinGecko API returned status {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Network error in get_sol_price: {e}")
    except Exception as e:
        print(f"⚠️ Unexpected error in get_sol_price: {e}")
    return 0  # fallback price



from time import time

_cached_price = 0
_last_fetch = 0

def get_sol_price():
    global _cached_price, _last_fetch
    now = time()
    if now - _last_fetch < 60:  # cache for 60 seconds
        return _cached_price
    
    # ... fetch as above ...
    if price > 0:
        _cached_price = price
        _last_fetch = now
    return price or _cached_price
    
def get_token_price(token_address, amount_sol=0.0215):
    """
    Get token price from Jupiter API
    
    Args:
        token_address: Token mint address
        amount_sol: Amount of SOL to swap
    
    Returns:
        Token price in SOL or None
    """
    params = {
        "inputMint": token_address,
        "outputMint": "So11111111111111111111111111111111111111112",  # WSOL
        "amount": int(amount_sol * 1e9),
        "slippageBps": 50
    }
    try:
        response = requests.get(JUPITER_API, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("data") and len(data["data"]) > 0:
                return float(data["data"][0]["outAmount"]) / 1e9
        return None
    except Exception as e:
        print(f"Token price error: {e}")
        return None

async def send_sol(wallet, receiver_address, amount):
    """
    Send SOL to another address
    
    Args:
        wallet: Keypair object of sender
        receiver_address: Recipient's wallet address
        amount: Amount in SOL
    
    Returns:
        Tuple of (success, result)
    """
    try:
        async with AsyncClient(SOLANA_RPC_URL) as client:
            # Create transfer instruction
            transfer_ix = transfer(
                TransferParams(
                    from_pubkey=wallet.pubkey(),
                    to_pubkey=Pubkey.from_string(receiver_address),
                    lamports=int(amount * 1e9)  # Convert SOL to lamports
                )
            )
            
            # Get recent blockhash
            recent_blockhash = await client.get_latest_blockhash()
            
            # Create and sign transaction
            transaction = Transaction()
            transaction.add(transfer_ix)
            transaction.recent_blockhash = recent_blockhash.value.blockhash
            transaction.fee_payer = wallet.pubkey()
            
            # Sign and send
            result = await client.send_transaction(transaction, wallet)
            
            return True, result.value
    except Exception as e:
        print(f"Send SOL error: {e}")
        return False, str(e)

def lamports_to_sol(lamports):
    """Convert lamports to SOL"""
    return lamports / 1_000_000_000

def sol_to_lamports(sol):
    """Convert SOL to lamports"""
    return int(sol * 1_000_000_000)
