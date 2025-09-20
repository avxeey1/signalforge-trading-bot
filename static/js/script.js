// Socket.io connection
const socket = io();

// Global state
let botStatus = 'loading';
let balanceData = null;
let tradeHistory = [];
let transactionHistory = [];

// Initialize page
document.addEventListener('DOMContentLoaded', function() {
    // Load initial data
    refreshStatus();
    refreshBalance();
    refreshTrades();
    refreshTransactions();
    
    // Set up socket listeners
    socket.on('bot_status', function(data) {
        updateBotStatus(data.status);
    });
    
    socket.on('status_update', function(data) {
        document.getElementById('status-detail').textContent = data.status === 'running' ? 'Running' : 'Stopped';
        document.getElementById('uptime').textContent = data.uptime;
        document.getElementById('total-trades').textContent = data.trades;
        
        const pnlElement = document.getElementById('pnl-display');
        pnlElement.textContent = data.pnl.amount.toFixed(4);
        pnlElement.className = data.pnl.amount >= 0 ? 'value profit' : 'value loss';
        
        // Update system info
        document.getElementById('system-uptime').textContent = data.uptime;
        document.getElementById('system-trades').textContent = data.trades;
        document.getElementById('system-status').textContent = data.status === 'running' ? 'Running' : 'Stopped';
    });
    
    socket.on('notification', function(data) {
        showNotification(data.title, data.message, data.type);
    });
    
    // Set up form handlers
    document.getElementById('send-form').addEventListener('submit', function(e) {
        e.preventDefault();
        sendFunds();
    });
    
    // Start periodic updates
    setInterval(() => {
        refreshStatus();
        refreshBalance();
    }, 10000);
});

// Update bot status
function updateBotStatus(status) {
    botStatus = status;
    const badge = document.getElementById('status-badge');
    const text = document.getElementById('status-text');
    const startBtn = document.getElementById('start-btn');
    const stopBtn = document.getElementById('stop-btn');
    
    if (status === 'running') {
        badge.className = 'status-badge bg-success';
        text.textContent = 'Running';
        startBtn.disabled = true;
        stopBtn.disabled = false;
    } else {
        badge.className = 'status-badge bg-danger';
        text.textContent = 'Stopped';
        startBtn.disabled = false;
        stopBtn.disabled = true;
    }
    
    document.getElementById('status-detail').textContent = status === 'running' ? 'Running' : 'Stopped';
    document.getElementById('system-status').textContent = status === 'running' ? 'Running' : 'Stopped';
}

// Refresh status
function refreshStatus() {
    fetch('/api/status')
        .then(response => response.json())
        .then(data => {
            updateBotStatus(data.status);
            document.getElementById('uptime').textContent = data.uptime;
            document.getElementById('total-trades').textContent = data.trades;
            document.getElementById('wallet-status').textContent = data.wallet_initialized ? 'Connected' : 'Not connected';
            document.getElementById('telegram-status').textContent = data.telegram_connected ? 'Connected' : 'Not connected';
            
            const pnlElement = document.getElementById('pnl-display');
            pnlElement.textContent = data.pnl.amount.toFixed(4);
            pnlElement.className = data.pnl.amount >= 0 ? 'value profit' : 'value loss';
            
            // Update system info
            document.getElementById('system-uptime').textContent = data.uptime;
            document.getElementById('system-trades').textContent = data.trades;
        })
        .catch(error => {
            console.error('Error refreshing status:', error);
        });
}

// Refresh balance
function refreshBalance() {
    fetch('/api/balance')
        .then(response => response.json())
        .then(data => {
            updateBalance(data);
        })
        .catch(error => {
            console.error('Error refreshing balance:', error);
        });
}

