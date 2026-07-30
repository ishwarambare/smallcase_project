"""Quick test for demand-supply zone detection on RELIANCE."""
import os, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'smallcase_project.settings'
sys.stdout.reconfigure(encoding='utf-8')

import django
django.setup()

from stocks.demand_supply import scan_stock_zones

print("=" * 60)
print("Testing GTF Zone Detection on RELIANCE")
print("=" * 60)

result = scan_stock_zones('RELIANCE')

if result is None:
    print("ERROR: No result returned (no candle data?)")
else:
    print(f"Symbol:          {result['symbol']}")
    print(f"Current Price:   Rs.{result['current_price']}")
    print(f"Sector:          {result['sector']}")
    print(f"Demand Overlap:  {result['demand_overlap_count']}")
    print(f"Supply Overlap:  {result['supply_overlap_count']}")
    print(f"Q Demand:        {result['quarterly_demand']}")
    print(f"M Demand:        {result['monthly_demand']}")
    print(f"W Demand:        {result['weekly_demand']}")
    print(f"Q Supply:        {result['quarterly_supply']}")
    print(f"M Supply:        {result['monthly_supply']}")
    print(f"W Supply:        {result['weekly_supply']}")
    print(f"Strongest Score: {result['strongest_zone_score']}")
    print()

    for zone_type in ['demand_zones', 'supply_zones']:
        zt = zone_type.replace('_zones', '').upper()
        print(f"--- {zt} ZONES ---")
        for tf, zones in result[zone_type].items():
            print(f"  {tf}: {len(zones)} zones")
            for z in zones[:3]:  # Show top 3
                fresh = "FRESH" if z['is_fresh'] else "tested"
                print(f"    Rs.{z['proximal']:.2f} - Rs.{z['distal']:.2f} | "
                      f"Score: {z['strength_score']} | "
                      f"{z['base_candles']} candle base | "
                      f"{z['move_pct']:.1f}% move | {fresh}")
        print()

    print("Test complete!")
