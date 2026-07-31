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
        freshOnly:       false,
        showDemand:      true,
        showSupply:      true,
        allTFMode:       false,
        showNearest:     true,
        minOverlap:      0,
        showEMA20:       true,
        showEMA50:       true,
        showRSI:         true,
        showCrossovers:  true,
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
        chart.timeScale().fitContent();
        rsiChart.timeScale().fitContent();
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

    // ─── Initial load ────────────────────────────────────────────
    await loadChartData('daily');

    // Apply default 1Y range after data loads
    applyDateRange('1Y');
});
