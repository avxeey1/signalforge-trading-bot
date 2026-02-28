"""
Telegram bot handlers for SignalForge Trading Bot
"""
import os
import asyncio
from datetime import datetime
from telethon import TelegramClient, events, Button
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
