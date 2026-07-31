// stocks/static/js/chart/draw_rectangles.js

/**
 * ZoneRenderer — draws Demand & Supply zones on a canvas overlay
 * synchronized with TradingView Lightweight Charts coordinates.
 *
 * Supports:
 *   - Fresh-only filter
 *   - Demand / Supply visibility toggles
 *   - Per-timeframe visibility toggles
 *   - All-TF overlay mode (show zones from all TFs regardless of chart TF)
 *   - Nearest zone highlighting (D1, D2, S1, S2)
 *   - Overlap count filter
 */
class ZoneRenderer {
    /**
     * @param {object}   chart         - LightweightCharts chart instance
     * @param {object}   series        - Candlestick series (for price coords)
     * @param {HTMLCanvasElement} canvas
     * @param {Array}    zones         - Full zone list (all TFs)
     * @param {Array}    candleData    - Current candle array
     * @param {string}   currentTf     - Active chart timeframe
     * @param {object}   filters       - Current filter state
     */
    constructor(chart, series, canvas, zones, candleData, currentTf = 'daily', filters = {}) {
        this.chart = chart;
        this.series = series;
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.zones = zones;
        this.currentTf = currentTf;
        this.filters = this._defaultFilters(filters);

        this.maxDate = candleData.length > 0
            ? candleData[candleData.length - 1].time
            : new Date().toISOString().split('T')[0];

        // Nearest zone refs (computed each draw)
        this.nearestDemand = null;
        this.nearestSupply = null;

        // Crossover events [{time, type:'golden'|'death'}]
        this.crossovers = [];

        // Bind
        this.chart.timeScale().subscribeVisibleLogicalRangeChange(() => this.draw());
        this.chart.timeScale().subscribeSizeChange(() => this.resizeAndDraw());

        this.resizeAndDraw();
    }

    _defaultFilters(f = {}) {
        return {
            freshOnly:    f.freshOnly    ?? false,
            showDemand:   f.showDemand   ?? true,
            showSupply:   f.showSupply   ?? true,
            allTFMode:    f.allTFMode    ?? false,   // show all TF zones on chart
            activeTFs:    f.activeTFs    ?? ['quarterly','monthly','weekly','daily','125min','75min'],
            minOverlap:   f.minOverlap   ?? 0,       // min # of TFs that zone must exist in
            showNearest:  f.showNearest  ?? true,
        };
    }

    updateFilters(newFilters) {
        Object.assign(this.filters, newFilters);
        this._computeNearestZones();
        this.draw();
    }

    /**
     * Set EMA crossover events to be drawn on chart.
     * @param {Array} crossovers  [{time: 'YYYY-MM-DD', type: 'golden'|'death'}, ...]
     */
    setCrossovers(crossovers) {
        this.crossovers = crossovers || [];
        this.draw();
    }

    // ─── Nearest Zone Logic ─────────────────────────────────────────────────
    _getCurrentPrice() {
        if (!this.zones || this.zones.length === 0) return null;
        // Use the midpoint of the last visible candle's range as proxy
        // Actually get from last candle's close
        try {
            const visRange = this.chart.timeScale().getVisibleLogicalRange();
            if (!visRange) return null;
        } catch (_) {}
        return null; // will be set externally via setCurrentPrice()
    }

    setCurrentPrice(price) {
        this.currentPrice = price;
        this._computeNearestZones();
    }

    _computeNearestZones() {
        if (!this.currentPrice) return;
        const price = this.currentPrice;

        const visibleZones = this._getVisibleZones();

        const demands = visibleZones
            .filter(z => z.zone_type === 'demand' && z.proximal_line <= price)
            .sort((a, b) => b.proximal_line - a.proximal_line); // closest below

        const supplies = visibleZones
            .filter(z => z.zone_type === 'supply' && z.proximal_line >= price)
            .sort((a, b) => a.proximal_line - b.proximal_line); // closest above

        this.nearestDemand = demands.slice(0, 2);  // D1, D2
        this.nearestSupply = supplies.slice(0, 2); // S1, S2
    }

