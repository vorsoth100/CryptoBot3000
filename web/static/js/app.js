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
    loadDashboard();  // Load dashboard data immediately on page load

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
    document.getElementById('restart-bot-btn').addEventListener('click', restartBot);
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
    const startBtn = document.getElementById('start-bot-btn');
    const stopBtn = document.getElementById('stop-bot-btn');
    const restartBtn = document.getElementById('restart-bot-btn');

    if (data.running) {
        indicator.className = 'status-indicator running';
        indicator.textContent = '🟢';
        text.textContent = 'Running';

        // Disable start button, enable stop and restart
        startBtn.disabled = true;
        startBtn.style.opacity = '0.5';
        startBtn.style.cursor = 'not-allowed';
        stopBtn.disabled = false;
        stopBtn.style.opacity = '1';
        stopBtn.style.cursor = 'pointer';
        restartBtn.disabled = false;
        restartBtn.style.opacity = '1';
        restartBtn.style.cursor = 'pointer';
    } else {
        indicator.className = 'status-indicator stopped';
        indicator.textContent = '⚫';
        text.textContent = 'Stopped';

        // Enable start button, disable stop and restart
        startBtn.disabled = false;
        startBtn.style.opacity = '1';
        startBtn.style.cursor = 'pointer';
        stopBtn.disabled = true;
        stopBtn.style.opacity = '0.5';
        stopBtn.style.cursor = 'not-allowed';
        restartBtn.disabled = true;
        restartBtn.style.opacity = '0.5';
        restartBtn.style.cursor = 'not-allowed';
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
    html += '<th>Coin</th><th>Quantity</th><th>Entry Price</th><th>Entry Value</th>';
    html += '<th>Current Price</th><th>Current Value</th><th>Fees Paid</th>';
    html += '<th>P&L</th><th>P&L %</th><th>Stop Loss Value</th><th>Take Profit Value</th><th>Actions</th>';
    html += '</tr></thead><tbody>';

    positions.forEach(pos => {
        const pnlClass = pos.net_pnl >= 0 ? 'positive' : 'negative';
        const currentPrice = pos.current_price || pos.entry_price;
        const entryValue = pos.quantity * pos.entry_price;
        const currentValue = pos.quantity * currentPrice;

        // Calculate total values for stop loss and take profit
        const stopLossValue = pos.stop_loss_price ? pos.quantity * pos.stop_loss_price : 0;
        const takeProfitValue = pos.take_profit_price ? pos.quantity * pos.take_profit_price : 0;

        html += '<tr>';
        html += `<td><strong>${pos.product_id}</strong></td>`;
        html += `<td>${parseFloat(pos.quantity).toFixed(6)}</td>`;
        html += `<td>${formatUSD(pos.entry_price)}</td>`;
        html += `<td>${formatUSD(entryValue)}</td>`;
        html += `<td>${formatUSD(currentPrice)}</td>`;
        html += `<td><strong>${formatUSD(currentValue)}</strong></td>`;
        html += `<td>${formatUSD(pos.entry_fee || 0)}</td>`;
        html += `<td class="${pnlClass}"><strong>${formatUSD(pos.net_pnl || 0)}</strong></td>`;
        html += `<td class="${pnlClass}"><strong>${(pos.pnl_pct || 0).toFixed(2)}%</strong></td>`;
        html += `<td style="color: #f44336;">${formatUSD(stopLossValue)}</td>`;
        html += `<td style="color: #4caf50;">${formatUSD(takeProfitValue)}</td>`;
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
        const isClosed = trade.net_pnl !== undefined && trade.net_pnl !== 0;
        const pnlClass = isClosed ? (parseFloat(trade.net_pnl) >= 0 ? 'profit' : 'loss') : '';
        const tradeValue = trade.quantity * trade.price;

        html += `<div class="trade-item ${pnlClass}">`;
        html += `<div class="trade-header">`;
        html += `<span><strong>${trade.product_id}</strong> - ${trade.side}</span>`;

        if (isClosed) {
            html += `<span class="${pnlClass}">${formatUSD(trade.net_pnl)} (${parseFloat(trade.pnl_pct).toFixed(2)}%)</span>`;
        } else {
            html += `<span style="color: #2196f3;">OPEN</span>`;
        }

        html += `</div>`;
        html += `<div class="trade-details">`;
        html += `<div><strong>Price:</strong> ${formatUSD(trade.price)}</div>`;
        html += `<div><strong>Quantity:</strong> ${parseFloat(trade.quantity).toFixed(6)}</div>`;
        html += `<div><strong>Trade Value:</strong> ${formatUSD(tradeValue)}</div>`;
        html += `<div><strong>Fees:</strong> ${formatUSD(trade.fee_usd)}</div>`;

        if (isClosed) {
            const totalCost = tradeValue + trade.fee_usd;
            html += `<div><strong>Total Cost:</strong> ${formatUSD(totalCost)}</div>`;
            html += `<div><strong>Hold Time:</strong> ${trade.hold_time_hours ? trade.hold_time_hours.toFixed(1) + 'h' : 'N/A'}</div>`;
        } else {
            const totalCost = tradeValue + trade.fee_usd;
            html += `<div><strong>Total Cost:</strong> ${formatUSD(totalCost)}</div>`;
            html += `<div><strong>Current Value:</strong> <span style="font-style: italic;">See Open Positions</span></div>`;
        }

        html += `<div><strong>Reason:</strong> ${trade.reason}</div>`;
        html += `<div><strong>Notes:</strong> ${trade.notes || 'N/A'}</div>`;
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
        document.getElementById('coinbase_maker_fee').value = config.coinbase_maker_fee * 100;  // Convert to percentage
        document.getElementById('coinbase_taker_fee').value = config.coinbase_taker_fee * 100;  // Convert to percentage
        document.getElementById('max_fee_pct').value = config.max_fee_pct * 100;  // Convert decimal to percentage for display
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
            coinbase_maker_fee: parseFloat(document.getElementById('coinbase_maker_fee').value) / 100,  // Convert to decimal
            coinbase_taker_fee: parseFloat(document.getElementById('coinbase_taker_fee').value) / 100,  // Convert to decimal
            max_fee_pct: parseFloat(document.getElementById('max_fee_pct').value) / 100,  // Convert percentage to decimal for storage
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

async function restartBot() {
    if (!confirm('Restart the bot? This will stop and start it.')) return;

    try {
        // First stop
        const stopResponse = await fetch('/api/bot/stop', {method: 'POST'});
        const stopResult = await stopResponse.json();

        if (!stopResult.success) {
            alert('Error stopping bot: ' + stopResult.error);
            return;
        }

        // Wait 2 seconds
        await new Promise(resolve => setTimeout(resolve, 2000));

        // Then start
        const startResponse = await fetch('/api/bot/start', {method: 'POST'});
        const startResult = await startResponse.json();

        if (startResult.success) {
            alert('Bot restarted successfully!');
            setTimeout(loadStatus, 1000);
        } else {
            alert('Error starting bot: ' + startResult.error);
        }

    } catch (error) {
        console.error('Error restarting bot:', error);
        alert('Error restarting bot');
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
        document.getElementById('claude-analysis-container').innerHTML = '<p>🔄 Running analysis...</p>';
        document.getElementById('claude-recommendations-container').innerHTML = '<p>Analyzing market...</p>';

        const response = await fetch('/api/claude/analyze', {method: 'POST'});
        const result = await response.json();

        if (result.success) {
            displayClaudeAnalysis(result.analysis);
            displayTradeRecommendations(result.analysis);
        } else {
            document.getElementById('claude-analysis-container').innerHTML =
                `<p class="test-error">Error: ${result.error}</p>`;
            document.getElementById('claude-recommendations-container').innerHTML = '<p class="no-data">Analysis failed</p>';
        }

    } catch (error) {
        console.error('Error running analysis:', error);
        document.getElementById('claude-analysis-container').innerHTML =
            `<p class="test-error">Error: ${error.message}</p>`;
    }
}

function displayClaudeAnalysis(analysis) {
    const container = document.getElementById('claude-analysis-container');

    try {
        // Parse the raw_analysis JSON string
        let parsed = analysis;
        if (analysis.raw_analysis) {
            const jsonMatch = analysis.raw_analysis.match(/```json\n([\s\S]*?)\n```/);
            if (jsonMatch) {
                parsed = JSON.parse(jsonMatch[1]);
            }
        }

        const assessment = parsed.market_assessment || {};
        const warnings = parsed.risk_warnings || [];

        let html = '<div style="background: #f5f5f5; padding: 15px; border-radius: 4px; color: #333;">';
        html += `<h3 style="color: #1a1a1a;">Market Regime: <span style="color: #2196f3;">${assessment.regime || 'Unknown'}</span></h3>`;
        html += `<p style="color: #333;"><strong>Confidence:</strong> ${assessment.confidence || 0}%</p>`;
        html += `<p style="color: #333;"><strong>Risk Level:</strong> ${assessment.risk_level || 'Unknown'}</p>`;

        if (assessment.key_factors && assessment.key_factors.length > 0) {
            html += '<h4 style="color: #1a1a1a;">Key Factors:</h4><ul style="color: #333;">';
            assessment.key_factors.forEach(factor => {
                html += `<li style="color: #333;">${factor}</li>`;
            });
            html += '</ul>';
        }

        if (warnings.length > 0) {
            html += '<h4 style="color: #c62828;">⚠️ Risk Warnings:</h4><ul>';
            warnings.forEach(warning => {
                html += `<li style="color: #c62828; font-weight: 500;">${warning}</li>`;
            });
            html += '</ul>';
        }

        html += '</div>';
        container.innerHTML = html;

    } catch (e) {
        console.error('Error parsing analysis:', e);
        container.innerHTML = `<pre style="white-space: pre-wrap;">${JSON.stringify(analysis, null, 2)}</pre>`;
    }
}

function displayTradeRecommendations(analysis) {
    const container = document.getElementById('claude-recommendations-container');

    try {
        // Parse the raw_analysis JSON string
        let parsed = analysis;
        if (analysis.raw_analysis) {
            const jsonMatch = analysis.raw_analysis.match(/```json\n([\s\S]*?)\n```/);
            if (jsonMatch) {
                parsed = JSON.parse(jsonMatch[1]);
            }
        }

        const actions = parsed.recommended_actions || [];
        const buyActions = actions.filter(a => a.action === 'buy');

        if (buyActions.length === 0) {
            container.innerHTML = '<p class="no-data">No buy recommendations at this time. Market conditions suggest holding cash.</p>';
            return;
        }

        let html = '';
        buyActions.forEach((rec, index) => {
            const convictionColor = rec.conviction >= 80 ? '#4caf50' : rec.conviction >= 60 ? '#ff9800' : '#f44336';
            const autoExecute = rec.conviction >= 80;

            html += `<div style="border: 2px solid ${convictionColor}; padding: 15px; margin: 10px 0; border-radius: 8px; background: #fafafa;">`;
            html += `<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">`;
            html += `<h3 style="margin: 0;">${rec.coin}</h3>`;
            html += `<span style="background: ${convictionColor}; color: white; padding: 5px 15px; border-radius: 20px; font-weight: bold;">${rec.conviction}% Conviction</span>`;
            html += `</div>`;

            if (autoExecute) {
                html += `<p style="color: #4caf50; font-weight: bold;">✅ HIGH CONVICTION - Would auto-execute in autonomous mode</p>`;
            } else {
                html += `<p style="color: #ff9800; font-weight: bold;">⚠️ MODERATE CONVICTION - Requires manual approval</p>`;
            }

            html += `<p><strong>Entry Price:</strong> $${rec.target_entry ? rec.target_entry.toFixed(2) : 'Market'}</p>`;
            html += `<p><strong>Stop Loss:</strong> $${rec.stop_loss ? rec.stop_loss.toFixed(2) : 'N/A'} (${rec.stop_loss && rec.target_entry ? (((rec.stop_loss - rec.target_entry) / rec.target_entry) * 100).toFixed(1) : '0'}%)</p>`;
            html += `<p><strong>Take Profit:</strong> `;
            if (rec.take_profit && rec.take_profit.length > 0) {
                rec.take_profit.forEach((tp, i) => {
                    const pct = rec.target_entry ? (((tp - rec.target_entry) / rec.target_entry) * 100).toFixed(1) : '0';
                    html += `$${tp.toFixed(2)} (+${pct}%) `;
                });
            }
            html += `</p>`;
            html += `<p><strong>Position Size:</strong> ${(rec.position_size_pct * 100).toFixed(0)}% ($${(rec.position_size_pct * 600).toFixed(2)})</p>`;
            html += `<p style="background: #e3f2fd; padding: 10px; border-radius: 4px; margin: 10px 0;"><strong>Reasoning:</strong> ${rec.reasoning}</p>`;

            html += `<div style="display: flex; gap: 10px; margin-top: 15px;">`;
            html += `<button class="btn btn-success" onclick="approveTrade('${rec.coin}', ${rec.position_size_pct}, ${rec.stop_loss}, ${rec.take_profit[0]})">✅ Approve & Execute</button>`;
            html += `<button class="btn btn-danger" onclick="rejectTrade('${rec.coin}')">❌ Reject</button>`;
            html += `</div>`;
            html += `</div>`;
        });

        container.innerHTML = html;

    } catch (e) {
        console.error('Error parsing recommendations:', e);
        container.innerHTML = '<p class="no-data">Error loading recommendations</p>';
    }
}

async function approveTrade(coin, positionSizePct, stopLoss, takeProfit) {
    if (!confirm(`Execute trade for ${coin}?\n\nPosition Size: ${(positionSizePct * 100).toFixed(0)}%\nStop Loss: $${stopLoss.toFixed(2)}\nTake Profit: $${takeProfit.toFixed(2)}`)) {
        return;
    }

    try {
        const response = await fetch('/api/trade/execute', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                product_id: coin,
                position_size_pct: positionSizePct,
                stop_loss: stopLoss,
                take_profit: takeProfit
            })
        });

        const result = await response.json();

        if (result.success) {
            alert(`✅ Trade executed successfully!\n\n${result.message}`);
            loadStatus();  // Refresh dashboard
            loadDashboard();
        } else {
            // Display detailed validation error
            let errorMsg = `❌ Trade Validation Failed\n\n${result.error}\n`;

            if (result.details) {
                errorMsg += '\n━━━━━━━━━━━━━━━━━━━━━━━━\n';
                errorMsg += '📋 Requirements:\n';
                if (result.details.min_trade_usd) {
                    errorMsg += `  • Minimum Trade Size: $${result.details.min_trade_usd.toFixed(2)}\n`;
                }
                if (result.details.max_fee_pct) {
                    errorMsg += `  • Maximum Fee: ${result.details.max_fee_pct.toFixed(2)}%\n`;
                }
                if (result.details.max_positions) {
                    errorMsg += `  • Max Positions: ${result.details.max_positions}\n`;
                }

                errorMsg += '\n📊 Your Trade:\n';
                if (result.details.attempted_size_usd) {
                    errorMsg += `  • Trade Size: $${result.details.attempted_size_usd.toFixed(2)}\n`;
                }
                if (result.details.attempted_fee_pct) {
                    errorMsg += `  • Fee: ${result.details.attempted_fee_pct.toFixed(2)}%\n`;
                }
                if (result.details.current_positions !== undefined) {
                    errorMsg += `  • Current Positions: ${result.details.current_positions}\n`;
                }
                if (result.details.current_balance) {
                    errorMsg += `  • Available Balance: $${result.details.current_balance.toFixed(2)}\n`;
                }
            }

            alert(errorMsg);
        }

    } catch (error) {
        alert(`❌ Error: ${error.message}`);
    }
}

