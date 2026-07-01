# stocks/fyers_service.py
"""
Fyers API v3 Integration Service
=================================
Handles incoming Fyers postback (webhook) data and pushes ticks
to the Django Channels layer for real-time WebSocket broadcasting.

Fyers postback docs:
  https://myapi.fyers.in/docsv3#tag/Postback-(Webhooks)

Webhook flow:
  Fyers API → POST /api/webhook/fyers/ → parse → Channel Layer → Browser WebSocket
"""

import json
import hashlib
import hmac
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.conf import settings
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Fyers Postback Payload Reference
# ─────────────────────────────────────────────────────────────────────────────
# Order Update example payload from Fyers postback:
# {
#   "symbol": "NSE:RELIANCE-EQ",
#   "id": "12345678",
#   "exchOrdId": "1100000020037743",
#   "side": 1,         # 1=Buy, -1=Sell
#   "type": 2,         # 1=Limit, 2=Market, 3=SL, 4=SL-M
#   "productType": "INTRADAY",
#   "status": 2,       # 1=Cancelled, 2=Traded/Filled, 3=...
#   "qty": 1,
#   "filledQty": 1,
#   "limitPrice": 0.0,
#   "stopPrice": 0.0,
#   "tradedPrice": 2510.5,
#   "ltp": 2510.5,
#   "message": "TRADED",
#   "offlineOrder": "false"
# }
# ─────────────────────────────────────────────────────────────────────────────


def verify_fyers_signature(request_body: bytes, received_signature: str) -> bool:
    """
    Verify the HMAC-SHA256 signature from Fyers postback headers.
    Returns True if signature is valid or if no webhook secret is configured.

    Args:
        request_body: Raw bytes of the request body
        received_signature: Value from 'X-Fyers-Signature' header (if Fyers adds it)

    Returns:
        bool: True if valid (or signature checking is disabled)
    """
    secret = getattr(settings, 'FYERS_WEBHOOK_SECRET', '').strip()
    if not secret:
        # No secret configured — skip validation (development mode)
        return True

    if not received_signature:
        logger.warning("Fyers postback received without signature header")
        return False

    expected = hmac.new(
        secret.encode('utf-8'),
        request_body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, received_signature)


def normalize_fyers_symbol(raw_symbol: str) -> str:
    """
    Normalize Fyers symbol format to a clean string.
    Examples:
        'NSE:RELIANCE-EQ'  → 'RELIANCE'
        'BSE:TCS-A'        → 'TCS'
        'NSE:NIFTY50-INDEX'→ 'NIFTY50'
    """
    if ':' in raw_symbol:
        raw_symbol = raw_symbol.split(':', 1)[1]
    # Remove common suffixes
    for suffix in ['-EQ', '-BE', '-A', '-B', '-INDEX', '-F&O']:
        raw_symbol = raw_symbol.replace(suffix, '')
    return raw_symbol.strip().upper()


def _safe_decimal(value, default=None):
    """Safely convert a value to Decimal, returning default on failure."""
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default


