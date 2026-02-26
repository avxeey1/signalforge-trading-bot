"""
Telegram utilities for SignalForge Trading Bot
"""
import os
import re
import requests

# Telegram bot API for sending logs
def send_log_to_telegram(message, bot_token=None, chat_id=None):
    """
    Send log message to Telegram
    
    Args:
        message: Message text to send
        bot_token: Telegram bot token (optional, uses env if not provided)
        chat_id: Telegram chat ID (optional, uses env if not provided)
    
    Returns:
        Boolean indicating success
    """
    if not bot_token:
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not chat_id:
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        print("❌ Telegram bot token or chat ID not configured")
        return False
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'}
    
    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            print("✅ Log sent to Telegram")
            return True
        else:
            print(f"❌ Telegram API error: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Failed to send log to Telegram: {e}")
        return False

def extract_token_address(message):
    """
    Extract Solana token address from message
    
    Args:
        message: Raw message text
    
    Returns:
        Token address or None
    """
    # Solana addresses are base58 strings of 32-44 characters
    match = re.findall(r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b', message)
    return match[-1] if match else None

def format_number(num, decimals=4):
    """Format number with specified decimals"""
    if num is None:
        return "N/A"
    return f"{num:.{decimals}f}"

def truncate_address(address, chars=8):
    """Truncate address for display"""
    if not address:
        return "N/A"
    if len(address) <= chars * 2:
        return address
    return f"{address[:chars]}...{address[-chars:]}"