function rejectTrade(coin) {
    alert(`Trade for ${coin} rejected`);
    // Could log this or remove from recommendations
}

async function submitManualTrade() {
    const coin = document.getElementById('manual_coin').value;
    const size = parseFloat(document.getElementById('manual_size').value);
    const stopLossPct = parseFloat(document.getElementById('manual_stop_loss').value);
    const takeProfitPct = parseFloat(document.getElementById('manual_take_profit').value);

    if (!coin || !size || !stopLossPct || !takeProfitPct) {
        alert('Please fill in all fields');
        return;
    }

    const statusDiv = document.getElementById('manual-trade-status');
    statusDiv.innerHTML = '<p style="color: #ff9800;">⏳ Loading trade preview...</p>';

    try {
        // First, get trade preview
        const previewResponse = await fetch('/api/trade/preview', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                product_id: coin,
                size_usd: size,
                stop_loss_pct: stopLossPct / 100,
                take_profit_pct: takeProfitPct / 100
            })
        });

        const previewResult = await previewResponse.json();

        if (!previewResult.success) {
            statusDiv.innerHTML = `<p style="color: #f44336;">❌ ${previewResult.error}</p>`;
            return;
        }

        const p = previewResult.preview;

        // Calculate total values at stop loss and take profit
        const stopLossValue = p.quantity * p.stop_loss_price;
        const takeProfitValue = p.quantity * p.take_profit_price;

        // Show confirmation dialog with full breakdown
        let confirmMsg = `🔍 TRADE PREVIEW\n\n`;
        confirmMsg += `━━━━━━━━━━━━━━━━━━━━━━━━\n`;
        confirmMsg += `📊 Trade Details:\n`;
        confirmMsg += `  • Asset: ${p.product_id}\n`;
        confirmMsg += `  • Current Price: $${p.current_price.toFixed(2)} per coin\n`;
        confirmMsg += `  • Quantity: ${p.quantity.toFixed(6)} ${p.product_id.split('-')[0]}\n`;
        confirmMsg += `\n💰 Cost Breakdown:\n`;
        confirmMsg += `  • Trade Size: $${p.trade_size_usd.toFixed(2)}\n`;
        confirmMsg += `  • Fee (${p.fee_rate_pct.toFixed(2)}%): $${p.fee_amount_usd.toFixed(2)}\n`;
        confirmMsg += `  • Total Cost: $${p.total_cost_usd.toFixed(2)}\n`;
        confirmMsg += `\n🎯 Risk Management:\n`;
        confirmMsg += `  • Stop Loss Price: $${p.stop_loss_price.toFixed(2)}/coin\n`;
        confirmMsg += `    └─ Total Value: $${stopLossValue.toFixed(2)} (-${p.stop_loss_pct.toFixed(1)}%)\n`;
        confirmMsg += `  • Take Profit Price: $${p.take_profit_price.toFixed(2)}/coin\n`;
        confirmMsg += `    └─ Total Value: $${takeProfitValue.toFixed(2)} (+${p.take_profit_pct.toFixed(1)}%)\n`;
        confirmMsg += `\n━━━━━━━━━━━━━━━━━━━━━━━━\n`;
        confirmMsg += `\nProceed with this trade?`;

        if (!confirm(confirmMsg)) {
            statusDiv.innerHTML = '<p style="color: #666;">Trade cancelled</p>';
            return;
        }

        // User confirmed, now execute the trade
        statusDiv.innerHTML = '<p style="color: #ff9800;">⏳ Placing trade...</p>';

        const response = await fetch('/api/trade/manual', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                product_id: coin,
                size_usd: size,
                stop_loss_pct: stopLossPct / 100,
                take_profit_pct: takeProfitPct / 100
            })
        });

        const result = await response.json();

        if (result.success) {
            statusDiv.innerHTML = `<p style="color: #4caf50;">✅ ${result.message}</p>`;
            document.getElementById('manual-trade-form').reset();
            loadStatus();  // Refresh dashboard
            loadDashboard();
        } else {
            // Display detailed validation error
            let errorMsg = `❌ Trade Validation Failed\n\n${result.error}\n`;

            if (result.details) {
                errorMsg += '\n━━━━━━━━━━━━━━━━━━━━━━━━\n';
                errorMsg += '📋 Requirements:\n';
                if (result.details.min_trade_usd) {
                    errorMsg += `  • Minimum Trade Size: $${result.details.min_trade_usd.toFixed(2)}\n`;
                }
                if (result.details.max_fee_pct) {
                    errorMsg += `  • Maximum Fee: ${result.details.max_fee_pct.toFixed(2)}%\n`;
                }
                if (result.details.max_positions) {
                    errorMsg += `  • Max Positions: ${result.details.max_positions}\n`;
                }

                errorMsg += '\n📊 Your Trade:\n';
                if (result.details.attempted_size_usd) {
                    errorMsg += `  • Trade Size: $${result.details.attempted_size_usd.toFixed(2)}\n`;
                }
                if (result.details.attempted_fee_pct) {
                    errorMsg += `  • Fee: ${result.details.attempted_fee_pct.toFixed(2)}%\n`;
                }
                if (result.details.current_positions !== undefined) {
                    errorMsg += `  • Current Positions: ${result.details.current_positions}\n`;
                }
                if (result.details.current_balance) {
                    errorMsg += `  • Available Balance: $${result.details.current_balance.toFixed(2)}\n`;
                }
            }

            alert(errorMsg);
            statusDiv.innerHTML = `<p style="color: #f44336;">❌ ${result.error}</p>`;
        }

    } catch (error) {
        statusDiv.innerHTML = `<p style="color: #f44336;">❌ Error: ${error.message}</p>`;
    }
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

        // Display all trades in reverse order (newest first)
        displayAllTradesTable(trades.reverse(), container);

    } catch (error) {
        console.error('Error loading trades:', error);
        document.getElementById('all-trades-container').innerHTML =
            `<p class="no-data">Error loading trades: ${error.message}</p>`;
    }
}

