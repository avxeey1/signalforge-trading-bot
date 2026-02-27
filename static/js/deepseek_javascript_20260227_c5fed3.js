// SignalForge Trading Bot - Main JavaScript

// Global variables
let socket = null;
let portfolioChart = null;
let allocationChart = null;
let refreshInterval = null;

// Initialize on document ready
document.addEventListener('DOMContentLoaded', function() {
    initializeSocket();
    initializeCharts();
    loadInitialData();
    setupEventListeners();
    startAutoRefresh();
});

// Initialize Socket.IO connection
function initializeSocket() {
    socket = io();
    
    socket.on('connect', function() {
        console.log('✅ Connected to server');
        showNotification('Connected to server', 'success');
    });
    
    socket.on('disconnect', function() {
        console.log('❌ Disconnected from server');
        showNotification('Disconnected from server', 'warning');
    });
    
    socket.on('status_update', function(data) {
        updateDashboard(data);
    });
    
    socket.on('bot_status', function(data) {
        updateBotStatus(data.status);
    });
    
    socket.on('notification', function(data) {
        showNotification(data.message, data.type);
    });
    
    socket.on('trade_executed', function(data) {
        onTradeExecuted(data);
    });
}

// Initialize charts
function initializeCharts() {
    // Portfolio Chart
    const portfolioCtx = document.getElementById('portfolioChart')?.getContext('2d');
    if (portfolioCtx) {
        portfolioChart = new Chart(portfolioCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Portfolio Value (USD)',
                    data: [],
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderWidth: 2,
                    pointRadius: 3,
                    pointBackgroundColor: '#667eea',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { mode: 'index', intersect: false }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(0,0,0,0.05)' },
                        ticks: { callback: value => '$' + value.toFixed(2) }
                    },
                    x: {
                        grid: { display: false }
                    }
                },
                interaction: { intersect: false, mode: 'index' }
            }
        });
    }
    
    // Allocation Chart
    const allocationCtx = document.getElementById('allocationChart')?.getContext('2d');
    if (allocationCtx) {
        allocationChart = new Chart(allocationCtx, {
            type: 'doughnut',
            data: {
                labels: ['SOL', 'Other Tokens'],
                datasets: [{
                    data: [0, 0],
                    backgroundColor: ['#667eea', '#764ba2'],
                    borderColor: ['#fff', '#fff'],
                    borderWidth: 2,
                    hoverOffset: 10
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom' },
                    tooltip: { 
                        callbacks: {
                            label: context => ` $${context.raw.toFixed(2)}`
                        }
                    }
                },
                cutout: '70%',
                animation: { animateRotate: true, animateScale: true }
            }
        });
    }
}

// Load initial data
async function loadInitialData() {
    showLoading();
    try {
        await Promise.all([
            loadStatus(),
            loadBalance(),
            loadHistory(),
            loadSettings()
        ]);
    } catch (error) {
        console.error('Error loading initial data:', error);
        showNotification('Failed to load initial data', 'error');
    } finally {
        hideLoading();
    }
}

// Load bot status
async function loadStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        updateDashboard(data);
    } catch (error) {
        console.error('Error loading status:', error);
    }
}

// Load wallet balance
async function loadBalance() {
    try {
        const response = await fetch('/api/balance');
        const data = await response.json();
        updateBalances(data);
        
        // Update allocation chart
        if (allocationChart && data.sol) {
            allocationChart.data.datasets[0].data = [
                data.sol.value || 0,
                data.total_value - (data.sol.value || 0)
            ];
            allocationChart.update();
        }
        
        // Update tokens table
        updateTokensTable(data.tokens || []);
    } catch (error) {
        console.error('Error loading balance:', error);
    }
}

// Load trading history
async function loadHistory() {
    try {
        const response = await fetch('/api/history');
        const data = await response.json();
        updateTradesTable(data.trades || []);
    } catch (error) {
        console.error('Error loading history:', error);
    }
}

