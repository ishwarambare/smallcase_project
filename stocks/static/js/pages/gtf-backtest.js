/* stocks/static/js/pages/gtf-backtest.js */

document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('gtf-backtest-form');
    const symbolsInput = document.getElementById('input-symbols');
    const startDateInput = document.getElementById('input-start-date');
    const endDateInput = document.getElementById('input-end-date');
    const progressContainer = document.getElementById('gtf-progress-container');
    const progressBar = document.getElementById('gtf-progress-bar');
    const progressPercent = document.getElementById('gtf-progress-percent');
    const progressStatus = document.getElementById('gtf-progress-status');
    const resultsSection = document.getElementById('gtf-results-section');
    const btnReset = document.getElementById('btn-reset-form');

    let equityChartInstance = null;
    let currentTradesLog = [];

    // Set dynamic default dates (last 30 days)
    const today = new Date();
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(today.getDate() - 30);

    if (startDateInput && endDateInput) {
        if (!startDateInput.value || startDateInput.value === '2025-09-01') {
            startDateInput.value = formatDate(thirtyDaysAgo);
        }
        if (!endDateInput.value || endDateInput.value === '2025-09-30') {
            endDateInput.value = formatDate(today);
        }
    }

    function formatDate(d) {
        return d.toISOString().split('T')[0];
    }

    // Quick Date Buttons
    document.querySelectorAll('.btn-date-quick').forEach(btn => {
        btn.addEventListener('click', function () {
            const range = this.getAttribute('data-range');
            const now = new Date();
            let start = new Date();

            if (range === '7d') {
                start.setDate(now.getDate() - 7);
            } else if (range === '30d') {
                start.setDate(now.getDate() - 30);
            } else if (range === 'month') {
                start = new Date(now.getFullYear(), now.getMonth(), 1);
            }

            if (startDateInput && endDateInput) {
                startDateInput.value = formatDate(start);
                endDateInput.value = formatDate(now);
            }
        });
    });

    // Presets
    const presets = {
        'top31': 'RELIANCE, HDFCBANK, ICICIBANK, INFY, TCS, ITC, LT, AXISBANK, SBIN, BHARTIARTL, TATASTEEL, BAJFINANCE, BAJAJ-AUTO, INDUSINDBK, HINDUNILVR, KOTAKBANK, TATAMOTORS, MARUTI, SUNPHARMA, TITAN, ULTRACEMCO, NTPC, POWERGRID, COALINDIA, HCLTECH, WIPRO, TECHM, ASIANPAINT, ADANIENT, ADANIPORTS, HDFCLIFE',
        'top10': 'RELIANCE, HDFCBANK, ICICIBANK, INFY, TCS, ITC, LT, AXISBANK, SBIN, BHARTIARTL',
        'nifty_top': 'RELIANCE, HDFCBANK, SBIN, TCS, INFY',
        'banks': 'HDFCBANK, ICICIBANK, SBIN, KOTAKBANK, AXISBANK, INDUSINDBK',
        'tech': 'TCS, INFY, WIPRO, TECHM, HCLTECH'
    };

    document.querySelectorAll('.btn-preset').forEach(btn => {
        btn.addEventListener('click', function () {
            const key = this.getAttribute('data-preset');
            if (presets[key]) {
                symbolsInput.value = presets[key];
                document.querySelectorAll('.btn-preset').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
            }
        });
    });

    if (btnReset) {
        btnReset.addEventListener('click', function () {
            form.reset();
            symbolsInput.value = presets['top31'];
            if (startDateInput && endDateInput) {
                startDateInput.value = formatDate(thirtyDaysAgo);
                endDateInput.value = formatDate(today);
            }
        });
    }

    // Tabs Navigation
    document.querySelectorAll('.tab-btn').forEach(tab => {
        tab.addEventListener('click', function () {
            document.querySelectorAll('.tab-btn').forEach(t => t.classList.remove('active'));
            this.classList.add('active');

            const target = this.getAttribute('data-target');
            document.querySelectorAll('.tab-content-panel').forEach(p => p.style.display = 'none');
            const panel = document.getElementById(target);
            if (panel) panel.style.display = 'block';
        });
    });

    // Form Submit
    form.addEventListener('submit', async function (e) {
        e.preventDefault();

        const formData = new FormData(form);
        const payload = {
            symbols: formData.get('symbols'),
            start_date: formData.get('start_date'),
            end_date: formData.get('end_date'),
            htf_interval: formData.get('htf_interval'),
            ltf_interval: formData.get('ltf_interval'),
            initial_capital: parseFloat(formData.get('initial_capital')),
            risk_per_trade: parseFloat(formData.get('risk_per_trade')),
            min_score: parseFloat(formData.get('min_score')),
            max_r_multiple: parseFloat(formData.get('max_r_multiple'))
        };

        // Loading State
        progressContainer.style.display = 'block';
        resultsSection.style.display = 'none';
        progressBar.style.width = '10%';
        progressPercent.textContent = '10%';
        progressStatus.textContent = 'Fetching multi-timeframe candle data via Fyers API & pre-calculating HTF zones...';

        let progressVal = 10;
        const progressInterval = setInterval(() => {
            if (progressVal < 88) {
                progressVal += 12;
                progressBar.style.width = progressVal + '%';
                progressPercent.textContent = progressVal + '%';
                if (progressVal > 40) {
                    progressStatus.textContent = 'Running GTF entry scoring, location curve filter & trade execution simulation...';
                }
            }
        }, 350);

        try {
            const response = await fetch('/api/demand-supply/backtest/run/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify(payload)
            });

            clearInterval(progressInterval);
            progressBar.style.width = '100%';
            progressPercent.textContent = '100%';

            const data = await response.json();

            setTimeout(() => {
                progressContainer.style.display = 'none';
                if (data.success) {
                    renderBacktestResults(data);
                } else {
                    alert('Backtest Error: ' + (data.error || 'Execution failed'));
                }
            }, 300);

        } catch (err) {
            clearInterval(progressInterval);
            progressContainer.style.display = 'none';
            alert('Server connection error: ' + err.message);
        }
    });

    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    function renderBacktestResults(data) {
        resultsSection.style.display = 'block';
        currentTradesLog = data.trades || [];

        // 1. KPI Cards
        const pnl = data.portfolio_pnl || 0;
        const pnlElement = document.getElementById('kpi-total-pnl');
        pnlElement.textContent = (pnl >= 0 ? '₹' : '-₹') + Math.abs(pnl).toLocaleString('en-IN', { minimumFractionDigits: 2 });
        pnlElement.className = 'kpi-value ' + (pnl >= 0 ? 'text-green' : 'text-red');

        const initialCap = data.portfolio_initial_capital || 100000;
        const pnlPct = ((pnl / initialCap) * 100).toFixed(2);
        document.getElementById('kpi-pnl-pct').textContent = (pnlPct >= 0 ? '+' : '') + pnlPct + '% Return';

        document.getElementById('kpi-win-rate').textContent = (data.win_rate || 0).toFixed(2) + '%';
        document.getElementById('kpi-win-breakdown').textContent = `${data.winning_trades || 0} Wins / ${data.losing_trades || 0} Losses`;

        document.getElementById('kpi-total-trades').textContent = data.total_trades || 0;
        document.getElementById('kpi-profit-factor').textContent = (data.profit_factor || 0).toFixed(2);

        // 2. Equity Curve Chart
        renderEquityChart(data.equity_curve || []);

        // 3. Symbol Summary Table
        renderSymbolSummaryTable(data.summary_by_symbol || []);

        // 4. Detailed Trades Table
        renderTradesTable(currentTradesLog);

        resultsSection.scrollIntoView({ behavior: 'smooth' });
    }

    function renderEquityChart(equityData) {
        const ctx = document.getElementById('equity-chart').getContext('2d');
        if (equityChartInstance) {
            equityChartInstance.destroy();
        }

        const labels = equityData.map(d => d.date);
        const points = equityData.map(d => d.equity);

        // Gradient Fill
        const gradient = ctx.createLinearGradient(0, 0, 0, 300);
        gradient.addColorStop(0, 'rgba(56, 189, 248, 0.35)');
        gradient.addColorStop(1, 'rgba(56, 189, 248, 0.0)');

        equityChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Portfolio Equity (₹)',
                    data: points,
                    borderColor: '#38bdf8',
                    backgroundColor: gradient,
                    borderWidth: 2.5,
                    fill: true,
                    tension: 0.25,
                    pointRadius: points.length > 60 ? 0 : 3,
                    pointHoverRadius: 6,
                    pointBackgroundColor: '#38bdf8'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        backgroundColor: '#0f172a',
                        borderColor: '#334155',
                        borderWidth: 1,
                        titleColor: '#f8fafc',
                        bodyColor: '#cbd5e1',
                        callbacks: {
                            label: function (context) {
                                return ' Portfolio Value: ₹' + context.parsed.y.toLocaleString('en-IN');
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(51, 65, 85, 0.3)' },
                        ticks: { color: '#64748b', maxRotation: 0, autoSkip: true, maxTicksLimit: 8 }
                    },
                    y: {
                        grid: { color: 'rgba(51, 65, 85, 0.3)' },
                        ticks: { color: '#64748b', callback: val => '₹' + val.toLocaleString('en-IN') }
                    }
                }
            }
        });
    }

    function renderSymbolSummaryTable(summaryList) {
        const tbody = document.getElementById('symbol-summary-tbody');
        tbody.innerHTML = '';

        if (summaryList.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--gtf-text-muted); padding: 20px;">No symbols backtested.</td></tr>`;
            return;
        }

        summaryList.forEach(item => {
            const tr = document.createElement('tr');
            const pnlClass = item.total_pnl > 0 ? 'text-green' : (item.total_pnl < 0 ? 'text-red' : '');
            const pnlSign = item.total_pnl > 0 ? '+' : '';
            tr.innerHTML = `
                <td><strong>${item.symbol}</strong></td>
                <td>${item.total_trades}</td>
                <td class="text-green">${item.winning_trades}</td>
                <td class="text-red">${item.losing_trades}</td>
                <td><strong>${item.win_rate.toFixed(2)}%</strong></td>
                <td class="${pnlClass}"><strong>${pnlSign}₹${item.total_pnl.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong></td>
                <td><span class="badge-status tp">COMPLETED</span></td>
            `;
            tbody.appendChild(tr);
        });
    }

    function renderTradesTable(trades) {
        const tbody = document.getElementById('trades-log-tbody');
        tbody.innerHTML = '';

        if (!trades || trades.length === 0) {
            tbody.innerHTML = `<tr><td colspan="14" style="text-align: center; color: var(--gtf-text-muted); padding: 24px;">No trades executed for selected timeframe and filters.</td></tr>`;
            return;
        }

        trades.forEach(tr => {
            const row = document.createElement('tr');
            const pnlClass = tr.pnl > 0 ? 'text-green' : (tr.pnl < 0 ? 'text-red' : '');
            const statusBadgeClass = tr.status === 'TP' ? 'tp' : (tr.status === 'SL' ? 'sl' : 'eod');
            const typeBadgeClass = tr.type === 'BUY' ? 'type-buy' : 'type-sell';
            const scoreClass = tr.score >= 7.0 ? 'high-score' : '';
            const pnlSign = tr.pnl > 0 ? '+' : '';

            row.innerHTML = `
                <td><strong>${tr.symbol}</strong></td>
                <td>#${tr.trade_id}</td>
                <td><span class="badge-status ${typeBadgeClass}">${tr.type}</span></td>
                <td><span class="badge-score ${scoreClass}">${tr.score}</span></td>
                <td>${tr.entry_date}</td>
                <td>${tr.exit_date}</td>
                <td>₹${tr.entry_price.toFixed(2)}</td>
                <td>₹${tr.exit_price.toFixed(2)}</td>
                <td>₹${tr.stop_loss.toFixed(2)}</td>
                <td>₹${tr.take_profit.toFixed(2)}</td>
                <td>${tr.qty}</td>
                <td><span class="badge-status ${statusBadgeClass}">${tr.status}</span></td>
                <td class="${pnlClass}"><strong>${pnlSign}₹${tr.pnl.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong></td>
                <td class="${pnlClass}"><strong>${tr.r_achieved > 0 ? '+' : ''}${tr.r_achieved}R</strong></td>
            `;
            tbody.appendChild(row);
        });
    }

    // Filter Listeners
    const searchInput = document.getElementById('trade-search-input');
    const statusSelect = document.getElementById('trade-status-filter');

    function applyTradeFilters() {
        const q = searchInput.value.toLowerCase().trim();
        const statusVal = statusSelect.value;

        const filtered = currentTradesLog.filter(tr => {
            const matchesSearch = !q || tr.symbol.toLowerCase().includes(q) || tr.type.toLowerCase().includes(q) || tr.status.toLowerCase().includes(q);
            const matchesStatus = statusVal === 'ALL' || tr.status === statusVal;
            return matchesSearch && matchesStatus;
        });

        renderTradesTable(filtered);
    }

    if (searchInput) searchInput.addEventListener('input', applyTradeFilters);
    if (statusSelect) statusSelect.addEventListener('change', applyTradeFilters);

    // CSV Export
    const btnExport = document.getElementById('btn-export-csv');
    if (btnExport) {
        btnExport.addEventListener('click', function () {
            if (!currentTradesLog || currentTradesLog.length === 0) {
                alert('No trades available to export.');
                return;
            }

            const headers = ['Symbol', 'Trade ID', 'Type', 'Score', 'Entry Time', 'Exit Time', 'Entry Price', 'Exit Price', 'Stop Loss', 'Take Profit', 'Qty', 'Status', 'PnL', 'R Achieved', 'Capital After'];
            const csvRows = [headers.join(',')];

            currentTradesLog.forEach(tr => {
                const row = [
                    tr.symbol, tr.trade_id, tr.type, tr.score,
                    `"${tr.entry_date}"`, `"${tr.exit_date}"`,
                    tr.entry_price, tr.exit_price, tr.stop_loss, tr.take_profit,
                    tr.qty, tr.status, tr.pnl, tr.r_achieved, tr.capital_after
                ];
                csvRows.push(row.join(','));
            });

            const blob = new Blob([csvRows.join('\n')], { type: 'text/csv' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.setAttribute('href', url);
            a.setAttribute('download', `GTF_Backtest_Trades_${new Date().toISOString().slice(0, 10)}.csv`);
            a.click();
        });
    }
});
