
 #!/usr/bin/env python3
"""
 SignalForge Trading Bot – Telegram only.
 """
import os
import re
import asyncio
import random
from datetime import datetime
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from dotenv import load_dotenv
 
 # Import helpers
try:
    from .solana_utils import (
        initialize_wallet, get_wallet_balance, get_token_balances,
        get_sol_price, get_token_price, send_sol,
    )
except ImportError:
    from solana_utils import (  # type: ignore
        initialize_wallet, get_wallet_balance, get_token_balances,
        get_sol_price, get_token_price, send_sol,
    )
 load_dotenv()
 
 # ========== Configuration ==========
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
CHANNEL = os.getenv("TELEGRAM_CHANNEL")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
DESTINATION = os.getenv("DESTINATION_ADDRESS")
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT_SOL", 0.0215))
TARGET_MULTIPLIER = float(os.getenv("TARGET_MULTIPLIER", 2.0))
DEFAULT_STATUS = os.getenv("DEFAULT_BOT_STATUS", "stopped").lower() == "running"
 

def _validate_runtime_config():
    errors = []
    if not BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN is required")
    if API_ID <= 0:
        errors.append("TELEGRAM_API_ID must be configured and greater than 0")
    if not API_HASH:
        errors.append("TELEGRAM_API_HASH is required")
    if TRADE_AMOUNT <= 0:
        errors.append("TRADE_AMOUNT_SOL must be greater than 0")
    if TARGET_MULTIPLIER <= 0:
        errors.append("TARGET_MULTIPLIER must be greater than 0")
    return errors
 
 # ========== Global State ==========
wallet = initialize_wallet(PRIVATE_KEY)
wallet_pubkey = wallet.pubkey() if wallet else None
bot_status = "running" if DEFAULT_STATUS else "stopped"
bot_start_time = datetime.now()
trading_history = []  # list of dicts: date, token, amount, price, return
 
 # ========== Utilities ==========
def extract_token_address(text):
     match = re.findall(r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b', text)
     return match[-1] if match else None
 
def truncate_address(addr, chars=8):
     if not addr or len(addr) <= chars*2:
         return addr
     return f"{addr[:chars]}...{addr[-chars:]}"
 
def simulate_trade(amount):
     """Random trade outcome for demo"""
     success = random.random() > 0.3
     if success:
         ret = amount * random.uniform(1.5, 3.0)
     else:
         ret = amount * random.uniform(0.5, 0.9)
     return success, ret
 
def calculate_pnl():
     total_invested = sum(t.get('amount', 0) for t in trading_history)
     total_returned = sum(t.get('return', 0) for t in trading_history)
     pnl = total_returned - total_invested
     pct = (pnl / total_invested * 100) if total_invested else 0
     return pnl, pct, total_invested, total_returned
 
def add_trade(token, amount, price=None, ret=None):
     trading_history.append({
         "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         "token": token,
         "amount": amount,
         "price": price,
         "return": ret
     })
 
 # ========== Telegram Bot Handlers ==========
client = TelegramClient(StringSession(), API_ID or 1, API_HASH or "dummy")
 
@client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
 buttons = [
  [Button.inline("💰 Balance", b"balance"),
   Button.inline("📊 History", b"history")],
  [Button.inline("📈 PnL", b"pnl"),
   Button.inline("🏦 Wallet", b"wallet")],
  [Button.inline("▶️ Run", b"run"),
   Button.inline("⏹️ Stop", b"stop")],
  [Button.inline("ℹ️ About", b"about"),
   Button.inline("❓ Help", b"help")],
 ]
 status_emoji = "✅" if bot_status == "running" else "🛑"
 await event.reply(
         f"🤖 **SignalForge Bot**\n\n"
         f"Status: {status_emoji} {bot_status.upper()}\n"
         f"Channel: {CHANNEL}\n"
         f"Trade amount: {TRADE_AMOUNT} SOL\n"
         f"Target: {TARGET_MULTIPLIER}x",
         buttons=buttons
 )
 
@client.on(events.NewMessage(pattern='/balance'))
 async def balance_handler(event):
  async def pnl_handler(event):
         f"USD: ${usd:.2f}"
)
 
 @client.on(events.NewMessage(pattern='/wallet'))
 async def wallet_handler(event):
     if wallet_pubkey:
         await event.reply(f"🏦 **Wallet**\n`{wallet_pubkey}`")
     else:
         await event.reply("❌ Wallet not available.")
 
 @client.on(events.NewMessage(pattern='/runbot'))
 async def runbot_handler(event):
     global bot_status
     bot_status = "running"
     await event.reply("✅ Bot started monitoring.")
 
 @client.on(events.NewMessage(pattern='/stopbot'))
 async def stopbot_handler(event):
     global bot_status
     bot_status = "stopped"
     await event.reply("🛑 Bot stopped.")
 
 @client.on(events.NewMessage(pattern='/about'))
 async def about_handler(event):
     uptime = datetime.now() - bot_start_time
