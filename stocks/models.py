# stocks/models.py

from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

# Get the User model (which is now in the user app)
User = get_user_model()


class Stock(models.Model):
    """Model to store stock information"""
    symbol = models.CharField(max_length=20, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    current_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True, db_index=True)

    def __str__(self):
        return f"{self.symbol} - {self.name}"

    class Meta:
        ordering = ['symbol']
        indexes = [
            models.Index(fields=['symbol']),
            models.Index(fields=['last_updated']),
        ]


class Basket(models.Model):
    """Model to store stock baskets"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='baskets', null=True, blank=True, db_index=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    investment_amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_default = models.BooleanField(default=False, db_index=True, help_text="Set to True to show this basket on all users' dashboards")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    def __str__(self):
        return self.name

    def get_total_value(self):
        """Calculate total current value of basket"""
        # OPTIMIZATION: Access prefetched items if available
        if hasattr(self, '_prefetched_objects_cache') and 'items' in self._prefetched_objects_cache:
            items = self.items.all()
        else:
            items = self.items.select_related('stock').all()
        
        total = sum(item.get_current_value() for item in items)
        return total

    def get_profit_loss(self):
        """Calculate profit/loss"""
        current_value = self.get_total_value()
        return int(current_value) - int(self.investment_amount)

    def get_profit_loss_percentage(self):
        """Calculate profit/loss percentage"""
        if self.investment_amount > 0:
            return (self.get_profit_loss() / self.investment_amount) * 100
        return 0
    
    class Meta:
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['updated_at']),
        ]


class BasketItem(models.Model):
    """Model to store individual stocks in a basket with equal weight"""
    basket = models.ForeignKey(Basket, on_delete=models.CASCADE, related_name='items')
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE)
    weight_percentage = models.DecimalField(max_digits=5, decimal_places=2)  # Equal weight
    allocated_amount = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.DecimalField(max_digits=10, decimal_places=4)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2)
    purchase_date = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.basket.name} - {self.stock.symbol}"

    def get_current_value(self):
        """Calculate current value of this stock in basket"""
        if self.stock.current_price:
            return float(self.quantity) * float(self.stock.current_price)
        return float(self.allocated_amount)

    def get_profit_loss(self):
        """Calculate profit/loss for this stock"""
        return self.get_current_value() - float(self.allocated_amount)

    class Meta:
        unique_together = ['basket', 'stock']
        ordering = ['stock__symbol']
        indexes = [
            models.Index(fields=['basket', 'stock']),
        ]


# ==========================================
# Chat Models for Group Messaging
# ==========================================

class ChatGroup(models.Model):
    """Model to store chat groups for group messaging"""
    GROUP_TYPE_CHOICES = [
        ('support', 'Support Chat'),
        ('group', 'Group Chat'),
        ('direct', 'Direct Message'),
    ]
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    group_type = models.CharField(max_length=20, choices=GROUP_TYPE_CHOICES, default='support')
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='created_chat_groups'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    avatar = models.CharField(max_length=10, default='👥')  # Emoji avatar
    is_ai_only = models.BooleanField(default=False)  # True for AI-only support chats
    
    def __str__(self):
        return f"{self.name} ({self.get_group_type_display()})"
    
    def get_members_count(self):
        return self.members.filter(is_active=True).count()
    
    def get_last_message(self):
        return self.messages.order_by('-created_at').first()
    
    def get_unread_count(self, user):
        """Get count of unread messages for a specific user"""
        return self.messages.exclude(sender=user).filter(is_read=False).count()
    
    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['group_type']),
        ]


class ChatGroupMember(models.Model):
    """Model to store group membership"""
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('moderator', 'Moderator'),
        ('member', 'Member'),
    ]
    
    group = models.ForeignKey(ChatGroup, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_group_memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    notifications_enabled = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.user.email} in {self.group.name}"
    
    class Meta:
        unique_together = ['group', 'user']
        ordering = ['joined_at']
        indexes = [
            models.Index(fields=['group', 'user']),
        ]


class ChatMessage(models.Model):
    """Model to store chat messages"""
    MESSAGE_TYPE_CHOICES = [
        ('text', 'Text Message'),
        ('system', 'System Message'),
        ('notification', 'Notification'),
    ]
    
    group = models.ForeignKey(ChatGroup, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='sent_messages'
    )
    content = models.TextField()
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, default='text')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_read = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    
    # For replies
    reply_to = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='replies'
    )
    
    def __str__(self):
        sender_name = self.sender.email if self.sender else 'System'
        return f"{sender_name}: {self.content[:50]}..."
    
    def get_sender_name(self):
        if self.sender:
            return self.sender.username or self.sender.email.split('@')[0]
        return 'Support Team'
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['group', '-created_at']),
            models.Index(fields=['sender']),
        ]


# ==========================================
# URL Shortening for Basket Sharing
# ==========================================

class TinyURL(models.Model):
    """Model to store shortened URLs for basket sharing"""
    short_code = models.CharField(max_length=10, unique=True, db_index=True)
    original_url = models.URLField(max_length=500)
    basket = models.ForeignKey(
        Basket, 
        on_delete=models.CASCADE, 
        related_name='tiny_urls',
        null=True,
        blank=True
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_tiny_urls'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    click_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.short_code} -> {self.original_url[:50]}"
    
    def is_expired(self):
        """Check if the URL has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    def increment_clicks(self):
        """Increment the click counter"""
        self.click_count += 1
        self.save(update_fields=['click_count'])
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['short_code']),
            models.Index(fields=['-created_at']),
        ]