// Load settings
async function loadSettings() {
    try {
        const response = await fetch('/api/settings');
        const data = await response.json();
        updateSettings(data);
    } catch (error) {
        console.error('Error loading settings:', error);
    }
}

// Update dashboard with status data
function updateDashboard(data) {
    // Update status badge
    updateBotStatus(data.status);
    
    // Update stats
    document.querySelectorAll('[data-stat]').forEach(el => {
        const stat = el.dataset.stat;
        if (data[stat] !== undefined) {
            if (stat.includes('usd') || stat.includes('value')) {
                el.textContent = formatUSD(data[stat]);
            } else if (stat.includes('sol')) {
                el.textContent = formatSOL(data[stat]);
            } else {
                el.textContent = data[stat];
            }
        }
    });
    
    // Update P&L
    if (data.pnl) {
        document.getElementById('pnlAmount')?.textContent = formatSOL(data.pnl.amount);
        document.getElementById('pnlPercentage')?.textContent = data.pnl.percentage.toFixed(2) + '%';
        document.getElementById('pnlUsd')?.textContent = formatUSD(data.pnl.usd);
    }
}

// Update bot status
function updateBotStatus(status) {
    const badge = document.getElementById('statusBadge');
    const text = document.getElementById('statusText');
    
    if (badge && text) {
        badge.className = `status-badge ${status}`;
        text.textContent = status.toUpperCase();
    }
    
    // Update buttons
    document.getElementById('startBtn')?.disabled = status === 'running';
    document.getElementById('stopBtn')?.disabled = status === 'stopped';
}

// Update balances
function updateBalances(data) {
    if (data.sol) {
        document.getElementById('solBalance')?.textContent = formatSOL(data.sol.balance);
        document.getElementById('solValue')?.textContent = formatUSD(data.sol.value);
    }
    
    document.getElementById('totalValue')?.textContent = formatUSD(data.total_value);
    document.getElementById('walletAddress')?.textContent = truncateAddress(data.wallet);
}

// Update tokens table
function updateTokensTable(tokens) {
    const tbody = document.getElementById('tokensBody');
    if (!tbody) return;
    
    if (tokens.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-center">No tokens found</td></tr>';
        return;
    }
    
    tbody.innerHTML = tokens.map(token => `
        <tr>
            <td>
                <strong>${token.symbol || 'Unknown'}</strong>
                <br>
                <small class="token-address">${truncateAddress(token.address)}</small>
            </td>
            <td>${token.balance.toFixed(4)}</td>
            <td>${formatUSD(token.price)}</td>
            <td class="${token.value > 0 ? 'profit' : ''}">${formatUSD(token.value)}</td>
        </tr>
    `).join('');
}

// Update trades table
function updateTradesTable(trades) {
    const tbody = document.getElementById('tradesBody');
    if (!tbody) return;
    
    if (trades.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center">No trades yet</td></tr>';
        return;
    }
    
    tbody.innerHTML = trades.map(trade => {
        const pnl = trade.return ? trade.return - trade.amount : 0;
        const pnlClass = pnl >= 0 ? 'profit' : 'loss';
        return `
            <tr>
                <td>${formatDate(trade.date)}</td>
                <td>
                    <span class="token-address">${truncateAddress(trade.token)}</span>
                </td>
                <td>${formatSOL(trade.amount)}</td>
                <td>${trade.return ? formatSOL(trade.return) : 'Pending'}</td>
                <td class="${pnlClass}">${pnl >= 0 ? '+' : ''}${formatSOL(pnl)}</td>
            </tr>
        `;
    }).join('');
}

// Update settings form
function updateSettings(settings) {
    document.getElementById('tradeAmount')?.value = settings.trade_amount;
    document.getElementById('targetMultiplier')?.value = settings.target_multiplier;
    document.getElementById('channel')?.value = settings.channel || 'Not configured';
}

// Format helpers
function formatUSD(value) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(value || 0);
}

function formatSOL(value) {
    return (value || 0).toFixed(4) + ' SOL';
}