def parse_fyers_postback(payload: dict) -> dict | None:
    """
    Parse a Fyers postback payload into a normalized tick dict.

    Fyers sends order/position updates, not raw tick data via postback.
    We extract the traded price / LTP as our real-time price signal.

    Returns:
        Normalized tick dict or None if payload cannot be parsed.

    Tick dict schema:
        {
            'symbol':     str,           # Clean symbol e.g. 'RELIANCE'
            'raw_symbol': str,           # Original e.g. 'NSE:RELIANCE-EQ'
            'ltp':        float,
            'open':       float | None,
            'high':       float | None,
            'low':        float | None,
            'prev_close': float | None,
            'volume':     int,
            'change':     float | None,
            'change_pct': float | None,
            'side':       int | None,    # 1=Buy, -1=Sell
            'status':     str,           # 'TRADED', 'CANCELLED', etc.
            'source':     'fyers',
            'event_type': str,           # 'order_update', 'position_update', etc.
            'timestamp':  str,           # ISO format
        }
    """
    try:
        raw_symbol = payload.get('symbol', '')
        if not raw_symbol:
            logger.warning("Fyers postback missing symbol field: %s", payload)
            return None

        symbol = normalize_fyers_symbol(raw_symbol)

        # LTP / traded price — prefer tradedPrice, fall back to ltp
        ltp_raw = payload.get('tradedPrice') or payload.get('ltp') or payload.get('price')
        ltp = _safe_decimal(ltp_raw)
        if ltp is None or ltp <= 0:
            logger.debug("Fyers postback: no valid LTP for %s, skipping", symbol)
            return None

        ltp_float = float(ltp)

        # Optional OHLCV fields (present in some Fyers response types)
        open_p = _safe_decimal(payload.get('openPrice') or payload.get('open'))
        high_p = _safe_decimal(payload.get('highPrice') or payload.get('high'))
        low_p = _safe_decimal(payload.get('lowPrice') or payload.get('low'))
        prev_close = _safe_decimal(payload.get('prevClose') or payload.get('prevClosePrice'))
        volume = int(payload.get('volume') or payload.get('filledQty') or 0)

        # Compute change / change_pct if we have prev_close
        change = None
        change_pct = None
        if prev_close and prev_close > 0:
            change = ltp_float - float(prev_close)
            change_pct = (change / float(prev_close)) * 100

        # Event classification
        status = str(payload.get('message', payload.get('status', 'UNKNOWN'))).upper()
        side = payload.get('side')  # 1=Buy, -1=Sell

        return {
            'symbol': symbol,
            'raw_symbol': raw_symbol,
            'ltp': ltp_float,
            'open': float(open_p) if open_p else None,
            'high': float(high_p) if high_p else None,
            'low': float(low_p) if low_p else None,
            'prev_close': float(prev_close) if prev_close else None,
            'volume': volume,
            'change': round(change, 4) if change is not None else None,
            'change_pct': round(change_pct, 4) if change_pct is not None else None,
            'side': side,
            'status': status,
            'source': 'fyers',
            'event_type': 'order_update',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
        }

    except Exception as exc:
        logger.exception("Failed to parse Fyers postback payload: %s | Error: %s", payload, exc)
        return None


def broadcast_tick_to_channel_layer(tick: dict) -> bool:
    """
    Push a normalized tick dict to Django Channels group.
    All browser WebSocket consumers subscribed to the symbol receive this.

    Channel groups:
        market_<SYMBOL>  — symbol-specific (e.g. 'market_RELIANCE')
        market_all       — global feed (all ticks, for dashboard)

    Returns:
        True if broadcast succeeded, False otherwise.
    """
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            logger.error("Channel layer not configured")
            return False

        symbol = tick['symbol']

        message = {
            'type': 'market_tick',   # maps to MarketDataConsumer.market_tick()
            'tick': tick,
        }

        # Broadcast to symbol-specific group
        async_to_sync(channel_layer.group_send)(
            f'market_{symbol}',
            message
        )

        # Broadcast to global all-symbols group
        async_to_sync(channel_layer.group_send)(
            'market_all',
            message
        )

        logger.debug("Broadcasted tick for %s @ %.4f", symbol, tick['ltp'])
        return True

    except Exception as exc:
        logger.exception("Failed to broadcast tick for %s: %s", tick.get('symbol'), exc)
        return False


def save_market_tick(tick: dict, raw_payload: dict) -> None:
    """
    Persist/update the latest tick in the MarketTick model (upsert by symbol).
    This allows browsers to fetch the last known price on page reload.
    """
    from .models import MarketTick

    try:
        MarketTick.objects.update_or_create(
            symbol=tick['symbol'],
            defaults={
                'ltp': tick['ltp'],
                'open_price': tick.get('open'),
                'high_price': tick.get('high'),
                'low_price': tick.get('low'),
                'prev_close': tick.get('prev_close'),
                'volume': tick.get('volume', 0),
                'change': tick.get('change'),
                'change_pct': tick.get('change_pct'),
                'source': 'fyers',
                'raw_payload': raw_payload,
            }
        )
    except Exception as exc:
        logger.exception("Failed to save MarketTick for %s: %s", tick.get('symbol'), exc)


def process_fyers_postback(payload: dict) -> dict:
    """
    Main entry point: parse → save → broadcast.
    Called from the Django webhook view.

    Returns:
        {'success': bool, 'symbol': str | None, 'error': str | None}
    """
    tick = parse_fyers_postback(payload)

    if tick is None:
        return {
            'success': False,
            'symbol': None,
            'error': 'Could not parse payload into a valid tick',
        }

    # Persist latest tick
    save_market_tick(tick, payload)

    # Broadcast to WebSocket consumers
    broadcast_ok = broadcast_tick_to_channel_layer(tick)

    return {
        'success': broadcast_ok,
        'symbol': tick['symbol'],
        'ltp': tick['ltp'],
        'error': None if broadcast_ok else 'Channel layer broadcast failed',
    }



