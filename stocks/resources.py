# stocks/resources.py

from import_export import resources, fields, widgets
from import_export.widgets import ForeignKeyWidget, DecimalWidget
from .models import (
    Stock, Basket, BasketItem, ChatGroup, ChatGroupMember,
    ChatMessage, TinyURL, StockDocument
)
from django.contrib.auth import get_user_model
import yfinance as yf
from decimal import Decimal

User = get_user_model()


class StockResource(resources.ModelResource):
    """
    Resource class for Stock model with import/export functionality.
    Automatically fetches stock data from Yahoo Finance during import.
    """
    
    class Meta:
        model = Stock
        fields = ('id', 'symbol', 'name', 'current_price', 'last_updated')
        export_order = ('id', 'symbol', 'name', 'current_price', 'last_updated')
        import_id_fields = ['symbol']  # Use symbol as the unique identifier
        skip_unchanged = True
        report_skipped = True
    
    def before_import_row(self, row, **kwargs):
        """
        Pre-process each row before import.
        Fetch stock data from Yahoo Finance if not provided.
        """
        symbol = row.get('symbol', '').strip()
        
        if symbol:
            # Add .NS suffix if not present (for NSE stocks)
            if not symbol.endswith('.NS') and not symbol.endswith('.BO'):
                symbol = f"{symbol}.NS"
                row['symbol'] = symbol
            
            # Fetch data from Yahoo Finance if name or price is missing
            if not row.get('name') or not row.get('current_price'):
                stock_data = self._fetch_stock_data(symbol)
                if stock_data:
                    if not row.get('name'):
                        row['name'] = stock_data['name']
                    if not row.get('current_price'):
                        row['current_price'] = stock_data['price']
    
    def _fetch_stock_data(self, symbol):
        """Fetch stock information from yfinance"""
        try:
            stock = yf.Ticker(symbol)
            try:
                info = stock.info or {}
            except Exception as ie:
                print(f"Info fetch failed for {symbol}: {ie}")
                info = {}
            
            # Get current price
            current_price = None
            if info and 'currentPrice' in info:
                current_price = info['currentPrice']
            elif info and 'regularMarketPrice' in info:
                current_price = info['regularMarketPrice']
            else:
                # Try to get from fast_info
                try:
                    finfo = stock.fast_info
                    current_price = finfo.last_price
                except Exception as fie:
                    print(f"fast_info fetch failed for {symbol}: {fie}")
                
                # Try to get from history if still None
                if not current_price:
                    hist = stock.history(period='1d')
                    if not hist.empty:
                        current_price = float(hist['Close'].iloc[-1])
            
            # Get company name
            name = info.get('longName') or info.get('shortName') if info else None
            if not name:
                name = symbol.split('.')[0]
            
            if current_price:
                return {
                    'name': name,
                    'price': Decimal(str(current_price))
                }
            return None
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            return None


class BasketResource(resources.ModelResource):
    """
    Resource class for Basket model with import/export functionality.
    """
    user = fields.Field(
        column_name='user',
        attribute='user',
        widget=ForeignKeyWidget(User, field='email')
    )
    
    class Meta:
        model = Basket
        fields = ('id', 'user', 'name', 'description', 'investment_amount', 
                  'created_at', 'updated_at')
        export_order = ('id', 'name', 'user', 'investment_amount', 'description',
                        'created_at', 'updated_at')
        import_id_fields = ['id']
        skip_unchanged = True
        report_skipped = True


class BasketItemResource(resources.ModelResource):
    """
    Resource class for BasketItem model with import/export functionality.
    """
    basket = fields.Field(
        column_name='basket',
        attribute='basket',
        widget=ForeignKeyWidget(Basket, field='name')
    )
    stock = fields.Field(
        column_name='stock',
        attribute='stock',
        widget=ForeignKeyWidget(Stock, field='symbol')
    )
    
    class Meta:
        model = BasketItem
        fields = ('id', 'basket', 'stock', 'weight_percentage', 'allocated_amount',
                  'quantity', 'purchase_price', 'purchase_date')
        export_order = ('id', 'basket', 'stock', 'weight_percentage', 'allocated_amount',
                        'quantity', 'purchase_price', 'purchase_date')
        import_id_fields = ['id']
        skip_unchanged = True
        report_skipped = True