function formatDate(dateString) {
    return new Date(dateString).toLocaleString();
}

function truncateAddress(address, chars = 8) {
    if (!address) return 'N/A';
    if (address.length <= chars * 2) return address;
    return address.slice(0, chars) + '...' + address.slice(-chars);
}

// Bot control functions
async function startBot() {
    if (!confirm('Are you sure you want to start the bot?')) return;
    
    showLoading();
    try {
        const response = await fetch('/api/start', { method: 'POST' });
        const data = await response.json();
        showNotification(data.message, 'success');
    } catch (error) {
        showNotification('Failed to start bot', 'error');
    } finally {
        hideLoading();
    }
}

async function stopBot() {
    if (!confirm('Are you sure you want to stop the bot?')) return;
    
    showLoading();
    try {
        const response = await fetch('/api/stop', { method: 'POST' });
        const data = await response.json();
        showNotification(data.message, 'warning');
    } catch (error) {
        showNotification('Failed to stop bot', 'error');
    } finally {
        hideLoading();
    }
}

async function updateSettings() {
    const settings = {
        trade_amount: parseFloat(document.getElementById('tradeAmount')?.value || 0.0215),
        target_multiplier: parseFloat(document.getElementById('targetMultiplier')?.value || 2.0)
    };
    
    showLoading();
    try {
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
        
        if (response.ok) {
            showNotification('Settings updated successfully', 'success');
        }
    } catch (error) {
        showNotification('Failed to update settings', 'error');
    } finally {
        hideLoading();
    }
}

// Refresh all data
async function refreshData() {
    showNotification('Refreshing data...', 'info');
    await loadInitialData();
}

// Export history
function exportHistory() {
    const trades = window.tradesData || [];
    const data = JSON.stringify({ trades, exportDate: new Date().toISOString() }, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `signalforge-history-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
    showNotification('History exported successfully', 'success');
}

// Notification system
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
        ${message}
        <span class="notification-close" onclick="this.parentElement.remove()">×</span>
    `;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
}

// Loading indicators
function showLoading() {
    document.body.classList.add('loading');
    const loader = document.getElementById('globalLoader');
    if (loader) loader.style.display = 'flex';
}

function hideLoading() {
    document.body.classList.remove('loading');
    const loader = document.getElementById('globalLoader');
    if (loader) loader.style.display = 'none';
}

// Auto refresh
function startAutoRefresh(interval = 30000) {
    if (refreshInterval) clearInterval(refreshInterval);
    refreshInterval = setInterval(refreshData, interval);
}

function stopAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
    }
}

// Event listeners
function setupEventListeners() {
    // Start bot button
    document.getElementById('startBtn')?.addEventListener('click', startBot);
    
    // Stop bot button
    document.getElementById('stopBtn')?.addEventListener('click', stopBot);
    
    // Refresh button
    document.getElementById('refreshBtn')?.addEventListener('click', refreshData);
    
    // Export button
    document.getElementById('exportBtn')?.addEventListener('click', exportHistory);
    
    // Save settings button
    document.getElementById('saveSettingsBtn')?.addEventListener('click', updateSettings);
    
    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + S to save settings
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            e.preventDefault();
            updateSettings();
        }
        
        // Ctrl/Cmd + R to refresh (but don't override browser refresh)
        if ((e.ctrlKey || e.metaKey) && e.key === 'r' && e.shiftKey) {
            e.preventDefault();
            refreshData();
        }
    });
}

// Trade execution callback
function onTradeExecuted(trade) {
    showNotification(`Trade executed: ${trade.token}`, 'success');
    loadHistory();
    loadBalance();
    
    // Play sound if supported
    if (window.Audio) {
        const audio = new Audio('/static/sounds/trade.mp3');
        audio.play().catch(() => {});
    }
}

// Export for use in HTML
window.SignalForge = {
    startBot,
    stopBot,
    refreshData,
    exportHistory,
    updateSettings,
    showNotification
};