// Update balance data
function updateBalance(data) {
    balanceData = data;
    
    if (data.sol) {
        document.getElementById('balance-sol').textContent = data.sol.balance.toFixed(4);
        document.getElementById('balance-usd').textContent = '$' + data.sol.value.toFixed(2);
        document.getElementById('wallet-sol').textContent = data.sol.balance.toFixed(4);
        document.getElementById('wallet-usd').textContent = '$' + data.total_value.toFixed(2);
    }
    
    // Update tokens table
    const tokensTable = document.getElementById('tokens-table');
    if (data.tokens && data.tokens.length > 0) {
        tokensTable.innerHTML = '';
        data.tokens.forEach(token => {
            const value = token.balance * token.price;
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${token.symbol}</td>
                <td>${token.balance.toFixed(4)}</td>
                <td>$${token.price.toFixed(4)}</td>
                <td>$${value.toFixed(2)}</td>
            `;
            tokensTable.appendChild(row);
        });
    } else {
        tokensTable.innerHTML = '<tr><td colspan="4" class="text-center text-muted">No tokens found</td></tr>';
    }
}

// Refresh trades
function refreshTrades() {
    fetch('/api/history')
        .then(response => response.json())
        .then(data => {
            updateTradeHistory(data.trades || []);
            updateTransactionHistory(data.transactions || []);
        })
        .catch(error => {
            console.error('Error refreshing history:', error);
        });
}

// Refresh transactions
function refreshTransactions() {
    fetch('/api/history')
        .then(response => response.json())
        .then(data => {
            updateTransactionHistory(data.transactions || []);
        })
        .catch(error => {
            console.error('Error refreshing transactions:', error);
        });
}

// Update trade history
function updateTradeHistory(data) {
    tradeHistory = data;
    const tradesTable = document.getElementById('trades-table');
    const recentTrades = document.getElementById('recent-trades');
    
    if (data.length > 0) {
        // Update trades table
        tradesTable.innerHTML = '';
        data.slice().reverse().forEach(trade => {
            const profit = trade.return ? (trade.return - trade.amount) : 0;
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${new Date(trade.date).toLocaleString()}</td>
                <td>${trade.token ? trade.token.substring(0, 8) + '...' : 'Unknown'}</td>
                <td>${trade.amount.toFixed(4)}</td>
                <td>${trade.return ? trade.return.toFixed(4) : 'N/A'}</td>
                <td class="${profit >= 0 ? 'profit' : 'loss'}">${profit ? profit.toFixed(4) : 'N/A'}</td>
            `;
            tradesTable.appendChild(row);
        });
        
        // Update recent trades
        recentTrades.innerHTML = '';
        data.slice(-5).reverse().forEach(trade => {
            const profit = trade.return ? (trade.return - trade.amount) : 0;
            const div = document.createElement('div');
            div.className = 'd-flex justify-content-between align-items-center mb-2 p-2 border-bottom';
            div.innerHTML = `
                <div>
                    <strong>${trade.token ? trade.token.substring(0, 6) + '...' : 'Unknown'}</strong>
                    <br><small class="text-muted">${new Date(trade.date).toLocaleDateString()}</small>
                </div>
                <div class="text-end">
                    <span class="${profit >= 0 ? 'profit' : 'loss'}">${profit.toFixed(4)} SOL</span>
                    <br><small>${trade.amount.toFixed(4)} SOL</small>
                </div>
            `;
            recentTrades.appendChild(div);
        });
        
        // Update analytics
        updateAnalytics(data);
    } else {
        tradesTable.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No trades yet</td></tr>';
        recentTrades.innerHTML = '<p class="text-center text-muted">No recent trades</p>';
    }
}

