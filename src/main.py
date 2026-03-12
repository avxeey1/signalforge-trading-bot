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
from solana_utils import (
    initialize_wallet, get_wallet_balance, get_token_balances,
    get_sol_price, get_token_price, send_sol
)

load_dotenv()

# ========== Configuration ==========
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL = os.getenv("TELEGRAM_CHANNEL")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
DESTINATION = os.getenv("DESTINATION_ADDRESS")
TRADE_AMOUNT = float(os.getenv("TRADE_AMOUNT_SOL", 0.0215))
TARGET_MULTIPLIER = float(os.getenv("TARGET_MULTIPLIER", 2.0))
DEFAULT_STATUS = os.getenv("DEFAULT_BOT_STATUS", "stopped").lower() == "running"

if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is required")

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
client = TelegramClient(StringSession(), None, None)

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
    if not wallet:
        await event.reply("❌ Wallet not initialized.")
        return
    await event.reply("💰 Fetching balance...")
    sol = await get_wallet_balance(str(wallet_pubkey))
    price = get_sol_price()
    value = sol * price
    tokens, token_value = await get_token_balances(str(wallet_pubkey))
    total = value + token_value
    msg = f"💰 **Balance**\nSOL: {sol:.4f} (${value:.2f})\n"
    if tokens:
        msg += "\n**Tokens**:\n"
        for t in tokens[:5]:
            msg += f"• {t['symbol']}: {t['balance']:.4f} (${t['balance']*t['price']:.2f})\n"
    msg += f"\n**Total**: ${total:.2f}"
    await event.reply(msg)

@client.on(events.NewMessage(pattern='/history'))
async def history_handler(event):
    if not trading_history:
        await event.reply("📊 No trades yet.")
        return
    msg = "📊 **Recent Trades**\n"
    for i, t in enumerate(trading_history[-5:], 1):
        pnl = (t.get('return',0)-t['amount']) if 'return' in t else 0
        emoji = "✅" if pnl>0 else "❌" if pnl<0 else "⚪"
        msg += f"\n**#{i}** {emoji}\n"
        msg += f"Token: {truncate_address(t['token'])}\n"
        msg += f"Amount: {t['amount']:.4f} SOL\n"
        if 'return' in t:
            msg += f"Return: {t['return']:.4f} SOL\n"
    pnl, pct, _, _ = calculate_pnl()
    msg += f"\n**Overall PnL**: {pnl:+.4f} SOL ({pct:+.2f}%)"
    await event.reply(msg)

@client.on(events.NewMessage(pattern='/pnl'))
async def pnl_handler(event):
    pnl, pct, inv, ret = calculate_pnl()
    if inv == 0:
        await event.reply("📈 No trades yet.")
        return
    usd = pnl * get_sol_price()
    await event.reply(
        f"📈 **PnL**\n"
        f"Invested: {inv:.4f} SOL\n"
        f"Returned: {ret:.4f} SOL\n"
        f"PnL: {pnl:+.4f} SOL ({pct:+.2f}%)\n"
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
    hours, rem = divmod(uptime.seconds, 3600)
    minutes, _ = divmod(rem, 60)
    pnl, _, _, _ = calculate_pnl()
    await event.reply(
        f"ℹ️ **About SignalForge**\n\n"
        f"Uptime: {hours}h {minutes}m\n"
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
        await event.reply("❌ Wallet not ready.")
        return
    parts = event.raw_text.split()
    if len(parts) < 3:
        await event.reply("Usage: /send <amount> <address>")
        return
    try:
        amount = float(parts[1])
        addr = parts[2]
        if len(addr) < 32 or len(addr) > 44:
            await event.reply("❌ Invalid address.")
            return
        await event.reply(f"🔄 Sending {amount} SOL...")
        success, tx = await send_sol(wallet, addr, amount)
        if success:
            await event.reply(f"✅ Sent! Tx: {tx}")
        else:
            await event.reply(f"❌ Failed: {tx}")
    except ValueError:
        await event.reply("❌ Invalid amount.")

@client.on(events.NewMessage(pattern='/receive'))
async def receive_handler(event):
    if wallet_pubkey:
        await event.reply(f"📥 **Receive**\n`{wallet_pubkey}`")
    else:
        await event.reply("❌ Wallet not available.")

@client.on(events.CallbackQuery)
async def callback_handler(event):
    data = event.data.decode()
    handlers = {
        "balance": balance_handler,
        "history": history_handler,
        "pnl": pnl_handler,
        "wallet": wallet_handler,
        "run": runbot_handler,
        "stop": stopbot_handler,
        "about": about_handler,
        "help": help_handler,
    }
    if data in handlers:
        await handlers[data](event)

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

async def main():
    print("🚀 SignalForge Bot starting...")
    await client.start(bot_token=BOT_TOKEN)  # Token used HERE, not in constructor
    me = await client.get_me()
    print(f"✅ Logged in as {me.username or me.first_name}")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
    
