import os
import re
import requests
import json
import time
import asyncio
import aiohttp
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
from flask_socketio import SocketIO
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams
from solana.transaction import Transaction
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
from dotenv import load_dotenv
import sys
import random
import base58

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))
CORS(app)
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*")

#=== Load Environment Variables ===
api_id_str = os.environ.get("API_ID")
api_hash = os.environ.get("API_HASH")
channel_username = os.environ.get("TELEGRAM_CHANNEL")
private_key_str = os.environ.get("PRIVATE_KEY")
DESTINATION_ADDRESS = os.environ.get("DESTINATION_ADDRESS")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

#=== Global Variables ===
trading_history = []
token_balances = {}
transaction_history = []
bot_start_time = datetime.now()
bot_status = "stopped"
monitoring_task = None
telegram_client = None
wallet = None
wallet_pubkey = None

#=== Constants ===
TRADE_AMOUNT_SOL = float(os.environ.get("TRADE_AMOUNT_SOL", 0.0215))
TARGET_MULTIPLIER = float(os.environ.get("TARGET_MULTIPLIER", 2.0))
JUPITER_API = "https://quote-api.jup.ag/v4/quote"

#=== Initialize Wallet ===
def initialize_wallet():
    global wallet, wallet_pubkey
    if private_key_str:
        try:
            # Handle different private key formats
            if private_key_str.startswith('['):
                private_key = bytes(map(int, private_key_str.strip('[]').split(',')))
            else:
                # Try to decode as base58
                private_key = base58.b58decode(private_key_str)
            
            wallet = Keypair.from_bytes(private_key)
            wallet_pubkey = wallet.pubkey()
            return True
        except Exception as e:
            print(f"Wallet initialization error: {e}")
            return False
    return False

#=== Function to get wallet balance ===
async def get_wallet_balance(wallet_pubkey: str):
    try:
        async with AsyncClient("https://api.mainnet-beta.solana.com") as client:
            pubkey = Pubkey.from_string(wallet_pubkey)
            resp = await client.get_balance(pubkey)
            if resp.value:
                return resp.value / 1e9  # Convert lamports to SOL
            return 0
    except Exception as e:
        print(f"Balance check error: {e}")
        return 0

#=== Function to get token balances ===
async def get_token_balances(wallet_address):
    url = f"https://public-api.solscan.io/account/tokens?account={wallet_address}"
    headers = {"accept": "application/json"}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            tokens = []
            total_usd_value = 0
            
            for token in data:
                if token.get("tokenAmount", {}).get("uiAmount", 0) > 0:
                    token_info = {
                        "symbol": token.get("tokenSymbol", "Unknown"),
                        "balance": token.get("tokenAmount", {}).get("uiAmount", 0),
                        "address": token.get("tokenAddress"),
                        "price": token.get("tokenPrice", 0),
                        "decimals": token.get("tokenAmount", {}).get("decimals", 9)
                    }
                    tokens.append(token_info)
                    total_usd_value += token_info["balance"] * token_info["price"]
            
            return tokens, total_usd_value
        else:
            return [], 0
    except Exception as e:
        print(f"Token balance error: {e}")
        return [], 0

#=== Function to get SOL price in USD ===
def get_sol_price():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
        response = requests.get(url)
        data = response.json()
        return data["solana"]["usd"]
    except:
        return 0

