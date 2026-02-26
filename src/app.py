"""
Main Flask application for SignalForge Trading Bot Dashboard
"""
import os
import sys
import threading
import asyncio
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import modules
from solana_utils import (
    initialize_wallet, get_wallet_balance, get_token_balances,
    get_sol_price, get_token_price, send_sol, lamports_to_sol, sol_to_lamports
)
from telegram_utils import send_log_to_telegram, extract_token_address, truncate_address
from utils import (
    trading_history, transaction_history, calculate_pnl, add_trade_record,
    add_transaction_record, format_uptime, simulate_trade
)
import bot

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__, 
            template_folder='../templates',
            static_folder='../static')
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24).hex())
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ============================================
# GLOBAL VARIABLES
# ============================================
bot_start_time = datetime.now()
wallet = None
wallet_pubkey = None
bot_status = os.environ.get("DEFAULT_BOT_STATUS", "stopped")
telegram_client = None

# Trading parameters
TRADE_AMOUNT_SOL = float(os.environ.get("TRADE_AMOUNT_SOL", 0.0215))
TARGET_MULTIPLIER = float(os.environ.get("TARGET_MULTIPLIER", 2.0))

# Telegram settings
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
CHANNEL_USERNAME = os.environ.get("TELEGRAM_CHANNEL")
PRIVATE_KEY = os.environ.get("PRIVATE_KEY")
DESTINATION_ADDRESS = os.environ.get("DESTINATION_ADDRESS")

# ============================================
# INITIALIZATION
# ============================================

def init_app():
    """Initialize the application"""
    global wallet, wallet_pubkey, bot_status, telegram_client
    
    print("=" * 50)
    print("🚀 SignalForge Trading Bot - Initializing")
    print("=" * 50)
    
    # Initialize wallet
    if PRIVATE_KEY:
        wallet = initialize_wallet(PRIVATE_KEY)
        if wallet:
            wallet_pubkey = wallet.pubkey()
            print(f"✅ Wallet initialized: {wallet_pubkey}")
        else:
            print("❌ Wallet initialization failed")
    else:
        print("⚠️ No private key provided - wallet features disabled")
    
    # Initialize Telegram bot
    if API_ID and API_HASH:
        try:
            from telethon import TelegramClient
            from telethon.sessions import StringSession
            telegram_client = TelegramClient(StringSession(), int(API_ID), API_HASH)
            print("✅ Telegram client initialized")
        except Exception as e:
            print(f"❌ Telegram client initialization failed: {e}")
    else:
        print("⚠️ Telegram credentials missing - bot features disabled")
    
    # Set bot status
    bot_status = os.environ.get("DEFAULT_BOT_STATUS", "stopped")
    
    print(f"📡 Monitoring channel: {CHANNEL_USERNAME or 'Not configured'}")
    print(f"🤖 Bot status: {bot_status}")
    print(f"💰 Trade amount: {TRADE_AMOUNT_SOL} SOL")
    print(f"🎯 Target multiplier: {TARGET_MULTIPLIER}x")
    print("=" * 50)
    
    # Start background tasks
    start_background_tasks()

def start_background_tasks():
    """Start all background threads"""
    # Status updater thread
    status_thread = threading.Thread(target=background_status_updater, daemon=True)
    status_thread.start()
    
    # Telegram bot thread (if configured)
    if telegram_client:
        telegram_thread = threading.Thread(target=run_telegram_bot, daemon=True)
        telegram_thread.start()

def background_status_updater():
    """Background task to update dashboard status"""
    while True:
        try:
            socketio.sleep(5)  # Update every 5 seconds
            
            # Calculate P&L
            pnl_amount, pnl_percentage, total_invested, total_returned = calculate_pnl()
            sol_price = get_sol_price()
            pnl_usd = pnl_amount * sol_price
            
            # Get wallet balance if available
            sol_balance = 0
            sol_value = 0
            if wallet and wallet_pubkey:
                try:
                    # Run async function in sync context
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    sol_balance = loop.run_until_complete(
                        get_wallet_balance(str(wallet_pubkey))
                    )
                    loop.close()
                    sol_value = sol_balance * sol_price
                except:
                    pass
            
            # Emit status update
            socketio.emit('status_update', {
                'status': bot_status,
                'uptime': format_uptime(bot_start_time),
                'trades': len(trading_history),
                'portfolio': sol_value + pnl_usd,
                'solBalance': sol_balance,
                'solValue': sol_value,
                'pnl': {
                    'amount': pnl_amount,
                    'percentage': pnl_percentage,
                    'usd': pnl_usd,
                    'invested': total_invested,
                    'returned': total_returned
                }
            })
            
        except Exception as e:
            print(f"❌ Background task error: {e}")

