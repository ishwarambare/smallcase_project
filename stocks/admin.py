# stocks/admin.py

from django.contrib import admin
from django.shortcuts import render, redirect
from django.urls import path
from django.contrib import messages
from django.http import HttpResponseRedirect
from import_export.admin import ImportExportModelAdmin, ExportActionMixin
from import_export.formats.base_formats import CSV, XLSX, JSON, HTML, DEFAULT_FORMATS
from .models import Stock, Basket, BasketItem, StockDocument, DocumentChunk
from .resources import (
    StockResource, BasketResource, BasketItemResource,
    ChatGroupResource, ChatGroupMemberResource, ChatMessageResource,
    TinyURLResource, StockDocumentResource
)
import pandas as pd
import yfinance as yf
from decimal import Decimal
from datetime import datetime


@admin.register(Stock)
class StockAdmin(ImportExportModelAdmin):
    """
    Stock admin with TWO import methods:
    1. Django Import-Export (NEW) - Click "Import" button - Supports CSV, XLSX, JSON
    2. Custom CSV Import (OLD) - Legacy system available at /admin/stocks/stock/import-stocks/
    """
    resource_class = StockResource
    list_display = ['symbol', 'name', 'current_price', 'last_updated']
    search_fields = ['symbol', 'name']
    list_filter = ['last_updated']
    ordering = ['symbol']
    
    # Import/Export settings (NEW django-import-export)
    import_template_name = 'admin/import_export/import.html'
    export_template_name = 'admin/import_export/export.html'
    
    # Customize import/export formats
    # formats = [
    #     CSV,
    #     XLSX,
    #     JSON,
    #     HTML,
    # ]

    format =  DEFAULT_FORMATS
    
    # OLD custom import system - Keep for backward compatibility
    def changelist_view(self, request, extra_context=None):
        """Add message showing custom import link"""
        extra_context = extra_context or {}
        from django.utils.safestring import mark_safe
        messages.info(
            request, 
            mark_safe(
                '💡 Two import options available: '
                '1) Click "Import" button above (recommended) '
                '2) <a href="/admin/stocks/stock/import-stocks/" style="color: #fff; text-decoration: underline;">Legacy CSV Import</a>'
            )
        )
        return super().changelist_view(request, extra_context=extra_context)
    
    def get_urls(self):
        """Add custom URL for legacy CSV import"""
        urls = super().get_urls()
        custom_urls = [
            path('import-stocks/', self.import_stocks_view, name='import_stocks'),
        ]
        return custom_urls + urls
    
    def import_stocks_view(self, request):
        """
        Legacy custom CSV/Excel upload handler (OLD SYSTEM)
        Kept for backward compatibility
        """
        if request.method == 'POST':
            uploaded_file = request.FILES.get('stock_file')
            exchange = request.POST.get('exchange', 'NSE')  # Default to NSE
            
            if not uploaded_file:
                messages.error(request, "Please select a file to upload.")
                return redirect('..')
            
            try:
                # Determine file type and read accordingly
                file_extension = uploaded_file.name.split('.')[-1].lower()
                
                if file_extension == 'csv':
                    df = pd.read_csv(uploaded_file)
                elif file_extension in ['xlsx', 'xls']:
                    df = pd.read_excel(uploaded_file)
                else:
                    messages.error(request, "Unsupported file format. Please upload CSV or Excel file.")
                    return redirect('..')
                
                # Process the data
                created_count = 0
                updated_count = 0
                failed_count = 0
                failed_symbols = []
                
                # Get the suffix based on exchange
                suffix = '.NS' if exchange == 'NSE' else '.BO'
                
                # Assuming the CSV/Excel has a column named 'symbol' or 'Symbol' or first column
                if 'symbol' in df.columns:
                    symbol_column = 'symbol'
                elif 'Symbol' in df.columns:
                    symbol_column = 'Symbol'
                elif 'SYMBOL' in df.columns:
                    symbol_column = 'SYMBOL'
                else:
                    # Use first column if no 'symbol' column found
                    symbol_column = df.columns[0]
                
                for index, row in df.iterrows():
                    try:
                        raw_symbol = str(row[symbol_column]).strip()
                        
                        # Skip empty rows
                        if not raw_symbol or raw_symbol.lower() in ['nan', 'none', '']:
                            continue
                        
                        # Add suffix if not already present
                        if not raw_symbol.endswith('.NS') and not raw_symbol.endswith('.BO'):
                            symbol = f"{raw_symbol}{suffix}"
                        else:
                            symbol = raw_symbol
                        
                        # Fetch stock data from yfinance
                        stock_info = self.fetch_stock_info(symbol)
                        
                        if stock_info:
                            # Create or update stock
                            stock, created = Stock.objects.update_or_create(
                                symbol=symbol,
                                defaults={
                                    'name': stock_info['name'],
                                    'current_price': stock_info['price'],
                                }
                            )
                            
                            if created:
                                created_count += 1
                            else:
                                updated_count += 1
                        else:
                            failed_count += 1
                            failed_symbols.append(raw_symbol)
                    
                    except Exception as e:
                        failed_count += 1
                        failed_symbols.append(f"{raw_symbol} (Error: {str(e)})")
                        continue
                
                # Show success/error messages
                if created_count > 0:
                    messages.success(request, f"Successfully created {created_count} new stocks.")
                if updated_count > 0:
                    messages.info(request, f"Updated {updated_count} existing stocks.")
                if failed_count > 0:
                    messages.warning(
                        request, 
                        f"Failed to import {failed_count} stocks. Failed symbols: {', '.join(failed_symbols[:10])}"
                        + (" ..." if len(failed_symbols) > 10 else "")
                    )
                
                return redirect('..')
            
            except Exception as e:
                messages.error(request, f"Error processing file: {str(e)}")
                return redirect('..')
        
        # Render the upload form
        context = {
            'site_title': 'Legacy CSV Import',
            'site_header': 'Stock Administration',
            'has_permission': True,
        }
        return render(request, 'admin/csv_form.html', context)
    
    def fetch_stock_info(self, symbol):
        """Fetch stock information from yfinance (used by legacy import)"""
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            
            # Get current price
            current_price = None
            if 'currentPrice' in info:
                current_price = info['currentPrice']
            elif 'regularMarketPrice' in info:
                current_price = info['regularMarketPrice']
            else:
                # Try to get from history
                hist = stock.history(period='1d')
                if not hist.empty:
                    current_price = float(hist['Close'].iloc[-1])
            
            # Get company name
            name = info.get('longName') or info.get('shortName') or symbol.split('.')[0]
            
            if current_price:
                return {
                    'name': name,
                    'price': Decimal(str(current_price))
                }
            else:
                return None
        
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            return None



