# demand_supply/models.py

# pyrefly: ignore [missing-import]
from django.db import models


# ==========================================
# GTF Demand-Supply Zone Models
# ==========================================

class DemandSupplyZone(models.Model):
    """
    Individual demand/supply zone for a stock at a specific timeframe.

    GTF methodology:
      - Demand Zone: base (consolidation) before a strong UP-move
      - Supply Zone: base before a strong DOWN-move
      - Proximal line = edge closest to current price (entry trigger)
      - Distal line = edge furthest from price (stop-loss reference)
    """
    ZONE_TYPE_CHOICES = [
        ('demand', 'Demand Zone'),
        ('supply', 'Supply Zone'),
    ]
    TIMEFRAME_CHOICES = [
        ('quarterly', 'Quarterly'),
        ('monthly', 'Monthly'),
        ('weekly', 'Weekly'),
        ('daily', 'Daily'),
        ('125min', '125-Minute'),
        ('75min', '75-Minute'),
    ]

    symbol = models.CharField(max_length=50, db_index=True)
    zone_type = models.CharField(max_length=10, choices=ZONE_TYPE_CHOICES, db_index=True)
    timeframe = models.CharField(max_length=15, choices=TIMEFRAME_CHOICES, db_index=True)
    proximal_line = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text='Edge of zone closest to current price (entry trigger)'
    )
    distal_line = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text='Edge of zone furthest from current price (stop-loss reference)'
    )
    formed_date = models.DateField(help_text='Date when the zone first formed')
    strength_score = models.FloatField(
        default=0.0,
        help_text='Zone strength score out of 7 (Core) or 14 (Expanded)'
    )
    is_fresh = models.BooleanField(
        default=True,
        help_text='True if price has NOT returned to test the zone since formation'
    )
    base_candle_count = models.IntegerField(
        default=1,
        help_text='Number of candles in the base consolidation (1-5, fewer = stronger)'
    )
    move_pct = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        help_text='Percentage move away from zone on breakout'
    )
    sector = models.CharField(max_length=100, blank=True, db_index=True)
    scan_date = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ['-strength_score']
        indexes = [
            models.Index(fields=['symbol', 'zone_type', 'timeframe']),
            models.Index(fields=['zone_type', '-strength_score']),
            models.Index(fields=['sector', 'zone_type']),
        ]

    def __str__(self):
        return (
            f"{self.symbol} {self.get_zone_type_display()} "
            f"({self.get_timeframe_display()}) "
            f"[{self.proximal_line}-{self.distal_line}] "
            f"Score: {self.strength_score}"
        )


class DemandSupplyScanResult(models.Model):
    """
    Aggregate scan result per stock — the 'screener row'.

    Stores the summary of all zones found for a stock across timeframes,
    plus overlap counts and sector classification.
    Updated each time a scan runs.
    """
    symbol = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=200, blank=True)
    sector = models.CharField(max_length=100, blank=True, db_index=True)
    current_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Key metrics: how many timeframe zones overlap on current price
    demand_overlap_count = models.IntegerField(
        default=0, db_index=True,
        help_text='Number of timeframes where price is in a demand zone (0-6)'
    )
    supply_overlap_count = models.IntegerField(
        default=0, db_index=True,
        help_text='Number of timeframes where price is in a supply zone (0-6)'
    )

    # Per-timeframe demand flags
    quarterly_demand = models.BooleanField(default=False)
    monthly_demand = models.BooleanField(default=False)
    weekly_demand = models.BooleanField(default=False)
    daily_demand = models.BooleanField(default=False)
    min125_demand = models.BooleanField(default=False)
    min75_demand = models.BooleanField(default=False)

    # Per-timeframe supply flags
    quarterly_supply = models.BooleanField(default=False)
    monthly_supply = models.BooleanField(default=False)
    weekly_supply = models.BooleanField(default=False)
    daily_supply = models.BooleanField(default=False)
    min125_supply = models.BooleanField(default=False)
    min75_supply = models.BooleanField(default=False)

    # Strongest zone score across all timeframes
    strongest_zone_score = models.FloatField(
        default=0.0, db_index=True,
        help_text='Highest zone strength score out of 7/14 across all detected zones'
    )

    # Full zone details as JSON (for UI rendering)
    zone_details = models.JSONField(
        default=dict, blank=True,
        help_text='Full JSON of all demand/supply zones for chart rendering'
    )

    scan_timestamp = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ['-demand_overlap_count', '-strongest_zone_score']
        indexes = [
            models.Index(fields=['-demand_overlap_count', '-strongest_zone_score']),
            models.Index(fields=['sector', '-demand_overlap_count']),
            models.Index(fields=['-supply_overlap_count']),
        ]

    def __str__(self):
        return (
            f"{self.symbol} — Demand×{self.demand_overlap_count} "
            f"Supply×{self.supply_overlap_count} "
            f"Score: {self.strongest_zone_score}"
        )

    def to_dict(self):
        """Serializable dict for API responses."""
        return {
            'symbol': self.symbol,
            'name': self.name,
            'sector': self.sector,
            'current_price': float(self.current_price) if self.current_price else None,
            'demand_overlap_count': self.demand_overlap_count,
            'supply_overlap_count': self.supply_overlap_count,
            'quarterly_demand': self.quarterly_demand,
            'monthly_demand': self.monthly_demand,
            'weekly_demand': self.weekly_demand,
            'daily_demand': self.daily_demand,
            'min125_demand': self.min125_demand,
            'min75_demand': self.min75_demand,
            'quarterly_supply': self.quarterly_supply,
            'monthly_supply': self.monthly_supply,
            'weekly_supply': self.weekly_supply,
            'daily_supply': self.daily_supply,
            'min125_supply': self.min125_supply,
            'min75_supply': self.min75_supply,
            'strongest_zone_score': self.strongest_zone_score,
            'zone_details': self.zone_details,
            'scan_timestamp': self.scan_timestamp.isoformat() if self.scan_timestamp else None,
        }
