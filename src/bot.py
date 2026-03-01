
from telethon.sessions import StringSession

import solana_utils
import telegram_utils
import utils

# Global state
bot_status = "stopped"
bot_start_time = datetime.now()
wallet = None
wallet_pubkey = None
telegram_client = None
trading_history = utils.trading_history
channel_username = os.environ.get("TELEGRAM_CHANNEL")

async def start_monitoring():
    """Start the bot monitoring"""
    global bot_status
    
    if bot_status == "running":
        return "Bot is already running!"
    
    bot_status = "running"
    telegram_utils.send_log_to_telegram("🤖 Bot monitoring started! Now listening for signals.")
    return "✅ Bot monitoring started! Now listening for signals."

async def stop_monitoring():
    """Stop the bot monitoring"""
    global bot_status
    
    if bot_status == "stopped":
        return "Bot is already stopped!"
    
    bot_status = "stopped"
    telegram_utils.send_log_to_telegram("🛑 Bot monitoring stopped!")
    return "🛑 Bot monitoring stopped!"

def setup_handlers(client, wallet_obj, wallet_pubkey_obj):
    """
    Setup all Telegram bot handlers
    
    Args:
        client: TelegramClient instance
        wallet_obj: Solana wallet Keypair
        wallet_pubkey_obj: Wallet public key
    """
    global telegram_client, wallet, wallet_pubkey
    telegram_client = client
    wallet = wallet_obj
    wallet_pubkey = wallet_pubkey_obj

    @client.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        """Start command handler"""
        buttons = [
            [Button.inline("💰 Balance", b"balance"),
             Button.inline("📊 History", b"history")],
            [Button.inline("📈 PnL", b"pnl"),
             Button.inline("🏦 Wallet", b"wallet_address")],
            [Button.inline("▶️ Run", b"runbot"),
             Button.inline("⏹️ Stop", b"stopbot")],
            [Button.inline("ℹ️ About", b"about"),
             Button.inline("❓ Help", b"help")]
        ]
        
        status_emoji = "✅" if bot_status == "running" else "🛑"
        
        await event.reply(
            f"🤖 **SignalForge Trading Bot**\n\n"
            f"**Status**: {status_emoji} {bot_status.upper()}\n"
            f"**Channel**: {channel_username}\n\n"
            f"Select an option below:",
            buttons=buttons
        )

    @client.on(events.NewMessage(pattern='/balance'))
    async def balance_handler(event):
        """Check wallet balance"""
        if not wallet:
            await event.reply("❌ Wallet not initialized")
            return
        
        await event.reply("💰 Fetching wallet balance...")
        
        sol_balance = await solana_utils.get_wallet_balance(str(wallet_pubkey))
        sol_price = solana_utils.get_sol_price()
        sol_value = sol_balance * sol_price
        
        tokens, total_token_value = await solana_utils.get_token_balances(str(wallet_pubkey))
        total_value = sol_value + total_token_value
        
        message = f"💰 **Wallet Balance**\n\n"
        message += f"**SOL**: {sol_balance:.4f} (${sol_value:.2f})\n"
        message += f"**SOL Price**: ${sol_price:.2f}\n\n"
        
        if tokens:
            message += "**Tokens**:\n"
            for token in tokens[:5]:
                message += f"• {token['symbol']}: {token['balance']:.4f} (${token['value']:.2f})\n"
            
            if len(tokens) > 5:
                message += f"\n... and {len(tokens) - 5} more tokens\n"
        
        message += f"\n**Total Portfolio**: ${total_value:.2f}"
        message += f"\n**Address**: `{telegram_utils.truncate_address(str(wallet_pubkey))}`"
        
        await event.reply(message)

    @client.on(events.NewMessage(pattern='/history'))
    async def history_handler(event):
        """Show trading history"""
        if not trading_history:
            await event.reply("📊 No trading history yet.")
            return
        
        message = "📊 **Trading History**\n\n"
        for i, trade in enumerate(trading_history[-5:], 1):
            message += f"**Trade #{i}**\n"
            message += f"Date: {trade['date']}\n"
            message += f"Token: {telegram_utils.truncate_address(trade.get('token', 'Unknown'))}\n"
            message += f"Amount: {trade['amount']:.4f} SOL\n"
            
            if 'return' in trade:
                profit = trade['return'] - trade['amount']
                emoji = "✅" if profit > 0 else "❌"
                message += f"Return: {trade['return']:.4f} SOL {emoji}\n"
            
            message += "\n"
        
        pnl_amount, pnl_percentage, _, _ = utils.calculate_pnl()
        message += f"**Overall PnL**: {pnl_amount:.4f} SOL ({pnl_percentage:.2f}%)"
        
        await event.reply(message)

    @client.on(events.NewMessage(pattern='/pnl'))
    async def pnl_handler(event):
        """Show profit and loss"""
        pnl_amount, pnl_percentage, total_invested, total_returned = utils.calculate_pnl()
        
        if total_invested == 0:
            await event.reply("📈 No trades executed yet. PnL: $0.00 (0.00%)")
            return
        
        sol_price = solana_utils.get_sol_price()
        pnl_usd = pnl_amount * sol_price
        
        message = "📈 **Profit & Loss**\n\n"
        message += f"Total Invested: {total_invested:.4f} SOL\n"
        message += f"Total Returned: {total_returned:.4f} SOL\n"
        message += f"PnL: {pnl_amount:.4f} SOL ({pnl_percentage:.2f}%)\n"
        message += f"PnL (USD): ${pnl_usd:.2f}\n\n"
        
        if pnl_amount > 0:
            message += "✅ Profitable"
        elif pnl_amount < 0:
            message += "❌ Losing"
        else:
            message += "⚪ Break-even"
        
        await event.reply(message)

    @client.on(events.NewMessage(pattern='/wallet'))
    async def wallet_handler(event):
        """Show wallet address"""
        if not wallet:
            await event.reply("❌ Wallet not initialized")
            return
        
        await event.reply(f"🏦 **Your Wallet Address:**\n`{wallet_pubkey}`")

    @client.on(events.NewMessage(pattern='/help'))
    async def help_handler(event):
        """Show help"""
        help_text = """
🤖 **SignalForge Trading Bot - Help**

**Commands:**
/start - Main menu
/balance - Check wallet balance
/history - View trading history
/pnl - Check profit/loss
/wallet - Show wallet address
/runbot - Start monitoring
/stopbot - Stop monitoring
/about - Bot information
/help - This message

**How to use:**
1. Use /runbot to start monitoring
2. Bot will listen to configured channel
3. When signals detected, bot will analyze
4. Check /balance and /pnl regularly
"""
        await event.reply(help_text)

    @client.on(events.NewMessage(pattern='/about'))
    async def about_handler(event):
        """Show about info"""
        uptime = utils.format_uptime(bot_start_time)
        pnl_amount, pnl_percentage, _, _ = utils.calculate_pnl()
        
        message = "ℹ️ **About SignalForge**\n\n"
        message += "Telegram trading bot for Solana\n"
        message += "Monitors channels for token signals\n\n"
        message += f"**Status**: {'✅ Running' if bot_status == 'running' else '🛑 Stopped'}\n"
        message += f"**Uptime**: {uptime}\n"
        message += f"**Trades**: {len(trading_history)}\n"
        message += f"**PnL**: {pnl_amount:.4f} SOL\n"
        message += f"**Channel**: {channel_username}\n\n"
        message += "Use /help to see commands"
        
        await event.reply(message)

    @client.on(events.NewMessage(pattern='/runbot'))
    async def runbot_handler(event):
        """Start bot"""
        result = await start_monitoring()
        await event.reply(result)

    @client.on(events.NewMessage(pattern='/stopbot'))
    async def stopbot_handler(event):
        """Stop bot"""
        result = await stop_monitoring()
        await event.reply(result)

    @client.on(events.CallbackQuery)
    async def callback_handler(event):
        """Handle button callbacks"""
        data = event.data.decode('utf-8')
        
        handlers = {
            "balance": balance_handler,
            "history": history_handler,
            "pnl": pnl_handler,
            "wallet_address": wallet_handler,
            "about": about_handler,
            "help": help_handler,
            "runbot": runbot_handler,
            "stopbot": stopbot_handler
        }
        
        if data in handlers:
            await handlers[data](event)

    @client.on(events.NewMessage(chats=channel_username))
    async def channel_handler(event):
        """Handle channel messages"""
        if bot_status != "running":
            return
        
        msg = event.raw_text
        token_addr = telegram_utils.extract_token_address(msg)
        
        if token_addr:
            print(f"📥 Token detected: {token_addr}")
            telegram_utils.send_log_to_telegram(f"📥 Token: {token_addr}")
            
            price = solana_utils.get_token_price(token_addr)
            
            if price:
                # Record the trade
                utils.add_trade_record(token_addr, 0.0215, price)
                
                print(f"💰 Token price: {price:.6f} SOL")
                telegram_utils.send_log_to_telegram(f"💰 Price: {price:.6f} SOL")
                
                # Simulate trade for testing
                success, return_amount = utils.simulate_trade(0.0215)
                
                if success:
                    utils.trading_history[-1]['return'] = return_amount
                    print(f"✅ Trade simulated: +{return_amount-0.0215:.4f} SOL")
                    telegram_utils.send_log_to_telegram(f"✅ Trade successful: +{return_amount-0.0215:.4f} SOL")
                else:
                    utils.trading_history[-1]['return'] = return_amount
                    print(f"❌ Trade simulated: -{0.0215-return_amount:.4f} SOL")
                    telegram_utils.send_log_to_telegram(f"❌ Trade lost: -{0.0215-return_amount:.4f} SOL")
        else:
            print("⚠️ No token address detected")
