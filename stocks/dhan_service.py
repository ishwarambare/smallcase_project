# stocks/dhan_service.py
"""
DhanHQ API v2 Integration Service
====================================
Uses the DhanHQ Python SDK v2 (dhanhq==2.2.0).

DhanHQ v2 uses a DhanContext object instead of passing client_id + token directly.

Credentials are read from .env:
    DHAN_CLIENT_ID=2606246016
    DHAN_ACCESS_TOKEN=<your JWT token>

DhanHQ docs: https://dhanhq.co/docs/v2/

Usage:
    from stocks.dhan_service import dhan_service

    # Check if configured
    if dhan_service.is_active:
        quote = dhan_service.get_quote_by_symbol('RELIANCE')
        candles = dhan_service.get_intraday_candles('2885')
"""

import logging
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# DhanHQ Security ID mapping for popular NSE stocks
# security_id is DhanHQ's internal instrument identifier (not NSE ticker)
# Full security list: https://images.dhan.co/api-data/api-scrip-master.csv
# ─────────────────────────────────────────────────────────────────────────────
DHAN_SECURITY_MAP = {
    'RELIANCE':   {'security_id': '2885',  'exchange': 'NSE_EQ'},
    'TCS':        {'security_id': '11536', 'exchange': 'NSE_EQ'},
    'INFY':       {'security_id': '1594',  'exchange': 'NSE_EQ'},
    'HDFCBANK':   {'security_id': '1333',  'exchange': 'NSE_EQ'},
    'ICICIBANK':  {'security_id': '4963',  'exchange': 'NSE_EQ'},
    'WIPRO':      {'security_id': '3787',  'exchange': 'NSE_EQ'},
    'BAJFINANCE': {'security_id': '317',   'exchange': 'NSE_EQ'},
    'SBIN':       {'security_id': '3045',  'exchange': 'NSE_EQ'},
    'AXISBANK':   {'security_id': '5900',  'exchange': 'NSE_EQ'},
    'HINDUNILVR': {'security_id': '1394',  'exchange': 'NSE_EQ'},
    'ADANIENT':   {'security_id': '25',    'exchange': 'NSE_EQ'},
    'MARUTI':     {'security_id': '10999', 'exchange': 'NSE_EQ'},
    'TATAMOTORS': {'security_id': '3456',  'exchange': 'NSE_EQ'},
    'TATASTEEL':  {'security_id': '3499',  'exchange': 'NSE_EQ'},
    'HCLTECH':    {'security_id': '1363',  'exchange': 'NSE_EQ'},
    'SUNPHARMA':  {'security_id': '3351',  'exchange': 'NSE_EQ'},
    'LT':         {'security_id': '11483', 'exchange': 'NSE_EQ'},
    'NIFTY':      {'security_id': '13',    'exchange': 'IDX_I'},
    'BANKNIFTY':  {'security_id': '25',    'exchange': 'IDX_I'},
    'SENSEX':     {'security_id': '51',    'exchange': 'IDX_I'},
}


