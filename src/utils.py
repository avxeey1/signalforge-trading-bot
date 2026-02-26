"""
General utilities for SignalForge Trading Bot
"""
import os
import json
import time
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# Trading history storage
trading_history = []
transaction_history = []

def calculate_pnl(trades=None):
    """
    Calculate profit and loss from trading history
    
    Args:
        trades: List of trade records (uses global if None)
    
    Returns:
        Tuple of (pnl_amount, pnl_percentage, total_invested, total_returned)
    """
    if trades is None:
        trades = trading_history
    
    if not trades:
        return 0, 0, 0, 0
    
    total_invested = sum(trade.get('amount', 0) for trade in trades)
    total_returned = sum(trade.get('return', 0) for trade in trades)
    
    pnl_amount = total_returned - total_invested
    pnl_percentage = (pnl_amount / total_invested * 100) if total_invested > 0 else 0
    
    return pnl_amount, pnl_percentage, total_invested, total_returned

def add_trade_record(token, amount, price=None, return_amount=None):
    """
    Add a trade record to history
    
    Args:
        token: Token address or symbol
        amount: Trade amount in SOL
        price: Token price at entry
        return_amount: Return amount if trade completed
    
    Returns:
        The created trade record
    """
    trade = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "timestamp": time.time(),
        "token": token,
        "amount": amount,
        "price": price
    }
    
    if return_amount is not None:
        trade["return"] = return_amount
    
    trading_history.append(trade)
    
    # Keep only last 100 trades to manage memory
    if len(trading_history) > 100:
        trading_history.pop(0)
    
    return trade

def add_transaction_record(tx_type, asset, amount, receiver=None, tx_hash=None):
    """
    Add a transaction record to history
    
    Args:
        tx_type: Transaction type (send, receive, swap)
        asset: Asset symbol (SOL, USDC, etc.)
        amount: Transaction amount
        receiver: Receiver address (for sends)
        tx_hash: Transaction hash
    
    Returns:
        The created transaction record
    """
    tx = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "timestamp": time.time(),
        "type": tx_type,
        "asset": asset,
        "amount": amount,
        "receiver": receiver,
        "tx_hash": tx_hash
    }
    
    transaction_history.append(tx)
    
    # Keep only last 50 transactions
    if len(transaction_history) > 50:
        transaction_history.pop(0)
    
    return tx

def format_uptime(start_time):
    """Format uptime from start time"""
    uptime = datetime.now() - start_time
    hours, remainder = divmod(uptime.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"

def simulate_trade(amount, success_rate=0.7, min_return=0.5, max_return=3.0):
    """
    Simulate a trade for testing purposes
    
    Args:
        amount: Trade amount
        success_rate: Probability of success (0-1)
        min_return: Minimum return multiplier on loss
        max_return: Maximum return multiplier on success
    
    Returns:
        Tuple of (success, return_amount)
    """
    success = random.random() < success_rate
    
    if success:
        return_amount = amount * random.uniform(1.5, max_return)
    else:
        return_amount = amount * random.uniform(min_return, 0.95)
    
    return success, return_amount

def load_env_file(filepath=".env"):
    """Load environment variables from .env file"""
    try:
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip().strip('"').strip("'")
        return True
    except Exception as e:
        print(f"Error loading .env file: {e}")
        return False