-    hours, rem = divmod(uptime.seconds, 3600)
+    total_seconds = int(uptime.total_seconds())
+    hours, rem = divmod(total_seconds, 3600)
     minutes, _ = divmod(rem, 60)
+    days, hours = divmod(hours, 24)
     pnl, _, _, _ = calculate_pnl()
+    uptime_text = f"{days}d {hours}h {minutes}m" if days else f"{hours}h {minutes}m"
     await event.reply(
         f"ℹ️ **About SignalForge**\n\n"
-        f"Uptime: {hours}h {minutes}m\n"
+        f"Uptime: {uptime_text}\n"
         f"Trades: {len(trading_history)}\n"
         f"PnL: {pnl:+.4f} SOL\n"
         f"Channel: {CHANNEL}"
     )
 
 @client.on(events.NewMessage(pattern='/help'))
 async def help_handler(event):
     await event.reply(
         "**Commands**\n"
         "/start – Main menu\n"
         "/balance – Wallet balance\n"
         "/history – Trade history\n"
         "/pnl – Profit/Loss\n"
         "/wallet – Show address\n"
         "/runbot – Start monitoring\n"
         "/stopbot – Stop monitoring\n"
         "/send – Send SOL (usage: /send <amount> <address>)\n"
         "/receive – Show address\n"
         "/about – Bot info\n"
         "/help – This message"
     )
 
 @client.on(events.NewMessage(pattern='/send'))
 async def send_handler(event):
     if not wallet:
            async def callback_handler(event):
             @client.on(events.NewMessage(chats=CHANNEL))
             async def channel_handler(event):
              if bot_status != "running":
               return
     msg = event.raw_text
     token = extract_token_address(msg)
     if not token:
         return
     print(f"📥 Signal: {token}")
     price = get_token_price(token, TRADE_AMOUNT)
     if price:
         add_trade(token, TRADE_AMOUNT, price)
         target = price * TARGET_MULTIPLIER
         print(f"💰 Price: {price:.6f} → Target: {target:.6f}")
         success, ret = simulate_trade(TRADE_AMOUNT)
         trading_history[-1]['return'] = ret
         diff = ret - TRADE_AMOUNT
         print(f"{'✅' if success else '❌'} Trade: {diff:+.4f} SOL")
     else:
         print("⚠️ Could not fetch price.")
 
 
 # ========== Main ==========
 async def main():
    config_errors = _validate_runtime_config()
    if config_errors:
        raise ValueError("Configuration errors: " + "; ".join(config_errors))

     print("🚀 SignalForge Bot starting...")
     # Start with bot token - this overrides the dummy credentials
     await client.start(bot_token=BOT_TOKEN)
     me = await client.get_me()
     print(f"✅ Logged in as {me.username or me.first_name}")
     print(f"📡 Monitoring channel: {CHANNEL}")
     print(f"💰 Trade amount: {TRADE_AMOUNT} SOL")
     print(f"🎯 Target multiplier: {TARGET_MULTIPLIER}x")
     print("=" * 50)
     await client.run_until_disconnected()
 
 if __name__ == "__main__":
     asyncio.run(main())
