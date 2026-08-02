import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smallcase_project.settings')
django.setup()

from demand_supply.engine import scan_stock_zones, cache
from stocks.fyers_service import FyersService

# Clear the cache to force recalculation
cache.clear()

fyers = FyersService()
result = scan_stock_zones("COALINDIA", fyers_svc=fyers)

if result:
    print("\n--- Weekly Demand Zones ---")
    for z in result.get('demand_zones', {}).get('weekly', []):
        print(f"[{z['formed_date']}] Distal: {z['distal']}, Proximal: {z['proximal']}, Base Candles: {z['base_candles']}, Status: {'Fresh' if z['is_fresh'] else 'Tested'}")
    
    print("\n--- Daily Demand Zones ---")
    for z in result.get('demand_zones', {}).get('daily', []):
        print(f"[{z['formed_date']}] Distal: {z['distal']}, Proximal: {z['proximal']}, Base Candles: {z['base_candles']}")
else:
    print("No result found.")
