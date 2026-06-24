import os
import csv
from django.db import connection, connections
from django.conf import settings
from .models import Stock

def auto_import_stocks():
    """
    Reads stocks from sample_stocks.csv, checks which ones are not in the database,
    and bulk imports them. Then runs a bulk price update for new stocks.
    Runs inside a background thread on startup to prevent blocking the server.
    """
    # 1. Safely check if the Stock table exists in the database.
    # This prevents crashes during migrations or tests.
    table_name = Stock._meta.db_table
    if table_name not in connection.introspection.table_names():
        return
        
    csv_path = os.path.join(settings.BASE_DIR, 'sample_stocks.csv')
    if not os.path.exists(csv_path):
        print(f"[AutoImport] sample_stocks.csv not found at {csv_path}. Skipping.")
        return
        
    try:
        stocks_to_create = []
        # Query all existing symbols to prevent duplicates
        existing_symbols = set(Stock.objects.values_list('symbol', flat=True))
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            
            # Read first row to check for header
            first_row = next(reader, None)
            if first_row:
                cleaned_first = [col.strip().lower() for col in first_row]
                if 'symbol' in cleaned_first:
                    # It is a header row
                    symbol_idx = cleaned_first.index('symbol')
                    name_idx = cleaned_first.index('name') if 'name' in cleaned_first else -1
                else:
                    # No header, treat first row as data and reset file pointer
                    symbol_idx = 0
                    name_idx = -1
                    f.seek(0)
                    reader = csv.reader(f)
                
            for row in reader:
                if not row or len(row) <= symbol_idx:
                    continue
                raw_symbol = row[symbol_idx].strip()
                if not raw_symbol or raw_symbol.lower() in ['symbol', 'none', 'nan', '']:
                    continue
                    
                # Format symbol (append .NS if not already present)
                symbol = raw_symbol
                if not symbol.endswith('.NS') and not symbol.endswith('.BO'):
                    symbol = f"{symbol}.NS"
                    
                if symbol not in existing_symbols:
                    name = row[name_idx].strip() if (name_idx != -1 and len(row) > name_idx) else raw_symbol
                    stocks_to_create.append(Stock(
                        symbol=symbol,
                        name=name or raw_symbol,
                        current_price=None
                    ))
                    
        if stocks_to_create:
            print(f"[AutoImport] Found {len(stocks_to_create)} new stocks to import. Writing to database...")
            Stock.objects.bulk_create(stocks_to_create)
            print(f"[AutoImport] Successfully auto-imported {len(stocks_to_create)} stocks.")
            
            # Fetch current prices in bulk for these new stocks
            from .utils import update_stock_prices_bulk
            new_symbols = [s.symbol for s in stocks_to_create]
            
            print(f"[AutoImport] Fetching initial prices for {len(new_symbols)} new stocks in bulk...")
            update_stock_prices_bulk(new_symbols)
            print("[AutoImport] Initial price fetch completed.")
            
    except Exception as e:
        print(f"[AutoImport] Error during auto stock import: {e}")
    finally:
        # Close connection to prevent thread connection leaks
        connections.close_all()