#=== Extract Solana token address ===
def extract_token_address(message):
    match = re.findall(r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b', message)
    return match[-1] if match else None

#=== Get token price from Jupiter API ===
def get_token_price(token_address):
    params = {
        "inputMint": token_address,
        "outputMint": "So11111111111111111111111111111111111111112",
        "amount": int(TRADE_AMOUNT_SOL * 1e9),
        "slippageBps": 50
    }
    try:
        res = requests.get(JUPITER_API, params=params)
        if res.status_code == 200:
            data = res.json()
            return float(data["data"][0]["outAmount"]) / 1e9
        else:
            return None
    except Exception as e:
        print(f"Token price error: {e}")
        return None

#=== Send log to Telegram ===
def send_log_to_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {'chat_id': TELEGRAM_CHAT_ID, 'text': message}
    try:
        requests.post(url, data=data)
        print("✅ Log Sent to Telegram successfully 📡")
        return True
    except Exception as e:
        print(f"❌ Failed to send log to Telegram: {e}")
        return False

#=== Send SOL ===
async def send_sol(receiver_address, amount):
    try:
        async with AsyncClient("https://api.mainnet-beta.solana.com") as client:
            # Create transfer instruction
            transfer_ix = transfer(
                TransferParams(
                    from_pubkey=wallet.pubkey(),
                    to_pubkey=Pubkey.from_string(receiver_address),
                    lamports=int(amount * 1e9)  # Convert SOL to lamports
                )
            )
            
            # Create transaction
            transaction = Transaction()
            transaction.add(transfer_ix)
            
            # Send transaction
            result = await client.send_transaction(transaction, wallet)
            
            # Record transaction
            transaction_history.append({
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": "send",
                "asset": "SOL",
                "amount": amount,
                "receiver": receiver_address,
                "tx_hash": result.value
            })
            
            return True, result.value
    except Exception as e:
        print(f"Send SOL error: {e}")
        return False, str(e)

#=== Calculate PnL ===
def calculate_pnl():
    if not trading_history:
        return 0, 0, 0, 0
    
    total_invested = sum(trade['amount'] for trade in trading_history)
    total_returned = sum(trade.get('return', 0) for trade in trading_history)
    
    pnl_amount = total_returned - total_invested
    pnl_percentage = (pnl_amount / total_invested * 100) if total_invested > 0 else 0
    
    return pnl_amount, pnl_percentage, total_invested, total_returned

#=== Start monitoring channel ===
async def start_monitoring():
    global bot_status
    
    if bot_status == "running":
        return "Bot is already running!"
    
    bot_status = "running"
    socketio.emit('bot_status', {'status': 'running'})
    socketio.emit('notification', {
        'title': 'Bot Started',
        'message': 'Signal monitoring has been enabled',
        'type': 'success'
    })
    
    send_log_to_telegram("🤖 Bot monitoring started! Now listening for signals.")
    
    return "✅ Bot monitoring started! Now listening for signals."

#=== Stop monitoring channel ===
async def stop_monitoring():
    global bot_status
    
    if bot_status == "stopped":
        return "Bot is already stopped!"
    
    bot_status = "stopped"
    socketio.emit('bot_status', {'status': 'stopped'})
    socketio.emit('notification', {
        'title': 'Bot Stopped',
        'message': 'Signal monitoring has been disabled',
        'type': 'warning'
    })
    
    send_log_to_telegram("🛑 Bot monitoring stopped!")
    
    return "🛑 Bot monitoring stopped!"

#=== Initialize Telegram Client ===
def init_telegram_client():
    global telegram_client
    
    if not api_id_str or not api_hash:
        return False
        
    try:
        api_id = int(api_id_str)
        telegram_client = TelegramClient(StringSession(), api_id, api_hash)
        return True
    except Exception as e:
        print(f"Telegram client error: {e}")
        return False

#=== Background Tasks ===
def background_status_updater():
    """Background task to update dashboard status periodically"""
    while True:
        try:
            time.sleep(5)
            # Emit status update to all connected clients
            uptime = datetime.now() - bot_start_time
            hours, remainder = divmod(uptime.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            
            pnl_amount, pnl_percentage, _, _ = calculate_pnl()
            sol_price = get_sol_price()
            pnl_usd = pnl_amount * sol_price
            
            socketio.emit('status_update', {
                'status': bot_status,
                'uptime': f"{int(hours)}h {int(minutes)}m {int(seconds)}s",
                'trades': len(trading_history),
                'pnl': {
                    'amount': pnl_amount,
                    'percentage': pnl_percentage,
                    'usd': pnl_usd
                }
            })
        except Exception as e:
            print(f"Error in background task: {e}")

#=== Initialize Application ===
def init_app():
    # Initialize wallet
    wallet_initialized = initialize_wallet()
    
    # Initialize Telegram client
    telegram_initialized = init_telegram_client()
    
    print("SignalForge Dashboard Initialized")
    print(f"Wallet initialized: {wallet_initialized}")
    print(f"Telegram client initialized: {telegram_initialized}")
    
    # Start background task
    threading.Thread(target=background_status_updater, daemon=True).start()

#=== Flask Routes ===
@app.route('/')
def index():
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == os.environ.get('DASHBOARD_PASSWORD', 'admin123'):
            session['authenticated'] = True
            return redirect(url_for('index'))
        return render_template('login.html', error='Invalid password')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    return redirect(url_for('login'))

@app.route('/api/status')
def api_status():
    uptime = datetime.now() - bot_start_time
    hours, remainder = divmod(uptime.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    
    pnl_amount, pnl_percentage, total_invested, total_returned = calculate_pnl()
    sol_price = get_sol_price()
    pnl_usd = pnl_amount * sol_price
    
    return jsonify({
        'status': bot_status,
        'uptime': f"{int(hours)}h {int(minutes)}m {int(seconds)}s",
        'trades': len(trading_history),
        'wallet_initialized': wallet is not None,
        'telegram_connected': telegram_client is not None,
        'pnl': {
            'amount': pnl_amount,
            'percentage': pnl_percentage,
            'usd': pnl_usd,
            'invested': total_invested,
            'returned': total_returned
        }
    })

@app.route('/api/balance')
async def api_balance():
    if not wallet:
        return jsonify({'error': 'Wallet not initialized'})
    
    sol_balance = await get_wallet_balance(str(wallet_pubkey))
    sol_price = get_sol_price()
    sol_value = sol_balance * sol_price
    
    tokens, total_token_value = await get_token_balances(str(wallet_pubkey))
    total_value = sol_value + total_token_value
    
    return jsonify({
        'sol': {
            'balance': sol_balance,
            'value': sol_value,
            'price': sol_price
        },
        'tokens': tokens,
        'total_value': total_value
    })

@app.route('/api/history')
def api_history():
    return jsonify({
        'trades': trading_history[-20:],
        'transactions': transaction_history[-20:]
    })

@app.route('/api/start', methods=['POST'])
async def api_start():
    result = await start_monitoring()
    return jsonify({'message': result})

@app.route('/api/stop', methods=['POST'])
async def api_stop():
    result = await stop_monitoring()
    return jsonify({'message': result})

@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    if request.method == 'POST':
        global TRADE_AMOUNT_SOL, TARGET_MULTIPLIER
        
        data = request.json
        if 'trade_amount' in data:
            TRADE_AMOUNT_SOL = float(data['trade_amount'])
        if 'target_multiplier' in data:
            TARGET_MULTIPLIER = float(data['target_multiplier'])
        
        socketio.emit('notification', {
            'title': 'Settings Updated',
            'message': 'Trading parameters have been updated',
            'type': 'success'
        })
        
        return jsonify({'message': 'Settings updated successfully'})
    
    return jsonify({
        'trade_amount': TRADE_AMOUNT_SOL,
        'target_multiplier': TARGET_MULTIPLIER
    })

@app.route('/api/send', methods=['POST'])
async def api_send():
    if not wallet:
        return jsonify({'error': 'Wallet not initialized'})
    
    data = request.json
    receiver = data.get('receiver')
    amount = float(data.get('amount', 0))
    asset = data.get('asset', 'SOL')
    
    if asset == 'SOL':
        success, result = await send_sol(receiver, amount)
        if success:
            return jsonify({'message': f'Sent {amount} SOL to {receiver}', 'tx_hash': result})
        else:
            return jsonify({'error': f'Failed to send SOL: {result}'}), 400
    else:
        return jsonify({'error': 'Only SOL transfers are currently supported'}), 400

#=== SocketIO Events ===
@socketio.on('connect')
def handle_connect():
    emit('bot_status', {'status': bot_status})
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

#=== Telegram Bot Handlers ===
def setup_telegram_handlers():
    if not telegram_client:
        return
    
    # Command handlers
    @telegram_client.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        """Start command handler"""
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
        
        await event.reply(
            "🤖 **SignalForge Trading Bot**\n\n"
            "Available commands:\n"
            "/start - Show this menu\n"
            "/runbot - Start the bot\n"
            "/stopbot - Stop the bot\n"
            "/balance - Check wallet balance\n"
            "/history - View trading history\n"
            "/pnl - Check profit and loss\n"
            "/wallet - Show wallet address\n"
            "/send - Send funds\n"
            "/receive - Receive funds\n"
            "/help - Show help information\n"
            "/about - About this bot\n"
            "/disclaimer - Legal disclaimer\n\n"
            "**Current Status**: " + ("✅ Running" if bot_status == "running" else "🛑 Stopped") + "\n\n"
            "Select an option below:",
            buttons=buttons
        )

    @telegram_client.on(events.NewMessage(pattern='/help'))
    async def help_handler(event):
        """Help command handler"""
        help_text = """
🤖 **SignalForge Trading Bot - Help Guide**

**Available Commands:**
/start - Show the main menu
/runbot - Start the bot and begin monitoring
/stopbot - Stop the bot from monitoring
/balance - Check your wallet balance and portfolio value
/history - View your trading history
/pnl - Check your profit and loss
/wallet - Show your wallet address
/send - Send SOL to another address
/receive - Show your wallet address to receive funds
/about - Information about this bot
/disclaimer - Legal disclaimer
/help - Show this help message

**How to Use:**
1. Use /runbot to start the bot
2. The bot will monitor the configured Telegram channel for signals
3. When a signal is detected, it will analyze the token
4. If conditions are favorable, it will execute a trade
5. You can check your balance and performance at any time

**Note:** This is a simulation bot. In a real implementation, it would execute actual trades on the Solana blockchain.
"""
        await event.reply(help_text)

    @telegram_client.on(events.NewMessage(pattern='/runbot'))
    async def runbot_handler(event):
        """Run bot command handler"""
        result = await start_monitoring()
        await event.reply(result)

    @telegram_client.on(events.NewMessage(pattern='/stopbot'))
    async def stopbot_handler(event):
        """Stop bot command handler"""
        result = await stop_monitoring()
        await event.reply(result)

    @telegram_client.on(events.NewMessage(pattern='/wallet'))
    async def wallet_handler(event):
        """Wallet address command handler"""
        if not wallet:
            await event.reply("❌ Wallet not initialized")
            return
        
        await event.reply(f"🏦 **Your Wallet Address:**\n`{wallet_pubkey}`\n\nUse this address to receive SOL and tokens.")

    @telegram_client.on(events.NewMessage(pattern='/send'))
    async def send_handler(event):
        """Send funds command handler"""
        if not wallet:
            await event.reply("❌ Wallet not initialized")
            return
        
        # Extract receiver and amount from message
        message_parts = event.raw_text.split()
        if len(message_parts) < 3:
            await event.reply("❌ Usage: /send <amount> <receiver_address>\nExample: /send 0.1 5gksC...")
            return
        
        try:
            amount = float(message_parts[1])
            receiver = message_parts[2]
            
            # Validate receiver address
            if len(receiver) < 32 or len(receiver) > 44:
                await event.reply("❌ Invalid receiver address")
                return
            
            await event.reply(f"🔄 Sending {amount} SOL to {receiver[:8]}...{receiver[-8:]}")
            
            # Send SOL
            success, result = await send_sol(receiver, amount)
            
            if success:
                await event.reply(f"✅ Successfully sent {amount} SOL\nTransaction: https://solscan.io/tx/{result}")
            else:
                await event.reply(f"❌ Failed to send SOL: {result}")
                
        except ValueError:
            await event.reply("❌ Invalid amount. Please use numbers only.")

    @telegram_client.on(events.NewMessage(pattern='/receive'))
    async def receive_handler(event):
        """Receive funds command handler"""
        if not wallet:
            await event.reply("❌ Wallet not initialized")
            return
        
        await event.reply(f"📥 **Your Wallet Address:**\n`{wallet_pubkey}`\n\nSend SOL or tokens to this address.")

    @telegram_client.on(events.NewMessage(pattern='/balance'))
    async def balance_handler(event):
        """Wallet balance command handler"""
        if not wallet:
            await event.reply("❌ Wallet not initialized")
            return
        
        sol_balance = await get_wallet_balance(str(wallet_pubkey))
        sol_price = get_sol_price()
        sol_value = sol_balance * sol_price
        
        tokens, total_token_value = await get_token_balances(str(wallet_pubkey))
        total_value = sol_value + total_token_value
        
        message = f"💰 **Wallet Balance**\n\n"
        message += f"**SOL**: {sol_balance:.4f} (${sol_value:.2f})\n\n"
        
        if tokens:
            message += "**Tokens**:\n"
            for token in tokens[:5]:  # Show first 5 tokens to avoid message too long
                token_value = token['balance'] * token['price']
                message += f"• {token['symbol']}: {token['balance']:.4f} (${token_value:.2f})\n"
            
            if len(tokens) > 5:
                message += f"\n... and {len(tokens) - 5} more tokens\n"
        
        message += f"\n**Total Portfolio Value**: ${total_value:.2f}"
        
        await event.reply(message)

    @telegram_client.on(events.NewMessage(pattern='/history'))
    async def history_handler(event):
        """Trading history command handler"""
        if not trading_history:
            await event.reply("📊 No trading history yet.")
            return
        
        message = "📊 **Trading History**\n\n"
        for i, trade in enumerate(trading_history[-5:], 1):  # Show last 5 trades
            message += f"**Trade #{i}**\n"
            message += f"Date: {trade['date']}\n"
            message += f"Token: {trade.get('token', 'Unknown')[:8]}...\n"
            message += f"Amount: {trade['amount']:.4f} SOL\n"
            
            if 'return' in trade:
                profit = trade['return'] - trade['amount']
                message += f"Return: {trade['return']:.4f} SOL\n"
                message += f"Profit: {profit:.4f} SOL\n"
            
            message += "\n"
        
        pnl_amount, pnl_percentage, _, _ = calculate_pnl()
        message += f"**Overall PnL**: {pnl_amount:.4f} SOL ({pnl_percentage:.2f}%)"
        
        await event.reply(message)

    @telegram_client.on(events.NewMessage(pattern='/pnl'))
    async def pnl_handler(event):
        """PnL command handler"""
        pnl_amount, pnl_percentage, total_invested, total_returned = calculate_pnl()
        
        if not trading_history:
            await event.reply("📈 No trades executed yet. PnL is $0.00 (0.00%)")
            return
        
        sol_price = get_sol_price()
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

    @telegram_client.on(events.NewMessage(pattern='/about'))
    async def about_handler(event):
        """About command handler"""
        uptime = datetime.now() - bot_start_time
        hours, remainder = divmod(uptime.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        message = "ℹ️ **About SignalForge Trading Bot**\n\n"
        message += """*⚡ SignalForge TradingBot*  
_Your automated gateway to fast, smart, and secure DEX trading on Solana._

SignalForge is a powerful Telegram trading bot that listens to *public signal channels*, extracts *token contract addresses*, and executes *instant trades via Jupiter Aggregator*—so you never miss a degen opportunity again!

*Key Features:*
- 🚀 Auto-buy on Solana DEX as soon as signal drops
- 📈 Auto-sell when price reaches 2x (or your set target)
- 🔐 Fully non-custodial — trades from your *own Phantom wallet*
- ⚙️ Fast, accurate contract parsing using AI-based filtering
- 📡 Built to react in real-time, 24/7

*Perfect for:*  
Degen hunters, signal followers, and crypto traders who want to automate gains and avoid rugs.\n\n"""
        message += f"**Status**: {'✅ Running' if bot_status == 'running' else '🛑 Stopped'}\n"
        message += f"**Uptime**: {int(hours)}h {int(minutes)}m {int(seconds)}s\n"
        message += f"**Wallet**: {str(wallet_pubkey)[:8]}...{str(wallet_pubkey)[-8:]}\n"
        message += f"**Trades Executed**: {len(trading_history)}\n"
        message += f"**Monitoring**: {channel_username}\n\n"
        message += "Use /help to see all available commands."
        
        await event.reply(message)

    @telegram_client.on(events.NewMessage(pattern='/disclaimer'))
    async def disclaimer_handler(event):
        """Disclaimer command handler"""
        message = "⚠️ **Disclaimer**\n\n"
        message += "1. This trading bot is provided as-is without any warranties.\n"
        message += "2. Cryptocurrency trading involves significant risk of loss.\n"
        message += "3. Past performance is not indicative of future results.\n"
        message += "4. You are solely responsible for any trading decisions.\n"
        message += "5. Always do your own research before investing.\n"
        message += "6. The bot developers are not responsible for any financial losses.\n\n"
        message += "By using this bot, you acknowledge and accept these risks."
        
        await event.reply(message)

    @telegram_client.on(events.NewMessage(pattern='/shutdown'))
    async def shutdown_handler(event):
        """Shutdown command handler"""
        result = await stop_monitoring()
        await event.reply(result + "\n\nTo restart the bot, use /runbot")

    @telegram_client.on(events.CallbackQuery)
    async def callback_handler(event):
        """Handle button callbacks"""
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

    # Handle incoming channel messages
    @telegram_client.on(events.NewMessage(chats=channel_username))
    async def channel_handler(event):
        if bot_status != "running":
            return
            
        msg = event.raw_text
        token_addr = extract_token_address(msg)
        
        if token_addr:
            print(f"📥 Token: {token_addr}")
            send_log_to_telegram(f"Token: {token_addr}")
            price = get_token_price(token_addr)
            
            if price:
                # Record the trade
                trade_record = {
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "token": token_addr,
                    "amount": TRADE_AMOUNT_SOL,
                    "price": price
                }
                trading_history.append(trade_record)
                
                print(f"Signal received: ✅ {token_addr}")
                send_log_to_telegram(f"Signal received: ✅ {token_addr}")
                print(f"💰 Token price: {price:.6f} SOL")
                send_log_to_telegram(f"💰 Token price: {price:.6f} SOL")
                
                target = price * TARGET_MULTIPLIER
                print(f"💰 Entry: {price:.6f} SOL → 🎯 Target: {target:.6f} SOL")
                send_log_to_telegram(f"💰 Entry: {price:.6f} SOL ➡️ 🎯 Target: {target:.6f} SOL")
                
                # Get wallet balance
                balance = await get_wallet_balance(str(wallet_pubkey))
                print(f"💰 Wallet balance: {balance} SOL")
                send_log_to_telegram(f"💰 Wallet balance: {balance} SOL")
                
                # Simulate trade execution
                print("🚀 Simulating trade execution...")
                send_log_to_telegram("🚀 Simulating trade execution...")
                
                # Simulate trade result after some time
                await asyncio.sleep(2)  # Simulate trade execution time
                
                # Randomly determine if trade was successful (for simulation)
                success = random.random() > 0.3  # 70% success rate
                
                if success:
                    return_amount = TRADE_AMOUNT_SOL * random.uniform(1.5, 3.0)  # 50-200% return
                    trading_history[-1]['return'] = return_amount
                    print(f"✅ Trade successful! Return: {return_amount:.4f} SOL")
                    send_log_to_telegram(f"✅ Trade successful! Return: {return_amount:.4f} SOL")
                else:
                    return_amount = TRADE_AMOUNT_SOL * random.uniform(0.5, 0.9)  # 10-50% loss
                    trading_history[-1]['return'] = return_amount
                    print(f"❌ Trade unsuccessful. Return: {return_amount:.4f} SOL")
                    send_log_to_telegram(f"❌ Trade unsuccessful. Return: {return_amount:.4f} SOL")
                
        else:
            print("⚠️ No contract address detected.")
            send_log_to_telegram("⚠️ No contract address detected.")
        
        print("Waiting for another signal...")
        print(f"📡 Listening to {channel_username}")
        print("🤖 SignalForge Trading Bot is running...")

#=== Run the Application ===
if __name__ == '__main__':
    init_app()
    setup_telegram_handlers()
    
    # Start Telegram client in a separate thread
    def run_telegram_client():
        if telegram_client:
            try:
                asyncio.run(telegram_client.start())
                asyncio.run(telegram_client.run_until_disconnected())
            except Exception as e:
                print(f"Telegram client error: {e}")
    
    telegram_thread = threading.Thread(target=run_telegram_client, daemon=True)
    telegram_thread.start()
    
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
