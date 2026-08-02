# demand_supply/urls.py

# pyrefly: ignore [missing-import]
from django.urls import path
from . import views
from .api import candles, zones, indicators

urlpatterns = [
    # ── GTF Demand-Supply Zone Scanner ────────────────────────────────────────
    # Dashboard (UI)
    path('demand-supply/', views.demand_supply_dashboard, name='demand_supply_dashboard'),
    # Trigger scan (POST)
    path('api/demand-supply/scan/', views.demand_supply_scan, name='demand_supply_scan'),
    # Screener results with filters (GET)
    path('api/demand-supply/results/', views.demand_supply_results, name='demand_supply_results'),
    # Single stock zone detail (GET)
    path('api/demand-supply/stock/<str:symbol>/', views.demand_supply_stock_detail, name='demand_supply_stock_detail'),
    # Sector strength rankings (GET)
    path('api/demand-supply/sectors/', views.demand_supply_sectors, name='demand_supply_sectors'),
    # Scan status / progress (GET)
    path('api/demand-supply/status/', views.demand_supply_scan_status, name='demand_supply_scan_status'),
    # Single stock visualization chart (GET) - Plotly fallback
    path('api/demand-supply/chart/<str:symbol>/', views.demand_supply_chart, name='demand_supply_chart'),
    # TradingView Lightweight Charts APIs
    path('api/demand-supply/candles/<str:symbol>/', candles.get_candles, name='api_candles'),
    path('api/demand-supply/zones/<str:symbol>/', zones.get_zones, name='api_zones'),
    # Technical indicators: EMA 20/50, RSI 14 + smoothing (GET)
    path('api/demand-supply/indicators/<str:symbol>/', indicators.get_indicators, name='api_indicators'),
    path('demand-supply/tv-chart/<str:symbol>/', views.demand_supply_tv_chart, name='demand_supply_tv_chart'),

    # ── Dhan API Endpoints ────────────────────────────────────────────────────
    path('api/dhan/status/', views.dhan_status, name='dhan_status'),
    path('api/dhan/calculate-order/', views.dhan_calculate_order, name='dhan_calculate_order'),
    path('api/dhan/place-super-order/', views.dhan_place_super_order, name='dhan_place_super_order'),
    path('api/dhan/place-alert/', views.dhan_place_alert, name='dhan_place_alert'),
    path('api/dhan/orders/', views.dhan_orders, name='dhan_orders'),
    path('api/dhan/cancel-order/', views.dhan_cancel_order, name='dhan_cancel_order'),

    # ── Fyers API Endpoints ───────────────────────────────────────────────────
    path('api/fyers/status/', views.fyers_status, name='fyers_status'),
    path('api/fyers/place-super-order/', views.fyers_place_super_order, name='fyers_place_super_order'),
    path('api/fyers/place-alert/', views.fyers_place_alert, name='fyers_place_alert'),

    # ── GTF Strategy Backtester ──────────────────────────────────────────────
    path('demand-supply/backtest/', views.gtf_backtest_dashboard, name='gtf_backtest_dashboard'),
    path('api/demand-supply/backtest/run/', views.api_run_gtf_backtest, name='api_run_gtf_backtest'),
]