# ==========================================
# Financial Document RAG (Retrieval-Augmented Generation)
# ==========================================

class StockDocument(models.Model):
    """
    Model to store uploaded financial documents (PDFs) for RAG querying.
    Users/admins upload earnings call transcripts, annual reports, etc.
    The rag_service.py pipeline indexes these into ChromaDB.
    """
    DOCUMENT_TYPE_CHOICES = [
        ('annual_report', 'Annual Report'),
        ('earnings_call', 'Earnings Call Transcript'),
        ('investor_presentation', 'Investor Presentation'),
        ('research_report', 'Research Report'),
        ('other', 'Other'),
    ]

    stock = models.ForeignKey(
        Stock,
        on_delete=models.CASCADE,
        related_name='documents',
        db_index=True,
    )
    title = models.CharField(max_length=300)
    document_type = models.CharField(
        max_length=30,
        choices=DOCUMENT_TYPE_CHOICES,
        default='other',
        db_index=True,
    )
    file = models.FileField(upload_to='stock_documents/%Y/%m/')
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_documents',
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_indexed = models.BooleanField(default=False, db_index=True)
    chunk_count = models.IntegerField(default=0)
    fiscal_year = models.CharField(max_length=10, blank=True, help_text="e.g. FY2025 or Q2-2025")
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.stock.symbol} — {self.title} ({self.get_document_type_display()})"

    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['stock', 'document_type']),
            models.Index(fields=['is_indexed']),
        ]


class DocumentChunk(models.Model):
    """
    Model to store text chunks and their embeddings for StockDocuments.
    Used for RAG (Retrieval-Augmented Generation) query matching.
    """
    document = models.ForeignKey(
        StockDocument,
        on_delete=models.CASCADE,
        related_name='chunks',
        db_index=True,
    )
    chunk_index = models.IntegerField()
    content = models.TextField()
    embedding = models.JSONField(help_text="Embedding vector as a list of floats")

    class Meta:
        ordering = ['chunk_index']
        unique_together = ['document', 'chunk_index']
        indexes = [
            models.Index(fields=['document']),
        ]

    def __str__(self):
        return f"Chunk {self.chunk_index} of {self.document.title}"


# ==========================================
# Real-Time Market Data (Webhook Ticks)
# ==========================================

