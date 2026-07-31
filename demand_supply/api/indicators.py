"""
demand_supply/api/indicators.py

Computes technical indicators (EMA 20, EMA 50, RSI 14 + smoothing) for
use in the TradingView Lightweight Charts overlay.

GET /api/demand-supply/indicators/<symbol>/?tf=daily
"""

import yfinance as yf
import pandas as pd
# pyrefly: ignore [missing-import]
from django.http import JsonResponse
from datetime import datetime, timedelta


# Reuse same config as candles.py
TF_CONFIG = {
    'quarterly': {'interval': '3mo', 'days': 365 * 20},
    'monthly':   {'interval': '1mo', 'days': 365 * 10},
    'weekly':    {'interval': '1wk', 'days': 365 * 5},
    'daily':     {'interval': '1d',  'days': 365 * 2},
    '125min':    {'interval': '60m', 'days': 60},
    '75min':     {'interval': '60m', 'days': 60},
}


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    return 100 - (100 / (1 + rs))


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def get_indicators(request, symbol):
    """
    GET /api/demand-supply/indicators/<symbol>/?tf=daily

    Returns JSON with keys:
        ema20  : [{time, value}, ...]
        ema50  : [{time, value}, ...]
        rsi    : [{time, value}, ...]
        rsi_signal : [{time, value}, ...]   (9-period EMA of RSI)
    """
    try:
        tf_param = request.GET.get('tf', 'daily').lower().strip()
        cfg = TF_CONFIG.get(tf_param, TF_CONFIG['daily'])
        interval = cfg['interval']
        days_history = cfg['days']

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_history)

        yf_symbol = f"{symbol}.NS"
        df = yf.download(
            yf_symbol,
            start=start_date.strftime('%Y-%m-%d'),
            end=end_date.strftime('%Y-%m-%d'),
            interval=interval,
            progress=False,
            auto_adjust=True,
        )

        if df.empty:
            df = yf.download(
                symbol,
                start=start_date.strftime('%Y-%m-%d'),
                end=end_date.strftime('%Y-%m-%d'),
                interval=interval,
                progress=False,
                auto_adjust=True,
            )

        if df.empty:
            return JsonResponse({"error": "No data found"}, status=404)

        df = _flatten_columns(df)
        close = df['Close'].dropna()

        # Compute indicators
        ema20_s  = _ema(close, 20)
        ema50_s  = _ema(close, 50)
        rsi_s    = _rsi(close, 14)
        rsi_sig  = _ema(rsi_s, 9)

        is_intraday = interval not in ('1d', '1wk', '1mo', '3mo')

        def series_to_json(s: pd.Series):
            out = []
            for idx, val in s.items():
                if pd.isna(val):
                    continue
                if is_intraday:
                    t = int(idx.timestamp())
                else:
                    t = idx.strftime('%Y-%m-%d')
                out.append({"time": t, "value": round(float(val), 4)})
            return out

        return JsonResponse({
            "ema20":      series_to_json(ema20_s),
            "ema50":      series_to_json(ema50_s),
            "rsi":        series_to_json(rsi_s),
            "rsi_signal": series_to_json(rsi_sig),
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)
