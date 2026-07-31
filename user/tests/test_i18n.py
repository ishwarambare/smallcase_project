"""
Quick test script to verify i18n setup
Run this to check if everything is configured correctly
"""

import os
import sys
from pathlib import Path

# Add project to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smallcase_project.settings')
import django
django.setup()

from django.conf import settings
from django.utils import translation

def test_i18n():
    print("=" * 60)
    print("Testing Multi-Language Setup")
    print("=" * 60)
    
    # Test 1: Check settings
    print("\n1. Checking Settings...")
    print(f"   ✓ USE_I18N: {settings.USE_I18N}")
    print(f"   ✓ LANGUAGE_CODE: {settings.LANGUAGE_CODE}")
    print(f"   ✓ LANGUAGES: {settings.LANGUAGES}")
    print(f"   ✓ LOCALE_PATHS: {settings.LOCALE_PATHS}")
    
    # Test 2: Check locale directories
    print("\n2. Checking Locale Directories...")
    for lang_code, lang_name in settings.LANGUAGES[1:]:  # Skip English
        po_file = BASE_DIR / 'locale' / lang_code / 'LC_MESSAGES' / 'django.po'
        mo_file = BASE_DIR / 'locale' / lang_code / 'LC_MESSAGES' / 'django.mo'
        
        if po_file.exists():
            print(f"   ✓ {lang_name} .po file exists")
        else:
            print(f"   ✗ {lang_name} .po file missing!")
            
        if mo_file.exists():
            print(f"   ✓ {lang_name} .mo file exists (compiled)")
        else:
            print(f"   ✗ {lang_name} .mo file missing! Run: python compile_messages.py")
    
    # Test 3: Test translations
    print("\n3. Testing Translations...")
    from django.utils.translation import gettext as _
    
    test_strings = [
        'Dashboard',
        'Create Basket',
        'Login',
        'Logout',
    ]
    
    for lang_code, lang_name in settings.LANGUAGES:
        translation.activate(lang_code)
        print(f"\n   {lang_name} ({lang_code}):")
        for string in test_strings:
            translated = _(string)
            print(f"      '{string}' → '{translated}'")
    
    translation.deactivate()
    
    # Test 4: Check middleware
    print("\n4. Checking Middleware...")
    middleware = settings.MIDDLEWARE
    if 'django.middleware.locale.LocaleMiddleware' in middleware:
        print("   ✓ LocaleMiddleware is configured")
    else:
        print("   ✗ LocaleMiddleware is missing!")
    
    print("\n" + "=" * 60)
    print("✅ Multi-Language Setup Test Complete!")
    print("=" * 60)
    print("\nNext Steps:")
    print("1. Restart your server if it's running")
    print("2. Visit: http://localhost:1234/en/i18n-demo/")
    print("3. Click the language switcher and try Hindi/Marathi")
    print("\n")

if __name__ == '__main__':
    test_i18n()
