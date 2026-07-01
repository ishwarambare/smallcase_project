import os
import sys
import django

sys.path.append('c:\\Users\\ishwa\\PycharmProjects\\smallcase_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smallcase_project.settings')
django.setup()

from stocks.fyers_service import fyers_service
from datetime import datetime

# Get intraday
candles_15 = fyers_service.get_historical_candles('NSE:RELIANCE-EQ', '15', '2026-06-25', '2026-07-01')
if candles_15:
    c = candles_15[0]
    dt = datetime.utcfromtimestamp(c['time'])
    print("15m:", c['time'], dt, dt.strftime('%Y-%m-%d %H:%M:%S'))

# Get daily
candles_D = fyers_service.get_historical_candles('NSE:RELIANCE-EQ', 'D', '2026-01-01', '2026-07-01')
if candles_D:
    c = candles_D[0]
    dt = datetime.utcfromtimestamp(c['time'])
    print("1D:", c['time'], dt, dt.strftime('%Y-%m-%d %H:%M:%S'))