class MarketTick(models.Model):
    """
    Stores the latest real-time tick for each symbol received from
    Fyers postback webhook or DhanHQ live data.
    Used for page-reload recovery (browser fetches last tick on connect).
    """
    SOURCE_CHOICES = [
        ('fyers', 'Fyers API'),
        ('dhan', 'DhanHQ'),
        ('manual', 'Manual / Test'),
    ]

    symbol = models.CharField(max_length=50, unique=True, db_index=True)
    ltp = models.DecimalField(
        max_digits=12, decimal_places=4,
        help_text="Last Traded Price"
    )
    open_price = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    high_price = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    low_price = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    prev_close = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    volume = models.BigIntegerField(default=0)
    change = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True,
        help_text="Absolute change from prev close"
    )
    change_pct = models.DecimalField(
        max_digits=8, decimal_places=4, null=True, blank=True,
        help_text="Percentage change from prev close"
    )
    timestamp = models.DateTimeField(
        auto_now=True, db_index=True,
        help_text="Last updated time (auto-set on save)"
    )
    source = models.CharField(
        max_length=20, choices=SOURCE_CHOICES, default='fyers',
        db_index=True
    )
    raw_payload = models.JSONField(
        null=True, blank=True,
        help_text="Raw JSON received from the webhook for debugging"
    )

    class Meta:
        ordering = ['symbol']
        indexes = [
            models.Index(fields=['symbol']),
            models.Index(fields=['-timestamp']),
            models.Index(fields=['source']),
        ]

    def __str__(self):
        return f"{self.symbol} @ {self.ltp} ({self.source})"

    def to_dict(self):
        """Return a serializable dict for WebSocket broadcasting."""
        return {
            'symbol': self.symbol,
            'ltp': float(self.ltp),
            'open': float(self.open_price) if self.open_price else None,
            'high': float(self.high_price) if self.high_price else None,
            'low': float(self.low_price) if self.low_price else None,
            'prev_close': float(self.prev_close) if self.prev_close else None,
            'volume': self.volume,
            'change': float(self.change) if self.change else None,
            'change_pct': float(self.change_pct) if self.change_pct else None,
            'source': self.source,
        }


# ==========================================
# 4-Agent Annual Report Analysis Pipeline
# ==========================================

class AnalysisJob(models.Model):
    """
    Tracks a single 4-agent AI analysis run for a stock's annual report.

    Lifecycle:
        pending → ingesting → analyzing → done / error

    Each agent (Quant, News, Governance, CIO) writes its JSON result
    to the corresponding field as it completes. The Django frontend
    polls /api/ai/annual-report/status/<id>/ to stream progress.
    """

    STATUS_CHOICES = [
        ('pending',   'Pending — queued, not yet started'),
        ('ingesting', 'Ingesting PDF into ChromaDB'),
        ('analyzing', 'Agents Running'),
        ('done',      'Analysis Complete'),
        ('error',     'Error'),
    ]

    # Linked stock and optional source document
    stock    = models.ForeignKey(
        Stock,
        on_delete=models.CASCADE,
        related_name='analysis_jobs',
        db_index=True,
    )
    document = models.ForeignKey(
        StockDocument,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='analysis_jobs',
        help_text='The PDF document that triggered this analysis (optional if re-using indexed data).',
    )

    # Job tracking
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    celery_task_id  = models.CharField(max_length=255, blank=True, db_index=True)
    current_step    = models.CharField(max_length=100, blank=True,
                                       help_text='Human-readable progress message shown in the UI.')

    # ── Per-agent results (populated as each agent finishes) ──
    agent_thoughts    = models.JSONField(default=list, blank=True, 
                                         help_text='List of intermediate thoughts and steps from the agents')
    quant_result      = models.JSONField(null=True, blank=True,
                                         help_text='Agent 1 Quant: ROCE, D/E, P/E, Revenue CAGR, verdict.')
    news_result       = models.JSONField(null=True, blank=True,
                                         help_text='Agent 2 News: headlines, sentiment score, summary.')
    governance_result = models.JSONField(null=True, blank=True,
                                         help_text='Agent 3 Governance: management commentary, red flags.')
    final_decision    = models.JSONField(null=True, blank=True,
                                         help_text='Agent 4 CIO: final BUY/HOLD/SELL decision + reasoning.')

    # Metadata
    error_message = models.TextField(blank=True)
    created_at    = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['stock', '-created_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"AnalysisJob #{self.pk} — {self.stock.symbol} [{self.get_status_display()}]"

    def to_status_dict(self):
        """Serializable dict for the status-polling API endpoint."""
        return {
            'id': self.pk,
            'symbol': self.stock.symbol,
            'status': self.status,
            'current_step': self.current_step,
            'agent_thoughts': self.agent_thoughts,
            'quant_result': self.quant_result,
            'news_result': self.news_result,
            'governance_result': self.governance_result,
            'final_decision': self.final_decision,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }



# ==========================================
# GTF Demand-Supply Zone Models
# ==========================================
# DemandSupplyZone and DemandSupplyScanResult have been moved to the
# dedicated `demand_supply` app → demand_supply/models.py
