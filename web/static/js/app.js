// CryptoBot Dashboard JavaScript

let refreshInterval = null;

// Initialize dashboard on load
document.addEventListener('DOMContentLoaded', function() {
    console.log('CryptoBot Dashboard Loaded');

    // Setup tab navigation
    setupTabs();

    // Load initial data
    loadStatus();
    loadConfig();

    // Setup auto-refresh
    startAutoRefresh();

    // Setup event listeners
    setupEventListeners();
});

// Tab Navigation
function setupTabs() {
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');

    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tabName = button.getAttribute('data-tab');

            // Remove active class from all tabs
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));

            // Add active class to clicked tab
            button.classList.add('active');
            document.getElementById(tabName + '-tab').classList.add('active');

            // Load tab-specific data
            loadTabData(tabName);
        });
    });
}

function loadTabData(tabName) {
    switch(tabName) {
        case 'dashboard':
            loadDashboard();
            break;
        case 'config':
            loadConfig();
            break;
        case 'claude':
            loadClaudeHistory();
            break;
        case 'trades':
            loadAllTrades();
            break;
        case 'performance':
            loadPerformance();
            break;
        case 'debug':
            // Debug tab loads on demand
            break;
    }
}

// Event Listeners
function setupEventListeners() {
    document.getElementById('start-bot-btn').addEventListener('click', startBot);
    document.getElementById('stop-bot-btn').addEventListener('click', stopBot);
    document.getElementById('refresh-btn').addEventListener('click', () => loadDashboard());
}

// Auto-refresh
function startAutoRefresh() {
    refreshInterval = setInterval(() => {
        loadStatus();

        // Refresh active tab
        const activeTab = document.querySelector('.tab-button.active');
        if (activeTab) {
            loadTabData(activeTab.getAttribute('data-tab'));
        }
    }, 10000); // Refresh every 10 seconds
}

function stopAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
}

// Load Status
async function loadStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();

        updateStatusDisplay(data);
    } catch (error) {
        console.error('Error loading status:', error);
    }
}

function updateStatusDisplay(data) {
    const indicator = document.getElementById('bot-status-indicator');
    const text = document.getElementById('bot-status-text');
    const modeValue = document.getElementById('mode-value');

    if (data.running) {
        indicator.className = 'status-indicator running';
        indicator.textContent = '🟢';
        text.textContent = 'Running';
    } else {
        indicator.className = 'status-indicator stopped';
        indicator.textContent = '⚫';
        text.textContent = 'Stopped';
    }

    if (data.dry_run) {
        modeValue.textContent = 'DRY RUN';
        modeValue.style.color = '#ffa500';
    } else {
        modeValue.textContent = 'LIVE';
        modeValue.style.color = '#e0245e';
    }
}

// Load Dashboard
async function loadDashboard() {
    try {
        // Load balance
        const balanceResponse = await fetch('/api/balance');
        const balanceData = await balanceResponse.json();
        document.getElementById('balance-usd').textContent = formatUSD(balanceData.balance_usd);

        // Load positions
        const positionsResponse = await fetch('/api/positions');
        const positions = await positionsResponse.json();
        document.getElementById('position-count').textContent = positions.length;
        displayPositions(positions);

        // Load performance
        const perfResponse = await fetch('/api/performance');
        const perf = await perfResponse.json();
        document.getElementById('total-pnl').textContent = formatUSD(perf.total_pnl || 0);
        document.getElementById('win-rate').textContent = (perf.win_rate || 0).toFixed(1) + '%';

        // Apply color to P&L
        const pnlElement = document.getElementById('total-pnl');
        if (perf.total_pnl > 0) {
            pnlElement.classList.add('positive');
            pnlElement.classList.remove('negative');
        } else if (perf.total_pnl < 0) {
            pnlElement.classList.add('negative');
            pnlElement.classList.remove('positive');
        }

        // Load recent trades
        const tradesResponse = await fetch('/api/trades');
        const trades = await tradesResponse.json();
        displayRecentTrades(trades.slice(-10).reverse());

    } catch (error) {
        console.error('Error loading dashboard:', error);
    }
}

function displayPositions(positions) {
    const container = document.getElementById('positions-container');

    if (!positions || positions.length === 0) {
        container.innerHTML = '<p class="no-data">No open positions</p>';
        return;
    }

    let html = '<table class="positions-table"><thead><tr>';
    html += '<th>Coin</th><th>Quantity</th><th>Entry Price</th><th>Current Price</th>';
    html += '<th>P&L</th><th>P&L %</th><th>Stop Loss</th><th>Actions</th>';
    html += '</tr></thead><tbody>';

    positions.forEach(pos => {
        const pnlClass = pos.net_pnl >= 0 ? 'positive' : 'negative';
        html += '<tr>';
        html += `<td><strong>${pos.product_id}</strong></td>`;
        html += `<td>${parseFloat(pos.quantity).toFixed(6)}</td>`;
        html += `<td>${formatUSD(pos.entry_price)}</td>`;
        html += `<td>${formatUSD(pos.current_price || pos.entry_price)}</td>`;
        html += `<td class="${pnlClass}">${formatUSD(pos.net_pnl || 0)}</td>`;
        html += `<td class="${pnlClass}">${(pos.pnl_pct || 0).toFixed(2)}%</td>`;
        html += `<td>${formatUSD(pos.stop_loss_price || 0)}</td>`;
        html += `<td><button class="btn btn-danger btn-sm" onclick="closePosition('${pos.product_id}')">Close</button></td>`;
        html += '</tr>';
    });

    html += '</tbody></table>';
    container.innerHTML = html;
}

