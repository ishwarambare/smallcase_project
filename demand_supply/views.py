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
from django.views.decorators.csrf import csrf_exempt


def demand_supply_dashboard(request):
    """
    GET /demand-supply/

    Render the demand-supply zone scanner dashboard page.
    """
    return render(request, 'demand_supply/demand_supply.j2')


@csrf_exempt
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


def demand_supply_chart(request, symbol):
    """
    GET /api/demand-supply/chart/<sym>/
    Returns the HTML div for the Plotly chart of the demand/supply zones.
    """
    from django.http import HttpResponse
    try:
        import yfinance as yf
        from .visualize import visualize_zones
        from datetime import datetime, timedelta
        
        # Fetch 1 year of data using yfinance
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        
        # Try finding the stock with .NS for NSE
        yf_symbol = f"{symbol}.NS"
        df = yf.download(yf_symbol, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), progress=False)
        
        if df.empty:
            # Fallback for non-Indian stocks or exact symbols
            df = yf.download(symbol, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), progress=False)
            
        if df.empty:
            return HttpResponse("<h2>No historical data found for this symbol.</h2>")
            
        fig = visualize_zones(symbol, df)
        chart_html = fig.to_html(full_html=True, include_plotlyjs='cdn')
        return HttpResponse(chart_html)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return HttpResponse(f"<h2>Error: {str(e)}</h2>")


def demand_supply_tv_chart(request, symbol):
    """
    GET /demand-supply/tv-chart/<sym>/
    Renders the HTML page hosting the TradingView Lightweight Chart
    """
    return render(request, 'demand_supply/chart.html', {'symbol': symbol})

