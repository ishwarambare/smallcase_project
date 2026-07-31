import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smallcase_project.settings')
django.setup()

from stocks.models import Basket
from django.contrib.auth import get_user_model
from stocks.ai_service import ai_service

User = get_user_model()

# Test with user kaka@gmail.com (ID=8)
user = User.objects.get(id=8)
print(f"\n=== Testing AI Service for {user.email} ===\n")

# Check baskets
baskets = Basket.objects.filter(user=user)
print(f"Baskets in DB: {baskets.count()}")
for b in baskets:
    print(f"  - {b.name}")

# Generate AI response
print("\n=== Generating AI Response ===\n")
response = ai_service.generate_response("How is my portfolio doing?", user)
print(f"\nAI Response:\n{response}")