    // ─── Zone Filtering ─────────────────────────────────────────────────────
    _getVisibleZones() {
        const f = this.filters;
        const price = this.currentPrice;   // may be null before first candle load

        return this.zones.filter(z => {
            // Zone type visibility
            if (z.zone_type === 'demand' && !f.showDemand) return false;
            if (z.zone_type === 'supply' && !f.showSupply) return false;

            // ── GTF Position Rule ────────────────────────────────────────
            // Demand zones MUST be below current price (proximal <= price)
            // Supply zones MUST be above current price (proximal >= price)
            if (price !== null && price !== undefined) {
                if (z.zone_type === 'demand' && z.proximal_line > price) return false;
                if (z.zone_type === 'supply' && z.proximal_line < price) return false;
            }
            // ─────────────────────────────────────────────────────────────

            // Timeframe filter
            if (f.allTFMode) {
                // Show all TFs but still respect the per-TF toggles
                if (!f.activeTFs.includes(z.timeframe)) return false;
            } else {
                // Only zones matching current chart TF AND in activeTFs
                if (z.timeframe !== this.currentTf) return false;
                if (!f.activeTFs.includes(z.timeframe)) return false;
            }

            // Fresh only
            if (f.freshOnly && !z.is_fresh) return false;

            return true;
        });
    }

    // ─── Drawing ────────────────────────────────────────────────────────────
    resizeAndDraw() {
        const chartElement = document.getElementById('chart-container');
        if (!chartElement) return;
        this.canvas.width  = chartElement.clientWidth;
        this.canvas.height = chartElement.clientHeight;
        this.draw();
    }

    draw() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        const visibleZones = this._getVisibleZones();

        // Compute overlap count per zone (how many TFs have that zone type near same price)
        // We use a simple grouping by zone_type × price_cluster
        const overlapCounts = this._computeOverlapCounts();

        visibleZones.forEach(zone => {
            if (this.filters.minOverlap > 0) {
                const key = zone.zone_type;
                const cnt = overlapCounts[key] || 0;
                if (cnt < this.filters.minOverlap) return;
            }
            this._drawZone(zone);
        });

        // Draw nearest zone indicators
        if (this.filters.showNearest && this.currentPrice) {
            this._drawNearestLabels();
        }

