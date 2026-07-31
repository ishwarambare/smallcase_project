import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smallcase_project.settings')
django.setup()

from stocks.models import Basket

# Get one specific basket
basket = Basket.objects.get(id=4)  # "Multi" basket for kaka@gmail.com

print(f"Testing basket: {basket.name}")
print(f"User: {basket.user.email if basket.user else 'None'}")
print(f"Investment: {basket.investment_amount}")

# Test the methods
try:
    curr_val = basket.get_current_value()
    print(f"Current Value: {curr_val}")
except Exception as e:
    print(f"ERROR getting current value: {e}")
    import traceback
    traceback.print_exc()

try:
    p_l = basket.get_profit_loss()
    print(f"Profit/Loss: {p_l}")
except Exception as e:
    print(f"ERROR getting profit/loss: {e}")
    import traceback
    traceback.print_exc()

try:
    p_l_pct = basket.get_profit_loss_percentage()
    print(f"Profit/Loss %: {p_l_pct}")
except Exception as e:
    print(f"ERROR getting profit/loss percentage: {e}")
    import traceback
    traceback.print_exc()

# Check items
print("\nBasket items:")
for item in basket.items.all():
    print(f"  - {item.stock.symbol if item.stock else 'NO STOCK'}: {item.quantity} shares")
