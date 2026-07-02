# stocks/live_feed.py
"""
Live Price Feed — Fyers Data WebSocket (Direct Integration)
============================================================
Connects directly to the Fyers WebSocket data streaming server
(`wss://socket.fyers.in/hsm/v1-5/prod`) and subscribes to real-time
tick data for all watchlist symbols.

Every tick received from Fyers is immediately:
    1. Normalised into a standard tick dict
    2. Persisted to DB (MarketTick model — upsert)
    3. Broadcast to Django Channels layer
    4. → MarketDataConsumer.market_tick()
    5. → Browser WebSocket onmessage → live chart & price updates

Flow:
    Fyers Data WebSocket  ──tick──►  on_message()
        ──►  _process_tick()
            ──►  save_market_tick()          (DB)
            ──►  broadcast_tick_to_channel_layer()   (Channels)
                ──►  Browser WebSocket (live!)

Usage:
    Called automatically from StocksConfig.ready() via start_live_feed().
"""

import logging
import threading
import time
from datetime import datetime

logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────
# Default watchlist (used before DB has any MarketTick rows)
DEFAULT_WATCHLIST = [
    'RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK',
    'WIPRO', 'BAJFINANCE', 'SBIN', 'AXISBANK', 'HINDUNILVR',
]

# Index symbols need different Fyers format
INDEX_MAP = {
    'NIFTY50': 'NSE:NIFTY50-INDEX',
    'NIFTY':   'NSE:NIFTY50-INDEX',
    'BANKNIFTY': 'NSE:NIFTYBANK-INDEX',
    'SENSEX':  'BSE:SENSEX-INDEX',
    'FINNIFTY': 'NSE:FINNIFTY-INDEX',
}

# Module-level handle so we can reconnect on demand
_data_socket = None
_socket_lock = threading.Lock()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _to_fyers_symbol(symbol: str) -> str:
    """Convert clean symbol → Fyers format e.g. 'AXISBANK' → 'NSE:AXISBANK-EQ'."""
    s = symbol.upper().strip()
    return INDEX_MAP.get(s, f'NSE:{s}-EQ')


def _get_subscribe_symbols() -> list[str]:
    """
    Return the list of Fyers-format symbols to subscribe to.
    Merges DB symbols (those with stored ticks) + DEFAULT_WATCHLIST.
    """
    try:
        from .models import MarketTick
        db_syms = list(MarketTick.objects.values_list('symbol', flat=True))
        combined = list(dict.fromkeys(db_syms + DEFAULT_WATCHLIST))
        return [_to_fyers_symbol(s) for s in combined[:50]]   # Fyers cap
    except Exception:
        return [_to_fyers_symbol(s) for s in DEFAULT_WATCHLIST]


def _clean_symbol(raw: str) -> str:
    """
    'NSE:AXISBANK-EQ'  → 'AXISBANK'
    'NSE:NIFTY50-INDEX' → 'NIFTY50'
    'BSE:SENSEX-INDEX'  → 'SENSEX'
    """
    s = raw
    if ':' in s:
        s = s.split(':', 1)[1]
    for suf in ('-EQ', '-INDEX', '-BE', '-A', '-B', '-F&O'):
        s = s.replace(suf, '')
    # Normalize known index names
    if 'NIFTY50' in s or s == 'NIFTY50':
        return 'NIFTY50'
    if 'NIFTY BANK' in s:
        return 'BANKNIFTY'
    return s.strip().upper()


# ─── Tick Processor ───────────────────────────────────────────────────────────

def _process_tick(message: dict | list) -> None:
    """
    Called by on_message for every tick from Fyers Data WebSocket.
    Parses the tick, saves to DB, broadcasts to Channels layer.

    Fyers SymbolUpdate lite-mode message example:
        {'symbol': 'NSE:AXISBANK-EQ', 'ltp': 1367.9, 'chp': -0.06, 'ch': -0.8,
         'open_price': 1374.0, 'high_price': 1375.5, 'low_price': 1363.9,
         'prev_close_price': 1368.7, 'volume': 580963, 'ask': 1367.9, 'bid': 1367.3}

    Full-mode adds: 'fyToken', 'tt', 'atp', 'spread', 'description', etc.

    NOTE: We guard against RuntimeError during Django StatReloader shutdown
    (executor pool is torn down while daemon threads still run).
    """
    from .fyers_service import broadcast_tick_to_channel_layer, save_market_tick

    try:
        # Fyers sometimes sends a list of ticks in one message
        ticks = message if isinstance(message, list) else [message]

        now_ts = datetime.utcnow().isoformat() + 'Z'

        for raw in ticks:
            if not isinstance(raw, dict):
                continue

            raw_sym = raw.get('symbol', '')
            ltp = float(raw.get('ltp', 0) or 0)

            if not raw_sym or ltp <= 0:
                continue

            symbol = _clean_symbol(raw_sym)

            prev_close = raw.get('prev_close_price') or raw.get('prev_close')
            prev_close = float(prev_close) if prev_close else None

            chg = raw.get('ch')
            chg_pct = raw.get('chp')
            change = round(float(chg), 4) if chg is not None else None
            change_pct = round(float(chg_pct), 4) if chg_pct is not None else None

            tick = {
                'symbol':     symbol,
                'raw_symbol': raw_sym,
                'ltp':        ltp,
                'open':       float(raw['open_price'])  if raw.get('open_price')  else None,
                'high':       float(raw['high_price'])  if raw.get('high_price')  else None,
                'low':        float(raw['low_price'])   if raw.get('low_price')   else None,
                'prev_close': prev_close,
                'volume':     int(raw.get('volume', 0) or 0),
                'change':     change,
                'change_pct': change_pct,
                'side':       None,
                'status':     'LIVE',
                'source':     'fyers_ws',
                'event_type': 'data_socket',
                'timestamp':  now_ts,
            }

            # Persist to DB
            try:
                save_market_tick(tick, raw)
            except RuntimeError:
                return   # interpreter shutting down — stop processing

            # Push to browser via Channels layer
            try:
                broadcast_tick_to_channel_layer(tick)
            except RuntimeError:
                return   # interpreter shutting down — stop processing

            logger.debug("WS tick: %s @ %.2f (chg=%.2f%%)", symbol, ltp, change_pct or 0)

    except Exception as exc:
        logger.exception("_process_tick error: %s", exc)