def demand_supply_stock_detail(request, symbol):
    """
    GET /api/demand-supply/stock/<SYMBOL>/

    Returns detailed zone information for a single stock.

    GTF Position Rules applied:
        - Demand zones must be BELOW current price  (proximal_line <= current_price)
        - Supply zones must be ABOVE current price  (proximal_line >= current_price)

    Query params:
        strict_position = 'true' (default) | 'false' — disable to see all zones
    """
    from .models import DemandSupplyScanResult, DemandSupplyZone

    symbol = symbol.upper().strip()
    strict = request.GET.get('strict_position', 'true').lower() == 'true'

    try:
        scan_result = DemandSupplyScanResult.objects.get(symbol=symbol)
    except DemandSupplyScanResult.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': f'No scan data for {symbol}. Run a scan first.',
        }, status=404)

    current_price = float(scan_result.current_price) if scan_result.current_price else None

    # Get all zones for this stock
    zones = DemandSupplyZone.objects.filter(symbol=symbol)
    zones_list = []
    for z in zones:
        proximal = float(z.proximal_line)
        distal   = float(z.distal_line)

        # ── GTF Position Rule ─────────────────────────────────────────────
        # Demand zone must be BELOW current price (proximal <= price)
        # Supply zone must be ABOVE current price (proximal >= price)
        if strict and current_price is not None:
            if z.zone_type == 'demand' and proximal > current_price:
                continue  # demand above price → invalid, skip
            if z.zone_type == 'supply' and proximal < current_price:
                continue  # supply below price → invalid, skip
        # ─────────────────────────────────────────────────────────────────

        zones_list.append({
            'zone_type':    z.zone_type,
            'timeframe':    z.timeframe,
            'proximal':     proximal,
            'distal':       distal,
            'formed_date':  z.formed_date.isoformat() if z.formed_date else None,
            'strength_score': z.strength_score,
            'is_fresh':     z.is_fresh,
            'base_candles': z.base_candle_count,
            'move_pct':     float(z.move_pct),
        })

    return JsonResponse({
        'success': True,
        'stock':   scan_result.to_dict(),
        'zones':   zones_list,
        'current_price': current_price,
        'position_rule_applied': strict,
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
    return JsonResponse(response)


# ═════════════════════════════════════════════════════════════════════════════
# Dhan API Views (Token Status, Order Calculation, Super Order Placement & Alerts)
# ═════════════════════════════════════════════════════════════════════════════

def dhan_status(request):
    """
    GET /api/dhan/status/

    Check validity of access token and account setup.
    Returns fund limits, available balance, client ID.
    """
    from stocks.dhan_service import dhan_service
    status_info = dhan_service.check_account_status()
    return JsonResponse(status_info)


@csrf_exempt
def dhan_calculate_order(request):
    """
    POST /api/dhan/calculate-order/
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    import json
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    from stocks.demand_supply import calculate_dhan_super_order

    res = calculate_dhan_super_order(
        entry_price=data.get('entry_price', 0),
        stop_loss_price=data.get('stop_loss_price', 0),
        capital=data.get('capital', 100000),
        risk_pct=data.get('risk_pct', 1.0),
        reward_ratio=data.get('reward_ratio', 2.0),
        side=data.get('side', 'BUY')
    )
    return JsonResponse(res)


@csrf_exempt
def dhan_place_super_order(request):
    """
    POST /api/dhan/place-super-order/
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    import json
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    from stocks.demand_supply import execute_dhan_zone_super_order

    res = execute_dhan_zone_super_order(
        symbol=data.get('symbol', ''),
        entry_price=data.get('entry_price', 0),
        stop_loss_price=data.get('stop_loss_price', 0),
        capital=data.get('capital', 100000),
        risk_pct=data.get('risk_pct', 1.0),
        reward_ratio=data.get('reward_ratio', 2.0),
        side=data.get('side', 'BUY'),
        order_type=data.get('order_type', 'LIMIT'),
        product_type=data.get('product_type', 'INTRA')
    )
    return JsonResponse(res)


@csrf_exempt
def dhan_place_alert(request):
    """
    POST /api/dhan/place-alert/
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    import json
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    from stocks.dhan_service import dhan_service

    symbol = data.get('symbol', '').upper()
    sec_info = dhan_service.get_security_id(symbol)
    if not sec_info:
        return JsonResponse({'success': False, 'error': f'Security ID not found for {symbol}'}, status=400)

    res = dhan_service.place_forever_alert(
        security_id=sec_info['security_id'],
        transaction_type=data.get('side', 'BUY'),
        quantity=int(data.get('quantity', 1)),
        price=float(data.get('price', 0)),
        trigger_price=float(data.get('trigger_price', 0)),
        exchange_segment=sec_info['exchange'],
        symbol=symbol
    )
    return JsonResponse({
        'success': res.get('status') == 'success',
        'dhan_response': res,
    })


def dhan_orders(request):
    """
    GET /api/dhan/orders/

    Fetch order list and active forever alerts.
    """
    from stocks.dhan_service import dhan_service
    orders = dhan_service.get_order_list()
    forevers = dhan_service.get_forever_orders()
    positions = dhan_service.get_positions()
    holdings = dhan_service.get_holdings()

    return JsonResponse({
        'success': True,
        'orders': orders,
        'forever_alerts': forevers,
        'positions': positions,
        'holdings': holdings,
    })


@csrf_exempt
def dhan_cancel_order(request):
    """
    POST /api/dhan/cancel-order/
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    import json
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    from stocks.dhan_service import dhan_service
    order_id = data.get('order_id', '')

    if data.get('is_forever'):
        res = dhan_service.cancel_forever_order(order_id)
    elif data.get('is_super'):
        res = dhan_service.cancel_super_order(order_id)
    else:
        res = dhan_service.cancel_order(order_id)

    return JsonResponse({
        'success': res.get('status') == 'success',
        'dhan_response': res,
    })


# ═════════════════════════════════════════════════════════════════════════════
# Fyers Broker API Endpoints
# ═════════════════════════════════════════════════════════════════════════════

def fyers_status(request):
    """
    GET /api/fyers/status/
    """
    from stocks.fyers_service import fyers_service
    active = fyers_service.check_and_refresh()
    if not active:
        return JsonResponse({'active': False})

    profile = fyers_service.get_profile()
    funds = fyers_service.get_funds()

    available_balance = 0.0
    if isinstance(funds, list):
        for f in funds:
            if f.get('title') == 'Available Balance':
                available_balance = f.get('equityAmount', 0.0)

    return JsonResponse({
        'active': True,
        'client_id': profile.get('fy_id') if profile else 'Unknown',
        'available_balance': available_balance,
        'profile': profile
    })

@csrf_exempt
def fyers_place_super_order(request):
    """
    POST /api/fyers/place-super-order/
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    import json
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    from stocks.demand_supply import execute_fyers_zone_super_order

    res = execute_fyers_zone_super_order(
        symbol=data.get('symbol', ''),
        entry_price=data.get('entry_price', 0),
        stop_loss_price=data.get('stop_loss_price', 0),
        capital=data.get('capital', 100000),
        risk_pct=data.get('risk_pct', 1.0),
        reward_ratio=data.get('reward_ratio', 2.0),
        side=data.get('side', 'BUY'),
        order_type=1 if data.get('order_type', 'LIMIT') == 'LIMIT' else 2,
        product_type=data.get('product_type', 'CNC')
    )
    return JsonResponse(res)

@csrf_exempt
def fyers_place_alert(request):
    """
    POST /api/fyers/place-alert/
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    import json
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    from stocks.fyers_service import fyers_service

    symbol = data.get('symbol', '').upper()
    res = fyers_service.place_alert(
        symbol=symbol,
        trigger_price=float(data.get('trigger_price', 0)),
        side=data.get('side', 'BUY'),
        quantity=int(data.get('quantity', 1))
    )
    return JsonResponse({
        'success': res.get('s') == 'ok',
        'fyers_response': res,
    })


# ── GTF Strategy Backtesting Views ───────────────────────────────────────────

def gtf_backtest_dashboard(request):
    """
    GET /demand-supply/backtest/

    Render the GTF Strategy Backtester interactive dashboard UI.
    """
    return render(request, 'demand_supply/gtf_backtest.j2')


@csrf_exempt
def api_run_gtf_backtest(request):
    """
    POST /api/demand-supply/backtest/run/

    Executes GTF Intraday Strategy Backtest based on configuration.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    import json
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        data = request.POST.dict()

    symbols_input = data.get('symbols', ['RELIANCE', 'HDFCBANK', 'SBIN', 'TCS', 'INFY'])
    if isinstance(symbols_input, str):
        symbols = [s.strip().upper() for s in symbols_input.replace('\n', ',').split(',') if s.strip()]
    elif isinstance(symbols_input, list):
        symbols = [str(s).strip().upper() for s in symbols_input if str(s).strip()]
    else:
        symbols = ['RELIANCE', 'HDFCBANK', 'SBIN']

    if not symbols:
        symbols = ['RELIANCE', 'HDFCBANK', 'SBIN']

    config = {
        'start_date': data.get('start_date', '2025-09-01'),
        'end_date': data.get('end_date', '2025-09-30'),
        'htf_interval': data.get('htf_interval', '60m'),
        'ltf_interval': data.get('ltf_interval', '15m'),
        'initial_capital': float(data.get('initial_capital', 100000.0)),
        'risk_per_trade': float(data.get('risk_per_trade', 1000.0)),
        'min_score': float(data.get('min_score', 4.5)),
        'max_r_multiple': float(data.get('max_r_multiple', 3.0)),
        'max_base_candles': int(data.get('max_base_candles', 3)),
        'base_candle_ratio': float(data.get('base_candle_ratio', 0.33)),
        'min_wick_ratio': float(data.get('min_wick_ratio', 0.4))
    }

    from .backtest_engine import execute_multi_gtf_backtest
    try:
        results = execute_multi_gtf_backtest(symbols, config)
        return JsonResponse(results)
    except Exception as e:
        import traceback
        logger.error(f"GTF Backtest error: {e}\n{traceback.format_exc()}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

