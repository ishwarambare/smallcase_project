# demand_supply/views.py

"""
GTF Demand-Supply Zone Scanner — API & UI views.

Endpoints:
    GET  /demand-supply/                  → Dashboard UI
    POST /api/demand-supply/scan/         → Trigger Celery scan
    GET  /api/demand-supply/results/      → Screener results (filtered)
    GET  /api/demand-supply/stock/<sym>/  → Single-stock zone detail
    GET  /api/demand-supply/sectors/      → Sector strength rankings
    GET  /api/demand-supply/status/       → Scan task status / progress
"""

# pyrefly: ignore [missing-import]
from django.shortcuts import render
# pyrefly: ignore [missing-import]
from django.http import JsonResponse


def demand_supply_dashboard(request):
    """
    GET /demand-supply/

    Render the demand-supply zone scanner dashboard page.
    """
    return render(request, 'demand_supply/demand_supply.j2')


def demand_supply_scan(request):
    """
    POST /api/demand-supply/scan/

    Trigger a demand-supply zone scan as a Celery background task.

    Optional JSON body:
        {"symbols": ["RELIANCE", "TCS", "INFY"]}
    If no symbols provided, scans all stocks in the Stock model.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    import json
    symbols = None
    if request.body:
        try:
            data = json.loads(request.body)
            symbols = data.get('symbols')
        except json.JSONDecodeError:
            pass

    from .tasks import scan_demand_supply_zones
    task = scan_demand_supply_zones.delay(symbols=symbols)

    return JsonResponse({
        'success': True,
        'task_id': task.id,
        'message': 'Scan started',
    })


def demand_supply_results(request):
    """
    GET /api/demand-supply/results/

    Returns screener results with optional filters.

    Query params:
        zone_type     = demand | supply (default: demand)
        min_overlap   = 1-6 (minimum timeframe overlap count)
        timeframes    = quarterly,monthly,weekly (comma-separated, which TFs must have zones)
        sector        = IT,Banking (comma-separated sector filter)
        sort_by       = overlap_count | strength_score | sector (default: overlap_count)
        fresh_only    = true | false (only show stocks in fresh zones)
        limit         = int (max results, default 100)
    """
    from .models import DemandSupplyScanResult

    zone_type = request.GET.get('zone_type', 'demand')
    min_overlap = int(request.GET.get('min_overlap', 0))
    timeframes = request.GET.get('timeframes', '')
    sectors = request.GET.get('sector', '')
    sort_by = request.GET.get('sort_by', 'overlap_count')
    fresh_only = request.GET.get('fresh_only', 'false').lower() == 'true'
    limit = int(request.GET.get('limit', 100))

    qs = DemandSupplyScanResult.objects.all()

    # Filter by overlap count
    if zone_type == 'supply':
        qs = qs.filter(supply_overlap_count__gte=min_overlap)
    else:
        qs = qs.filter(demand_overlap_count__gte=min_overlap)

    # Filter by specific timeframes
    if timeframes:
        tf_list = [t.strip().lower() for t in timeframes.split(',')]
        if zone_type == 'demand':
            if 'quarterly' in tf_list:
                qs = qs.filter(quarterly_demand=True)
            if 'monthly' in tf_list:
                qs = qs.filter(monthly_demand=True)
            if 'weekly' in tf_list:
                qs = qs.filter(weekly_demand=True)
            if 'daily' in tf_list:
                qs = qs.filter(daily_demand=True)
        else:
            if 'quarterly' in tf_list:
                qs = qs.filter(quarterly_supply=True)
            if 'monthly' in tf_list:
                qs = qs.filter(monthly_supply=True)
            if 'weekly' in tf_list:
                qs = qs.filter(weekly_supply=True)
            if 'daily' in tf_list:
                qs = qs.filter(daily_supply=True)

    # Filter by sector
    if sectors:
        sector_list = [s.strip() for s in sectors.split(',')]
        qs = qs.filter(sector__in=sector_list)

    # Filter fresh zones only
    if fresh_only:
        from .models import DemandSupplyZone
        fresh_symbols = DemandSupplyZone.objects.filter(
            is_fresh=True,
            zone_type=zone_type,
        ).values_list('symbol', flat=True).distinct()
        qs = qs.filter(symbol__in=list(fresh_symbols))

    # Sorting
    if sort_by == 'strength_score':
        qs = qs.order_by('-strongest_zone_score')
    elif sort_by == 'sector':
        qs = qs.order_by('sector', '-demand_overlap_count')
    elif zone_type == 'supply':
        qs = qs.order_by('-supply_overlap_count', '-strongest_zone_score')
    else:
        qs = qs.order_by('-demand_overlap_count', '-strongest_zone_score')

    results = [r.to_dict() for r in qs[:limit]]

    # Get last scan time
    latest = DemandSupplyScanResult.objects.order_by('-scan_timestamp').first()
    last_scan = latest.scan_timestamp.isoformat() if latest and latest.scan_timestamp else None

    return JsonResponse({
        'success': True,
        'results': results,
        'total': len(results),
        'last_scan': last_scan,
        'filters': {
            'zone_type': zone_type,
            'min_overlap': min_overlap,
            'timeframes': timeframes,
            'sectors': sectors,
            'sort_by': sort_by,
            'fresh_only': fresh_only,
        },
    })


def demand_supply_stock_detail(request, symbol):
    """
    GET /api/demand-supply/stock/<SYMBOL>/

    Returns detailed zone information for a single stock.
    """
    from .models import DemandSupplyScanResult, DemandSupplyZone

    symbol = symbol.upper().strip()

    try:
        scan_result = DemandSupplyScanResult.objects.get(symbol=symbol)
    except DemandSupplyScanResult.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': f'No scan data for {symbol}. Run a scan first.',
        }, status=404)

    # Get all zones for this stock
    zones = DemandSupplyZone.objects.filter(symbol=symbol)
    zones_list = []
    for z in zones:
        zones_list.append({
            'zone_type': z.zone_type,
            'timeframe': z.timeframe,
            'proximal': float(z.proximal_line),
            'distal': float(z.distal_line),
            'formed_date': z.formed_date.isoformat() if z.formed_date else None,
            'strength_score': z.strength_score,
            'is_fresh': z.is_fresh,
            'base_candles': z.base_candle_count,
            'move_pct': float(z.move_pct),
        })

    return JsonResponse({
        'success': True,
        'stock': scan_result.to_dict(),
        'zones': zones_list,
    })


def demand_supply_sectors(request):
    """
    GET /api/demand-supply/sectors/

    Returns sector strength rankings based on demand/supply zone analysis.
    """
    from .models import DemandSupplyScanResult
    from django.db.models import Count, Avg, Q

    sectors = (
        DemandSupplyScanResult.objects
        .exclude(sector='')
        .exclude(sector='Unknown')
        .values('sector')
        .annotate(
            total_stocks=Count('id'),
            stocks_in_demand=Count('id', filter=Q(demand_overlap_count__gt=0)),
            stocks_in_supply=Count('id', filter=Q(supply_overlap_count__gt=0)),
            avg_demand_overlap=Avg('demand_overlap_count'),
            avg_supply_overlap=Avg('supply_overlap_count'),
            avg_strength=Avg('strongest_zone_score'),
        )
        .order_by('-stocks_in_demand')
    )

    result = []
    for s in sectors:
        total = s['total_stocks']
        demand_pct = round((s['stocks_in_demand'] / total) * 100, 1) if total > 0 else 0
        supply_pct = round((s['stocks_in_supply'] / total) * 100, 1) if total > 0 else 0

        # Get top 3 stocks in this sector by demand overlap
        top_stocks = list(
            DemandSupplyScanResult.objects
            .filter(sector=s['sector'], demand_overlap_count__gt=0)
            .order_by('-demand_overlap_count', '-strongest_zone_score')
            .values('symbol', 'current_price', 'demand_overlap_count', 'strongest_zone_score')
            [:3]
        )
        for ts in top_stocks:
            if ts['current_price']:
                ts['current_price'] = float(ts['current_price'])

        result.append({
            'sector': s['sector'],
            'total_stocks': total,
            'stocks_in_demand': s['stocks_in_demand'],
            'stocks_in_supply': s['stocks_in_supply'],
            'demand_strength_pct': demand_pct,
            'supply_strength_pct': supply_pct,
            'avg_demand_overlap': round(float(s['avg_demand_overlap'] or 0), 2),
            'avg_supply_overlap': round(float(s['avg_supply_overlap'] or 0), 2),
            'avg_strength': round(float(s['avg_strength'] or 0), 1),
            'top_stocks': top_stocks,
        })

    return JsonResponse({
        'success': True,
        'sectors': result,
    })


def demand_supply_scan_status(request):
    """
    GET /api/demand-supply/status/

    Returns the status of a running scan task.

    Query params:
        task_id = Celery task ID (from the /scan/ response)
    """
    task_id = request.GET.get('task_id', '')

    if not task_id:
        # Return general status
        from .models import DemandSupplyScanResult
        latest = DemandSupplyScanResult.objects.order_by('-scan_timestamp').first()
        total = DemandSupplyScanResult.objects.count()

        return JsonResponse({
            'success': True,
            'status': 'idle',
            'last_scan': latest.scan_timestamp.isoformat() if latest and latest.scan_timestamp else None,
            'total_results': total,
        })

    # Check Celery task status
    from celery.result import AsyncResult
    result = AsyncResult(task_id)

    response = {
        'success': True,
        'task_id': task_id,
        'status': result.status,
    }

    if result.status == 'PROGRESS':
        response['progress'] = result.info
    elif result.status == 'SUCCESS':
        response['result'] = result.result
    elif result.status == 'FAILURE':
        response['error'] = str(result.result)

    return JsonResponse(response)
