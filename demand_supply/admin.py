# demand_supply/admin.py

# pyrefly: ignore [missing-import]
from django.contrib import admin
from .models import DemandSupplyZone, DemandSupplyScanResult


@admin.register(DemandSupplyZone)
class DemandSupplyZoneAdmin(admin.ModelAdmin):
    """Admin for individual demand/supply zones."""
    list_display = [
        'symbol', 'zone_type', 'timeframe',
        'proximal_line', 'distal_line',
        'strength_score', 'is_fresh', 'base_candle_count',
        'move_pct', 'sector', 'formed_date',
    ]
    list_filter = ['zone_type', 'timeframe', 'is_fresh', 'sector']
    search_fields = ['symbol', 'sector']
    ordering = ['-strength_score']
    readonly_fields = ['scan_date']
    list_per_page = 50


@admin.register(DemandSupplyScanResult)
class DemandSupplyScanResultAdmin(admin.ModelAdmin):
    """Admin for the screener / aggregate scan results per stock."""
    list_display = [
        'symbol', 'name', 'sector',
        'current_price',
        'demand_overlap_count', 'supply_overlap_count',
        'strongest_zone_score',
        'quarterly_demand', 'monthly_demand', 'weekly_demand',
        'quarterly_supply', 'monthly_supply', 'weekly_supply',
        'scan_timestamp',
    ]
    list_filter = [
        'sector',
        'quarterly_demand', 'monthly_demand', 'weekly_demand',
        'quarterly_supply', 'monthly_supply', 'weekly_supply',
    ]
    search_fields = ['symbol', 'name', 'sector']
    ordering = ['-demand_overlap_count', '-strongest_zone_score']
    readonly_fields = ['scan_timestamp']
    list_per_page = 100
