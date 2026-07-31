// stocks/static/js/chart/api.js

/**
 * Resolves an API path with the optional language prefix (e.g., /en/).
 */
function getApiPath(path) {
    const match = window.location.pathname.match(/^\/([a-z]{2})\//);
    return match ? `/${match[1]}${path}` : path;
}

/**
 * Fetches candle (OHLC) data from the backend.
 * Returns array of {time, open, high, low, close}.
 *
 * @param {string} symbol
 * @param {string} tf  — 'quarterly' | 'monthly' | 'weekly' | 'daily' | '125min' | '75min'
 */
async function fetchCandles(symbol, tf = 'daily') {
    try {
        const url = getApiPath(`/api/demand-supply/candles/${symbol}/?tf=${tf}`);
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (e) {
        console.error('Error fetching candles:', e);
        return [];
    }
}

/**
 * Fetches all demand/supply zones for a symbol (all timeframes).
 * Returns array of zone objects.
 *
 * @param {string} symbol
 */
async function fetchZones(symbol) {
    try {
        const url = getApiPath(`/api/demand-supply/zones/${symbol}/`);
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (e) {
        console.error('Error fetching zones:', e);
        return [];
    }
}

/**
 * Fetches technical indicators (EMA 20, EMA 50, RSI 14, RSI signal).
 * Returns { ema20, ema50, rsi, rsi_signal } — each an array of {time, value}.
 *
 * @param {string} symbol
 * @param {string} tf
 */
async function fetchIndicators(symbol, tf = 'daily') {
    try {
        const url = getApiPath(`/api/demand-supply/indicators/${symbol}/?tf=${tf}`);
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (e) {
        console.error('Error fetching indicators:', e);
        return { ema20: [], ema50: [], rsi: [], rsi_signal: [] };
    }
}