function displayAllTradesTable(trades, container) {
    if (!trades || trades.length === 0) {
        container.innerHTML = '<p class="no-data">No trades</p>';
        return;
    }

    let html = '<div style="max-height: 600px; overflow-y: auto;">';

    trades.forEach((trade, index) => {
        const isBuy = trade.side === 'BUY';
        const isClosed = trade.net_pnl !== null && trade.net_pnl !== undefined;
        const tradeValue = trade.quantity * trade.price;

        html += `<div class="trade-card" style="margin-bottom: 15px; padding: 15px; border: 1px solid #ddd; border-radius: 4px;">`;
        html += `<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">`;
        html += `<div style="display: flex; align-items: center; gap: 10px;">`;
        html += `<h3 style="margin: 0;">${trade.product_id}</h3>`;
        html += `<span class="trade-side ${isBuy ? 'buy' : 'sell'}" style="padding: 4px 8px; border-radius: 4px; font-weight: bold; ${isBuy ? 'background: #e8f5e9; color: #2e7d32;' : 'background: #ffebee; color: #c62828;'}">${trade.side}</span>`;

        if (isClosed) {
            const pnlClass = trade.net_pnl >= 0 ? 'positive' : 'negative';
            const pnlColor = trade.net_pnl >= 0 ? '#4caf50' : '#f44336';
            const pnlPct = (trade.pnl_pct !== null && trade.pnl_pct !== undefined) ? trade.pnl_pct : 0;
            html += `<span style="padding: 4px 8px; border-radius: 4px; font-weight: bold; color: white; background: ${pnlColor};">`;
            html += `${trade.net_pnl >= 0 ? '+' : ''}${formatUSD(trade.net_pnl)} (${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(2)}%)`;
            html += `</span>`;
        } else {
            html += `<span style="padding: 4px 8px; border-radius: 4px; background: #e0e0e0; color: #666;">OPEN</span>`;
        }

        html += `</div>`;
        html += `<div style="color: #666; font-size: 0.9em;">${new Date(trade.timestamp).toLocaleString()}</div>`;
        html += `</div>`;

        html += `<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; font-size: 0.95em;">`;
        html += `<div><strong>Price:</strong> ${formatUSD(trade.price || 0)}</div>`;
        html += `<div><strong>Quantity:</strong> ${(trade.quantity || 0).toFixed(6)}</div>`;
        html += `<div><strong>Trade Value:</strong> ${formatUSD(tradeValue)}</div>`;
        html += `<div><strong>Fees:</strong> ${formatUSD(trade.fee_usd || 0)}</div>`;

        if (isClosed) {
            const totalCost = tradeValue + (trade.fee_usd || 0);
            html += `<div><strong>Total Cost:</strong> ${formatUSD(totalCost)}</div>`;
            html += `<div><strong>Hold Time:</strong> ${trade.hold_time_hours ? trade.hold_time_hours.toFixed(1) + 'h' : 'N/A'}</div>`;
        } else {
            const totalCost = tradeValue + (trade.fee_usd || 0);
            html += `<div><strong>Total Cost:</strong> ${formatUSD(totalCost)}</div>`;
        }

        html += `<div><strong>Reason:</strong> ${trade.reason || 'N/A'}</div>`;
        html += `<div><strong>Notes:</strong> ${trade.notes || 'N/A'}</div>`;
        html += `</div>`;
        html += `</div>`;
    });

    html += '</div>';
    container.innerHTML = html;
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

// Screener Functions
async function runScreener() {
    const statusDiv = document.getElementById('screener-status');
    const resultsContainer = document.getElementById('screener-results-container');

    try {
        statusDiv.innerHTML = '<p style="color: #ff9800;">⏳ Running screener...</p>';
        resultsContainer.innerHTML = '<p class="no-data">Scanning markets...</p>';

        const response = await fetch('/api/screener');

        // Check if response is OK
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const contentType = response.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
            const text = await response.text();
            console.error('Non-JSON response:', text);
            throw new Error('Server returned an error page. Check bot logs for details.');
        }

        const data = await response.json();

        // Check if response contains an error
        if (data.error) {
            throw new Error(data.error);
        }

        const opportunities = data;

        if (!Array.isArray(opportunities) || opportunities.length === 0) {
            statusDiv.innerHTML = '<p style="color: #666;">ℹ️ No opportunities found</p>';
            resultsContainer.innerHTML = '<p class="no-data">No trading opportunities found</p>';
            return;
        }

        statusDiv.innerHTML = `<p style="color: #4caf50;">✓ Found ${opportunities.length} opportunities</p>`;

        // Display results in a table
        let html = '<table style="width: 100%; border-collapse: collapse;">';
        html += '<thead><tr style="background: #f5f5f5;">';
        html += '<th style="padding: 8px; text-align: left; color: #333; font-weight: 600;">Coin</th>';
        html += '<th style="padding: 8px; text-align: left; color: #333; font-weight: 600;">Signal</th>';
        html += '<th style="padding: 8px; text-align: right; color: #333; font-weight: 600;">Score</th>';
        html += '<th style="padding: 8px; text-align: right; color: #333; font-weight: 600;">Confidence</th>';
        html += '<th style="padding: 8px; text-align: right; color: #333; font-weight: 600;">Price</th>';
        html += '</tr></thead><tbody>';

        opportunities.forEach((opp, index) => {
            const signalColor = opp.signal === 'strong_buy' ? '#4caf50' :
                               opp.signal === 'buy' ? '#8bc34a' :
                               opp.signal === 'neutral' ? '#ff9800' : '#f44336';

            html += `<tr style="border-bottom: 1px solid #eee;">`;
            html += `<td style="padding: 8px;"><strong>${opp.product_id}</strong></td>`;
            html += `<td style="padding: 8px; color: ${signalColor};">${opp.signal.toUpperCase()}</td>`;
            html += `<td style="padding: 8px; text-align: right;">${opp.score.toFixed(1)}</td>`;
            html += `<td style="padding: 8px; text-align: right;">${opp.confidence.toFixed(0)}%</td>`;
            html += `<td style="padding: 8px; text-align: right;">$${opp.price.toFixed(2)}</td>`;
            html += `</tr>`;
        });

        html += '</tbody></table>';
        resultsContainer.innerHTML = html;

    } catch (error) {
        console.error('Error running screener:', error);
        statusDiv.innerHTML = `<p style="color: #f44336;">✗ Error: ${error.message}</p>`;
        resultsContainer.innerHTML = '<p class="no-data">Error loading results</p>';
    }
}

