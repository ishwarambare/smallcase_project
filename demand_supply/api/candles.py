import yfinance as yf
import pandas as pd
# pyrefly: ignore [missing-import]
from django.http import JsonResponse
from datetime import datetime, timedelta


TF_CONFIG = {
    'quarterly': {'interval': '3mo', 'days': 365 * 20},
    'monthly':   {'interval': '1mo', 'days': 365 * 10},
    'weekly':    {'interval': '1wk', 'days': 365 * 5},
    'daily':     {'interval': '1d',  'days': 365 * 2},
    '125min':    {'interval': '60m', 'days': 60},
    '75min':     {'interval': '60m', 'days': 60},
}


def _flatten_columns(df):
    """Flatten MultiIndex columns returned by yfinance >= 0.2."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def get_candles(request, symbol):
    """
    GET /api/demand-supply/candles/<symbol>/?tf=<tf>

    Returns OHLC data formatted for TradingView Lightweight Charts.

    Timeframes:
        quarterly, monthly, weekly, daily (default), 125min, 75min
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

        is_intraday = interval not in ('1d', '1wk', '1mo', '3mo')

        data = []
        for index, row in df.iterrows():
            try:
                open_  = float(row['Open'])
                high   = float(row['High'])
                low    = float(row['Low'])
                close  = float(row['Close'])
            except (KeyError, ValueError, TypeError):
                continue

            if any(v != v for v in [open_, high, low, close]):  # NaN check
                continue

            if is_intraday:
                time_val = int(index.timestamp())
            else:
                time_val = index.strftime('%Y-%m-%d')

            data.append({
                "time":  time_val,
                "open":  round(open_, 2),
                "high":  round(high, 2),
                "low":   round(low, 2),
                "close": round(close, 2),
            })

        return JsonResponse(data, safe=False)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)
