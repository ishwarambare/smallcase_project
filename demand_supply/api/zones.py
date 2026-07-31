# pyrefly: ignore [missing-import]
from django.http import JsonResponse
from demand_supply.models import DemandSupplyZone, DemandSupplyScanResult


def get_zones(request, symbol):
    """
    GET /api/demand-supply/zones/<symbol>/

    Returns demand and supply zones in JSON format.

    Rules (GTF):
        - Demand zones are BELOW current price (proximal_line <= price)
        - Supply zones are ABOVE current price (proximal_line >= price)

    Query params:
        tf              = Filter by timeframe (e.g. 'daily'). Omit for all TFs.
        type            = 'demand' | 'supply' | 'all' (default: 'all')
        strict_position = 'true' | 'false' (default: 'true')
                          When true (default), enforces price-position rule:
                            - demand zones only shown if proximal_line <= current_price
                            - supply zones only shown if proximal_line >= current_price
    """
    try:
        symbol = symbol.upper().strip()
        qs = DemandSupplyZone.objects.filter(symbol=symbol)

        # Optional timeframe filter
        tf_param = request.GET.get('tf', '').strip().lower()
        if tf_param:
            qs = qs.filter(timeframe=tf_param)

        # Optional zone type filter
        type_param = request.GET.get('type', 'all').strip().lower()
        if type_param in ('demand', 'supply'):
            qs = qs.filter(zone_type=type_param)

        # Strict position filter (default: ON)
        strict = request.GET.get('strict_position', 'true').lower() == 'true'

        # Get current price for position filtering
        current_price = None
        if strict:
            try:
                scan_result = DemandSupplyScanResult.objects.filter(symbol=symbol).first()
                if scan_result and scan_result.current_price:
                    current_price = float(scan_result.current_price)
            except Exception:
                current_price = None

        data = []
        for z in qs.order_by('zone_type', 'timeframe'):
            is_fresh = getattr(z, 'is_fresh', True)
            strength = float(getattr(z, 'strength_score', 0) or 0)
            proximal = float(z.proximal_line)
            distal = float(z.distal_line)

            # ── POSITION RULE ──────────────────────────────────────────────
            # Demand zones must be BELOW current price (proximal <= price)
            # Supply zones must be ABOVE current price (proximal >= price)
            if strict and current_price is not None:
                if z.zone_type == 'demand' and proximal > current_price:
                    continue  # Skip demand zones that are above price
                if z.zone_type == 'supply' and proximal < current_price:
                    continue  # Skip supply zones that are below price
            # ──────────────────────────────────────────────────────────────

            data.append({
                "id":             z.id,
                "zone_type":      z.zone_type,       # 'demand' or 'supply'
                "timeframe":      z.timeframe,
                "proximal_line":  proximal,
                "distal_line":    distal,
                "formed_date":    z.formed_date.strftime('%Y-%m-%d') if z.formed_date else None,
                "is_fresh":       is_fresh,
                "strength_score": strength,
                # Backward-compatible status field
                "status":         "Fresh" if is_fresh else "Tested",
            })

        return JsonResponse(data, safe=False)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({"error": str(e)}, status=500)
