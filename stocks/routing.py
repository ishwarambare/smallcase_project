# stocks/routing.py
"""
WebSocket URL routing for Django Channels.
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # ── Chat WebSocket (existing) ──────────────────────────────────────────
    re_path(r'ws/chat/$', consumers.ChatConsumer.as_asgi()),
    re_path(r'ws/chat/(?P<group_id>\d+)/$', consumers.ChatConsumer.as_asgi()),

    # ── Market Data WebSocket (real-time ticks) ────────────────────────────
    # ws/market/           → global feed (all symbols)
    # ws/market/RELIANCE/  → symbol-specific feed
    re_path(r'ws/market/$', consumers.MarketDataConsumer.as_asgi()),
    re_path(r'ws/market/(?P<symbol>[A-Z0-9._\-]+)/$', consumers.MarketDataConsumer.as_asgi()),
]