async function loadScreenerConfig() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();

        document.getElementById('screener-mode').textContent = config.screener_mode || 'breakouts';
        document.getElementById('screener-coin-count').textContent = config.screener_coins.length || 0;

        const coinsList = document.getElementById('screener-coins-list');
        let html = '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 8px; margin-top: 10px;">';

        config.screener_coins.forEach(coin => {
            html += `<div style="padding: 6px; background: #e3f2fd; border: 1px solid #2196f3; border-radius: 4px; text-align: center; font-size: 0.9em; color: #1976d2; font-weight: 500;">${coin}</div>`;
        });

        html += '</div>';
        coinsList.innerHTML = html;

    } catch (error) {
        console.error('Error loading screener config:', error);
    }
}

// System Maintenance Functions
async function resetConfiguration() {
    const statusDiv = document.getElementById('maintenance-status');

    if (!confirm('Reset configuration to latest defaults?\n\nThis will:\n• Backup your current config\n• Load 25 coins (was 9)\n• Enable semi-autonomous mode\n• Enable twice-daily analysis\n\nContinue?')) {
        return;
    }

    try {
        statusDiv.innerHTML = '<p style="color: #ff9800;">⏳ Resetting configuration...</p>';

        const response = await fetch('/api/config/reset', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (data.success) {
            statusDiv.innerHTML = `
                <p style="color: #4caf50;">✓ ${data.message}</p>
                <p style="color: #666; font-size: 0.9em;">
                    Old config backed up to data/config.json.backup<br>
                    New config loaded with 25 coins and semi-autonomous mode<br>
                    <strong>Please refresh the page to see updated settings</strong>
                </p>
            `;

            // Auto-refresh after 2 seconds
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        } else {
            statusDiv.innerHTML = `<p style="color: #f44336;">✗ Error: ${data.error}</p>`;
        }

    } catch (error) {
        console.error('Error resetting config:', error);
        statusDiv.innerHTML = `<p style="color: #f44336;">✗ Error: ${error.message}</p>`;
    }
}

async function clearCache() {
    const statusDiv = document.getElementById('maintenance-status');

    try {
        statusDiv.innerHTML = '<p style="color: #ff9800;">⏳ Clearing cache...</p>';

        // This would need a backend endpoint - for now just show a message
        statusDiv.innerHTML = `
            <p style="color: #2196f3;">ℹ️ Cache will be cleared on next bot restart</p>
            <p style="color: #666; font-size: 0.9em;">
                To manually clear cache, restart the Docker container:<br>
                <code>docker restart cryptobot</code>
            </p>
        `;

    } catch (error) {
        console.error('Error clearing cache:', error);
        statusDiv.innerHTML = `<p style="color: #f44336;">✗ Error: ${error.message}</p>`;
    }
}

async function resetAccount() {
    const statusDiv = document.getElementById('maintenance-status');

    // Confirmation dialog
    const confirmed = confirm(
        '⚠️ RESET ACCOUNT - ARE YOU SURE?\n\n' +
        'This will:\n' +
        '• DELETE all open positions\n' +
        '• DELETE all trade history\n' +
        '• Reset capital to initial_capital setting\n' +
        '• Clear position and trade files\n\n' +
        'This action CANNOT be undone!\n\n' +
        'Only use this for testing!\n\n' +
        'Continue?'
    );

    if (!confirmed) {
        statusDiv.innerHTML = '<p style="color: #666;">Reset cancelled</p>';
        return;
    }

    // Double confirmation
    const doubleConfirmed = confirm(
        '🔥 FINAL WARNING 🔥\n\n' +
        'You are about to permanently delete all trading data.\n\n' +
        'Are you absolutely sure?'
    );

    if (!doubleConfirmed) {
        statusDiv.innerHTML = '<p style="color: #666;">Reset cancelled</p>';
        return;
    }

    try {
        statusDiv.innerHTML = '<p style="color: #ff9800;">⏳ Resetting account...</p>';

        const response = await fetch('/api/debug/reset-account', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });

        const result = await response.json();

        if (result.success) {
            statusDiv.innerHTML = `
                <p style="color: #4caf50;">✅ ${result.message}</p>
                <p style="color: #2196f3; margin-top: 10px;">
                    Files deleted:<br>
                    ${result.deleted_files.map(f => `• ${f}`).join('<br>')}
                </p>
                <p style="color: #666; margin-top: 10px;">
                    Refreshing dashboard...
                </p>
            `;

            // Refresh the dashboard after 2 seconds
            setTimeout(() => {
                loadStatus();
                loadDashboard();
                statusDiv.innerHTML += '<p style="color: #4caf50;">Dashboard refreshed!</p>';
            }, 2000);
        } else {
            statusDiv.innerHTML = `<p style="color: #f44336;">✗ ${result.error}</p>`;
        }

    } catch (error) {
        console.error('Error resetting account:', error);
        statusDiv.innerHTML = `<p style="color: #f44336;">✗ Error: ${error.message}</p>`;
    }
}

