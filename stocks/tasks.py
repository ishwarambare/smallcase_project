"""
stocks/tasks.py

NOTE: Demand-supply Celery tasks have been moved to the `demand_supply` app.
This module re-exports the task for backward compatibility with any code that
imports from `stocks.tasks`.

Use the new import path:
    from demand_supply.tasks import scan_demand_supply_zones
"""

# Re-export for backward compatibility
from demand_supply.tasks import scan_demand_supply_zones  # noqa: F401

__all__ = ['scan_demand_supply_zones']
