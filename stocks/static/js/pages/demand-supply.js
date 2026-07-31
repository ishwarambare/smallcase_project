/**
 * stocks/static/js/pages/demand-supply.js
 *
 * GTF Demand-Supply Zone Scanner — Frontend Logic
 *
 * Handles:
 *  - Triggering scans via API (Nifty 500 only)
 *  - Polling scan progress
 *  - Fetching and rendering screener results
 *  - Sector strength cards
 *  - Frontend filtering: symbol search, zone type, overlap, sector, sort, fresh, timeframe chips
 *  - Stock detail modal with zone list
 */

(function () {
    'use strict';

    // ─── State ─────────────────────────────────────────────────
    let currentTaskId = null;
    let pollInterval = null;
    let allResults = [];          // Full API result set for client-side filtering
    let activeTimeframes = [];    // Timeframe chips that are ON

    let currentFilters = {
        zone_type: 'demand',
        min_overlap: 0,
        timeframes: '',
        sector: '',
        sort_by: 'overlap_count',
        fresh_only: false,
    };

    // ─── DOM Refs ──────────────────────────────────────────────
    const scanBtn       = document.getElementById('ds-scan-btn');
    const progressBar   = document.getElementById('ds-progress-bar');
    const progressFill  = document.getElementById('ds-progress-fill');
    const progressText  = document.getElementById('ds-progress-text');
    const tableBody     = document.getElementById('ds-table-body');
    const sectorContainer = document.getElementById('ds-sector-cards');
    const modalOverlay  = document.getElementById('ds-modal-overlay');
    const modalBody     = document.getElementById('ds-modal-body');
    const modalTitle    = document.getElementById('ds-modal-title');
    const modalClose    = document.getElementById('ds-modal-close');
    const lastScanEl    = document.getElementById('ds-last-scan');
    const emptyState    = document.getElementById('ds-empty-state');
    const tableWrapper  = document.getElementById('ds-table-wrapper');

    // Summary stat elements
    const statTotal  = document.getElementById('stat-total');
    const statDemand = document.getElementById('stat-demand');
    const statSupply = document.getElementById('stat-supply');
    const statTriple = document.getElementById('stat-triple');

    // Filter elements
    const filterSearch   = document.getElementById('filter-search');
    const filterZoneType = document.getElementById('filter-zone-type');
    const filterOverlap  = document.getElementById('filter-overlap');
    const filterSector   = document.getElementById('filter-sector');
    const filterSort     = document.getElementById('filter-sort');
    const filterFresh    = document.getElementById('filter-fresh');
    const filterClear    = document.getElementById('filter-clear');
    const tfChips        = document.querySelectorAll('.ds-tf-chip');

    // ─── CSRF Token ────────────────────────────────────────────
    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) return meta.getAttribute('content');
        const cookie = document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='));
        return cookie ? cookie.split('=')[1] : '';
    }

    // ─── API Base URL Helper ───────────────────────────────────
    function getApiUrl(endpoint) {
        const match = window.location.pathname.match(/^\/([a-z]{2})\//);
        if (match) return `/${match[1]}${endpoint}`;
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
                const pct     = data.progress.percent || 0;
                const symbol  = data.progress.symbol || '...';
                const current = data.progress.current || 0;
                const total   = data.progress.total || 0;
                progressFill.style.width = pct + '%';
                progressText.innerHTML = `Scanning <span>${symbol}</span> (${current}/${total}) — ${pct}%`;

            } else if (data.status === 'SUCCESS') {
                stopPolling();
                hideProgress();
                resetScanBtn();
                await loadResults();
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
        params.set('sort_by', currentFilters.sort_by);
        params.set('limit', 500);           // fetch all, client will filter/search
        if (currentFilters.fresh_only) params.set('fresh_only', 'true');

        try {
            const resp = await fetch(getApiUrl(`/api/demand-supply/results/?${params}`));
            const data = await resp.json();
            if (data.success) {
                allResults = data.results || [];
                if (data.last_scan) updateLastScan(data.last_scan);
                applyClientFilters();
            }
        } catch (err) {
            console.error('Load results error:', err);
        }
    }

    async function loadSectors() {
        try {
            const resp = await fetch(getApiUrl('/api/demand-supply/sectors/'));
            const data = await resp.json();
            if (data.success) renderSectors(data.sectors);
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
            if (data.last_scan) updateLastScan(data.last_scan);
            if (data.total_results > 0) {
                await loadResults();
                loadSectors();
            }
        } catch (err) {
            console.error('Initial status check error:', err);
        }
    }

    // ─── Client-Side Filtering ─────────────────────────────────
    function applyClientFilters() {
        const searchTerm = (filterSearch ? filterSearch.value.trim().toLowerCase() : '');
        const minOverlap = parseInt(currentFilters.min_overlap) || 0;
        const sector     = currentFilters.sector;
        const zoneType   = currentFilters.zone_type;

        let filtered = allResults.filter(r => {
            // Symbol / name search
            if (searchTerm) {
                const sym  = (r.symbol || '').toLowerCase();
                const name = (r.name   || '').toLowerCase();
                if (!sym.includes(searchTerm) && !name.includes(searchTerm)) return false;
            }

            // Sector
            if (sector && r.sector !== sector) return false;

            // Min overlap
            const overlap = zoneType === 'supply' ? r.supply_overlap_count : r.demand_overlap_count;
            if (overlap < minOverlap) return false;

            // Timeframe chips (must have ALL active TF flags set)
            if (activeTimeframes.length > 0) {
                for (const tf of activeTimeframes) {
                    const flag = zoneType === 'supply' ? `${tf}_supply` : `${tf}_demand`;
                    if (!r[flag]) return false;
                }
            }

            return true;
        });

        // Sort
        const sortBy = currentFilters.sort_by;
        filtered.sort((a, b) => {
            if (sortBy === 'strength_score') return b.strongest_zone_score - a.strongest_zone_score;
            if (sortBy === 'sector')         return (a.sector || '').localeCompare(b.sector || '');
            // default: overlap_count
            const aOv = zoneType === 'supply' ? a.supply_overlap_count : a.demand_overlap_count;
            const bOv = zoneType === 'supply' ? b.supply_overlap_count : b.demand_overlap_count;
            if (bOv !== aOv) return bOv - aOv;
            return b.strongest_zone_score - a.strongest_zone_score;
        });

        renderResults(filtered);
        updateSummaryStats(filtered);
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
            const demandOv = r.demand_overlap_count || 0;
            const supplyOv = r.supply_overlap_count || 0;
            const score    = r.strongest_zone_score || 0;

            return `
                <tr data-symbol="${r.symbol}" onclick="window.dsShowDetail('${r.symbol}')">
                    <td>
                        <div class="stock-symbol">${r.symbol}</div>
                        <div class="stock-name">${r.name || ''}</div>
                    </td>
                    <td class="price">₹${formatPrice(r.current_price)}</td>
                    <td><span class="stock-sector">${r.sector || '—'}</span></td>
                    <td>${zoneBadge(r.quarterly_demand, r.quarterly_supply)}</td>
                    <td>${zoneBadge(r.monthly_demand,  r.monthly_supply)}</td>
                    <td>${zoneBadge(r.weekly_demand,   r.weekly_supply)}</td>
                    <td>${zoneBadge(r.daily_demand,    r.daily_supply)}</td>
                    <td>${zoneBadge(r.min125_demand,   r.min125_supply)}</td>
                    <td>${zoneBadge(r.min75_demand,    r.min75_supply)}</td>
                    <td>${overlapBadge(demandOv, 'demand')}</td>
                    <td>${overlapBadge(supplyOv, 'supply')}</td>
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
            demandZones.forEach(z => { html += zoneItem(z, 'demand'); });
            html += '</div>';
        }

        if (supplyZones.length > 0) {
            html += `<h3 style="font-size: 0.9rem; margin: 1.5rem 0 0.75rem; color: #ef4444;">📉 Supply Zones (${supplyZones.length})</h3>`;
            html += '<div class="ds-zone-list">';
            supplyZones.forEach(z => { html += zoneItem(z, 'supply'); });
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
    function updateSummaryStats(results) {
        if (!results) return;
        if (statTotal)  statTotal.textContent  = results.length;
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
        if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
        currentTaskId = null;
    }

    function resetScanBtn() {
        scanBtn.disabled = false;
        scanBtn.innerHTML = '🔍 Run Scan';
    }

    // ─── Clear all filters ─────────────────────────────────────
    function clearAllFilters() {
        if (filterSearch)   filterSearch.value = '';
        if (filterZoneType) filterZoneType.value = 'demand';
        if (filterOverlap)  filterOverlap.value = '0';
        if (filterSector)   filterSector.value = '';
        if (filterSort)     filterSort.value = 'overlap_count';
        if (filterFresh)    filterFresh.classList.remove('active');

        activeTimeframes = [];
        tfChips.forEach(c => c.classList.remove('active'));

        currentFilters = {
            zone_type: 'demand',
            min_overlap: 0,
            timeframes: '',
            sector: '',
            sort_by: 'overlap_count',
            fresh_only: false,
        };

        applyClientFilters();
    }

    // ─── Global handlers (called from onclick) ─────────────────
    window.dsShowDetail = function (symbol) {
        loadStockDetail(symbol);
    };

    window.dsFilterBySector = function (sector) {
        if (currentFilters.sector === sector) {
            currentFilters.sector = '';
            if (filterSector) filterSector.value = '';
        } else {
            currentFilters.sector = sector;
            if (filterSector) filterSector.value = sector;
        }

        document.querySelectorAll('.ds-sector-card').forEach(card => {
            card.classList.toggle('active', card.dataset.sector === currentFilters.sector);
        });

        applyClientFilters();
    };

    // ─── Init ──────────────────────────────────────────────────
    function init() {
        // Scan button
        if (scanBtn) scanBtn.addEventListener('click', triggerScan);

        // Modal close
        if (modalClose) {
            modalClose.addEventListener('click', () => modalOverlay.classList.remove('active'));
        }
        if (modalOverlay) {
            modalOverlay.addEventListener('click', e => {
                if (e.target === modalOverlay) modalOverlay.classList.remove('active');
            });
        }

        // Filter listeners — all client-side now
        if (filterSearch) {
            let searchTimer;
            filterSearch.addEventListener('input', () => {
                clearTimeout(searchTimer);
                searchTimer = setTimeout(applyClientFilters, 200);
            });
        }

        if (filterZoneType) {
            filterZoneType.addEventListener('change', () => {
                currentFilters.zone_type = filterZoneType.value;
                // reload from API so correct zone_type results are fetched
                loadResults();
            });
        }

        if (filterOverlap) {
            filterOverlap.addEventListener('change', () => {
                currentFilters.min_overlap = parseInt(filterOverlap.value) || 0;
                applyClientFilters();
            });
        }

        if (filterSector) {
            filterSector.addEventListener('change', () => {
                currentFilters.sector = filterSector.value;
                applyClientFilters();
            });
        }

        if (filterSort) {
            filterSort.addEventListener('change', () => {
                currentFilters.sort_by = filterSort.value;
                applyClientFilters();
            });
        }

        if (filterFresh) {
            filterFresh.addEventListener('click', () => {
                currentFilters.fresh_only = !currentFilters.fresh_only;
                filterFresh.classList.toggle('active', currentFilters.fresh_only);
                loadResults();   // reload — fresh_only is a server-side filter
            });
        }

        if (filterClear) {
            filterClear.addEventListener('click', clearAllFilters);
        }

        // Timeframe chip toggle
        tfChips.forEach(chip => {
            chip.addEventListener('click', () => {
                const tf = chip.dataset.tf;
                chip.classList.toggle('active');
                if (chip.classList.contains('active')) {
                    if (!activeTimeframes.includes(tf)) activeTimeframes.push(tf);
                } else {
                    activeTimeframes = activeTimeframes.filter(t => t !== tf);
                }
                applyClientFilters();
            });
        });

        // Escape to close modal
        document.addEventListener('keydown', e => {
            if (e.key === 'Escape' && modalOverlay && modalOverlay.classList.contains('active')) {
                modalOverlay.classList.remove('active');
            }
        });

        // Initial data load
        checkInitialStatus();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