# ═════════════════════════════════════════════════════════════════════════════
# FyersService — Fyers API v3 SDK wrapper with auto token refresh
# App ID: WN2QO5TH4Z-100 | Secret: 2KHAT88JEB
# ═════════════════════════════════════════════════════════════════════════════

class FyersService:
    """
    Fyers API v3 full wrapper with AUTOMATIC daily token refresh.

    .env variables:
        FYERS_CLIENT_ID     = WN2QO5TH4Z-100
        FYERS_SECRET_KEY    = 2KHAT88JEB
        FYERS_ACCESS_TOKEN  = <auto-managed>
        FYERS_REFRESH_TOKEN = <auto-managed, valid 15 days>
        FYERS_PIN           = <your 4-digit Fyers trading PIN>

    Token lifecycle:
        Access Token  → expires daily at ~6:30 AM IST
        Refresh Token → expires every 15 days

    Auto-refresh (no daily manual login needed):
        python manage.py fyers_refresh_token
        — or —
        POST /api/fyers/refresh/

    Initial login (once, and every 15 days when refresh token expires):
        GET  /api/fyers/auth-url/ → open URL in browser → login
        POST /api/fyers/callback/ with {"auth_code": "..."}
        → access_token + refresh_token auto-saved to .env
    """

    REFRESH_ENDPOINT = 'https://api-t1.fyers.in/api/v3/validate-refresh-token'
    REDIRECT_URI     = 'https://myapi.fyers.in/api/v3/validate-authcode'

    def __init__(self):
        self.client_id     = getattr(settings, 'FYERS_CLIENT_ID', '').strip()
        self.secret_key    = getattr(settings, 'FYERS_SECRET_KEY', '').strip()
        self.access_token  = getattr(settings, 'FYERS_ACCESS_TOKEN', '').strip()
        self.refresh_token = getattr(settings, 'FYERS_REFRESH_TOKEN', '').strip()
        self.pin           = getattr(settings, 'FYERS_PIN', '').strip()
        self._fyers        = None
        self._session      = None

        if self.client_id and self.secret_key:
            self._init_session()

        _invalid = {'', 'your_fyers_access_token', 'none', 'null'}
        if self.access_token.lower() not in _invalid:
            self._init_fyers_client()

    # ── Internal setup ────────────────────────────────────────────────────────

    def _init_session(self):
        """Initialize Fyers SessionModel for OAuth auth-code flow."""
        try:
            from fyers_apiv3 import fyersModel
            self._session = fyersModel.SessionModel(
                client_id    = self.client_id,
                secret_key   = self.secret_key,
                redirect_uri = self.REDIRECT_URI,
                response_type= 'code',
                grant_type   = 'authorization_code',
            )
            logger.info("Fyers SessionModel ready. client_id=%s", self.client_id)
        except ImportError:
            logger.error("fyers-apiv3 not installed. Run: pip install fyers-apiv3")
        except Exception as exc:
            logger.exception("Fyers SessionModel init error: %s", exc)

    def _init_fyers_client(self):
        """Create FyersModel API client with stored access token."""
        try:
            from fyers_apiv3 import fyersModel
            self._fyers = fyersModel.FyersModel(
                client_id=self.client_id,
                token    =self.access_token,
                is_async =False,
                log_path ='',
            )
            logger.info("Fyers API client ready. client_id=%s", self.client_id)
        except Exception as exc:
            logger.exception("Fyers API client init error: %s", exc)
            self._fyers = None

    @property
    def is_active(self) -> bool:
        return self._fyers is not None

    # ── Token persistence ─────────────────────────────────────────────────────

    def _update_env_token(self, key: str, value: str) -> bool:
        """Write key=value into the project .env file automatically."""
        import re
        from pathlib import Path
        from django.conf import settings as _s

        env_path = Path(_s.BASE_DIR) / '.env'
        if not env_path.exists():
            logger.warning(".env not found at %s — cannot persist token", env_path)
            return False
        try:
            content = env_path.read_text(encoding='utf-8')
            pattern = rf'^{re.escape(key)}=.*$'
            if re.search(pattern, content, re.MULTILINE):
                new_content = re.sub(pattern, f'{key}={value}', content, flags=re.MULTILINE)
            else:
                new_content = content.rstrip() + f'\n{key}={value}\n'
            env_path.write_text(new_content, encoding='utf-8')
            logger.info("Persisted %s to .env", key)
            return True
        except Exception as exc:
            logger.exception("Failed to update .env for %s: %s", key, exc)
            return False

    def _app_id_hash(self) -> str:
        """SHA-256(client_id:secret_key) — required by validate-refresh-token."""
        raw = f"{self.client_id}:{self.secret_key}"
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    # ── AUTO REFRESH (the main feature) ──────────────────────────────────────

    def refresh_access_token(self, pin: str = '') -> dict:
        """
        Silently refresh the access token using refresh_token + PIN.
        No browser / manual login required.

        Endpoint: POST https://api-t1.fyers.in/api/v3/validate-refresh-token
        Body:
            grant_type    : "refresh_token"
            appIdHash     : SHA-256(client_id:secret_key)
            refresh_token : 15-day token
            pin           : 4-digit Fyers trading PIN

        Token validity:
            access_token  → 24h (refreshed by this call)
            refresh_token → 15 days (requires re-login after expiry)

        Returns:
            {'success': bool, 'access_token': str|None, 'error': str|None}

        Schedule daily via cron/Task Scheduler:
            python manage.py fyers_refresh_token
        """
        import requests as _req

        pin = pin or self.pin
        if not pin:
            return {
                'success': False, 'access_token': None,
                'error': 'FYERS_PIN not set in .env — add your 4-digit trading PIN.',
            }

        rt = self.refresh_token
        if not rt or rt.lower() in ('', 'none', 'your_refresh_token'):
            return {
                'success': False, 'access_token': None,
                'error': (
                    'FYERS_REFRESH_TOKEN not found. '
                    'Complete first-time OAuth login via GET /api/fyers/auth-url/'
                ),
            }

        try:
            payload = {
                'grant_type'   : 'refresh_token',
                'appIdHash'    : self._app_id_hash(),
                'refresh_token': rt,
                'pin'          : str(pin),
            }
            response = _req.post(
                self.REFRESH_ENDPOINT,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=15,
            )
            data = response.json()
            logger.debug("Fyers refresh response: %s", data)

            if data.get('s') == 'ok' or data.get('code') == 200:
                new_at = data.get('access_token', '')
                new_rt = data.get('refresh_token', rt)   # rotates on some accounts

                if not new_at:
                    return {
                        'success': False, 'access_token': None,
                        'error': f'API returned ok but no access_token. Raw: {data}',
                    }

                self.access_token = new_at
                if new_rt and new_rt != rt:
                    self.refresh_token = new_rt
                    self._update_env_token('FYERS_REFRESH_TOKEN', new_rt)

                self._update_env_token('FYERS_ACCESS_TOKEN', new_at)
                self._init_fyers_client()

                logger.info("✅ Fyers access token refreshed successfully")
                return {'success': True, 'access_token': new_at, 'error': None}

            else:
                err = data.get('message') or data.get('error_description') or str(data)
                hint = ''
                if any(w in err.lower() for w in ('invalid', 'expired', 'unauthori')):
                    hint = (
                        ' Refresh token may have expired (15-day limit). '
                        'Re-run OAuth flow: GET /api/fyers/auth-url/'
                    )
                logger.error("Fyers token refresh failed: %s%s", err, hint)
                return {'success': False, 'access_token': None, 'error': err + hint}

        except Exception as exc:
            logger.exception("refresh_access_token error: %s", exc)
            return {'success': False, 'access_token': None, 'error': str(exc)}

    def check_and_refresh(self) -> bool:
        """
        Check if current access token is valid; auto-refresh if expired.
        Returns True if token is valid (or refreshed successfully).
        """
        if not self.is_active:
            return False
        try:
            result = self._fyers.get_profile()
            if result and result.get('s') == 'ok':
                return True

            code = result.get('code', 0) if result else 0
            if code in (-16, 10, -10) or 'token' in str(result).lower():
                logger.info("Token expired (code=%s) — attempting auto-refresh…", code)
                r = self.refresh_access_token()
                return r['success']
            return False
        except Exception as exc:
            logger.exception("check_and_refresh error: %s", exc)
            return False

    # ── Initial OAuth (once per 15 days) ─────────────────────────────────────

    def get_auth_url(self) -> str | None:
        """Generate Fyers OAuth login URL. Open in browser → login → get auth_code."""
        if not self._session:
            return None
        try:
            return self._session.generate_authcode()
        except Exception as exc:
            logger.exception("get_auth_url error: %s", exc)
            return None

    def exchange_auth_code(self, auth_code: str) -> dict:
        """
        Exchange auth_code → access_token + refresh_token.
        Both tokens are auto-saved to .env.
        """
        if not self._session:
            return {'success': False, 'access_token': None, 'refresh_token': None,
                    'error': 'Session not initialized'}
        try:
            self._session.set_token(auth_code)
            response = self._session.generate_token()

            if response and response.get('s') == 'ok':
                at = response.get('access_token', '')
                rt = response.get('refresh_token', '')

                self.access_token  = at
                self.refresh_token = rt

                if at: self._update_env_token('FYERS_ACCESS_TOKEN', at)
                if rt: self._update_env_token('FYERS_REFRESH_TOKEN', rt)

                self._init_fyers_client()
                logger.info("✅ Fyers tokens saved. access_token + refresh_token written to .env")
                return {'success': True, 'access_token': at, 'refresh_token': rt, 'error': None}

            err = response.get('message', 'Unknown') if response else 'No response'
            return {'success': False, 'access_token': None, 'refresh_token': None, 'error': err}

        except Exception as exc:
            logger.exception("exchange_auth_code error: %s", exc)
            return {'success': False, 'access_token': None, 'refresh_token': None, 'error': str(exc)}

    # ── Market Data ───────────────────────────────────────────────────────────

    def get_profile(self) -> dict | None:
        if not self.is_active: return None
        try:
            r = self._fyers.get_profile()
            return r.get('data') if r and r.get('s') == 'ok' else None
        except Exception as exc:
            logger.exception("get_profile error: %s", exc); return None

    def get_funds(self) -> list | None:
        if not self.is_active: return None
        try:
            r = self._fyers.funds()
            return r.get('fund_limit') if r and r.get('s') == 'ok' else None
        except Exception as exc:
            logger.exception("get_funds error: %s", exc); return None

    def get_quotes(self, symbols: list[str]) -> list[dict]:
        """Live quotes. symbols=['NSE:RELIANCE-EQ', 'NSE:TCS-EQ']"""
        if not self.is_active: return []
        try:
            r = self._fyers.quotes(data={'symbols': ','.join(symbols)})
            return r.get('d', []) if r and r.get('s') == 'ok' else []
        except Exception as exc:
            logger.exception("get_quotes error: %s", exc); return []

    def get_historical_candles(
        self,
        symbol: str,
        resolution: str = '1',
        date_from: str = '',
        date_to: str = '',
        cont_flag: int = 1,
    ) -> list[dict]:
        """
        Fyers OHLCV history. resolution: '1','5','15','60','D'.
        Returns lightweight-charts compatible [{time,open,high,low,close,volume}].
        """
        if not self.is_active: return []
        try:
            from datetime import datetime, timedelta
            if not date_from:
                date_from = (datetime.today() - timedelta(days=30)).strftime('%Y-%m-%d')
            if not date_to:
                date_to = datetime.today().strftime('%Y-%m-%d')

            r = self._fyers.history(data={
                'symbol'    : symbol,
                'resolution': resolution,
                'date_format': 1,
                'range_from': date_from,
                'range_to'  : date_to,
                'cont_flag' : cont_flag,
            })
            if r and r.get('s') == 'ok':
                candles = [
                    {'time': int(c[0]), 'open': float(c[1]), 'high': float(c[2]),
                     'low': float(c[3]), 'close': float(c[4]), 'volume': int(c[5])}
                    for c in r.get('candles', []) if len(c) >= 6
                ]
                logger.info("Fyers history: %d candles for %s (%s)", len(candles), symbol, resolution)
                return candles
        except Exception as exc:
            logger.exception("get_historical_candles error: %s", exc)
        return []

    def get_market_depth(self, symbol: str) -> dict | None:
        if not self.is_active: return None
        try:
            r = self._fyers.depth(data={'symbol': symbol, 'ohlcv_flag': 1})
            return r.get('d') if r and r.get('s') == 'ok' else None
        except Exception as exc:
            logger.exception("get_market_depth error: %s", exc); return None

    def get_positions(self) -> list[dict]:
        if not self.is_active: return []
        try:
            r = self._fyers.positions()
            return r.get('netPositions', []) if r and r.get('s') == 'ok' else []
        except Exception as exc:
            logger.exception("get_positions error: %s", exc); return []

    def get_holdings(self) -> list[dict]:
        if not self.is_active: return []
        try:
            r = self._fyers.holdings()
            return r.get('holdings', []) if r and r.get('s') == 'ok' else []
        except Exception as exc:
            logger.exception("get_holdings error: %s", exc); return []


# ─────────────────────────────────────────────────────────────────────────────
# Singleton — from stocks.fyers_service import fyers_service
# ─────────────────────────────────────────────────────────────────────────────
fyers_service = FyersService()