function displayRecentTrades(trades) {
    const container = document.getElementById('recent-trades-container');

    if (!trades || trades.length === 0) {
        container.innerHTML = '<p class="no-data">No recent trades</p>';
        return;
    }

    let html = '';
    trades.forEach(trade => {
        if (!trade.net_pnl) return; // Skip entry-only trades

        const pnlClass = parseFloat(trade.net_pnl) >= 0 ? 'profit' : 'loss';
        html += `<div class="trade-item ${pnlClass}">`;
        html += `<div class="trade-header">`;
        html += `<span><strong>${trade.product_id}</strong> - ${trade.side}</span>`;
        html += `<span class="${pnlClass}">${formatUSD(trade.net_pnl)} (${parseFloat(trade.pnl_pct).toFixed(2)}%)</span>`;
        html += `</div>`;
        html += `<div class="trade-details">`;
        html += `<div>Price: ${formatUSD(trade.price)}</div>`;
        html += `<div>Quantity: ${parseFloat(trade.quantity).toFixed(6)}</div>`;
        html += `<div>Fees: ${formatUSD(trade.fee_usd)}</div>`;
        html += `<div>Reason: ${trade.reason}</div>`;
        html += `</div>`;
        html += `</div>`;
    });

    container.innerHTML = html;
}

// Configuration
async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();

        // Populate form
        document.getElementById('dry_run').checked = config.dry_run;
        document.getElementById('initial_capital').value = config.initial_capital;
        document.getElementById('min_trade_usd').value = config.min_trade_usd;
        document.getElementById('max_positions').value = config.max_positions;
        document.getElementById('max_position_pct').value = config.max_position_pct;
        document.getElementById('stop_loss_pct').value = config.stop_loss_pct;
        document.getElementById('take_profit_pct').value = config.take_profit_pct;
        document.getElementById('max_drawdown_pct').value = config.max_drawdown_pct;
        document.getElementById('claude_analysis_mode').value = config.claude_analysis_mode;
        document.getElementById('claude_confidence_threshold').value = config.claude_confidence_threshold;

    } catch (error) {
        console.error('Error loading config:', error);
    }
}

async function saveConfig() {
    try {
        const config = {
            dry_run: document.getElementById('dry_run').checked,
            initial_capital: parseFloat(document.getElementById('initial_capital').value),
            min_trade_usd: parseFloat(document.getElementById('min_trade_usd').value),
            max_positions: parseInt(document.getElementById('max_positions').value),
            max_position_pct: parseFloat(document.getElementById('max_position_pct').value),
            stop_loss_pct: parseFloat(document.getElementById('stop_loss_pct').value),
            take_profit_pct: parseFloat(document.getElementById('take_profit_pct').value),
            max_drawdown_pct: parseFloat(document.getElementById('max_drawdown_pct').value),
            claude_analysis_mode: document.getElementById('claude_analysis_mode').value,
            claude_confidence_threshold: parseInt(document.getElementById('claude_confidence_threshold').value)
        };

        const response = await fetch('/api/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(config)
        });

        const result = await response.json();

        if (result.success) {
            alert('Configuration saved successfully!');
        } else {
            alert('Error saving configuration: ' + result.error);
        }

    } catch (error) {
        console.error('Error saving config:', error);
        alert('Error saving configuration');
    }
}

async function applyPreset(presetName) {
    try {
        const response = await fetch(`/api/config/preset/${presetName}`, {
            method: 'POST'
        });

        const result = await response.json();

        if (result.success) {
            alert(`Applied ${presetName} preset!`);
            loadConfig();
        } else {
            alert('Error applying preset: ' + result.error);
        }

    } catch (error) {
        console.error('Error applying preset:', error);
    }
}

// Bot Controls
async function startBot() {
    try {
        const response = await fetch('/api/bot/start', {method: 'POST'});
        const result = await response.json();

        if (result.success) {
            alert('Bot started!');
            setTimeout(loadStatus, 1000);
        } else {
            alert('Error starting bot: ' + result.error);
        }

    } catch (error) {
        console.error('Error starting bot:', error);
        alert('Error starting bot');
    }
}

