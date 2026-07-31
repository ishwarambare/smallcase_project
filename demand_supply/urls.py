# demand_supply/urls.py

# pyrefly: ignore [missing-import]
from django.urls import path
from . import views

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
]