class ChatGroupResource(resources.ModelResource):
    """
    Resource class for ChatGroup model with import/export functionality.
    """
    created_by = fields.Field(
        column_name='created_by',
        attribute='created_by',
        widget=ForeignKeyWidget(User, field='email')
    )
    
    class Meta:
        model = ChatGroup
        fields = ('id', 'name', 'description', 'group_type', 'created_by',
                  'created_at', 'updated_at', 'is_active', 'avatar', 'is_ai_only')
        export_order = ('id', 'name', 'group_type', 'created_by', 'description',
                        'is_active', 'is_ai_only', 'avatar', 'created_at', 'updated_at')
        import_id_fields = ['id']
        skip_unchanged = True
        report_skipped = True


class ChatGroupMemberResource(resources.ModelResource):
    """
    Resource class for ChatGroupMember model with import/export functionality.
    """
    group = fields.Field(
        column_name='group',
        attribute='group',
        widget=ForeignKeyWidget(ChatGroup, field='name')
    )
    user = fields.Field(
        column_name='user',
        attribute='user',
        widget=ForeignKeyWidget(User, field='email')
    )
    
    class Meta:
        model = ChatGroupMember
        fields = ('id', 'group', 'user', 'role', 'joined_at', 'is_active',
                  'notifications_enabled')
        export_order = ('id', 'group', 'user', 'role', 'is_active',
                        'notifications_enabled', 'joined_at')
        import_id_fields = ['id']
        skip_unchanged = True
        report_skipped = True


class ChatMessageResource(resources.ModelResource):
    """
    Resource class for ChatMessage model with import/export functionality.
    """
    group = fields.Field(
        column_name='group',
        attribute='group',
        widget=ForeignKeyWidget(ChatGroup, field='name')
    )
    sender = fields.Field(
        column_name='sender',
        attribute='sender',
        widget=ForeignKeyWidget(User, field='email')
    )
    
    class Meta:
        model = ChatMessage
        fields = ('id', 'group', 'sender', 'content', 'message_type',
                  'created_at', 'updated_at', 'is_read', 'is_deleted')
        export_order = ('id', 'group', 'sender', 'message_type', 'content',
                        'is_read', 'is_deleted', 'created_at', 'updated_at')
        import_id_fields = ['id']
        skip_unchanged = True
        report_skipped = True


class TinyURLResource(resources.ModelResource):
    """
    Resource class for TinyURL model with import/export functionality.
    """
    basket = fields.Field(
        column_name='basket',
        attribute='basket',
        widget=ForeignKeyWidget(Basket, field='name')
    )
    created_by = fields.Field(
        column_name='created_by',
        attribute='created_by',
        widget=ForeignKeyWidget(User, field='email')
    )
    
    class Meta:
        model = TinyURL
        fields = ('id', 'short_code', 'original_url', 'basket', 'created_by',
                  'created_at', 'expires_at', 'click_count', 'is_active')
        export_order = ('id', 'short_code', 'original_url', 'basket', 'created_by',
                        'click_count', 'is_active', 'created_at', 'expires_at')
        import_id_fields = ['short_code']
        skip_unchanged = True
        report_skipped = True


class StockDocumentResource(resources.ModelResource):
    """
    Resource class for StockDocument model with import/export functionality.
    """
    stock = fields.Field(
        column_name='stock',
        attribute='stock',
        widget=ForeignKeyWidget(Stock, field='symbol')
    )
    uploaded_by = fields.Field(
        column_name='uploaded_by',
        attribute='uploaded_by',
        widget=ForeignKeyWidget(User, field='email')
    )

    class Meta:
        model = StockDocument
        fields = (
            'id', 'stock', 'title', 'document_type', 'file', 'uploaded_by',
            'uploaded_at', 'is_indexed', 'chunk_count', 'fiscal_year', 'notes'
        )
        export_order = (
            'id', 'stock', 'title', 'document_type', 'file', 'uploaded_by',
            'uploaded_at', 'is_indexed', 'chunk_count', 'fiscal_year', 'notes'
        )
        import_id_fields = ['id']
        skip_unchanged = True
        report_skipped = True