        // Draw Golden / Death crossover labels
        if (this.crossovers && this.crossovers.length > 0) {
            this._drawCrossovers();
        }
    }

    _computeOverlapCounts() {
        // Count how many timeframes have zones near each price level
        // Returns map of zone_type → count for zones that are visible
        const counts = { demand: 0, supply: 0 };
        const seenTFs = { demand: new Set(), supply: new Set() };

        this._getVisibleZones().forEach(z => {
            seenTFs[z.zone_type]?.add(z.timeframe);
        });

        counts.demand = seenTFs.demand.size;
        counts.supply = seenTFs.supply.size;
        return counts;
    }

    _drawZone(zone) {
        const ctx = this.ctx;

        const y1 = this.series.priceToCoordinate(zone.proximal_line);
        const y2 = this.series.priceToCoordinate(zone.distal_line);
        if (y1 === null || y2 === null) return;

        const topY    = Math.min(y1, y2);
        const bottomY = Math.max(y1, y2);
        const height  = Math.max(bottomY - topY, 2);

        // X coordinates
        const startDateStr = zone.formed_date || this.maxDate;
        let x1 = this.chart.timeScale().timeToCoordinate(startDateStr);
        if (x1 === null) x1 = 0;

        let x2 = this.chart.timeScale().timeToCoordinate(this.maxDate);
        if (x2 === null) x2 = this.canvas.width;
        else x2 += 120; // extend into future

        const width = x2 - x1;
        if (width <= 0) return;

        // Check if this zone is a "nearest" zone for highlight
        const isNearest = this._isNearestZone(zone);

        // Determine colors
        const { bgColor, borderColor, borderDash, alpha } = this._getZoneStyle(zone, isNearest);

        // Fill
        ctx.globalAlpha = alpha;
        ctx.fillStyle = bgColor;
        ctx.fillRect(x1, topY, width, height);
        ctx.globalAlpha = 1.0;

        // Border
        ctx.beginPath();
        ctx.setLineDash(borderDash);
        ctx.strokeStyle = borderColor;
        ctx.lineWidth = isNearest ? 2 : 1;
        ctx.rect(x1, topY, width, height);
        ctx.stroke();
        ctx.setLineDash([]);

        // Label
        this._drawZoneLabel(zone, x1, topY, borderColor, isNearest);
    }

    _getZoneStyle(zone, isNearest) {
        let bgColor, borderColor, borderDash = [], alpha = 1.0;

        if (zone.status === 'Broken' || (!zone.is_fresh && zone.status !== 'Fresh')) {
            if (zone.is_fresh === false && zone.status !== 'Broken') {
                // Tested zone — slightly faded
                borderDash = [];
                if (zone.zone_type === 'demand') {
                    bgColor     = 'rgba(16, 185, 129, 0.12)';
                    borderColor = 'rgba(16, 185, 129, 0.6)';
                } else {
                    bgColor     = 'rgba(239, 68, 68, 0.12)';
                    borderColor = 'rgba(239, 68, 68, 0.6)';
                }
                alpha = 0.85;
            } else {
                // Broken
                borderDash  = [5, 5];
                bgColor     = zone.zone_type === 'demand' ? 'rgba(16,185,129,0.05)' : 'rgba(239,68,68,0.05)';
                borderColor = zone.zone_type === 'demand' ? 'rgba(16,185,129,0.5)' : 'rgba(239,68,68,0.5)';
                alpha = 0.7;
            }
        } else {
            // Fresh zone
            if (zone.zone_type === 'demand') {
                bgColor     = isNearest ? 'rgba(16, 185, 129, 0.30)' : 'rgba(16, 185, 129, 0.18)';
                borderColor = 'rgba(16, 185, 129, 1)';
            } else {
                bgColor     = isNearest ? 'rgba(239, 68, 68, 0.30)' : 'rgba(239, 68, 68, 0.18)';
                borderColor = 'rgba(239, 68, 68, 1)';
            }
        }

        return { bgColor, borderColor, borderDash, alpha };
    }

    _drawZoneLabel(zone, x1, topY, color, isNearest) {
        const ctx = this.ctx;
        const labelX = Math.max(x1, 4) + 5;
        const labelY = topY + 12;

        // Nearest zone gets a special label (D1/D2/S1/S2)
        let label = `${zone.zone_type.toUpperCase()[0]} · ${zone.timeframe}`;
        if (isNearest) {
            const rank = this._getNearestRank(zone);
            label = `${rank} ${zone.timeframe} ${zone.is_fresh ? '✦' : ''}`;
        } else if (this.filters.allTFMode) {
            label = `${zone.zone_type[0].toUpperCase()} ${zone.timeframe}${zone.is_fresh ? ' ✦' : ''}`;
        }

        ctx.font = isNearest ? 'bold 11px Arial' : '10px Arial';
        
        if (zone.zone_type === 'demand') {
            ctx.lineWidth = 2;
            ctx.strokeStyle = '#000000';
            ctx.strokeText(label, labelX, labelY);
            ctx.fillStyle = '#ffffff';
            ctx.fillText(label, labelX, labelY);
        } else if (zone.zone_type === 'supply') {
            ctx.lineWidth = 2;
            ctx.strokeStyle = '#000000';
            ctx.strokeText(label, labelX, labelY);
            ctx.fillStyle = '#60a5fa'; // Blue
            ctx.fillText(label, labelX, labelY);
        } else {
            ctx.fillStyle = color;
            ctx.fillText(label, labelX, labelY);
        }

        // Price label on right edge
        const priceLabel = zone.proximal_line.toFixed(1);
        const pw = ctx.measureText(priceLabel).width;
        ctx.font = '10px Arial';
        ctx.fillStyle = color;
        ctx.fillText(priceLabel, this.canvas.width - pw - 64, labelY);
    }

    _isNearestZone(zone) {
        if (!this.nearestDemand || !this.nearestSupply) return false;
        return [...this.nearestDemand, ...this.nearestSupply].some(nz => nz.id === zone.id);
    }

    _getNearestRank(zone) {
        if (zone.zone_type === 'demand') {
            const idx = (this.nearestDemand || []).findIndex(nz => nz.id === zone.id);
            return idx === 0 ? 'D1' : 'D2';
        } else {
            const idx = (this.nearestSupply || []).findIndex(nz => nz.id === zone.id);
            return idx === 0 ? 'S1' : 'S2';
        }
    }

    _drawNearestLabels() {
        const ctx = this.ctx;
        const all = [
            ...(this.nearestDemand || []).map((z, i) => ({ z, rank: `D${i + 1}` })),
            ...(this.nearestSupply || []).map((z, i) => ({ z, rank: `S${i + 1}` })),
        ];

        all.forEach(({ z, rank }) => {
            const y = this.series.priceToCoordinate(z.proximal_line);
            if (y === null) return;

            const color = z.zone_type === 'demand' ? '#10b981' : '#ef4444';
            const label = `${rank}: ₹${z.proximal_line.toFixed(1)}`;

            // Pin badge on right edge
            const badgeW = ctx.measureText(label).width + 12;
            const badgeX = this.canvas.width - badgeW - 60;

            ctx.fillStyle = color;
            ctx.globalAlpha = 0.85;
            ctx.beginPath();
            ctx.roundRect?.(badgeX, y - 9, badgeW, 18, 4) || ctx.rect(badgeX, y - 9, badgeW, 18);
            ctx.fill();
            ctx.globalAlpha = 1.0;

            ctx.fillStyle = '#ffffff';
            ctx.font = 'bold 10px Arial';
            ctx.fillText(label, badgeX + 6, y + 4);
        });
    }

    // ─── Crossover Labels ────────────────────────────────────────────────────
    _drawCrossovers() {
        const ctx = this.ctx;
        const canvasH = this.canvas.height;

        // Track x-positions used to avoid label overlap
        const usedX = [];

        this.crossovers.forEach(({ time, type }) => {
            const x = this.chart.timeScale().timeToCoordinate(time);
            if (x === null || x < 0 || x > this.canvas.width) return;

            const isGolden = type === 'golden';
            const label    = isGolden ? '☀ Golden Cross' : '✝ Death Cross';
            const color    = isGolden ? '#f59e0b' : '#ef4444';
            const glowClr  = isGolden ? 'rgba(245,158,11,0.35)' : 'rgba(239,68,68,0.35)';
            const borderClr= isGolden ? 'rgba(245,158,11,0.85)' : 'rgba(239,68,68,0.85)';
            const bgClr    = isGolden ? 'rgba(245,158,11,0.13)' : 'rgba(239,68,68,0.13)';

            ctx.font = 'bold 10px Inter, Arial';
            const textW = ctx.measureText(label).width;
            const padX = 8, padY = 5;
            const badgeW = textW + padX * 2;
            const badgeH = 18;

            // Place badge: try to centre on x, shift if off-screen
            let bx = x - badgeW / 2;
            bx = Math.max(4, Math.min(this.canvas.width - badgeW - 4, bx));

            // Avoid horizontal collision with previous labels
            let by = canvasH * 0.18; // default vertical position (top area)
            for (const ux of usedX) {
                if (Math.abs(ux.x - bx) < badgeW + 6) {
                    by = ux.y + badgeH + 4; // stack below
                }
            }
            usedX.push({ x: bx, y: by });

            // Vertical dashed guide line at crossing point
            ctx.save();
            ctx.setLineDash([4, 4]);
            ctx.strokeStyle = color;
            ctx.lineWidth = 1;
            ctx.globalAlpha = 0.45;
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, canvasH);
            ctx.stroke();
            ctx.setLineDash([]);
            ctx.globalAlpha = 1.0;
            ctx.restore();

            // Glow shadow
            ctx.save();
            ctx.shadowColor = glowClr;
            ctx.shadowBlur  = 8;

            // Badge background
            ctx.fillStyle = bgClr;
            ctx.globalAlpha = 0.95;
            if (ctx.roundRect) {
                ctx.beginPath();
                ctx.roundRect(bx, by, badgeW, badgeH, 5);
                ctx.fill();
            } else {
                ctx.fillRect(bx, by, badgeW, badgeH);
            }

            // Badge border
            ctx.strokeStyle = borderClr;
            ctx.lineWidth = 1.2;
            ctx.globalAlpha = 0.9;
            if (ctx.roundRect) {
                ctx.beginPath();
                ctx.roundRect(bx, by, badgeW, badgeH, 5);
                ctx.stroke();
            } else {
                ctx.strokeRect(bx, by, badgeW, badgeH);
            }

            ctx.shadowBlur = 0;
            ctx.restore();

            // Label text
            ctx.globalAlpha = 1.0;
            ctx.fillStyle = color;
            ctx.font = 'bold 10px Inter, Arial';
            ctx.fillText(label, bx + padX, by + badgeH - padY);

            // Small triangle pointer at bottom of badge pointing down toward crossing line
            const tipX = x;
            const tipY = by + badgeH + 5;
            ctx.beginPath();
            ctx.moveTo(tipX - 4, by + badgeH);
            ctx.lineTo(tipX + 4, by + badgeH);
            ctx.lineTo(tipX, tipY);
            ctx.closePath();
            ctx.fillStyle = borderClr;
            ctx.globalAlpha = 0.8;
            ctx.fill();
            ctx.globalAlpha = 1.0;
        });
    }
}
