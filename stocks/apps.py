# stocks/apps.py

from django.apps import AppConfig
import sys
import os
import threading


class StocksConfig(AppConfig):
    name = 'stocks'

    def ready(self):
        # Skip for common management commands that shouldn't trigger data loading
        skip_commands = {'migrate', 'makemigrations', 'collectstatic', 'createsuperuser', 'test', 'check'}
        cmd = sys.argv[1] if len(sys.argv) > 1 else None
        if cmd in skip_commands:
            return

        # Avoid running in the parent reload process of Django runserver
        if cmd == 'runserver' and os.environ.get('RUN_MAIN') != 'true':
            return

        # Import inside ready() to avoid circular imports / AppRegistryNotReady
        from .auto_import import auto_import_stocks
        
        # Spawn in a background thread so it doesn't block server startup
        threading.Thread(target=auto_import_stocks, daemon=True).start()