// Update transaction history
function updateTransactionHistory(data) {
    transactionHistory = data;
    const transactionsTable = document.getElementById('transactions-table');
    
    if (data.length > 0) {
        transactionsTable.innerHTML = '';
        data.slice().reverse().forEach(transaction => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${new Date(transaction.date).toLocaleString()}</td>
                <td><span class="badge bg-${transaction.type === 'send' ? 'warning' : 'success'}">${transaction.type}</span></td>
                <td>${transaction.asset}</td>
                <td>${transaction.amount.toFixed(4)}</td>
                <td><span class="badge bg-success">Confirmed</span></td>
            `;
            transactionsTable.appendChild(row);
        });
    } else {
        transactionsTable.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No transactions yet</td></tr>';
    }
}

// Update analytics
function updateAnalytics(data) {
    const successfulTrades = data.filter(t => t.return && t.return > t.amount).length;
    const failedTrades = data.length - successfulTrades;
    const totalInvested = data.reduce((sum, trade) => sum + trade.amount, 0);
    const totalReturned = data.reduce((sum, trade) => sum + (trade.return || 0), 0);
    const pnlPercentage = totalInvested > 0 ? ((totalReturned - totalInvested) / totalInvested * 100) : 0;
    
    document.getElementById('success-count').textContent = successfulTrades;
    document.getElementById('failure-count').textContent = failedTrades;
    document.getElementById('total-invested').textContent = totalInvested.toFixed(4);
    document.getElementById('total-returned').textContent = totalReturned.toFixed(4);
    document.getElementById('pnl-percentage').textContent = pnlPercentage.toFixed(2) + '%';
    document.getElementById('pnl-percentage').className = pnlPercentage >= 0 ? 'profit' : 'loss';
    
    const successPercent = data.length > 0 ? (successfulTrades / data.length * 100) : 0;
    const failurePercent = data.length > 0 ? (failedTrades / data.length * 100) : 0;
    
    document.getElementById('success-bar').style.width = successPercent + '%';
    document.getElementById('success-bar').textContent = successPercent.toFixed(0) + '%';
    document.getElementById('failure-bar').style.width = failurePercent + '%';
    document.getElementById('failure-bar').textContent = failurePercent.toFixed(0) + '%';
    
    document.getElementById('success-bar-analytics').style.width = successPercent + '%';
    document.getElementById('success-bar-analytics').textContent = successPercent.toFixed(0) + '%';
    document.getElementById('failure-bar-analytics').style.width = failurePercent + '%';
    document.getElementById('failure-bar-analytics').textContent = failurePercent.toFixed(0) + '%';
    
    // Calculate average return
    const avgReturn = data.length > 0 ? (totalReturned / totalInvested * 100 - 100) : 0;
    document.getElementById('success-rate').textContent = successPercent.toFixed(1) + '%';
    document.getElementById('avg-return').textContent = avgReturn.toFixed(1) + '%';
}

// Show notification
function showNotification(title, message, type = 'info') {
    const toastElement = document.getElementById('notification-toast');
    const toastTitle = document.getElementById('toast-title');
    const toastMessage = document.getElementById('toast-message');
    
    toastTitle.textContent = title;
    toastMessage.textContent = message;
    
    // Set toast color based on type
    const toast = toastElement.querySelector('.toast');
    toast.className = 'toast';
    if (type === 'success') toast.classList.add('text-bg-success');
    else if (type === 'warning') toast.classList.add('text-bg-warning');
    else if (type === 'danger') toast.classList.add('text-bg-danger');
    else toast.classList.add('text-bg-info');
    
    // Show toast
    toastElement.style.display = 'block';
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
}

// Show section
function showSection(sectionId) {
    // Hide all sections
    document.querySelectorAll('.section').forEach(section => {
        section.style.display = 'none';
    });
    
    // Show selected section
    document.getElementById(sectionId + '-section').style.display = 'block';
    
    // Update page title
    document.getElementById('page-title').textContent = document.querySelector(`[href="#${sectionId}"]`).textContent.trim();
    
    // Update active menu item
    document.querySelectorAll('.sidebar-menu .nav-link').forEach(link => {
        link.classList.remove('active');
    });
    document.querySelector(`[href="#${sectionId}"]`).classList.add('active');
    
    // Refresh data for specific sections
    if (sectionId === 'wallet') {
        refreshBalance();
    } else if (sectionId === 'trades') {
        refreshTrades();
    } else if (sectionId === 'transactions') {
        refreshTransactions();
    }
}


// Start bot
function startBot() {
    fetch('/api/start', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            showNotification('Bot Started', data.message, 'success');
        })
        .catch(error => {
            showNotification('Error', 'Failed to start bot', 'danger');
        });
}

// Stop bot
function stopBot() {
    fetch('/api/stop', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            showNotification('Bot Stopped', data.message, 'warning');
        })
        .catch(error => {
            showNotification('Error', 'Failed to stop bot', 'danger');
        });
}

// Save settings
function saveSettings() {
    const tradeAmount = parseFloat(document.getElementById('trade-amount').value);
    const targetMultiplier = parseFloat(document.getElementById('target-multiplier').value);
    
    fetch('/api/settings', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            trade_amount: tradeAmount,
            target_multiplier: targetMultiplier
        })
    })
    .then(response => response.json())
    .then(data => {
        showNotification('Settings Saved', data.message, 'success');
    })
    .catch(error => {
        showNotification('Error', 'Failed to save settings', 'danger');
    });
}

// Send funds
function sendFunds() {
    const receiver = document.getElementById('recipient-address').value;
    const amount = parseFloat(document.getElementById('send-amount').value);
    const asset = document.getElementById('send-asset').value;
    
    fetch('/api/send', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            receiver: receiver,
            amount: amount,
            asset: asset
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            showNotification('Error', data.error, 'danger');
        } else {
            showNotification('Success', data.message, 'success');
            document.getElementById('send-form').reset();
            refreshBalance();
            refreshTransactions();
        }
    })
    .catch(error => {
        showNotification('Error', 'Failed to send funds', 'danger');
    });
}

// Copy wallet address
function copyWalletAddress() {
    const walletAddress = document.getElementById('wallet-address').textContent;
    navigator.clipboard.writeText(walletAddress)
        .then(() => {
            showNotification('Success', 'Wallet address copied to clipboard', 'success');
        })
        .catch(err => {
            showNotification('Error', 'Failed to copy address', 'danger');
        });
}

// Download QR code
function downloadQRCode() {
    showNotification('Info', 'QR code generation would be implemented here', 'info');
}