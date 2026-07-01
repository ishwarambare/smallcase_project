# stocks/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # Home and stock management
    path('', views.landing, name='landing'),
    path('dashboard/', views.home, name='home'),
    path('stock/<str:symbol>/', views.stock_detail, name='stock_detail'),
    path('populate-stocks/', views.populate_stocks, name='populate_stocks'),
    path('update-prices/', views.update_prices, name='update_prices'),

    # Stock history API (for charts)
    path('api/stock-history/', views.stock_history_api, name='stock_history_api'),
    
    # Basket management
    path('basket/create/', views.basket_create, name='basket_create'),
    path('basket/<int:basket_id>/', views.basket_detail, name='basket_detail'),
    path('basket/<int:basket_id>/performance/', views.basket_performance, name='basket_performance'),
    path('basket/<int:basket_id>/chart-data/', views.basket_chart_data, name='basket_chart_data'),
    path('basket/<int:basket_id>/delete/', views.basket_delete, name='basket_delete'),
    path('basket/<int:basket_id>/duplicate/', views.basket_duplicate, name='basket_duplicate'),
    path('basket/<int:basket_id>/edit-investment/', views.basket_edit_investment, name='basket_edit_investment'),
    path('basket/preview/', views.preview_basket, name='preview_basket'),
    path('basket-item/<int:item_id>/edit/', views.basket_item_edit, name='basket_item_edit'),
    path('basket/<int:basket_id>/stock/<int:stock_id>/delete/', views.basket_stock_delete, name='basket_stock_delete'),
    path('basket/<int:basket_id>/stock/add/', views.basket_stock_add, name='basket_stock_add'),
    path('basket/<int:basket_id>/available-stocks/', views.basket_get_available_stocks, name='basket_available_stocks'),
    
    # Static pages
    path('contact/', views.contact_us, name='contact_us'),
    path('i18n-demo/', views.i18n_demo, name='i18n_demo'),  # Multi-language demo

    
    # Chat API endpoints
    path('api/chat/send/', views.chat_send_message, name='chat_send_message'),
    path('api/chat/messages/', views.chat_get_messages, name='chat_get_messages'),
    path('api/chat/groups/', views.chat_get_groups, name='chat_get_groups'),
    path('api/chat/groups/create/', views.chat_create_group, name='chat_create_group'),
    path('api/chat/groups/members/', views.chat_get_members, name='chat_get_members'),
    path('api/chat/groups/add-member/', views.chat_add_member, name='chat_add_member'),
    path('api/chat/groups/leave/', views.chat_leave_group, name='chat_leave_group'),
    path('api/chat/users/search/', views.chat_search_users, name='chat_search_users'),
    
    # AI Chat API
    path('api/ai/chat/', views.ai_chat, name='ai_chat'),

    # AI Stock Intelligence APIs (async — called after page load)
    path('api/ai/stock-summary/<str:symbol>/', views.ai_stock_summary, name='ai_stock_summary'),
    path('api/ai/news-sentiment/<str:symbol>/', views.ai_news_sentiment, name='ai_news_sentiment'),
    path('api/stock/analysis-summary/', views.stock_analysis_summary_api, name='stock_analysis_summary_api'),

    # Autonomous Portfolio Agent
    path('api/ai/portfolio-agent/<int:basket_id>/', views.portfolio_agent_run, name='portfolio_agent_run'),

    # Financial Document RAG — "Chat with a Stock"
    path('api/ai/rag/upload/<str:symbol>/', views.rag_upload_document, name='rag_upload_document'),
    path('api/ai/rag/query/<str:symbol>/', views.rag_query_document, name='rag_query_document'),
    path('api/ai/rag/documents/<str:symbol>/', views.rag_list_documents, name='rag_list_documents'),
    path('api/ai/rag/reindex/<str:symbol>/', views.rag_reindex_documents, name='rag_reindex_documents'),
    path('api/ai/rag/delete/<str:symbol>/<int:doc_id>/', views.rag_delete_document, name='rag_delete_document'),
    path('api/ai/rag/generate-default/<str:symbol>/', views.rag_generate_default_document, name='rag_generate_default_document'),


    # Tiny URL for basket sharing
    path('basket/<int:basket_id>/share/', views.create_tiny_url, name='create_tiny_url'),
    path('s/<str:short_code>/', views.redirect_tiny_url, name='redirect_tiny_url'),
    path('s/<str:short_code>/stats/', views.tiny_url_stats, name='tiny_url_stats'),

    # ─── Real-Time Market Data ────────────────────────────────────────────────
    # Dashboard (UI)
    path('market/', views.market_dashboard, name='market_dashboard'),

    # Fyers postback webhook — register this URL in Fyers API dashboard
    # e.g. https://yourdomain.com/api/webhook/fyers/
    path('api/webhook/fyers/', views.fyers_postback_webhook, name='fyers_postback_webhook'),

    # REST API — latest tick(s) from DB (for page-load init before WS connects)
    path('api/market/ticks/', views.market_tick_api, name='market_ticks_api'),
    path('api/market/tick/<str:symbol>/', views.market_tick_api, name='market_tick_api'),

    # DhanHQ candles API — seeds the chart with historical intraday OHLCV
    # GET /api/market/candles/<SYMBOL>/          → intraday (today)
    # GET /api/market/candles/<SYMBOL>/daily/    → daily OHLCV (last 90 days)
    path('api/market/candles/<str:symbol>/', views.dhan_candles_api, name='dhan_candles_api'),
    path('api/market/candles/<str:symbol>/daily/', views.dhan_daily_candles_api, name='dhan_daily_candles_api'),

    # Fyers historical candles API (requires FYERS_ACCESS_TOKEN)
    # GET /api/market/fyers/candles/<SYMBOL>/    → 1-min candles (today)
    # GET /api/market/fyers/candles/<SYMBOL>/?resolution=15&days=30
    path('api/market/fyers/candles/<str:symbol>/', views.fyers_candles_api, name='fyers_candles_api'),

    # Fyers OAuth helpers
    # GET  /api/fyers/auth-url/  → returns login URL
    # POST /api/fyers/callback/  → exchanges auth_code for access_token
    path('api/fyers/auth-url/', views.fyers_auth_url, name='fyers_auth_url'),
    path('api/fyers/callback/', views.fyers_auth_callback, name='fyers_auth_callback'),
]


# ======================================
# smallcase_project/urls.py
# ======================================

"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('stocks.urls')),
]
"""