"""
Telegram bot handlers for SignalForge Trading Bot
Fixed: Uses bot token instead of user login, absolute imports, and preserves all original commands.
"""
import os
import asyncio
from datetime import datetime
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession

# Absolute imports (no dots)
from solana_utils import (
    get_wallet_balance, get_token_balances, get_sol_price,
    get_token_price, send_sol
)
from telegram_utils import send_log_to_telegram, extract_token_address, truncate_address
from utils import trading_history, add_trade_record, simulate_trade, calculate_pnl

# Global variables (same as original)
bot_status = "stopped"
bot_start_time = datetime.now()
wallet = None
wallet_pubkey = None
telegram_client = None
channel_username = os.environ.get("TELEGRAM_CHANNEL")
TRADE_AMOUNT_SOL = float(os.environ.get("TRADE_AMOUNT_SOL", 0.0215))
TARGET_MULTIPLIER = float(os.environ.get("TARGET_MULTIPLIER", 2.0))

async def start_monitoring():
    """Start the bot monitoring"""
    global bot_status
    if bot_status == "running":
        return "Bot is already running!"
    bot_status = "running"
    send_log_to_telegram("🤖 Bot monitoring started! Now listening for signals.")
    return "✅ Bot monitoring started!"

async def stop_monitoring():
    """Stop the bot monitoring"""
    global bot_status
    if bot_status == "stopped":
        return "Bot is already stopped!"
    bot_status = "stopped"
    send_log_to_telegram("🛑 Bot monitoring stopped!")
    return "🛑 Bot monitoring stopped!"

