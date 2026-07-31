import os
import sys
import django

sys.path.append('c:\\Users\\ishwa\\PycharmProjects\\smallcase_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smallcase_project.settings')
django.setup()

from stocks.fyers_service import fyers_service
from stocks.analysis import compute_indicators

candles = fyers_service.get_historical_candles('NSE:RELIANCE-EQ', '5', '2026-06-25', '2026-07-01')
if candles:
    res = compute_indicators(candles, ['SMA:50', 'EMA:200', 'RSI:14', 'MACD', 'SUPERTREND:7:3'])
    for k, v in res.items():
        print(k, "length:", len(v) if isinstance(v, list) else 0)
        if isinstance(v, list) and len(v) > 0:
            print("Sample", k, ":", v[-1])
else:
    print("No candles fetched")
