import os
import sys
import django

sys.path.append('c:\\Users\\ishwa\\PycharmProjects\\smallcase_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smallcase_project.settings')
django.setup()

from stocks.fyers_service import fyers_service
from stocks.analysis import compute_indicators

candles = fyers_service.get_historical_candles('NSE:RELIANCE-EQ', 'D', '2025-01-01', '2026-07-01')
if candles:
    res = compute_indicators(candles, ['SMA:50', 'EMA:200', 'RSI:14', 'MACD', 'SUPERTREND:7:3'])
    for k, v in res.items():
        print(k, "length:", len(v) if isinstance(v, list) else 0)
    if 'SMA:50' in res and res['SMA:50']:
        print("Sample SMA:", res['SMA:50'][-1])
else:
    print("No candles fetched")