async function stopBot() {
    try {
        const response = await fetch('/api/bot/stop', {method: 'POST'});
        const result = await response.json();

        if (result.success) {
            alert('Bot stopped!');
            setTimeout(loadStatus, 1000);
        } else {
            alert('Error stopping bot: ' + result.error);
        }

    } catch (error) {
        console.error('Error stopping bot:', error);
        alert('Error stopping bot');
    }
}

async function closePosition(productId) {
    if (!confirm(`Close position in ${productId}?`)) return;

    try {
        const response = await fetch(`/api/position/close/${productId}`, {method: 'POST'});
        const result = await response.json();

        if (result.success) {
            alert(`Closed ${productId}`);
            loadDashboard();
        } else {
            alert('Error closing position: ' + result.error);
        }

    } catch (error) {
        console.error('Error closing position:', error);
    }
}

// Claude AI
async function runClaudeAnalysis() {
    try {
        document.getElementById('claude-analysis-container').innerHTML = '<p>Running analysis...</p>';

        const response = await fetch('/api/claude/analyze', {method: 'POST'});
        const result = await response.json();

        if (result.success) {
            displayClaudeAnalysis(result.analysis);
        } else {
            document.getElementById('claude-analysis-container').innerHTML =
                `<p class="test-error">Error: ${result.error}</p>`;
        }

    } catch (error) {
        console.error('Error running analysis:', error);
        document.getElementById('claude-analysis-container').innerHTML =
            `<p class="test-error">Error: ${error.message}</p>`;
    }
}

function displayClaudeAnalysis(analysis) {
    const container = document.getElementById('claude-analysis-container');
    const content = JSON.stringify(analysis, null, 2);
    container.innerHTML = `<div class="analysis-content">${content}</div>`;
}

function loadClaudeHistory() {
    // Would load from logs
    console.log('Loading Claude history...');
}

// Trades
async function loadAllTrades() {
    try {
        const response = await fetch('/api/trades');
        const trades = await response.json();

        const container = document.getElementById('all-trades-container');

        if (!trades || trades.length === 0) {
            container.innerHTML = '<p class="no-data">No trades</p>';
            return;
        }

        displayRecentTrades(trades.reverse());
        document.getElementById('all-trades-container').innerHTML =
            document.getElementById('recent-trades-container').innerHTML;

    } catch (error) {
        console.error('Error loading trades:', error);
    }
}

// Performance
async function loadPerformance() {
    try {
        const response = await fetch('/api/performance');
        const perf = await response.json();

        document.getElementById('perf-total-trades').textContent = perf.total_trades || 0;
        document.getElementById('perf-win-rate').textContent = (perf.win_rate || 0).toFixed(1) + '%';
        document.getElementById('perf-profit-factor').textContent = (perf.profit_factor || 0).toFixed(2);
        document.getElementById('perf-total-fees').textContent = formatUSD(perf.total_fees || 0);
        document.getElementById('perf-avg-win').textContent = formatUSD(perf.avg_win || 0);
        document.getElementById('perf-avg-loss').textContent = formatUSD(Math.abs(perf.avg_loss || 0));

    } catch (error) {
        console.error('Error loading performance:', error);
    }
}

// Debug / Testing
async function testCoinbase() {
    try {
        const response = await fetch('/api/test/coinbase', {method: 'POST'});
        const result = await response.json();

        const container = document.getElementById('test-results');

        if (result.success) {
            container.innerHTML = `<p class="test-success">✓ ${result.message}<br>Balance: ${formatUSD(result.balance_usd)}</p>`;
        } else {
            container.innerHTML = `<p class="test-error">✗ ${result.error}</p>`;
        }

    } catch (error) {
        document.getElementById('test-results').innerHTML = `<p class="test-error">✗ ${error.message}</p>`;
    }
}

async function testClaude() {
    try {
        const response = await fetch('/api/test/claude', {method: 'POST'});
        const result = await response.json();

        const container = document.getElementById('test-results');

        if (result.success) {
            container.innerHTML = `<p class="test-success">✓ ${result.message}<br>Model: ${result.model}</p>`;
        } else {
            container.innerHTML = `<p class="test-error">✗ ${result.error}</p>`;
        }

    } catch (error) {
        document.getElementById('test-results').innerHTML = `<p class="test-error">✗ ${error.message}</p>`;
    }
}

async function loadBotLogs() {
    try {
        const response = await fetch('/api/logs/bot');
        const data = await response.json();

        document.getElementById('bot-logs-container').textContent = data.logs || 'No logs';

    } catch (error) {
        console.error('Error loading logs:', error);
    }
}

async function loadClaudeLogs() {
    try {
        const response = await fetch('/api/logs/claude');
        const data = await response.json();

        document.getElementById('claude-logs-container').textContent = data.logs || 'No Claude logs';

    } catch (error) {
        console.error('Error loading logs:', error);
    }
}

// Utilities
function formatUSD(value) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(value || 0);
}