def run_telegram_bot():
    """Run Telegram bot in background thread"""
    global telegram_client
    
    if not telegram_client:
        return
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Setup bot handlers
        from bot import setup_handlers
        setup_handlers(telegram_client, wallet, wallet_pubkey)
        
        # Start the client
        loop.run_until_complete(telegram_client.start())
        print("✅ Telegram bot is running")
        
        # Send startup notification
        if DESTINATION_ADDRESS:
            send_log_to_telegram(
                f"🤖 SignalForge Bot Started\n"
                f"📡 Monitoring: {CHANNEL_USERNAME}\n"
                f"💰 Trade amount: {TRADE_AMOUNT_SOL} SOL\n"
                f"🎯 Target: {TARGET_MULTIPLIER}x"
            )
        
        # Run until disconnected
        loop.run_until_complete(telegram_client.run_until_disconnected())
        
    except Exception as e:
        print(f"❌ Telegram bot error: {e}")

# ============================================
# ROUTES
# ============================================

@app.route('/')
def index():
    """Dashboard home page"""
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        password = request.form.get('password')
        dashboard_password = os.environ.get('DASHBOARD_PASSWORD', 'admin123')
        
        if password == dashboard_password:
            session['authenticated'] = True
            session.permanent = True
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Invalid password')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout"""
    session.pop('authenticated', None)
    return redirect(url_for('login'))

# ============================================
# API ROUTES
# ============================================