# ─── WebSocket Callbacks ──────────────────────────────────────────────────────

def _on_message(message):
    """Fyers Data WebSocket on_message callback."""
    try:
        _process_tick(message)
    except Exception as exc:
        logger.exception("on_message error: %s", exc)


def _on_connect(message=None):
    """Called when Fyers Data WebSocket connects successfully."""
    logger.info("✅ Fyers Data WebSocket connected: %s", message)
    # Subscribe to symbols right after connecting
    _subscribe_symbols()


def _on_error(message=None):
    """Called on Fyers Data WebSocket error."""
    logger.warning("⚠️  Fyers Data WebSocket error: %s", message)


def _on_close(message=None):
    """Called when Fyers Data WebSocket closes."""
    logger.warning("🔌 Fyers Data WebSocket closed: %s", message)


# ─── Subscription Management ─────────────────────────────────────────────────

def _subscribe_symbols():
    """Subscribe to all watchlist symbols on the active socket."""
    global _data_socket
    if _data_socket is None:
        return
    try:
        symbols = _get_subscribe_symbols()
        logger.info("Subscribing to %d symbols: %s…", len(symbols), symbols[:5])
        _data_socket.subscribe(
            symbols=symbols,
            data_type='SymbolUpdate',   # LTP + OHLCV full mode
        )
        logger.info("✅ Subscribed to %d symbols", len(symbols))
    except Exception as exc:
        logger.exception("_subscribe_symbols error: %s", exc)


def subscribe_symbol(symbol: str) -> None:
    """
    Dynamically add a symbol to the active WebSocket subscription.
    Call this when a new symbol is added to the watchlist.
    """
    global _data_socket
    if _data_socket is None or not _data_socket.is_connected():
        return
    try:
        fyers_sym = _to_fyers_symbol(symbol.upper().strip())
        _data_socket.subscribe(symbols=[fyers_sym], data_type='SymbolUpdate')
        logger.info("Dynamically subscribed: %s", fyers_sym)
    except Exception as exc:
        logger.exception("subscribe_symbol error: %s", exc)


# ─── Main Entry Point ─────────────────────────────────────────────────────────

def _live_feed_loop():
    """
    Background thread:
      1. Waits for Django to fully start
      2. Connects FyersDataSocket
      3. Subscribes to watchlist symbols
      4. Loops — the SDK handles reconnects internally (reconnect=True)
      5. Re-creates socket if the SDK gives up reconnecting
    """
    global _data_socket

    # Give Django/Daphne time to finish starting
    time.sleep(4)
    logger.info("🚀 Fyers Data WebSocket feed thread starting…")

    while True:
        try:
            from .fyers_service import fyers_service
            from fyers_apiv3.FyersWebsocket import data_ws

            if not fyers_service.is_active:
                logger.warning(
                    "Fyers service not active (no valid token). "
                    "Run: python test_fyer.py  then restart the server."
                )
                time.sleep(30)
                continue

            # Build the full access token in format expected by Data WebSocket SDK:
            # "<client_id>:<raw_jwt>"
            access_token = f"{fyers_service.client_id}:{fyers_service.access_token}"

            with _socket_lock:
                logger.info("Creating FyersDataSocket…")
                # Reset the SDK singleton so a fresh instance is created
                # (important after Django StatReloader restarts the process)
                data_ws.FyersDataSocket._instance = None
                _data_socket = data_ws.FyersDataSocket(
                    access_token=access_token,
                    write_to_file=True,        # True → ws_thread runs as daemon thread
                    litemode=False,            # full mode: LTP + OHLCV
                    reconnect=True,            # auto-reconnect on drop
                    reconnect_retry=10,
                    on_message=_on_message,
                    on_connect=_on_connect,
                    on_error=_on_error,
                    on_close=_on_close,
                )

            # Connect (non-blocking — SDK runs in daemon threads with write_to_file=True)
            _data_socket.connect()

            # Give the WebSocket a moment to handshake and fire on_connect → subscribe
            time.sleep(3)
            logger.info("Fyers Data WebSocket connecting (SDK handles reconnects)…")

            # Block this thread keeping it alive — the SDK runs in daemon threads.
            # We just sleep and check if the socket is still alive.
            while True:
                time.sleep(60)
                # If the SDK exhausted all reconnect attempts, it gives up.
                # We detect this and restart the whole loop.
                if _data_socket and not _data_socket.is_connected():
                    logger.warning("Data socket disconnected — restarting in 30s…")
                    break

        except Exception as exc:
            logger.exception("Live feed loop error: %s | Retrying in 30s…", exc)
            time.sleep(30)


def start_live_feed() -> threading.Thread:
    """
    Launch the Fyers Data WebSocket live feed in a daemon thread.
    Called from StocksConfig.ready() — safe to call once per process.
    """
    t = threading.Thread(target=_live_feed_loop, name='FyersDataWS', daemon=True)
    t.start()
    logger.info("Fyers Data WebSocket feed thread launched.")
    return t
