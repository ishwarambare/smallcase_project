/**
 * stocks/static/js/pages/demand-supply.js
 *
 * GTF Demand-Supply Zone Scanner — Frontend Logic
 *
 * Handles:
 *  - Triggering scans via API
 *  - Polling scan progress
 *  - Fetching and rendering screener results
 *  - Sector strength cards
 *  - Filtering and sorting
 *  - Stock detail modal with zone list
 */

(function () {
    'use strict';

    // ─── State ─────────────────────────────────────────────────
    let currentTaskId = null;
    let pollInterval = null;
    let currentFilters = {
        zone_type: 'demand',
        min_overlap: 0,
        timeframes: '',
        sector: '',
        sort_by: 'overlap_count',
        fresh_only: false,
    };

    // ─── DOM Refs ──────────────────────────────────────────────
    const scanBtn = document.getElementById('ds-scan-btn');
    const progressBar = document.getElementById('ds-progress-bar');
    const progressFill = document.getElementById('ds-progress-fill');
    const progressText = document.getElementById('ds-progress-text');
    const tableBody = document.getElementById('ds-table-body');
    const sectorContainer = document.getElementById('ds-sector-cards');
    const modalOverlay = document.getElementById('ds-modal-overlay');
    const modalBody = document.getElementById('ds-modal-body');
    const modalTitle = document.getElementById('ds-modal-title');
    const modalClose = document.getElementById('ds-modal-close');
    const lastScanEl = document.getElementById('ds-last-scan');
    const emptyState = document.getElementById('ds-empty-state');
    const tableWrapper = document.getElementById('ds-table-wrapper');

    // Summary stat elements
    const statTotal = document.getElementById('stat-total');
    const statDemand = document.getElementById('stat-demand');
    const statSupply = document.getElementById('stat-supply');
    const statTriple = document.getElementById('stat-triple');

    // Filter elements
    const filterZoneType = document.getElementById('filter-zone-type');
    const filterOverlap = document.getElementById('filter-overlap');
    const filterSector = document.getElementById('filter-sector');
    const filterFresh = document.getElementById('filter-fresh');

    // ─── CSRF Token ────────────────────────────────────────────
    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) return meta.getAttribute('content');
        const cookie = document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='));
        return cookie ? cookie.split('=')[1] : '';
    }

    // ─── API Base URL Helper ───────────────────────────────────
    function getApiUrl(endpoint) {
        // Prepend language prefix if present in the current URL (e.g. /en/)
        const match = window.location.pathname.match(/^\/([a-z]{2})\//);
        if (match) {
            return `/${match[1]}${endpoint}`;
        }
        return endpoint;
    }

    // ─── API Calls ─────────────────────────────────────────────
    async function triggerScan() {
        scanBtn.disabled = true;
        scanBtn.innerHTML = '<span class="ds-spinner"></span> Scanning…';

        try {
            const resp = await fetch(getApiUrl('/api/demand-supply/scan/'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                },
            });
            const data = await resp.json();

            if (data.success && data.task_id) {
                currentTaskId = data.task_id;
                showProgress();
                startPolling();
            } else {
                alert('Failed to start scan: ' + (data.error || 'Unknown error'));
                resetScanBtn();
            }
        } catch (err) {
            console.error('Scan trigger error:', err);
            alert('Failed to connect to server');
            resetScanBtn();
        }
    }

    async function pollStatus() {
        if (!currentTaskId) return;

        try {
            const resp = await fetch(getApiUrl(`/api/demand-supply/status/?task_id=${currentTaskId}`));
            const data = await resp.json();

            if (data.status === 'PROGRESS' && data.progress) {
                const pct = data.progress.percent || 0;
                const symbol = data.progress.symbol || '...';
                const current = data.progress.current || 0;
                const total = data.progress.total || 0;

                progressFill.style.width = pct + '%';
                progressText.innerHTML = `Scanning <span>${symbol}</span> (${current}/${total}) — ${pct}%`;

            } else if (data.status === 'SUCCESS') {
                stopPolling();
                hideProgress();
                resetScanBtn();
                loadResults();
                loadSectors();

            } else if (data.status === 'FAILURE') {
                stopPolling();
                hideProgress();
                resetScanBtn();
                alert('Scan failed: ' + (data.error || 'Unknown error'));
            }
        } catch (err) {
            console.error('Poll error:', err);
        }
    }

    async function loadResults() {
        const params = new URLSearchParams();
        params.set('zone_type', currentFilters.zone_type);
        if (currentFilters.min_overlap > 0) params.set('min_overlap', currentFilters.min_overlap);
        if (currentFilters.timeframes) params.set('timeframes', currentFilters.timeframes);
        if (currentFilters.sector) params.set('sector', currentFilters.sector);
        params.set('sort_by', currentFilters.sort_by);
        if (currentFilters.fresh_only) params.set('fresh_only', 'true');

        try {
            const resp = await fetch(getApiUrl(`/api/demand-supply/results/?${params}`));
            const data = await resp.json();

            if (data.success) {
                renderResults(data.results);
                updateSummaryStats(data);
                if (data.last_scan) {
                    updateLastScan(data.last_scan);
                }
            }
        } catch (err) {
            console.error('Load results error:', err);
        }
    }

    async function loadSectors() {
        try {
            const resp = await fetch(getApiUrl('/api/demand-supply/sectors/'));
            const data = await resp.json();

            if (data.success) {
                renderSectors(data.sectors);
            }
        } catch (err) {
            console.error('Load sectors error:', err);
        }
    }

    async function loadStockDetail(symbol) {
        try {
            const resp = await fetch(getApiUrl(`/api/demand-supply/stock/${symbol}/`));
            const data = await resp.json();

            if (data.success) {
                renderStockModal(data.stock, data.zones);
            } else {
                alert(data.error || 'Could not load stock data');
            }
        } catch (err) {
            console.error('Stock detail error:', err);
        }
    }

    async function checkInitialStatus() {
        try {
            const resp = await fetch(getApiUrl('/api/demand-supply/status/'));
            const data = await resp.json();

            if (data.last_scan) {
                updateLastScan(data.last_scan);
            }
            if (data.total_results > 0) {
                loadResults();
                loadSectors();
            }
        } catch (err) {
            console.error('Initial status check error:', err);
        }
    }

    // ─── Renderers ─────────────────────────────────────────────
    function renderResults(results) {
        if (!results || results.length === 0) {
            tableWrapper.style.display = 'none';
            emptyState.style.display = 'block';
            return;
        }

        tableWrapper.style.display = 'block';
        emptyState.style.display = 'none';

        tableBody.innerHTML = results.map(r => {
            const demandOverlap = r.demand_overlap_count || 0;
            const supplyOverlap = r.supply_overlap_count || 0;
            const score = r.strongest_zone_score || 0;

            return `
                <tr data-symbol="${r.symbol}" onclick="window.dsShowDetail('${r.symbol}')">
                    <td>
                        <div class="stock-symbol">${r.symbol}</div>
                        <div class="stock-name">${r.name || ''}</div>
                    </td>
                    <td class="price">₹${formatPrice(r.current_price)}</td>
                    <td><span class="stock-sector">${r.sector || '—'}</span></td>
                    <td>${zoneBadge(r.quarterly_demand, r.quarterly_supply)}</td>
                    <td>${zoneBadge(r.monthly_demand, r.monthly_supply)}</td>
                    <td>${zoneBadge(r.weekly_demand, r.weekly_supply)}</td>
                    <td>${overlapBadge(demandOverlap, 'demand')}</td>
                    <td>${overlapBadge(supplyOverlap, 'supply')}</td>
                    <td>${strengthBar(score)}</td>
                </tr>
            `;
        }).join('');
    }

    function renderSectors(sectors) {
        if (!sectors || sectors.length === 0) {
            sectorContainer.innerHTML = '<p style="color: var(--text-secondary); font-size: 0.85rem;">No sector data yet. Run a scan first.</p>';
            return;
        }

        sectorContainer.innerHTML = sectors.map(s => {
            const topStocksHtml = (s.top_stocks || []).map(ts =>
                `<span style="font-size:0.72rem; color: var(--text-secondary);">${ts.symbol}</span>`
            ).join(', ');

            return `
                <div class="ds-sector-card" data-sector="${s.sector}" onclick="window.dsFilterBySector('${s.sector}')">
                    <div class="ds-sector-name">${s.sector}</div>
                    <div class="ds-sector-stats">
                        <div class="ds-sector-stat">
                            <div class="value demand">${s.demand_strength_pct}%</div>
                            <div class="label">Demand</div>
                        </div>
                        <div class="ds-sector-stat">
                            <div class="value supply">${s.supply_strength_pct}%</div>
                            <div class="label">Supply</div>
                        </div>
                        <div class="ds-sector-stat">
                            <div class="value" style="color: var(--text-primary);">${s.total_stocks}</div>
                            <div class="label">Stocks</div>
                        </div>
                    </div>
                    <div class="ds-sector-bar">
                        <div class="ds-sector-bar-fill demand" style="width: ${s.demand_strength_pct}%"></div>
                    </div>
                    ${topStocksHtml ? `<div style="margin-top: 0.5rem; font-size: 0.72rem; color: var(--text-secondary);">Top: ${topStocksHtml}</div>` : ''}
                </div>
            `;
        }).join('');

        // Populate sector filter dropdown
        if (filterSector) {
            const existingOptions = filterSector.querySelectorAll('option:not([value=""])');
            existingOptions.forEach(o => o.remove());
            sectors.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s.sector;
                opt.textContent = s.sector;
                filterSector.appendChild(opt);
            });
        }
    }

    function renderStockModal(stock, zones) {
        modalTitle.textContent = `${stock.symbol} — Zone Analysis`;

        const demandZones = zones.filter(z => z.zone_type === 'demand');
        const supplyZones = zones.filter(z => z.zone_type === 'supply');

        let html = `
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.75rem; margin-bottom: 1.5rem;">
                <div class="ds-stat-card">
                    <div class="ds-stat-value blue">₹${formatPrice(stock.current_price)}</div>
                    <div class="ds-stat-label">Current Price</div>
                </div>
                <div class="ds-stat-card">
                    <div class="ds-stat-value green">${stock.demand_overlap_count}</div>
                    <div class="ds-stat-label">Demand Overlaps</div>
                </div>
                <div class="ds-stat-card">
                    <div class="ds-stat-value red">${stock.supply_overlap_count}</div>
                    <div class="ds-stat-label">Supply Overlaps</div>
                </div>
            </div>
        `;

        if (demandZones.length > 0) {
            html += `<h3 style="font-size: 0.9rem; margin-bottom: 0.75rem; color: #10b981;">📈 Demand Zones (${demandZones.length})</h3>`;
            html += '<div class="ds-zone-list">';
            demandZones.forEach(z => {
                html += zoneItem(z, 'demand');
            });
            html += '</div>';
        }

        if (supplyZones.length > 0) {
            html += `<h3 style="font-size: 0.9rem; margin: 1.5rem 0 0.75rem; color: #ef4444;">📉 Supply Zones (${supplyZones.length})</h3>`;
            html += '<div class="ds-zone-list">';
            supplyZones.forEach(z => {
                html += zoneItem(z, 'supply');
            });
            html += '</div>';
        }

        if (demandZones.length === 0 && supplyZones.length === 0) {
            html += '<p style="text-align:center; color: var(--text-secondary); padding: 2rem;">No zones detected for this stock.</p>';
        }

        modalBody.innerHTML = html;
        modalOverlay.classList.add('active');
    }

    // ─── HTML Helpers ──────────────────────────────────────────
    function zoneBadge(isDemand, isSupply) {
        if (isDemand) return '<span class="zone-badge demand" title="In Demand Zone">✅</span>';
        if (isSupply) return '<span class="zone-badge supply" title="In Supply Zone">🔴</span>';
        return '<span class="zone-badge none">—</span>';
    }

    function overlapBadge(count, type) {
        const color = type === 'demand' ? 'green' : 'red';
        if (count >= 3) return `<span class="overlap-badge triple">${count} 🔥</span>`;
        if (count === 2) return `<span class="overlap-badge double">${count}</span>`;
        if (count === 1) return `<span class="overlap-badge single">${count}</span>`;
        return `<span class="overlap-badge zero">0</span>`;
    }

    function strengthBar(score) {
        const cls = score >= 70 ? 'high' : score >= 40 ? 'medium' : 'low';
        return `
            <div class="strength-bar-container">
                <div class="strength-bar">
                    <div class="strength-bar-fill ${cls}" style="width: ${score}%"></div>
                </div>
                <span class="strength-score">${score}</span>
            </div>
        `;
    }

    function zoneItem(zone, type) {
        const icon = type === 'demand' ? '🟢' : '🔴';
        const scoreClass = zone.strength_score >= 70 ? 'high' : zone.strength_score >= 40 ? 'medium' : 'low';
        const freshHtml = zone.is_fresh
            ? '<span class="fresh-badge fresh">✨ Fresh</span>'
            : '<span class="fresh-badge tested">⚡ Tested</span>';

        return `
            <div class="ds-zone-item">
                <div class="ds-zone-tf">${icon} ${zone.timeframe}</div>
                <div class="ds-zone-range">
                    <span class="proximal">₹${formatPrice(zone.proximal)}</span>
                    <span class="distal"> → ₹${formatPrice(zone.distal)}</span>
                    <span style="font-size: 0.72rem; color: var(--text-secondary); margin-left: 0.5rem;">
                        ${zone.base_candles} candle base · ${zone.move_pct}% move
                    </span>
                </div>
                <div class="ds-zone-meta">
                    ${freshHtml}
                    ${strengthBar(zone.strength_score)}
                </div>
            </div>
        `;
    }

    function formatPrice(price) {
        if (price == null) return '—';
        return parseFloat(price).toLocaleString('en-IN', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    // ─── Stats ─────────────────────────────────────────────────
    function updateSummaryStats(data) {
        if (!data.results) return;
        const results = data.results;

        if (statTotal) statTotal.textContent = results.length;
        if (statDemand) statDemand.textContent = results.filter(r => r.demand_overlap_count > 0).length;
        if (statSupply) statSupply.textContent = results.filter(r => r.supply_overlap_count > 0).length;
        if (statTriple) statTriple.textContent = results.filter(r => r.demand_overlap_count >= 3).length;
    }

    function updateLastScan(isoStr) {
        if (!lastScanEl) return;
        try {
            const dt = new Date(isoStr);
            lastScanEl.innerHTML = `Last scan: <span class="last-scan-time">${dt.toLocaleString('en-IN')}</span>`;
        } catch (e) {
            lastScanEl.textContent = 'Last scan: ' + isoStr;
        }
    }

    // ─── Progress ──────────────────────────────────────────────
    function showProgress() {
        progressBar.classList.add('active');
        progressFill.style.width = '0%';
        progressText.innerHTML = 'Starting scan…';
    }

    function hideProgress() {
        progressBar.classList.remove('active');
    }

    function startPolling() {
        if (pollInterval) clearInterval(pollInterval);
        pollInterval = setInterval(pollStatus, 2000);
    }

    function stopPolling() {
        if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }
        currentTaskId = null;
    }

    function resetScanBtn() {
        scanBtn.disabled = false;
        scanBtn.innerHTML = '🔍 Run Scan';
    }

    // ─── Filters ───────────────────────────────────────────────
    function applyFilters() {
        if (filterZoneType) currentFilters.zone_type = filterZoneType.value;
        if (filterOverlap) currentFilters.min_overlap = parseInt(filterOverlap.value) || 0;
        if (filterSector) currentFilters.sector = filterSector.value;
        loadResults();
    }

    // ─── Global handlers (called from onclick) ─────────────────
    window.dsShowDetail = function (symbol) {
        loadStockDetail(symbol);
    };

    window.dsFilterBySector = function (sector) {
        // Toggle sector filter
        if (currentFilters.sector === sector) {
            currentFilters.sector = '';
            if (filterSector) filterSector.value = '';
        } else {
            currentFilters.sector = sector;
            if (filterSector) filterSector.value = sector;
        }

        // Highlight active card
        document.querySelectorAll('.ds-sector-card').forEach(card => {
            card.classList.toggle('active', card.dataset.sector === currentFilters.sector);
        });

        loadResults();
    };

    // ─── Init ──────────────────────────────────────────────────
    function init() {
        // Scan button
        if (scanBtn) {
            scanBtn.addEventListener('click', triggerScan);
        }

        // Modal close
        if (modalClose) {
            modalClose.addEventListener('click', () => {
                modalOverlay.classList.remove('active');
            });
        }
        if (modalOverlay) {
            modalOverlay.addEventListener('click', (e) => {
                if (e.target === modalOverlay) {
                    modalOverlay.classList.remove('active');
                }
            });
        }

        // Filter listeners
        if (filterZoneType) filterZoneType.addEventListener('change', applyFilters);
        if (filterOverlap) filterOverlap.addEventListener('change', applyFilters);
        if (filterSector) filterSector.addEventListener('change', applyFilters);
        if (filterFresh) {
            filterFresh.addEventListener('click', () => {
                currentFilters.fresh_only = !currentFilters.fresh_only;
                filterFresh.classList.toggle('active', currentFilters.fresh_only);
                loadResults();
            });
        }

        // Escape to close modal
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modalOverlay && modalOverlay.classList.contains('active')) {
                modalOverlay.classList.remove('active');
            }
        });

        // Initial data load
        checkInitialStatus();
    }

    // Wait for DOM
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