class BasketItemInline(admin.TabularInline):
    model = BasketItem
    extra = 0
    readonly_fields = ['quantity', 'purchase_price', 'allocated_amount']


@admin.register(Basket)
class BasketAdmin(ImportExportModelAdmin):
    """Basket admin with import/export functionality."""
    resource_class = BasketResource
    list_display = ['name', 'user', 'investment_amount', 'created_at', 'get_current_value', 'get_profit_loss']
    search_fields = ['name', 'description', 'user__email']
    list_filter = ['created_at', 'user']
    ordering = ['-created_at']
    inlines = [BasketItemInline]

    def get_current_value(self, obj):
        return f"₹{obj.get_total_value():,.2f}"

    get_current_value.short_description = 'Current Value'

    def get_profit_loss(self, obj):
        pl = obj.get_profit_loss()
        return f"₹{pl:,.2f}"

    get_profit_loss.short_description = 'P/L'


@admin.register(BasketItem)
class BasketItemAdmin(ImportExportModelAdmin):
    """BasketItem admin with import/export functionality."""
    resource_class = BasketItemResource
    list_display = ['basket', 'stock', 'weight_percentage', 'allocated_amount', 'quantity', 'purchase_price']
    list_filter = ['basket', 'purchase_date']
    search_fields = ['basket__name', 'stock__symbol']