def setup_handlers(client, wallet_obj, wallet_pubkey_obj):
    """
    Setup all Telegram bot handlers (preserves original functionality)
    
    Args:
        client: TelegramClient instance (bot token based)
        wallet_obj: Solana wallet Keypair
        wallet_pubkey_obj: Wallet public key
    """
    global telegram_client, wallet, wallet_pubkey
    telegram_client = client
    wallet = wallet_obj
    wallet_pubkey = wallet_pubkey_obj

    @client.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        """Start command handler (original buttons)"""
        buttons = [
            [Button.inline("💰 Wallet Balance", b"balance"),
             Button.inline("📊 Trading History", b"history")],
            [Button.inline("📈 PnL", b"pnl"),
             Button.inline("🏦 Wallet Address", b"wallet_address")],
            [Button.inline("📤 Send Funds", b"send_funds"),
             Button.inline("📥 Receive Funds", b"receive_funds")],
            [Button.inline("▶️ Run Bot", b"runbot"),
             Button.inline("⏹️ Stop Bot", b"stopbot")],
            [Button.inline("ℹ️ About", b"about"),
             Button.inline("❓ Help", b"help")],
            [Button.inline("⚠️ Disclaimer", b"disclaimer"),
             Button.inline("🛑 Shutdown", b"shutdown")]
        ]
        
        status_emoji = "✅" if bot_status == "running" else "🛑"
        
        await event.reply(
            f"🤖 **SignalForge Trading Bot**\n\n"
            f"**Status**: {status_emoji} {bot_status.upper()}\n"
            f"**Channel**: {channel_username}\n"
            f"**Trade Amount**: {TRADE_AMOUNT_SOL} SOL\n"
            f"**Target**: {TARGET_MULTIPLIER}x\n\n"
            f"Select an option below:",
            buttons=buttons
        )

    @client.on(events.NewMessage(pattern='/help'))
    async def help_handler(event):
        """Help command handler"""
        help_text = """
🤖 **SignalForge Trading Bot - Help Guide**

**Available Commands:**
/start - Show the main menu
/runbot - Start the bot and begin monitoring
/stopbot - Stop the bot
/balance - Check your wallet balance
/history - View your trading history
/pnl - Check your profit and loss
/wallet - Show your wallet address
/send - Send SOL to another address
/receive - Show your wallet address to receive funds
/about - Information about this bot
/disclaimer - Legal disclaimer
/help - Show this help message
"""
        await event.reply(help_text)

    @client.on(events.NewMessage(pattern='/runbot'))
    async def runbot_handler(event):
        """Run bot command handler"""
        result = await start_monitoring()
        await event.reply(result)

    @client.on(events.NewMessage(pattern='/stopbot'))
    async def stopbot_handler(event):
        """Stop bot command handler"""
        result = await stop_monitoring()
        await event.reply(result)

    @client.on(events.NewMessage(pattern='/wallet'))
    async def wallet_handler(event):
        """Wallet address command handler"""
        if not wallet:
            await event.reply("❌ Wallet not initialized")
            return
        await event.reply(f"🏦 **Your Wallet Address:**\n`{wallet_pubkey}`")

    @client.on(events.NewMessage(pattern='/send'))
    async def send_handler(event):
        """Send funds command handler (original)"""
        if not wallet:
            await event.reply("❌ Wallet not initialized")
            return
        
        message_parts = event.raw_text.split()
        if len(message_parts) < 3:
            await event.reply("❌ Usage: /send <amount> <receiver_address>\nExample: /send 0.1 5gksC...")
            return
        
        try:
            amount = float(message_parts[1])
            receiver = message_parts[2]
            
            if len(receiver) < 32 or len(receiver) > 44:
                await event.reply("❌ Invalid receiver address")
                return
            
            await event.reply(f"🔄 Sending {amount} SOL to {receiver[:8]}...{receiver[-8:]}")
            
            success, result = await send_sol(wallet, receiver, amount)
            
            if success:
                await event.reply(f"✅ Successfully sent {amount} SOL\nTransaction: https://solscan.io/tx/{result}")
            else:
                await event.reply(f"❌ Failed to send SOL: {result}")
                
        except ValueError:
            await event.reply("❌ Invalid amount. Please use numbers only.")

    @client.on(events.NewMessage(pattern='/receive'))
    async def receive_handler(event):
        """Receive funds command handler"""
        if not wallet:
            await event.reply("❌ Wallet not initialized")
            return
        await event.reply(f"📥 **Your Wallet Address:**\n`{wallet_pubkey}`\n\nSend SOL or tokens to this address.")

    @client.on(events.NewMessage(pattern='/balance'))
    async def balance_handler(event):
        """Wallet balance command handler (original)"""
        if not wallet:
            await event.reply("❌ Wallet not initialized")
            return
        
        await event.reply("💰 Fetching wallet balance...")
        
        sol_balance = await get_wallet_balance(str(wallet_pubkey))
        sol_price = get_sol_price()
        sol_value = sol_balance * sol_price
        
        tokens, total_token_value = await get_token_balances(str(wallet_pubkey))
        total_value = sol_value + total_token_value
        
        message = f"💰 **Wallet Balance**\n\n"
        message += f"**SOL**: {sol_balance:.4f} (${sol_value:.2f})\n\n"
        
        if tokens:
            message += "**Tokens**:\n"
            for token in tokens[:5]:
                token_value = token['balance'] * token['price']
                message += f"• {token['symbol']}: {token['balance']:.4f} (${token_value:.2f})\n"
            
            if len(tokens) > 5:
                message += f"\n... and {len(tokens) - 5} more tokens\n"
        
        message += f"\n**Total Portfolio Value**: ${total_value:.2f}"
        await event.reply(message)

    @client.on(events.NewMessage(pattern='/history'))
    async def history_handler(event):
        """Trading history command handler (original)"""
        if not trading_history:
            await event.reply("📊 No trading history yet.")
            return
        
        message = "📊 **Trading History**\n\n"
        for i, trade in enumerate(trading_history[-5:], 1):
            pnl = trade.get('return', 0) - trade.get('amount', 0)
            emoji = "✅" if pnl > 0 else "❌" if pnl < 0 else "⚪"
            
            message += f"**Trade #{i}** {emoji}\n"
            message += f"Date: {trade['date']}\n"
            message += f"Token: {truncate_address(trade.get('token', 'Unknown'))}\n"
            message += f"Amount: {trade['amount']:.4f} SOL\n"
            
            if 'return' in trade:
                message += f"Return: {trade['return']:.4f} SOL\n"
                message += f"PnL: {pnl:+.4f} SOL\n"
            
            message += "\n"
        
        pnl_amount, pnl_percentage, _, _ = calculate_pnl()
        message += f"**Overall PnL**: {pnl_amount:+.4f} SOL ({pnl_percentage:+.2f}%)"
        await event.reply(message)

    @client.on(events.NewMessage(pattern='/pnl'))
    async def pnl_handler(event):
        """PnL command handler (original)"""
        pnl_amount, pnl_percentage, total_invested, total_returned = calculate_pnl()
        
        if total_invested == 0:
            await event.reply("📈 No trades executed yet.")
            return
        
        sol_price = get_sol_price()
        pnl_usd = pnl_amount * sol_price
        
        message = "📈 **Profit & Loss**\n\n"
        message += f"Total Invested: {total_invested:.4f} SOL\n"
        message += f"Total Returned: {total_returned:.4f} SOL\n"
        message += f"PnL: {pnl_amount:+.4f} SOL ({pnl_percentage:+.2f}%)\n"
        message += f"PnL (USD): ${pnl_usd:.2f}\n\n"
        
        if pnl_amount > 0:
            message += "✅ Profitable"
        elif pnl_amount < 0:
            message += "❌ Losing"
        else:
            message += "⚪ Break-even"
        
        await event.reply(message)

    @client.on(events.NewMessage(pattern='/about'))
    async def about_handler(event):
        """About command handler (original)"""
        uptime = datetime.now() - bot_start_time
        hours, remainder = divmod(uptime.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        pnl_amount, pnl_percentage, _, _ = calculate_pnl()
        
        message = "ℹ️ **About SignalForge Trading Bot**\n\n"
        message += """*⚡ SignalForge TradingBot*  
_Your automated gateway to fast, smart, and secure DEX trading on Solana._

SignalForge is a powerful Telegram trading bot that listens to *public signal channels*, extracts *token contract addresses*, and executes *instant trades via Jupiter Aggregator*.\n\n"""
        message += f"**Status**: {'✅ Running' if bot_status == 'running' else '🛑 Stopped'}\n"
        message += f"**Uptime**: {int(hours)}h {int(minutes)}m {int(seconds)}s\n"
        message += f"**Wallet**: {truncate_address(str(wallet_pubkey))}\n"
        message += f"**Trades Executed**: {len(trading_history)}\n"
        message += f"**PnL**: {pnl_amount:+.4f} SOL\n"
        message += f"**Monitoring**: {channel_username}\n\n"
        message += "Use /help to see all available commands."
        
        await event.reply(message)

    @client.on(events.NewMessage(pattern='/disclaimer'))
    async def disclaimer_handler(event):
        """Disclaimer command handler (original)"""
        message = "⚠️ **Disclaimer**\n\n"
        message += "1. This trading bot is provided as-is without any warranties.\n"
        message += "2. Cryptocurrency trading involves significant risk of loss.\n"
        message += "3. Past performance is not indicative of future results.\n"
        message += "4. You are solely responsible for any trading decisions.\n"
        message += "5. The bot developers are not responsible for any financial losses.\n\n"
        message += "By using this bot, you acknowledge and accept these risks."
        
        await event.reply(message)

    @client.on(events.CallbackQuery)
    async def callback_handler(event):
        """Handle button callbacks (original)"""
        data = event.data.decode('utf-8')
        
        if data == "balance":
            await balance_handler(event)
        elif data == "history":
            await history_handler(event)
        elif data == "pnl":
            await pnl_handler(event)
        elif data == "about":
            await about_handler(event)
        elif data == "disclaimer":
            await disclaimer_handler(event)
        elif data == "help":
            await help_handler(event)
        elif data == "runbot":
            result = await start_monitoring()
            await event.edit(result)
        elif data == "stopbot":
            result = await stop_monitoring()
            await event.edit(result)
        elif data == "wallet_address":
            await wallet_handler(event)
        elif data == "send_funds":
            await event.edit("📤 To send funds, use the command: /send <amount> <receiver_address>")
        elif data == "receive_funds":
            await wallet_handler(event)
        elif data == "shutdown":
            await event.edit("🛑 Shutdown command received. Use /runbot to restart.")
        else:
            await event.answer("Unknown command")

    @client.on(events.NewMessage(chats=channel_username))
    async def channel_handler(event):
        """Handle incoming channel messages (original signal processing)"""
        if bot_status != "running":
            return
            
        msg = event.raw_text
        token_addr = extract_token_address(msg)
        
        if token_addr:
            print(f"📥 Token detected: {token_addr}")
            send_log_to_telegram(f"📥 Token: {token_addr}")
            
            price = get_token_price(token_addr, TRADE_AMOUNT_SOL)
            
            if price:
                # Record the trade
                add_trade_record(token_addr, TRADE_AMOUNT_SOL, price)
                
                target = price * TARGET_MULTIPLIER
                
                print(f"💰 Price: {price:.6f} SOL → 🎯 Target: {target:.6f} SOL")
                send_log_to_telegram(f"💰 Price: {price:.6f} SOL → 🎯 Target: {target:.6f} SOL")
                
                # Simulate trade
                success, return_amount = simulate_trade(TRADE_AMOUNT_SOL)
                
                if success:
                    trading_history[-1]['return'] = return_amount
                    profit = return_amount - TRADE_AMOUNT_SOL
                    print(f"✅ Trade successful: +{profit:.4f} SOL")
                    send_log_to_telegram(f"✅ Trade successful: +{profit:.4f} SOL")
                else:
                    trading_history[-1]['return'] = return_amount
                    loss = TRADE_AMOUNT_SOL - return_amount
                    print(f"❌ Trade lost: -{loss:.4f} SOL")
                    send_log_to_telegram(f"❌ Trade lost: -{loss:.4f} SOL")
            else:
                print("⚠️ Could not fetch token price")
                send_log_to_telegram("⚠️ Could not fetch token price")
        else:
            print("⚠️ No token address detected in message")

def init_bot():
    """Initialize the Telegram bot client using bot token (fixes EOF error)"""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    
    if not bot_token:
        print("❌ TELEGRAM_BOT_TOKEN not found in environment variables")
        return None
    
    # Create bot client (no API_ID/API_HASH needed for bot accounts)
    client = TelegramClient(StringSession(), bot_token=bot_token)
    return client
