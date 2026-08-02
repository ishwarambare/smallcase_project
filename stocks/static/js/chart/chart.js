// stocks/static/js/chart/chart.js
//
// Main chart controller — integrates:
//   - Candlestick series
//   - EMA 20 / EMA 50 line series
//   - RSI pane (separate chart) with smoothing line
//   - ZoneRenderer (canvas overlay with filters)
//   - Filter panel state management
//   - Auto-fit, timeframe switching, nearest zone

document.addEventListener('DOMContentLoaded', async () => {
    if (typeof SYMBOL === 'undefined') {
        console.error('SYMBOL is not defined.');
        return;
    }

    // ─── Element Refs ───────────────────────────────────────────
    const container   = document.getElementById('chart-container');
    const rsiContainer = document.getElementById('rsi-container');
    const loading     = document.getElementById('loading');
    const overlayCanvas = document.getElementById('custom-canvas-overlay');

    // ─── Filter state ───────────────────────────────────────────
    const filterState = {
        freshOnly:       true,
        showDemand:      true,
        showSupply:      true,
        allTFMode:       false,
        showNearest:     true,
        minOverlap:      0,
        showEMA20:       true,
        showEMA50:       true,
        showRSI:         true,
        showCrossovers:  false,
        // Per-TF visibility (all on by default)
        activeTFs: ['quarterly', 'monthly', 'weekly', 'daily', '125min', '75min'],
    };

    // ─── Main Chart ─────────────────────────────────────────────
    const chart = LightweightCharts.createChart(container, {
        autoSize: true,
        layout: {
            background: { type: 'solid', color: '#0f1117' },
            textColor: '#d1d4dc',
        },
        grid: {
            vertLines: { color: '#1e2130' },
            horzLines: { color: '#1e2130' },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
        },
        rightPriceScale: {
            borderColor: '#2a2e39',
            scaleMargins: { top: 0.08, bottom: 0.08 },
        },
        timeScale: {
            borderColor: '#2a2e39',
            timeVisible: true,
        },
    });

    // Candlestick series
    const candleSeries = chart.addCandlestickSeries({
        upColor:        '#26a69a',
        downColor:      '#ef5350',
        borderVisible:  false,
        wickUpColor:    '#26a69a',
        wickDownColor:  '#ef5350',
    });

    // EMA 20 line series
    const ema20Series = chart.addLineSeries({
        color:     '#f59e0b',
        lineWidth:  2,
        priceLineVisible: false,
        lastValueVisible: true,
        title: 'EMA 20',
    });

    // EMA 50 line series
    const ema50Series = chart.addLineSeries({
        color:     '#3b82f6',
        lineWidth:  2,
        priceLineVisible: false,
        lastValueVisible: true,
        title: 'EMA 50',
    });

    // ─── RSI Chart (separate pane) ───────────────────────────────
    const rsiChart = LightweightCharts.createChart(rsiContainer, {
        autoSize: true,
        layout: {
            background: { type: 'solid', color: '#0f1117' },
            textColor: '#d1d4dc',
        },
        grid: {
            vertLines: { color: '#1e2130' },
            horzLines: { color: '#1e2130' },
        },
        rightPriceScale: {
            borderColor: '#2a2e39',
            scaleMargins: { top: 0.05, bottom: 0.05 },
            minimum: 0,
            maximum: 100,
        },
        timeScale: {
            borderColor: '#2a2e39',
            timeVisible: true,
            visible: false, // hide duplicate time axis
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
        },
    });

    // RSI line
    const rsiSeries = rsiChart.addLineSeries({
        color:      '#a78bfa',
        lineWidth:   2,
        priceLineVisible: false,
        lastValueVisible: true,
        title: 'RSI 14',
    });

    // RSI Signal line (9-period EMA of RSI)
    const rsiSignalSeries = rsiChart.addLineSeries({
        color:      '#f472b6',
        lineWidth:   1,
        lineStyle:   LightweightCharts.LineStyle.Dashed,
        priceLineVisible: false,
        lastValueVisible: true,
        title: 'Signal',
    });

    // RSI reference lines at 70 and 30
    [70, 30].forEach(level => {
        rsiChart.addLineSeries({
            color:      level === 70 ? 'rgba(239,68,68,0.4)' : 'rgba(16,185,129,0.4)',
            lineWidth:   1,
            lineStyle:   LightweightCharts.LineStyle.Dotted,
            priceLineVisible: false,
            lastValueVisible: false,
        }).setData([]);  // will be set after we know the time range
    });
    const rsiOB = rsiChart.addLineSeries({ color:'rgba(239,68,68,0.4)', lineWidth:1, lineStyle:2, priceLineVisible:false, lastValueVisible:false });
    const rsiOS = rsiChart.addLineSeries({ color:'rgba(16,185,129,0.4)', lineWidth:1, lineStyle:2, priceLineVisible:false, lastValueVisible:false });

    // Sync time scales
    function syncTimeScales(sourceChart, targetChart) {
        sourceChart.timeScale().subscribeVisibleLogicalRangeChange(range => {
            if (range !== null) {
                targetChart.timeScale().setVisibleLogicalRange(range);
            }
        });
    }
    syncTimeScales(chart, rsiChart);
    syncTimeScales(rsiChart, chart);

    // ─── State ──────────────────────────────────────────────────
    let zoneRenderer = null;
    let allZones     = [];
    let currentTf    = 'daily';
    let lastClose    = null;
    let lastCrossovers = [];

    // ─── Crossover Detection ─────────────────────────────────────
    /**
     * Find all Golden/Death crossover events between two EMA series.
     * @param {Array} ema20 [{time, value}, ...]
     * @param {Array} ema50 [{time, value}, ...]
     * @returns {Array} [{time, type: 'golden'|'death'}, ...]
     */
    function detectCrossovers(ema20, ema50) {
        if (!ema20 || !ema50 || ema20.length < 2 || ema50.length < 2) return [];

        // Build lookup for ema50 by time
        const ema50Map = {};
        ema50.forEach(p => { ema50Map[p.time] = p.value; });

        const crossovers = [];
        let prevDiff = null;

        for (let i = 0; i < ema20.length; i++) {
            const t = ema20[i].time;
            const v20 = ema20[i].value;
            const v50 = ema50Map[t];
            if (v50 === undefined) continue;

            const diff = v20 - v50;
            if (prevDiff !== null) {
                if (prevDiff < 0 && diff >= 0) {
                    crossovers.push({ time: t, type: 'golden' });
                } else if (prevDiff > 0 && diff <= 0) {
                    crossovers.push({ time: t, type: 'death' });
                }
            }
            prevDiff = diff;
        }
        return crossovers;
    }

    // ─── Load Everything ─────────────────────────────────────────
    async function loadChartData(tf) {
        currentTf = tf;
        loading.style.display = 'block';
        loading.innerText = 'Loading chart data…';

        try {
            // Fetch candles + indicators in parallel; zones cached after first load
            const [candles, indicators] = await Promise.all([
                fetchCandles(SYMBOL, tf),
                fetchIndicators(SYMBOL, tf),
            ]);

            if (allZones.length === 0) {
                allZones = await fetchZones(SYMBOL);
            }

            if (candles.length === 0) {
                loading.innerText = 'No historical data for this timeframe.';
                candleSeries.setData([]);
                return;
            }

            // Set candle data
            candleSeries.setData(candles);
            loading.style.display = 'none';

            // Last close for nearest zone computation
            lastClose = candles[candles.length - 1].close;

            // EMA series
            let ema20Data = [];
            let ema50Data = [];
            if (indicators.ema20 && filterState.showEMA20) {
                ema20Data = indicators.ema20;
                ema20Series.setData(ema20Data);
            } else ema20Series.setData([]);

            if (indicators.ema50 && filterState.showEMA50) {
                ema50Data = indicators.ema50;
                ema50Series.setData(ema50Data);
            } else ema50Series.setData([]);

            // Detect EMA crossovers
            lastCrossovers = detectCrossovers(indicators.ema20, indicators.ema50);

            // RSI
            if (indicators.rsi && filterState.showRSI) {
                rsiSeries.setData(indicators.rsi);
                rsiSignalSeries.setData(indicators.rsi_signal || []);

                // Draw OB/OS reference lines across full time range
                const tStart = candles[0].time;
                const tEnd   = candles[candles.length - 1].time;
                rsiOB.setData([{ time: tStart, value: 70 }, { time: tEnd, value: 70 }]);
                rsiOS.setData([{ time: tStart, value: 30 }, { time: tEnd, value: 30 }]);
            } else {
                rsiSeries.setData([]);
                rsiSignalSeries.setData([]);
                rsiOB.setData([]);
                rsiOS.setData([]);
            }

            // Zone renderer
            const maxDate = candles[candles.length - 1].time;
            if (zoneRenderer) {
                zoneRenderer.zones     = allZones;
                zoneRenderer.currentTf = tf;
                zoneRenderer.maxDate   = maxDate;
                zoneRenderer.candleData = candles;
                zoneRenderer.setCurrentPrice(lastClose);
                zoneRenderer.setCrossovers(filterState.showCrossovers ? lastCrossovers : []);
                zoneRenderer.draw();
            } else {
                zoneRenderer = new ZoneRenderer(
                    chart, candleSeries, overlayCanvas,
                    allZones, candles, tf,
                    filterState
                );
                zoneRenderer.setCurrentPrice(lastClose);
                zoneRenderer.setCrossovers(filterState.showCrossovers ? lastCrossovers : []);
            }

            // Auto-fit on first load
            chart.timeScale().fitContent();

        } catch (err) {
            console.error(err);
            loading.innerText = 'Error loading chart data.';
        }
    }

    // ─── Apply Filter Changes ────────────────────────────────────
    function applyFilters() {
        if (!zoneRenderer) return;
        zoneRenderer.updateFilters({ ...filterState });

        // EMA visibility
        if (filterState.showEMA20) {
            fetchIndicators(SYMBOL, currentTf).then(ind => {
                ema20Series.setData(ind.ema20 || []);
            });
        } else {
            ema20Series.setData([]);
        }

        if (filterState.showEMA50) {
            fetchIndicators(SYMBOL, currentTf).then(ind => {
                ema50Series.setData(ind.ema50 || []);
            });
        } else {
            ema50Series.setData([]);
        }

        // RSI pane visibility
        rsiContainer.style.display = filterState.showRSI ? 'block' : 'none';
        if (filterState.showRSI) {
            fetchIndicators(SYMBOL, currentTf).then(ind => {
                rsiSeries.setData(ind.rsi || []);
                rsiSignalSeries.setData(ind.rsi_signal || []);
            });
        } else {
            rsiSeries.setData([]);
            rsiSignalSeries.setData([]);
        }
    }

    // ─── Timeframe Buttons ───────────────────────────────────────
    document.querySelectorAll('.tf-btn').forEach(btn => {
        btn.addEventListener('click', e => {
            document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
            e.currentTarget.classList.add('active');
            loadChartData(e.currentTarget.dataset.tf);
        });
    });

    // ─── Auto-Fit Button ─────────────────────────────────────────
    document.getElementById('btn-auto-fit')?.addEventListener('click', () => {
        // Reset price scales to auto-fit the visible data
        chart.priceScale('right').applyOptions({ autoScale: true });
        rsiChart.priceScale('right').applyOptions({ autoScale: true });
    });

    // ─── Filter Panel: Fresh Only ─────────────────────────────────
    document.getElementById('filter-fresh-only')?.addEventListener('change', e => {
        filterState.freshOnly = e.target.checked;
        applyFilters();
    });

    // ─── Filter Panel: Demand / Supply toggles ───────────────────
    document.getElementById('filter-show-demand')?.addEventListener('change', e => {
        filterState.showDemand = e.target.checked;
        applyFilters();
    });
    document.getElementById('filter-show-supply')?.addEventListener('change', e => {
        filterState.showSupply = e.target.checked;
        applyFilters();
    });

    // ─── Filter Panel: All-TF Overlay ────────────────────────────
    document.getElementById('filter-all-tf')?.addEventListener('change', e => {
        filterState.allTFMode = e.target.checked;
        applyFilters();
    });

    // ─── Filter Panel: Nearest Zone ──────────────────────────────
    document.getElementById('filter-nearest')?.addEventListener('change', e => {
        filterState.showNearest = e.target.checked;
        applyFilters();
    });

    // ─── Filter Panel: Overlap Count ─────────────────────────────
    document.getElementById('filter-overlap')?.addEventListener('change', e => {
        filterState.minOverlap = parseInt(e.target.value) || 0;
        document.getElementById('filter-overlap-val').textContent = filterState.minOverlap;
        applyFilters();
    });

    // ─── Filter Panel: Per-TF Toggles ────────────────────────────
    document.querySelectorAll('.tf-zone-toggle').forEach(toggle => {
        toggle.addEventListener('change', e => {
            const tf = e.target.dataset.tf;
            if (e.target.checked) {
                if (!filterState.activeTFs.includes(tf)) filterState.activeTFs.push(tf);
            } else {
                filterState.activeTFs = filterState.activeTFs.filter(t => t !== tf);
            }
            applyFilters();
        });
    });

    // ─── EMA Toggles ─────────────────────────────────────────────
    document.getElementById('filter-ema20')?.addEventListener('change', e => {
        filterState.showEMA20 = e.target.checked;
        applyFilters();
    });
    document.getElementById('filter-ema50')?.addEventListener('change', e => {
        filterState.showEMA50 = e.target.checked;
        applyFilters();
    });

    // ─── RSI Toggle ──────────────────────────────────────────────
    document.getElementById('filter-rsi')?.addEventListener('change', e => {
        filterState.showRSI = e.target.checked;
        applyFilters();
    });

    // ─── Crossovers Toggle ───────────────────────────────────────
    document.getElementById('filter-crossovers')?.addEventListener('change', e => {
        filterState.showCrossovers = e.target.checked;
        zoneRenderer?.setCrossovers(filterState.showCrossovers ? lastCrossovers : []);
    });

    // ─── Date Range Toolbar ───────────────────────────────────────
    /**
     * Returns a {from, to} object (YYYY-MM-DD strings) for the given
     * range code, anchored to today's date.
     */
    function buildDateRange(range) {
        const now  = new Date();
        const to   = now.toISOString().split('T')[0];
        const from = new Date(now);

        switch (range) {
            case '1D': from.setDate(from.getDate() - 1);         break;
            case '1M': from.setMonth(from.getMonth() - 1);       break;
            case '3M': from.setMonth(from.getMonth() - 3);       break;
            case '6M': from.setMonth(from.getMonth() - 6);       break;
            case '1Y': from.setFullYear(from.getFullYear() - 1); break;
            case '3Y': from.setFullYear(from.getFullYear() - 3); break;
            case '5Y': from.setFullYear(from.getFullYear() - 5); break;
            case 'ALL': return null; // fit all content
            default:   return null;
        }
        return { from: from.toISOString().split('T')[0], to };
    }

    function applyDateRange(range) {
        const dateRange = buildDateRange(range);
        if (!dateRange) {
            // ALL — fit everything
            chart.timeScale().fitContent();
            rsiChart.timeScale().fitContent();
        } else {
            chart.timeScale().setVisibleRange(dateRange);
            rsiChart.timeScale().setVisibleRange(dateRange);
        }
    }

    // Attach range button listeners
    document.querySelectorAll('.range-btn').forEach(btn => {
        btn.addEventListener('click', e => {
            document.querySelectorAll('.range-btn').forEach(b => b.classList.remove('active'));
            e.currentTarget.classList.add('active');
            applyDateRange(e.currentTarget.dataset.range);
        });
    });

    // ─── Window resize ───────────────────────────────────────────
    window.addEventListener('resize', () => {
        chart.resize(container.clientWidth, container.clientHeight);
        rsiChart.resize(rsiContainer.clientWidth, rsiContainer.clientHeight);
        zoneRenderer?.resizeAndDraw();
    });

    // ─── Broker & Super Order Controller ─────────────────────
    let activeBroker = 'FYERS'; // 'DHAN' or 'FYERS'
    let dhanPriceLines = { entry: null, stopLoss: null, target: null };
    let dhanPickingChartMode = false;
    let currentSide = 'BUY';

    // Broker toggle listeners
    const btnBrokerDhan = document.getElementById('btn-broker-dhan');
    const btnBrokerFyers = document.getElementById('btn-broker-fyers');
    const panelTitle = document.getElementById('panel-title');

    function switchBroker(broker) {
        activeBroker = broker;
        if (broker === 'DHAN') {
            if (btnBrokerDhan) {
                btnBrokerDhan.classList.add('active');
                btnBrokerDhan.style.background = 'var(--accent)';
                btnBrokerDhan.style.color = '#fff';
            }
            if (btnBrokerFyers) {
                btnBrokerFyers.classList.remove('active');
                btnBrokerFyers.style.background = 'transparent';
                btnBrokerFyers.style.color = 'var(--text-light)';
            }
            if (panelTitle) panelTitle.textContent = '⚡ Dhan Trading Panel';
        } else {
            if (btnBrokerFyers) {
                btnBrokerFyers.classList.add('active');
                btnBrokerFyers.style.background = 'var(--accent)';
                btnBrokerFyers.style.color = '#fff';
            }
            if (btnBrokerDhan) {
                btnBrokerDhan.classList.remove('active');
                btnBrokerDhan.style.background = 'transparent';
                btnBrokerDhan.style.color = 'var(--text-light)';
            }
            if (panelTitle) panelTitle.textContent = '⚡ Fyers Trading Panel';
        }
        checkBrokerStatus();
        
        // Update submit button labels
        const btnOrder = document.getElementById('btn-submit-super-order');
        if (btnOrder) btnOrder.textContent = `🚀 Place Super Order (${activeBroker})`;
        const btnAlert = document.getElementById('btn-submit-forever-alert');
        if (btnAlert) btnAlert.textContent = `🔔 Create Alert (${activeBroker})`;
    }
    
    if (btnBrokerDhan && btnBrokerFyers) {
        btnBrokerDhan.addEventListener('click', () => switchBroker('DHAN'));
        btnBrokerFyers.addEventListener('click', () => switchBroker('FYERS'));
    }

    // Account status check
    async function checkBrokerStatus() {
        const badge = document.getElementById('broker-status-badge');
        const bal = document.getElementById('broker-acc-balance');
        const accId = document.getElementById('broker-acc-id');
        const endpoint = activeBroker === 'DHAN' ? '/api/dhan/status/' : '/api/fyers/status/';
        
        try {
            if (badge) { badge.textContent = 'Connecting...'; badge.className = 'dhan-badge'; }
            const res = await fetch(endpoint);
            const data = await res.json();
            if (data.active) {
                if (badge) { badge.textContent = '🟢 Connected'; badge.className = 'dhan-badge active'; }
                if (bal) { bal.textContent = `₹${(data.available_balance || 0).toLocaleString('en-IN', {minimumFractionDigits: 2})}`; }
                if (accId) { accId.textContent = data.client_id || (activeBroker === 'DHAN' ? '1106020477' : '...'); }
            } else {
                if (badge) { badge.textContent = '🔴 Inactive'; badge.className = 'dhan-badge error'; }
                if (bal) { bal.textContent = data.error || 'Not configured'; }
                if (accId) { accId.textContent = '...'; }
            }
        } catch (err) {
            console.error(activeBroker + ' status check error:', err);
            if (badge) { badge.textContent = '⚠️ Offline'; badge.className = 'dhan-badge error'; }
        }
    }
    checkBrokerStatus();
    switchBroker(activeBroker);

    // Side selector listener
    const sideBuyBtn = document.getElementById('dhan-side-buy');
    const sideSellBtn = document.getElementById('dhan-side-sell');
    if (sideBuyBtn && sideSellBtn) {
        sideBuyBtn.addEventListener('click', () => {
            currentSide = 'BUY';
            sideBuyBtn.classList.add('active');
            sideSellBtn.classList.remove('active');
            recalculateDhanOrder();
        });
        sideSellBtn.addEventListener('click', () => {
            currentSide = 'SELL';
            sideSellBtn.classList.add('active');
            sideBuyBtn.classList.remove('active');
            recalculateDhanOrder();
        });
    }

    // Input elements
    const inpCapital = document.getElementById('dhan-capital');
    const inpRiskPct = document.getElementById('dhan-risk-pct');
    const inpRewardRatio = document.getElementById('dhan-reward-ratio');
    const inpEntry = document.getElementById('dhan-entry-price');
    const inpSL = document.getElementById('dhan-stop-loss');

    [inpCapital, inpRiskPct, inpRewardRatio, inpEntry, inpSL].forEach(el => {
        el?.addEventListener('input', recalculateDhanOrder);
    });

    // ─── Dual Chart Pick & Distal Line Logic ───────────────────────
    let dhanPickMode = null; // 'ENTRY' or 'SL'

    const btnPickEntry = document.getElementById('btn-pick-entry');
    const btnPickSL = document.getElementById('btn-pick-sl');

    function setDhanPickMode(mode) {
        if (dhanPickMode === mode) {
            dhanPickMode = null; // toggle off
        } else {
            dhanPickMode = mode;
        }

        if (btnPickEntry) {
            btnPickEntry.style.background = dhanPickMode === 'ENTRY' ? 'var(--accent)' : 'transparent';
            btnPickEntry.style.color = dhanPickMode === 'ENTRY' ? '#fff' : 'var(--accent)';
        }
        if (btnPickSL) {
            btnPickSL.style.background = dhanPickMode === 'SL' ? 'var(--accent)' : 'transparent';
            btnPickSL.style.color = dhanPickMode === 'SL' ? '#fff' : 'var(--accent)';
        }
    }

    btnPickEntry?.addEventListener('click', () => setDhanPickMode('ENTRY'));
    btnPickSL?.addEventListener('click', () => setDhanPickMode('SL'));

    chart.subscribeClick(param => {
        if (!dhanPickMode || !param.point) return;
        const price = candleSeries.coordinateToPrice(param.point.y);
        if (price && price > 0) {
            if (dhanPickMode === 'ENTRY') {
                inpEntry.value = price.toFixed(2);
            } else if (dhanPickMode === 'SL') {
                inpSL.value = price.toFixed(2);
            }
            setDhanPickMode(null); // deactivate pick mode
            recalculateDhanOrder();
        }
    });

    // Auto-set SL from nearest zone distal line
    document.getElementById('btn-auto-sl')?.addEventListener('click', () => {
        let zones = allZonesData?.zones || [];

        let entry = parseFloat(inpEntry?.value) || 0;
        if (!entry && rawCandlesData && rawCandlesData.length > 0) {
            entry = rawCandlesData[rawCandlesData.length - 1].close;
            inpEntry.value = entry.toFixed(2);
        }

        if (zones.length > 0) {
            let bestDistal = null;
            let minDiff = Infinity;

            zones.forEach(z => {
                const distal = parseFloat(z.distal);
                if (currentSide === 'BUY') {
                    // For BUY: prefer distal line below entry (demand zone distal line)
                    if (distal < entry) {
                        const diff = entry - distal;
                        if (diff < minDiff) { minDiff = diff; bestDistal = distal; }
                    }
                } else {
                    // For SELL: prefer distal line above entry (supply zone distal line)
                    if (distal > entry) {
                        const diff = distal - entry;
                        if (diff < minDiff) { minDiff = diff; bestDistal = distal; }
                    }
                }
            });

            // Fallback: nearest distal line of any zone
            if (bestDistal === null) {
                zones.forEach(z => {
                    const distal = parseFloat(z.distal);
                    const diff = Math.abs(distal - entry);
                    if (diff < minDiff) { minDiff = diff; bestDistal = distal; }
                });
            }

            if (bestDistal !== null) {
                inpSL.value = bestDistal.toFixed(2);
                recalculateDhanOrder();
                return;
            }
        }

        // Fallback if no zones available: set SL 1% away
        if (entry > 0) {
            const fallbackSL = currentSide === 'BUY' ? entry * 0.99 : entry * 1.01;
            inpSL.value = fallbackSL.toFixed(2);
            recalculateDhanOrder();
        }
    });

    function recalculateDhanOrder() {
        const capital = parseFloat(inpCapital?.value) || 100000;
        const riskPct = parseFloat(inpRiskPct?.value) || 1.0;
        const rewardRatio = parseFloat(inpRewardRatio?.value) || 2.0;
        const entry = parseFloat(inpEntry?.value) || 0;
        const sl = parseFloat(inpSL?.value) || 0;

        if (entry <= 0 || sl <= 0 || entry === sl) {
            updateDhanCalcDisplay(0, 0, 0, 0, 0, 0, riskPct, rewardRatio);
            clearDhanPriceLines();
            return;
        }

        const maxRiskAmount = capital * (riskPct / 100.0);
        const gap = Math.abs(entry - sl);
        const qty = Math.max(1, Math.floor(maxRiskAmount / gap));
        const targetGap = rewardRatio * gap;
        const targetPrice = currentSide === 'BUY' ? (entry + targetGap) : (entry - targetGap);
        const totalExposure = qty * entry;
        const potentialLoss = qty * gap;
        const potentialProfit = qty * targetGap;

        updateDhanCalcDisplay(gap, targetPrice, qty, totalExposure, potentialLoss, potentialProfit, riskPct, (potentialProfit/capital)*100);
        updateDhanPriceLines(entry, sl, targetPrice);
    }

    function updateDhanCalcDisplay(gap, target, qty, exposure, loss, profit, riskPct, rewardPct) {
        const elGap = document.getElementById('dhan-val-gap');
        const elTarget = document.getElementById('dhan-val-target');
        const elQty = document.getElementById('dhan-val-qty');
        const elExp = document.getElementById('dhan-val-exposure');
        const elLoss = document.getElementById('dhan-val-loss');
        const elProfit = document.getElementById('dhan-val-profit');

        if (elGap) elGap.textContent = `₹${gap.toFixed(2)}`;
        if (elTarget) elTarget.textContent = `₹${target.toFixed(2)}`;
        if (elQty) elQty.textContent = `${qty} shares`;
        if (elExp) elExp.textContent = `₹${exposure.toLocaleString('en-IN', {maximumFractionDigits: 2})}`;
        if (elLoss) elLoss.textContent = `₹${loss.toLocaleString('en-IN', {maximumFractionDigits: 2})} (${riskPct.toFixed(1)}%)`;
        if (elProfit) elProfit.textContent = `₹${profit.toLocaleString('en-IN', {maximumFractionDigits: 2})} (${rewardPct.toFixed(1)}%)`;
    }

    function updateDhanPriceLines(entry, sl, target) {
        clearDhanPriceLines();
        dhanPriceLines.entry = candleSeries.createPriceLine({
            price: entry, color: '#3b82f6', lineWidth: 2, lineStyle: LightweightCharts.LineStyle.Solid, title: '🔵 ENTRY',
        });
        dhanPriceLines.stopLoss = candleSeries.createPriceLine({
            price: sl, color: '#ef4444', lineWidth: 2, lineStyle: LightweightCharts.LineStyle.Dashed, title: '🔴 STOP LOSS',
        });
        dhanPriceLines.target = candleSeries.createPriceLine({
            price: target, color: '#10b981', lineWidth: 2, lineStyle: LightweightCharts.LineStyle.Dashed, title: `🟢 TARGET (${inpRewardRatio?.value || 2}x)`,
        });
    }

    function clearDhanPriceLines() {
        if (dhanPriceLines.entry) { candleSeries.removePriceLine(dhanPriceLines.entry); dhanPriceLines.entry = null; }
        if (dhanPriceLines.stopLoss) { candleSeries.removePriceLine(dhanPriceLines.stopLoss); dhanPriceLines.stopLoss = null; }
        if (dhanPriceLines.target) { candleSeries.removePriceLine(dhanPriceLines.target); dhanPriceLines.target = null; }
    }

    // Submit Super Order
    document.getElementById('btn-submit-super-order')?.addEventListener('click', async () => {
        const entry = parseFloat(inpEntry?.value);
        const sl = parseFloat(inpSL?.value);
        if (!entry || !sl || entry === sl) {
            alert('Please specify valid Entry and Stop Loss prices.');
            return;
        }

        const payload = {
            symbol: SYMBOL,
            entry_price: entry,
            stop_loss_price: sl,
            capital: parseFloat(inpCapital?.value) || 100000,
            risk_pct: parseFloat(inpRiskPct?.value) || 1.0,
            reward_ratio: parseFloat(inpRewardRatio?.value) || 2.0,
            side: currentSide,
            order_type: 'LIMIT',
            product_type: document.getElementById('dhan-product-type')?.value || 'INTRA',
        };

        try {
            const btn = document.getElementById('btn-submit-super-order');
            btn.disabled = true;
            btn.textContent = '⏳ Placing Super Order...';

            const endpoint = activeBroker === 'DHAN' ? '/api/dhan/place-super-order/' : '/api/fyers/place-super-order/';
            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            btn.disabled = false;
            btn.textContent = `🚀 Place Super Order (${activeBroker})`;

            if (data.success) {
                alert(`✅ Super Order Placed Successfully via ${activeBroker}!\n\nOrder ID: ${data.order_id || 'Submitted'}\nQty: ${data.calculation?.quantity}\nTarget: ₹${data.calculation?.target_price}\nSL: ₹${data.calculation?.stop_loss_price}`);
            } else {
                let msg = data.error;
                const brokerResp = data.dhan_response || data.fyers_response;
                if (!msg && brokerResp && (brokerResp.remarks || brokerResp.message)) {
                    const r = brokerResp.remarks || brokerResp.message;
                    if (typeof r === 'object') {
                        msg = r.error_message || JSON.stringify(r);
                        if (r.error_code === 'DH-905') {
                            msg += '\n\n💡 IP Restriction Notice: Please add your IP address to the allowed list in your Dhan Web Dashboard (dhanhq.co -> Profile -> Access API).';
                        }
                    } else {
                        msg = r;
                    }
                }
                alert(`❌ Order Placement Failed (${activeBroker}):\n${msg || 'Unknown error'}`);
            }
        } catch (err) {
            alert(`⚠️ Error submitting order: ${err.message}`);
        }
    });

    // Submit Forever Trigger Alert
    document.getElementById('btn-submit-forever-alert')?.addEventListener('click', async () => {
        const entry = parseFloat(inpEntry?.value);
        if (!entry) {
            alert('Please specify an Entry/Trigger price.');
            return;
        }
        const qtyStr = document.getElementById('dhan-val-qty')?.textContent || '1';
        const qty = parseInt(qtyStr) || 1;

        const payload = {
            symbol: SYMBOL,
            trigger_price: entry,
            price: entry,
            quantity: qty,
            side: currentSide,
        };

        try {
            const endpoint = activeBroker === 'DHAN' ? '/api/dhan/place-alert/' : '/api/fyers/place-alert/';
            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (data.success) {
                alert(`🔔 Alert Created on ${activeBroker}!\n\nSymbol: ${SYMBOL}\nTrigger Price: ₹${entry}\nSide: ${currentSide}`);
            } else {
                let msg = data.error;
                const brokerResp = data.dhan_response || data.fyers_response;
                if (!msg && brokerResp && (brokerResp.remarks || brokerResp.message)) {
                    const r = brokerResp.remarks || brokerResp.message;
                    msg = typeof r === 'object' ? (r.error_message || JSON.stringify(r)) : r;
                }
                alert(`❌ Failed to create Alert (${activeBroker}):\n${msg || 'Unknown error'}`);
            }
        } catch (err) {
            alert(`⚠️ Error creating alert: ${err.message}`);
        }
    });

    // ─── Initial load ────────────────────────────────────────────
    await loadChartData('daily');

    // Auto fill entry price from last candle if available
    if (rawCandlesData && rawCandlesData.length > 0) {
        const lastClose = rawCandlesData[rawCandlesData.length - 1].close;
        if (inpEntry && !inpEntry.value) {
            inpEntry.value = lastClose.toFixed(2);
            // Default SL 1% below for BUY
            if (inpSL && !inpSL.value) {
                inpSL.value = (lastClose * 0.99).toFixed(2);
            }
            recalculateDhanOrder();
        }
    }

    // Apply default 1Y range after data loads
    applyDateRange('1Y');
});