// Live Logs Tab
let autoRefreshInterval = null;

async function loadLiveLogs() {
    try {
        const response = await fetch('/api/logs/bot');
        const data = await response.json();

        if (data.error) {
            document.getElementById('live-logs-container').textContent = `Error loading logs: ${data.error}`;
            return;
        }

        const logLines = data.logs;
        const container = document.getElementById('live-logs-container');
        const errorsOnly = document.getElementById('filter-errors-only').checked;
        const showWarnings = document.getElementById('filter-warnings').checked;

        if (!logLines || logLines.length === 0) {
            container.innerHTML = '<div style="color: #888;">No logs available</div>';
            return;
        }

        let html = '';

        logLines.forEach(line => {
            // Apply filters
            if (errorsOnly && !line.includes('ERROR')) {
                return;
            }
            if (!showWarnings && line.includes('WARNING')) {
                return;
            }

            // Color code based on log level
            let color = '#d4d4d4'; // default
            let bgColor = 'transparent';

            if (line.includes('ERROR')) {
                color = '#ff6b6b';
                bgColor = '#3d1f1f';
            } else if (line.includes('WARNING')) {
                color = '#ffa500';
            } else if (line.includes('INFO')) {
                color = '#4dabf7';
            } else if (line.includes('Starting') || line.includes('auto-started') || line.includes('CryptoBot v')) {
                color = '#ff9800';  // Orange for bot starts
                bgColor = '#3d2e1f';
            }

            const escapedLine = line
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');

            html += `<div style="color: ${color}; background: ${bgColor}; padding: 2px 0; margin: 1px 0;">${escapedLine}</div>`;
        });

        container.innerHTML = html;

        // Auto-scroll to top (newest logs)
        container.scrollTop = 0;

    } catch (error) {
        console.error('Error loading logs:', error);
        document.getElementById('live-logs-container').textContent = `Error: ${error.message}`;
    }
}

function toggleAutoRefresh() {
    const button = document.getElementById('auto-refresh-text');

    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
        button.textContent = 'Resume Auto-Refresh';
    } else {
        loadLiveLogs(); // Load immediately
        autoRefreshInterval = setInterval(loadLiveLogs, 5000); // Refresh every 5 seconds
        button.textContent = 'Pause Auto-Refresh';
    }
}

// Start auto-refresh when logs tab is opened
document.addEventListener('DOMContentLoaded', function() {
    const tabButtons = document.querySelectorAll('.tab-button');
    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            const tab = this.getAttribute('data-tab');
            if (tab === 'logs' && !autoRefreshInterval) {
                loadLiveLogs();
                autoRefreshInterval = setInterval(loadLiveLogs, 5000);
                document.getElementById('auto-refresh-text').textContent = 'Pause Auto-Refresh';
            } else if (tab !== 'logs' && autoRefreshInterval) {
                clearInterval(autoRefreshInterval);
                autoRefreshInterval = null;
                document.getElementById('auto-refresh-text').textContent = 'Resume Auto-Refresh';
            }
        });
    });
});

// Utilities
function formatUSD(value) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(value || 0);
}
