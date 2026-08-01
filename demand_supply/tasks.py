"""
demand_supply/tasks.py

Celery tasks for demand-supply zone scanning.
Runs the GTF-style zone detection engine as a background task.

Usage:
    # Scan all stocks in DB
    from demand_supply.tasks import scan_demand_supply_zones
    scan_demand_supply_zones.delay()

    # Scan specific symbols
    scan_demand_supply_zones.delay(symbols=['RELIANCE', 'TCS', 'INFY'])
"""

import logging
# pyrefly: ignore [missing-import]
from celery import shared_task
# pyrefly: ignore [missing-import]
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='demand_supply.scan_demand_supply_zones')
def scan_demand_supply_zones(self, symbols=None):
    """
    Celery task: Scan stocks for demand/supply zones across all timeframes.

    Args:
        symbols: Optional list of NSE symbols. If None, scans all stocks in DB.

    Returns:
        dict with scan summary (total scanned, stocks in demand/supply, etc.)
    """
    from stocks.models import Stock
    from .models import DemandSupplyZone, DemandSupplyScanResult
    from .engine import batch_scan
    from .nifty500 import get_nifty500_symbols

    # Determine stock list
    if symbols:
        # Explicit symbols passed in — filter to Nifty 500 universe
        nifty500_set = set(get_nifty500_symbols())
        stock_symbols = [s.upper().strip() for s in symbols if s.upper().strip() in nifty500_set]
        if not stock_symbols:
            # If caller passed symbols not in Nifty 500, use them anyway (override mode)
            stock_symbols = [s.upper().strip() for s in symbols]
    else:
        # Auto-mode: scan only Nifty 500 stocks
        nifty500_symbols = set(get_nifty500_symbols())
        # Get DB stocks that are in the Nifty 500 universe (clean suffixes first)
        db_symbols = list(
            Stock.objects.values_list('symbol', flat=True).order_by('symbol')
        )
        db_clean = {
            s.replace('.NS', '').replace('.BO', '').strip().upper()
            for s in db_symbols
        }
        # Use Nifty 500 directly (we don't require them to be in DB — yfinance will fetch data)
        stock_symbols = sorted(nifty500_symbols)

    if not stock_symbols:
        logger.warning("No stocks to scan")
        return {'success': False, 'error': 'No stocks found to scan'}

    logger.info("Starting demand-supply scan for %d stocks", len(stock_symbols))

    # Try to get Fyers service
    fyers_svc = None
    try:
        from stocks.fyers_service import fyers_service
        if fyers_service.is_active:
            fyers_svc = fyers_service
            logger.info("Using Fyers API for candle data")
        else:
            logger.info("Fyers not active, using yfinance fallback")
    except Exception as e:
        logger.warning("Could not load Fyers service: %s", e)

    # Progress callback to update Celery task state
    def progress_callback(current, total, symbol):
        self.update_state(
            state='PROGRESS',
            meta={
                'current': current,
                'total': total,
                'symbol': symbol,
                'percent': round((current / total) * 100, 1),
            }
        )

    # Run the batch scan
    scan_data = batch_scan(
        symbols=stock_symbols,
        fyers_svc=fyers_svc,
        progress_callback=progress_callback,
    )

    # Persist results to database
    _persist_scan_results(scan_data)

    # Clean up obsolete records if this was a full scan
    if not symbols:
        from .models import DemandSupplyZone, DemandSupplyScanResult
        DemandSupplyScanResult.objects.exclude(symbol__in=stock_symbols).delete()
        DemandSupplyZone.objects.exclude(symbol__in=stock_symbols).delete()
        logger.info("Cleaned up obsolete database records not in current scan.")

    summary = {
        'success': True,
        'total_scanned': scan_data['total_scanned'],
        'total_attempted': scan_data['total_attempted'],
        'stocks_in_demand': scan_data['stocks_in_demand'],
        'stocks_in_supply': scan_data['stocks_in_supply'],
        'errors_count': len(scan_data.get('errors', [])),
        'scan_time_seconds': scan_data['scan_time_seconds'],
        'sector_count': len(scan_data['sector_strength']),
    }

    logger.info(
        "Demand-supply scan complete: %d/%d scanned, %d in demand, %d in supply (%.1fs)",
        summary['total_scanned'], summary['total_attempted'],
        summary['stocks_in_demand'], summary['stocks_in_supply'],
        summary['scan_time_seconds'],
    )

    return summary


def _persist_scan_results(scan_data: dict):
    """
    Save scan results to database models.
    Upserts DemandSupplyScanResult and replaces DemandSupplyZone records.
    """
    from .models import DemandSupplyZone, DemandSupplyScanResult
    from datetime import datetime

    for result in scan_data.get('scan_results', []):
        symbol = result['symbol']

        # Upsert the scan result (screener row)
        DemandSupplyScanResult.objects.update_or_create(
            symbol=symbol,
            defaults={
                'name': result.get('name', symbol),
                'sector': result.get('sector', ''),
                'current_price': result.get('current_price'),
                'demand_overlap_count': result.get('demand_overlap_count', 0),
                'supply_overlap_count': result.get('supply_overlap_count', 0),
                'quarterly_demand': result.get('quarterly_demand', False),
                'monthly_demand': result.get('monthly_demand', False),
                'weekly_demand': result.get('weekly_demand', False),
                'daily_demand': result.get('daily_demand', False),
                'min125_demand': result.get('min125_demand', False),
                'min75_demand': result.get('min75_demand', False),
                'quarterly_supply': result.get('quarterly_supply', False),
                'monthly_supply': result.get('monthly_supply', False),
                'weekly_supply': result.get('weekly_supply', False),
                'daily_supply': result.get('daily_supply', False),
                'min125_supply': result.get('min125_supply', False),
                'min75_supply': result.get('min75_supply', False),
                'strongest_zone_score': result.get('strongest_zone_score', 0),
                'zone_details': result.get('zone_details', {}),
            }
        )

        # Replace zones for this symbol
        DemandSupplyZone.objects.filter(symbol=symbol).delete()

        zone_objects = []
        for zone_type in ['demand_zones', 'supply_zones']:
            zt = 'demand' if zone_type == 'demand_zones' else 'supply'
            for timeframe, zones in result.get(zone_type, {}).items():
                for zone in zones:
                    formed = zone.get('formed_date', '')
                    try:
                        if isinstance(formed, str) and formed:
                            formed_date = datetime.strptime(formed[:10], '%Y-%m-%d').date()
                        else:
                            formed_date = datetime.today().date()
                    except (ValueError, TypeError):
                        formed_date = datetime.today().date()

                    zone_objects.append(DemandSupplyZone(
                        symbol=symbol,
                        zone_type=zt,
                        timeframe=timeframe,
                        proximal_line=zone.get('proximal', 0),
                        distal_line=zone.get('distal', 0),
                        formed_date=formed_date,
                        strength_score=zone.get('strength_score', 0),
                        is_fresh=zone.get('is_fresh', False),
                        base_candle_count=zone.get('base_candles', 1),
                        move_pct=zone.get('move_pct', 0),
                        sector=result.get('sector', ''),
                    ))

        if zone_objects:
            DemandSupplyZone.objects.bulk_create(zone_objects)

    logger.info(
        "Persisted scan results: %d stocks, zones replaced",
        len(scan_data.get('scan_results', []))
    )