@app.route('/api/status')
def api_status():
    """Get bot status"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    pnl_amount, pnl_percentage, total_invested, total_returned = calculate_pnl()
    sol_price = get_sol_price()
    
    # Get wallet balance if available
    sol_balance = 0
    if wallet and wallet_pubkey:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            sol_balance = loop.run_until_complete(
                get_wallet_balance(str(wallet_pubkey))
            )
            loop.close()
        except:
            pass
    
    return jsonify({
        'status': bot_status,
        'uptime': format_uptime(bot_start_time),
        'trades': len(trading_history),
        'wallet_initialized': wallet is not None,
        'wallet_address': str(wallet_pubkey) if wallet_pubkey else None,
        'sol_balance': sol_balance,
        'pnl': {
            'amount': pnl_amount,
            'percentage': pnl_percentage,
            'usd': pnl_amount * sol_price,
            'invested': total_invested,
            'returned': total_returned
        },
        'settings': {
            'trade_amount': TRADE_AMOUNT_SOL,
            'target_multiplier': TARGET_MULTIPLIER,
            'channel': CHANNEL_USERNAME
        }
    })

@app.route('/api/balance')
def api_balance():
    """Get wallet balance"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    if not wallet or not wallet_pubkey:
        return jsonify({'error': 'Wallet not initialized'}), 400
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Get SOL balance
        sol_balance = loop.run_until_complete(
            get_wallet_balance(str(wallet_pubkey))
        )
        sol_price = get_sol_price()
        sol_value = sol_balance * sol_price
        
        # Get token balances
        tokens, total_token_value = loop.run_until_complete(
            get_token_balances(str(wallet_pubkey))
        )
        
        loop.close()
        
        total_value = sol_value + total_token_value
        
        return jsonify({
            'sol': {
                'balance': sol_balance,
                'value': sol_value,
                'price': sol_price
            },
            'tokens': tokens,
            'total_value': total_value,
            'wallet': str(wallet_pubkey)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/history')
def api_history():
    """Get trading history"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    return jsonify({
        'trades': trading_history[-50:],  # Last 50 trades
        'transactions': transaction_history[-50:]  # Last 50 transactions
    })

@app.route('/api/start', methods=['POST'])
def api_start():
    """Start bot"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    global bot_status
    
    if bot_status == 'running':
        return jsonify({'message': 'Bot is already running'})
    
    bot_status = 'running'
    
    # Notify via Telegram
    if DESTINATION_ADDRESS:
        send_log_to_telegram("▶️ Bot started - Now monitoring for signals")
    
    # Emit socket event
    socketio.emit('bot_status', {'status': 'running'})
    socketio.emit('notification', {
        'title': 'Bot Started',
        'message': 'Signal monitoring has been enabled',
        'type': 'success'
    })
    
    return jsonify({'message': '✅ Bot started successfully'})

@app.route('/api/stop', methods=['POST'])
def api_stop():
    """Stop bot"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    global bot_status
    
    if bot_status == 'stopped':
        return jsonify({'message': 'Bot is already stopped'})
    
    bot_status = 'stopped'
    
    # Notify via Telegram
    if DESTINATION_ADDRESS:
        send_log_to_telegram("⏹️ Bot stopped - No longer monitoring")
    
    # Emit socket event
    socketio.emit('bot_status', {'status': 'stopped'})
    socketio.emit('notification', {
        'title': 'Bot Stopped',
        'message': 'Signal monitoring has been disabled',
        'type': 'warning'
    })
    
    return jsonify({'message': '⏹️ Bot stopped successfully'})

@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    """Get or update settings"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    global TRADE_AMOUNT_SOL, TARGET_MULTIPLIER
    
    if request.method == 'POST':
        data = request.json
        
        if 'trade_amount' in data:
            TRADE_AMOUNT_SOL = float(data['trade_amount'])
        if 'target_multiplier' in data:
            TARGET_MULTIPLIER = float(data['target_multiplier'])
        
        # Notify via Telegram
        if DESTINATION_ADDRESS:
            send_log_to_telegram(
                f"⚙️ Settings updated:\n"
                f"Trade amount: {TRADE_AMOUNT_SOL} SOL\n"
                f"Target multiplier: {TARGET_MULTIPLIER}x"
            )
        
        socketio.emit('notification', {
            'title': 'Settings Updated',
            'message': 'Trading parameters have been updated',
            'type': 'success'
        })
        
        return jsonify({'message': 'Settings updated successfully'})
    
    return jsonify({
        'trade_amount': TRADE_AMOUNT_SOL,
        'target_multiplier': TARGET_MULTIPLIER,
        'channel': CHANNEL_USERNAME or 'Not configured'
    })

@app.route('/api/send', methods=['POST'])
def api_send():
    """Send SOL to another address"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    if not wallet:
        return jsonify({'error': 'Wallet not initialized'}), 400
    
    data = request.json
    receiver = data.get('receiver')
    amount = float(data.get('amount', 0))
    
    if not receiver or amount <= 0:
        return jsonify({'error': 'Invalid receiver or amount'}), 400
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        success, result = loop.run_until_complete(
            send_sol(wallet, receiver, amount)
        )
        
        loop.close()
        
        if success:
            # Add to transaction history
            add_transaction_record('send', 'SOL', amount, receiver, result)
            
            socketio.emit('notification', {
                'title': 'Transfer Successful',
                'message': f'Sent {amount} SOL to {truncate_address(receiver)}',
                'type': 'success'
            })
            
            return jsonify({
                'message': f'✅ Sent {amount} SOL successfully',
                'tx_hash': result
            })
        else:
            return jsonify({'error': f'Failed to send: {result}'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/token/<address>/price')
def api_token_price(address):
    """Get token price"""
    price = get_token_price(address, TRADE_AMOUNT_SOL)
    if price:
        return jsonify({
            'address': address,
            'price': price,
            'target': price * TARGET_MULTIPLIER
        })
    return jsonify({'error': 'Could not fetch price'}), 400

@app.route('/api/simulate', methods=['POST'])
def api_simulate():
    """Simulate a trade (for testing)"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    token = data.get('token', 'unknown')
    amount = float(data.get('amount', TRADE_AMOUNT_SOL))
    
    success, return_amount = simulate_trade(amount)
    
    if success:
        add_trade_record(token, amount, None, return_amount)
        
        socketio.emit('notification', {
            'title': 'Trade Simulated',
            'message': f'Simulated trade: +{return_amount-amount:.4f} SOL',
            'type': 'success'
        })
    else:
        add_trade_record(token, amount, None, return_amount)
        socketio.emit('notification', {
            'title': 'Trade Simulated',
            'message': f'Simulated loss: -{amount-return_amount:.4f} SOL',
            'type': 'warning'
        })
    
    return jsonify({
        'success': success,
        'amount': amount,
        'return': return_amount,
        'pnl': return_amount - amount
    })

# ============================================
# SOCKET.IO EVENTS
# ============================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    if session.get('authenticated'):
        emit('bot_status', {'status': bot_status})
        print(f"✅ Client connected - Session authenticated")
    else:
        print("⚠️ Unauthenticated client connected")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print("❌ Client disconnected")

@socketio.on('request_status')
def handle_status_request():
    """Client requests status update"""
    if session.get('authenticated'):
        pnl_amount, pnl_percentage, _, _ = calculate_pnl()
        sol_price = get_sol_price()
        
        emit('status_update', {
            'status': bot_status,
            'uptime': format_uptime(bot_start_time),
            'trades': len(trading_history),
            'pnl': {
                'amount': pnl_amount,
                'percentage': pnl_percentage,
                'usd': pnl_amount * sol_price
            }
        })

# ============================================
# ERROR HANDLERS
# ============================================

@app.errorhandler(404)
def not_found(error):
    """404 error handler"""
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """500 error handler"""
    return jsonify({'error': 'Internal server error'}), 500

# ============================================
# MAIN ENTRY POINT
# ============================================

if __name__ == '__main__':
    # Initialize the application
    init_app()
    
    # Get port from environment or use default
    port = int(os.environ.get('PORT', 5000))
    
    # Run the app
    print(f"\n🚀 Starting SignalForge Dashboard on port {port}")
    print(f"📊 Access the dashboard at: http://localhost:{port}")
    print("=" * 50)
    
    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true',
        allow_unsafe_werkzeug=True
)
