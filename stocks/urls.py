# stocks/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # Home and stock management
    path('', views.home, name='home'),
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

    # Autonomous Portfolio Agent
    path('api/ai/portfolio-agent/<int:basket_id>/', views.portfolio_agent_run, name='portfolio_agent_run'),

    # Financial Document RAG — "Chat with a Stock"
    path('api/ai/rag/upload/<str:symbol>/', views.rag_upload_document, name='rag_upload_document'),
    path('api/ai/rag/query/<str:symbol>/', views.rag_query_document, name='rag_query_document'),
    path('api/ai/rag/documents/<str:symbol>/', views.rag_list_documents, name='rag_list_documents'),

    # Tiny URL for basket sharing
    path('basket/<int:basket_id>/share/', views.create_tiny_url, name='create_tiny_url'),
    path('s/<str:short_code>/', views.redirect_tiny_url, name='redirect_tiny_url'),
    path('s/<str:short_code>/stats/', views.tiny_url_stats, name='tiny_url_stats'),
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