class DhanService:
    """
    DhanHQ API v2 client wrapper.

    DhanHQ v2 SDK structure:
        DhanContext(client_id, access_token)  → authentication context
        dhanhq(ctx)                           → main trading client
        Funds(ctx)                            → fund/margin queries
        HistoricalData(ctx)                   → OHLCV data
        MarketFeed(ctx, instruments, ...)     → live WebSocket feed

    Activates only when DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN are set in .env.
    All methods return None / [] gracefully when not configured.
    """

    def __init__(self):
        self.client_id    = getattr(settings, 'DHAN_CLIENT_ID', '').strip()
        self.access_token = getattr(settings, 'DHAN_ACCESS_TOKEN', '').strip()
        self._ctx         = None
        self._client      = None
        self._configured  = bool(self.client_id and self.access_token)

        if self._configured:
            self._init_client()
        else:
            logger.info(
                "DhanService: DHAN_CLIENT_ID / DHAN_ACCESS_TOKEN not set in .env. "
                "Service is in stub mode."
            )

    def _init_client(self):
        """Initialize DhanContext and dhanhq client (DhanHQ v2 pattern)."""
        try:
            from dhanhq import DhanContext, dhanhq as DhanHQ
            # DhanContext holds credentials; passed to every service class
            self._ctx    = DhanContext(self.client_id, self.access_token)
            self._client = DhanHQ(self._ctx)
            logger.info(
                "DhanHQ v2 client initialized. client_id=%s", self.client_id
            )
        except ImportError:
            logger.error("dhanhq package not installed. Run: pip install dhanhq")
            self._configured = False
        except Exception as exc:
            logger.exception("Failed to initialize DhanHQ client: %s", exc)
            self._configured = False

    @property
    def is_active(self) -> bool:
        """Returns True if DhanHQ client is ready."""
        return self._configured and self._client is not None

    # ─────────────────────────────────────────────────────────────────────────
    # Fund / Account
    # ─────────────────────────────────────────────────────────────────────────

    def get_fund_limits(self) -> Optional[dict]:
        """Fetch available margin / fund limits."""
        if not self.is_active:
            return None
        try:
            from dhanhq import Funds
            f = Funds(self._ctx)
            result = f.get_fund_limits()
            if result and result.get('status') == 'success':
                return result.get('data', {})
            logger.warning("DhanHQ fund_limits: %s", result)
            return None
        except Exception as exc:
            logger.exception("DhanHQ get_fund_limits error: %s", exc)
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # Market Quotes (REST - snapshot)
    # ─────────────────────────────────────────────────────────────────────────

    def get_quote(self, security_id: str, exchange: str = 'NSE_EQ') -> Optional[dict]:
        """
        Get OHLCV + LTP snapshot for one instrument.
        Uses DhanHQ quote_data endpoint.

        Returns dict with keys: ltp, open, high, low, close, volume
        """
        if not self.is_active:
            return None
        try:
            result = self._client.ohlc_data(
                securities={exchange: [int(security_id)]}
            )
            if result and result.get('status') == 'success':
                data = result.get('data', {})
                # ohlc_data returns {exchange: [{...}]}
                rows = data.get(exchange, [])
                if rows:
                    row = rows[0]
                    return {
                        'security_id': str(security_id),
                        'ltp':   float(row.get('last_price', 0)),
                        'open':  float(row.get('open', 0)),
                        'high':  float(row.get('high', 0)),
                        'low':   float(row.get('low', 0)),
                        'close': float(row.get('close', 0)),
                    }
            logger.debug("DhanHQ ohlc_data response: %s", result)
        except Exception as exc:
            logger.exception("DhanHQ get_quote error for %s: %s", security_id, exc)
        return None

    def get_quote_by_symbol(self, symbol: str) -> Optional[dict]:
        """
        Get quote by NSE symbol name (e.g. 'RELIANCE').
        Uses DHAN_SECURITY_MAP for the security_id lookup.
        """
        mapping = DHAN_SECURITY_MAP.get(symbol.upper())
        if not mapping:
            logger.warning("DhanHQ: no security_id for symbol '%s'", symbol)
            return None
        return self.get_quote(mapping['security_id'], mapping['exchange'])

    def get_ltp(self, security_id: str, exchange: str = 'NSE_EQ') -> Optional[float]:
        """Get only the LTP (Last Traded Price) for a security."""
        quote = self.get_quote(security_id, exchange)
        return quote['ltp'] if quote else None

    def get_ltp_by_symbol(self, symbol: str) -> Optional[float]:
        """Get LTP by NSE symbol."""
        quote = self.get_quote_by_symbol(symbol)
        return quote['ltp'] if quote else None

    # ─────────────────────────────────────────────────────────────────────────
    # Historical / Intraday Data (for chart seeding)
    # ─────────────────────────────────────────────────────────────────────────

    def get_intraday_candles(
        self,
        security_id: str,
        exchange: str = 'NSE_EQ',
        interval: int = 1,
    ) -> list[dict]:
        """
        Fetch intraday OHLCV candles using DhanHQ intraday_minute_data.

        Args:
            security_id: DhanHQ security ID (e.g. '2885' for RELIANCE)
            exchange: Exchange segment ('NSE_EQ', 'BSE_EQ', 'IDX_I', etc.)
            interval: Candle interval in minutes (1, 5, 15, 25, 60)

        Returns:
            List of candle dicts compatible with lightweight-charts:
            [{'time': <unix_ts>, 'open': float, 'high': float, 'low': float, 'close': float, 'volume': int}]
        """
        if not self.is_active:
            return []
        try:
            result = self._client.intraday_minute_data(
                security_id=security_id,
                exchange_segment=exchange,
                instrument_type='EQUITY'
            )
            if result and result.get('status') == 'success':
                raw_candles = result.get('data', [])
                candles = []
                for c in raw_candles:
                    # DhanHQ v2 candle keys: open, high, low, close, volume, timestamp
                    ts_raw = c.get('timestamp', c.get('start_Time', ''))
                    # Convert ISO string or epoch to Unix timestamp
                    unix_ts = _parse_timestamp(ts_raw)
                    if unix_ts is None:
                        continue
                    candles.append({
                        'time':   unix_ts,
                        'open':   float(c.get('open', 0)),
                        'high':   float(c.get('high', 0)),
                        'low':    float(c.get('low', 0)),
                        'close':  float(c.get('close', 0)),
                        'volume': int(c.get('volume', 0)),
                    })
                logger.info(
                    "DhanHQ intraday_candles: %d candles for security_id=%s",
                    len(candles), security_id
                )
                return candles

            logger.debug("DhanHQ intraday_candles response: %s", str(result)[:200])
        except Exception as exc:
            logger.exception(
                "DhanHQ get_intraday_candles error for security_id=%s: %s",
                security_id, exc
            )
        return []

    def get_intraday_candles_by_symbol(self, symbol: str, interval: int = 1) -> list[dict]:
        """Get intraday candles by NSE symbol."""
        mapping = DHAN_SECURITY_MAP.get(symbol.upper())
        if not mapping:
            logger.warning("DhanHQ: no security_id for symbol '%s'", symbol)
            return []
        return self.get_intraday_candles(mapping['security_id'], mapping['exchange'], interval)

    def get_historical_daily(
        self,
        security_id: str,
        exchange: str = 'NSE_EQ',
        from_date: str = '',
        to_date: str = '',
    ) -> list[dict]:
        """
        Fetch daily OHLCV candles (EOD data) for a date range.

        Args:
            security_id: DhanHQ security ID
            exchange: Exchange segment
            from_date: 'YYYY-MM-DD'
            to_date:   'YYYY-MM-DD'

        Returns:
            List of candle dicts compatible with lightweight-charts.
        """
        if not self.is_active:
            return []
        try:
            from datetime import datetime, timedelta
            if not from_date:
                from_date = (datetime.today() - timedelta(days=90)).strftime('%Y-%m-%d')
            if not to_date:
                to_date = datetime.today().strftime('%Y-%m-%d')

            result = self._client.historical_daily_data(
                security_id=security_id,
                exchange_segment=exchange,
                instrument_type='EQUITY',
                expiry_code=0,
                from_date=from_date,
                to_date=to_date,
            )
            if result and result.get('status') == 'success':
                raw = result.get('data', [])
                candles = []
                for c in raw:
                    ts_raw = c.get('timestamp', c.get('start_Time', ''))
                    unix_ts = _parse_timestamp(ts_raw)
                    if unix_ts is None:
                        continue
                    candles.append({
                        'time':   unix_ts,
                        'open':   float(c.get('open', 0)),
                        'high':   float(c.get('high', 0)),
                        'low':    float(c.get('low', 0)),
                        'close':  float(c.get('close', 0)),
                        'volume': int(c.get('volume', 0)),
                    })
                return candles

            logger.debug("DhanHQ historical_daily response: %s", str(result)[:200])
        except Exception as exc:
            logger.exception(
                "DhanHQ get_historical_daily error for %s: %s", security_id, exc
            )
        return []

    # ─────────────────────────────────────────────────────────────────────────
    # Positions & Holdings
    # ─────────────────────────────────────────────────────────────────────────

    def get_positions(self) -> list[dict]:
        """Get all open intraday positions."""
        if not self.is_active:
            return []
        try:
            result = self._client.get_positions()
            if result and result.get('status') == 'success':
                return result.get('data', [])
        except Exception as exc:
            logger.exception("DhanHQ get_positions error: %s", exc)
        return []

    def get_holdings(self) -> list[dict]:
        """Get all long-term holdings (DELIVERY / CNC)."""
        if not self.is_active:
            return []
        try:
            result = self._client.get_holdings()
            if result and result.get('status') == 'success':
                return result.get('data', [])
        except Exception as exc:
            logger.exception("DhanHQ get_holdings error: %s", exc)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Helper: parse various timestamp formats → Unix timestamp (int)
# ─────────────────────────────────────────────────────────────────────────────

def _parse_timestamp(ts) -> Optional[int]:
    """Convert DhanHQ timestamp (ISO string or epoch int) to Unix seconds."""
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        return int(ts)
    if isinstance(ts, str):
        ts = ts.strip()
        if ts.isdigit():
            return int(ts)
        # Try ISO 8601
        from datetime import datetime
        for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                dt = datetime.strptime(ts[:19], fmt)
                import calendar
                return int(calendar.timegm(dt.timetuple()))
            except ValueError:
                continue
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Singleton instance — import this in views/services
# ─────────────────────────────────────────────────────────────────────────────
dhan_service = DhanService()