@admin.register(StockDocument)
class StockDocumentAdmin(ImportExportModelAdmin):
    resource_class = StockDocumentResource
    list_display = ['stock', 'document_type', 'file_name', 'uploaded_at']
    list_filter = ['document_type', 'uploaded_at']
    search_fields = ['stock__symbol', 'title', 'document_type', 'notes']

    def file_name(self, obj):
        if obj.file:
            return obj.file.name.split('/')[-1]
        return '-'

    file_name.short_description = 'File Name'


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ['document', 'chunk_index', 'get_short_content', 'get_embedding_length']
    list_filter = ['document__stock', 'document__document_type']
    search_fields = ['content', 'document__title']
    ordering = ['document', 'chunk_index']

    def get_short_content(self, obj):
        return obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
    get_short_content.short_description = 'Content Excerpt'

    def get_embedding_length(self, obj):
        if obj.embedding:
            return len(obj.embedding)
        return 0
    get_embedding_length.short_description = 'Embedding Dimension'




# ==========================================
# Chat Admin Configuration
# ==========================================

from .models import ChatGroup, ChatGroupMember, ChatMessage


class ChatGroupMemberInline(admin.TabularInline):
    model = ChatGroupMember
    extra = 1
    autocomplete_fields = ['user']


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ['sender', 'content', 'message_type', 'created_at', 'is_read']
    can_delete = False
    max_num = 10
    ordering = ['-created_at']
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ChatGroup)
class ChatGroupAdmin(ImportExportModelAdmin):
    """ChatGroup admin with import/export functionality."""
    resource_class = ChatGroupResource
    list_display = ['name', 'group_type', 'created_by', 'get_members_count', 'is_active', 'created_at']
    list_filter = ['group_type', 'is_active', 'created_at']
    search_fields = ['name', 'description', 'created_by__email']
    ordering = ['-created_at']
    inlines = [ChatGroupMemberInline]
    autocomplete_fields = ['created_by']
    date_hierarchy = 'created_at'
    
    def get_members_count(self, obj):
        return obj.get_members_count()
    get_members_count.short_description = 'Members'


@admin.register(ChatGroupMember)
class ChatGroupMemberAdmin(ImportExportModelAdmin):
    """ChatGroupMember admin with import/export functionality."""
    resource_class = ChatGroupMemberResource
    list_display = ['user', 'group', 'role', 'is_active', 'notifications_enabled', 'joined_at']
    list_filter = ['role', 'is_active', 'notifications_enabled', 'joined_at']
    search_fields = ['user__email', 'group__name']
    autocomplete_fields = ['user', 'group']
    ordering = ['-joined_at']


@admin.register(ChatMessage)
class ChatMessageAdmin(ImportExportModelAdmin):
    """ChatMessage admin with import/export functionality."""
    resource_class = ChatMessageResource
    list_display = ['get_short_content', 'group', 'sender', 'message_type', 'is_read', 'created_at']
    list_filter = ['message_type', 'is_read', 'is_deleted', 'created_at']
    search_fields = ['content', 'sender__email', 'group__name']
    autocomplete_fields = ['sender', 'group', 'reply_to']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
    
    def get_short_content(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    get_short_content.short_description = 'Message'


# ==========================================
# Tiny URL Admin Configuration
# ==========================================

from .models import TinyURL


@admin.register(TinyURL)
class TinyURLAdmin(ImportExportModelAdmin):
    """TinyURL admin with import/export functionality."""
    resource_class = TinyURLResource
    list_display = ['short_code', 'get_basket_name', 'click_count', 'is_active', 'created_by', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['short_code', 'original_url', 'basket__name', 'created_by__email']
    readonly_fields = ['short_code', 'original_url', 'click_count', 'created_at', 'created_by']
    autocomplete_fields = ['basket', 'created_by']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    
    def get_basket_name(self, obj):
        return obj.basket.name if obj.basket else 'N/A'
    get_basket_name.short_description = 'Basket'
