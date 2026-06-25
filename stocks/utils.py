# stocks/utils.py

import yfinance as yf
from decimal import Decimal
from .models import Stock

# Popular Indian stocks (NSE symbols - add .NS suffix for yfinance)
INDIAN_STOCKS = {
    'RELIANCE.NS': 'Reliance Industries',
    'TCS.NS': 'Tata Consultancy Services',
    'HDFCBANK.NS': 'HDFC Bank',
    'INFY.NS': 'Infosys',
    'ICICIBANK.NS': 'ICICI Bank',
    'HINDUNILVR.NS': 'Hindustan Unilever',
    'BHARTIARTL.NS': 'Bharti Airtel',
    'ITC.NS': 'ITC Limited',
    'SBIN.NS': 'State Bank of India',
    'LT.NS': 'Larsen & Toubro',
    'AXISBANK.NS': 'Axis Bank',
    'KOTAKBANK.NS': 'Kotak Mahindra Bank',
    'BAJFINANCE.NS': 'Bajaj Finance',
    'ASIANPAINT.NS': 'Asian Paints',
    'MARUTI.NS': 'Maruti Suzuki',
    'TITAN.NS': 'Titan Company',
    'SUNPHARMA.NS': 'Sun Pharmaceutical',
    'WIPRO.NS': 'Wipro',
    'HCLTECH.NS': 'HCL Technologies',
    'ULTRACEMCO.NS': 'UltraTech Cement',
    'CGPOWER.NS': 'CG Power & Industrial Solutions',
    'AUROPHARMA.NS': 'Aurobindo Pharma',
    'CAMS.NS': 'CAMS',
    'CDSL.NS': 'CDSL',
    'CHALET.NS': 'Chalet Hotels',
    'KAYNES.NS': 'Kaynes Technology India',
    'LUPIN.NS': 'Lupin',
    'PERSISTENT.NS': 'Persistent Systems',
    'POWERGRID.NS': 'Power Grid Corporation of India',
    'PRICOLLTD.NS': 'Pricol',
    'THYROCARE.NS': 'Thyrocare Technologies',
    'UNITDSPR.NS': 'United Spirits',
    'TARIL.NS': 'Transformers & Rectifiers',
    'MAZDOCK.NS': 'Mazagon Dock Shipbuilding',
    'GRSE.NS': 'Garden Reach Shipbuilders', 
    'COFORGE.NS': 'Coforge', 
    'INDHOTEL.NS': 'Indian Hotels Company', 
    'HEROMOTOCO.NS': 'Hero Motocorp', 
    'LT.NS': 'Larsen & Toubro', 
    'RELIANCE.NS': 'Reliance Industries', 
    'CHAMBLFERT.NS': 'Chambal Fertilisers & Chemicals', 
    'BEL.NS': 'Bharat Electronics', 
    'INDIGO.NS': 'Interglobe Aviation', 
    'BHARTIARTL.NS': 'Bharti Airtel'
}

# Indian market indices
INDIAN_INDICES = {
    '^NSEI': 'Nifty 50',
    '^NSEBANK': 'Nifty Bank',
    '^BSESN': 'Sensex',
}

# Time period mappings for yfinance
TIME_PERIODS = {
    '1d': '1d',
    '7d': '7d',
    '1m': '1mo',
    '3m': '3mo',
    '6m': '6mo',
    '1y': '1y',
    '3y': '3y',
    '5y': '5y',
}


def fetch_index_historical_data(index_symbol, period='1mo'):
    """
    Fetch historical data for an index
    
    Args:
        index_symbol: Index ticker (e.g., '^NSEI' for Nifty 50)
        period: Time period - '1d', '7d', '1m', '3m', '6m', '1y', '3y', '5y'
    
    Returns:
        List of {date, value} dictionaries
    """
    import math, pandas as pd
    try:
        yf_period = TIME_PERIODS.get(period, '1mo')
        df = yf.download(index_symbol, period=yf_period, progress=False, auto_adjust=True)

        if df.empty:
            return []

        # yfinance now returns MultiIndex even for single tickers: (field, ticker)
        if isinstance(df.columns, pd.MultiIndex):
            close_col = ('Close', index_symbol)
            if close_col not in df.columns:
                # Try finding Close column regardless of ticker label
                close_cols = [c for c in df.columns if c[0] == 'Close']
                if not close_cols:
                    return []
                close_col = close_cols[0]
            close_series = df[close_col].dropna()
        else:
            close_series = df['Close'].dropna()

        result = []
        for date, value in close_series.items():
            price = float(value)
            if not math.isnan(price) and price > 0:
                result.append({'date': date.strftime('%Y-%m-%d'), 'value': price})
        return result
    except Exception as e:
        print(f"Error fetching index data for {index_symbol}: {e}")
        return []


def fetch_stock_historical_data(symbol, period='1mo'):
    """
    Fetch historical data for a stock
    
    Args:
        symbol: Stock ticker (e.g., 'RELIANCE.NS')
        period: Time period - '1d', '7d', '1m', '3m', '6m', '1y', '3y', '5y'
    
    Returns:
        List of {date, value} dictionaries
    """
    import math, pandas as pd
    try:
        yf_period = TIME_PERIODS.get(period, '1mo')
        df = yf.download(symbol, period=yf_period, progress=False, auto_adjust=True)

        if df.empty:
            return []

        # yfinance now returns MultiIndex even for single tickers: (field, ticker)
        if isinstance(df.columns, pd.MultiIndex):
            close_col = ('Close', symbol)
            if close_col not in df.columns:
                close_cols = [c for c in df.columns if c[0] == 'Close']
                if not close_cols:
                    return []
                close_col = close_cols[0]
            close_series = df[close_col].dropna()
        else:
            close_series = df['Close'].dropna()

        result = []
        for date, value in close_series.items():
            price = float(value)
            if not math.isnan(price) and price > 0:
                result.append({'date': date.strftime('%Y-%m-%d'), 'value': price})
        return result
    except Exception as e:
        print(f"Error fetching stock data for {symbol}: {e}")
        return []


def calculate_basket_historical_performance(basket, period='1mo'):
    """
    Calculate historical performance of a basket
    
    Args:
        basket: Basket model instance
        period: Time period
    
    Returns:
        List of {date, value} dictionaries representing basket value over time
    """
    from .models import BasketItem
    
    items = basket.items.all()
    if not items:
        return []
    
    # Fetch historical data for all stocks in basket
    stock_histories = {}
    for item in items:
        hist_data = fetch_stock_historical_data(item.stock.symbol, period)
        if hist_data:
            stock_histories[item.stock.symbol] = hist_data
    
    if not stock_histories:
        return []

    # Build fast date->price lookup per symbol
    symbol_lookup = {}
    for sym, hist_data in stock_histories.items():
        symbol_lookup[sym] = {point['date']: point['value'] for point in hist_data}

    # Collect union of all dates
    all_dates = set()
    for date_map in symbol_lookup.values():
        all_dates.update(date_map.keys())

    basket_performance = []

    for date in sorted(all_dates):
        total_value = 0
        covered_weight = 0

        for item in items:
            symbol = item.stock.symbol
            date_map = symbol_lookup.get(symbol, {})
            price = date_map.get(date)
            if price is not None:
                total_value += float(item.quantity) * price
                covered_weight += float(item.weight_percentage)

        # Include date if we have data for at least 80% of the basket weight
        if covered_weight >= 80 and total_value > 0:
            basket_performance.append({'date': date, 'value': total_value})

    return basket_performance


def fetch_stock_price(symbol):
    """
    Fetch current stock price using yfinance
    Returns price or None if failed
    """
    try:
        stock = yf.Ticker(symbol)
        data = stock.history(period='1d')
        if not data.empty:
            return float(data['Close'].iloc[-1])
        return None
    except Exception as e:
        print(f"Error fetching price for {symbol}: {e}")
        return None


def update_stock_prices_bulk(symbols):
    """
    Update prices for multiple stocks in bulk using yfinance.
    Processes in batches of 50 to stay within API limits.
    Skips NaN/invalid prices gracefully.

    Args:
        symbols: List of stock symbols to update (with .NS or .BO suffix)

    Returns:
        Number of stocks updated
    """
    import math
    import pandas as pd

    if not symbols:
        return 0

    updated_count = 0
    batch_size = 50
    batches = [symbols[i:i + batch_size] for i in range(0, len(symbols), batch_size)]

    for batch_num, batch in enumerate(batches):
        try:
            batch_str = ' '.join(batch)
            data = yf.download(batch_str, period='2d', group_by='ticker', progress=False, auto_adjust=True)

            if data.empty:
                continue

            # Determine if result is single-ticker (flat columns) or multi-ticker (MultiIndex)
            is_multi = isinstance(data.columns, pd.MultiIndex)

            for symbol in batch:
                try:
                    if is_multi:
                        # Multi-ticker: columns are (ticker, field) — Level 0 = ticker, Level 1 = field
                        if symbol not in data.columns.get_level_values(0):
                            continue
                        ticker_data = data.xs(symbol, axis=1, level=0)
                    else:
                        # Single-ticker: flat columns like 'Close'
                        ticker_data = data

                    if ticker_data.empty or 'Close' not in ticker_data.columns:
                        continue

                    # Get last valid (non-NaN) close price
                    close_series = ticker_data['Close'].dropna()
                    if close_series.empty:
                        continue

                    price = float(close_series.iloc[-1])
                    if math.isnan(price) or math.isinf(price) or price <= 0:
                        continue

                    Stock.objects.filter(symbol=symbol).update(
                        current_price=Decimal(str(round(price, 2)))
                    )
                    updated_count += 1

                except Exception:
                    continue

        except Exception as e:
            print(f"[PriceFetch] Batch {batch_num + 1} failed: {e}")
            # Fallback: fetch one-by-one for failed batch
            for symbol in batch:
                try:
                    price = fetch_stock_price(symbol)
                    if price and not math.isnan(price) and price > 0:
                        Stock.objects.filter(symbol=symbol).update(
                            current_price=Decimal(str(round(price, 2)))
                        )
                        updated_count += 1
                except Exception:
                    continue

    print(f"[PriceFetch] Updated prices for {updated_count} / {len(symbols)} stocks")
    return updated_count


def update_stock_prices():
    """Update prices for all stocks in database (with 5-minute cache)"""
    from datetime import datetime, timedelta
    from django.utils import timezone
    
    stocks = Stock.objects.all()
    
    # Filter stocks that need updating (no price or stale price)
    stale_stocks = []
    for stock in stocks:
        should_update = False
        if not stock.current_price:
            should_update = True
        elif stock.last_updated and stock.last_updated < timezone.now() - timedelta(minutes=5):
            should_update = True
        
        if should_update:
            stale_stocks.append(stock.symbol)
    
    if not stale_stocks:
        print("All stock prices are up to date")
        return 0
    
    # OPTIMIZATION: Use bulk update instead of individual fetches
    updated_count = update_stock_prices_bulk(stale_stocks)
    
    print(f"Updated {updated_count} stock prices")
    return updated_count


def populate_indian_stocks():
    """Populate database with Indian stocks"""
    created_count = 0
    for symbol, name in INDIAN_STOCKS.items():
        stock, created = Stock.objects.get_or_create(
            symbol=symbol,
            defaults={'name': name}
        )
        if created:
            created_count += 1
            # Fetch initial price
            price = fetch_stock_price(symbol)
            if price:
                stock.current_price = Decimal(str(price))
                stock.save()
    return created_count


def calculate_equal_weight_basket(stock_symbols, investment_amount):
    """
    Calculate equal weight allocation for selected stocks

    Args:
        stock_symbols: List of stock symbols
        investment_amount: Total amount to invest

    Returns:
        List of dictionaries with stock allocation details
    """
    if not stock_symbols:
        return []

    num_stocks = len(stock_symbols)
    weight_per_stock = Decimal('100.00') / num_stocks
    amount_per_stock = Decimal(str(investment_amount)) / num_stocks

    allocations = []

    for symbol in stock_symbols:
        try:
            stock = Stock.objects.get(symbol=symbol)

            # Fetch latest price if not available
            if not stock.current_price:
                price = fetch_stock_price(symbol)
                if price:
                    stock.current_price = Decimal(str(price))
                    stock.save()

            if stock.current_price and stock.current_price > 0:
                # Calculate quantity as whole number
                quantity = int(amount_per_stock / stock.current_price)
                
                # Recalculate actual allocated amount based on whole quantity
                actual_allocated_amount = quantity * stock.current_price
                
                # Recalculate actual weight based on actual allocated amount
                actual_weight = (actual_allocated_amount / Decimal(str(investment_amount))) * 100

                allocations.append({
                    'stock': stock,
                    'weight_percentage': actual_weight,
                    'allocated_amount': actual_allocated_amount,
                    'quantity': quantity,
                    'price': stock.current_price,
                })
        except Stock.DoesNotExist:
            continue

    return allocations


def create_basket_with_stocks(name, description, investment_amount, stock_symbols, user=None):
    """
    Create a basket with equal-weighted stocks (quantities as whole numbers)

    Args:
        name: Basket name
        description: Basket description
        investment_amount: Total investment amount
        stock_symbols: List of stock symbols to include
        user: User who owns the basket (optional for backward compatibility)

    Returns:
        Basket object
    """
    from .models import Basket, BasketItem

    # Calculate allocations
    allocations = calculate_equal_weight_basket(stock_symbols, investment_amount)

    if not allocations:
        return None

    # Create basket
    basket = Basket.objects.create(
        name=name,
        description=description,
        investment_amount=Decimal(str(investment_amount)),
        user=user
    )

    # Create basket items with whole number quantities
    total_allocated = Decimal('0')
    
    for alloc in allocations:
        BasketItem.objects.create(
            basket=basket,
            stock=alloc['stock'],
            weight_percentage=alloc['weight_percentage'],
            allocated_amount=alloc['allocated_amount'],
            quantity=alloc['quantity'],  # Already an integer
            purchase_price=alloc['price']
        )
        total_allocated += alloc['allocated_amount']

    # Update basket investment amount to actual total
    if total_allocated > 0:
        basket.investment_amount = total_allocated
        basket.save()
        
        # Recalculate weights to ensure they sum to 100% relative to actual investment
        for item in basket.items.all():
            item.weight_percentage = (item.allocated_amount / total_allocated) * 100
            item.save()

    return basket


def remove_stock_from_basket(basket_id, stock_id):
    """
    Remove a stock from a basket and recalculate all values
    
    IMPORTANT: This only removes the BasketItem relationship. The Stock object 
    itself remains in the database and can still be used by other baskets.
    
    This function removes a specific stock from a basket and automatically:
    - Removes the BasketItem entry
    - Recalculates the total investment amount
    - Redistributes weight percentages equally among remaining stocks
    - Updates allocated amounts for remaining stocks
    
    Args:
        basket_id: ID of the basket
        stock_id: ID of the stock to remove
    
    Returns:
        Dictionary with:
            - success: Boolean indicating if deletion was successful
            - message: Success or error message
            - basket: Updated basket object (if successful)
            - deleted_amount: Amount that was removed from basket
    """
    from .models import Basket, BasketItem
    
    try:
        # Get the basket
        basket = Basket.objects.get(id=basket_id)
        
        # Get the basket item to delete
        basket_item = BasketItem.objects.get(basket=basket, stock_id=stock_id)
        
        # Store the allocated amount before removal
        deleted_amount = basket_item.allocated_amount
        deleted_stock_name = basket_item.stock.name
        
        # Remove the basket item (only the relationship, not the Stock object)
        basket_item.delete()
        
        # Get remaining items
        remaining_items = basket.items.all()
        
        if remaining_items.count() == 0:
            # If no items left, set investment amount to 0
            basket.investment_amount = Decimal('0')
            basket.save()
            
            return {
                'success': True,
                'message': f'Successfully removed {deleted_stock_name}. Basket is now empty.',
                'basket': basket,
                'deleted_amount': float(deleted_amount),
                'remaining_stocks': 0
            }
        
        # Recalculate total investment amount (sum of remaining allocated amounts)
        total_allocated = sum(item.allocated_amount for item in remaining_items)
        
        # Update basket investment amount
        basket.investment_amount = total_allocated
        basket.save()
        
        # Recalculate weight percentages for remaining stocks
        # Equal weight distribution
        num_remaining = remaining_items.count()
        equal_weight = Decimal('100.00') / num_remaining
        
        for item in remaining_items:
            # Update weight percentage to equal distribution
            item.weight_percentage = (item.allocated_amount / total_allocated) * 100
            item.save()
        
        return {
            'success': True,
            'message': f'Successfully removed {deleted_stock_name} from basket. Investment amount reduced by ₹{deleted_amount:.2f}.',
            'basket': basket,
            'deleted_amount': float(deleted_amount),
            'remaining_stocks': num_remaining,
            'new_investment_amount': float(total_allocated)
        }
        
    except Basket.DoesNotExist:
        return {
            'success': False,
            'message': f'Basket with ID {basket_id} not found.',
            'basket': None,
            'deleted_amount': 0
        }
    
    except BasketItem.DoesNotExist:
        return {
            'success': False,
            'message': f'Stock not found in this basket.',
            'basket': None,
            'deleted_amount': 0
        }
    
    except Exception as e:
        return {
            'success': False,
            'message': f'Error removing stock from basket: {str(e)}',
            'basket': None,
            'deleted_amount': 0
        }


def recalculate_basket_weights(basket_id):
    """
    Recalculate weight percentages for all stocks in a basket
    
    This ensures all weights sum to 100% based on current allocated amounts
    
    Args:
        basket_id: ID of the basket to recalculate
    
    Returns:
        Dictionary with success status and message
    """
    from .models import Basket
    
    try:
        basket = Basket.objects.get(id=basket_id)
        items = basket.items.all()
        
        if items.count() == 0:
            return {
                'success': True,
                'message': 'Basket is empty, nothing to recalculate.'
            }
        
        # Calculate total allocated amount
        total_allocated = sum(item.allocated_amount for item in items)
        
        if total_allocated == 0:
            return {
                'success': False,
                'message': 'Total allocated amount is zero, cannot recalculate weights.'
            }
        
        # Update each item's weight percentage
        for item in items:
            item.weight_percentage = (item.allocated_amount / total_allocated) * 100
            item.save()
        
        # Update basket investment amount
        basket.investment_amount = total_allocated
        basket.save()
        
        return {
            'success': True,
            'message': f'Successfully recalculated weights for {items.count()} stocks.',
            'total_investment': float(total_allocated)
        }
        
    except Basket.DoesNotExist:
        return {
            'success': False,
            'message': f'Basket with ID {basket_id} not found.'
        }
    
    except Exception as e:
        return {
            'success': False,
            'message': f'Error recalculating basket weights: {str(e)}'
        }


def add_stock_to_basket(basket_id, stock_id, quantity=0):
    """
    Add a stock to an existing basket with initial quantity of 0
    
    This function adds a stock to a basket and recalculates all weights:
    - Adds the new BasketItem entry with 0 quantity
    - Recalculates weight percentages for all stocks
    
    Args:
        basket_id: ID of the basket
        stock_id: ID of the stock to add
        quantity: Initial quantity (default 0)
    
    Returns:
        Dictionary with:
            - success: Boolean indicating if addition was successful
            - message: Success or error message
            - basket: Updated basket object (if successful)
            - basket_item: The newly created BasketItem (if successful)
    """
    from .models import Basket, BasketItem, Stock
    
    try:
        # Get the basket
        basket = Basket.objects.get(id=basket_id)
        
        # Get the stock
        stock = Stock.objects.get(id=stock_id)
        
        # Check if stock already exists in basket
        if BasketItem.objects.filter(basket=basket, stock=stock).exists():
            return {
                'success': False,
                'message': f'{stock.symbol} is already in this basket.',
                'basket': basket,
                'basket_item': None
            }
        
        # Fetch latest price if not available
        if not stock.current_price:
            price = fetch_stock_price(stock.symbol)
            if price:
                stock.current_price = Decimal(str(price))
                stock.save()
        
        # If still no price, return error
        if not stock.current_price or stock.current_price <= 0:
            return {
                'success': False,
                'message': f'Cannot add {stock.symbol}: No price data available.',
                'basket': basket,
                'basket_item': None
            }
        
        # Create new basket item with quantity 0
        quantity = int(quantity)
        allocated_amount = Decimal(str(quantity)) * stock.current_price
        
        basket_item = BasketItem.objects.create(
            basket=basket,
            stock=stock,
            weight_percentage=Decimal('0'),  # Will be recalculated
            allocated_amount=allocated_amount,
            quantity=quantity,
            purchase_price=stock.current_price
        )
        
        # Recalculate weights for all stocks
        all_items = basket.items.all()
        total_allocated = sum(item.allocated_amount for item in all_items)
        
        if total_allocated > 0:
            for item in all_items:
                item.weight_percentage = (item.allocated_amount / total_allocated) * 100
                item.save()
            
            # Update basket investment amount
            basket.investment_amount = total_allocated
            basket.save()
        
        return {
            'success': True,
            'message': f'Successfully added {stock.symbol} to basket.',
            'basket': basket,
            'basket_item': basket_item,
            'new_investment_amount': float(total_allocated if total_allocated > 0 else basket.investment_amount)
        }
        
    except Basket.DoesNotExist:
        return {
            'success': False,
            'message': f'Basket with ID {basket_id} not found.',
            'basket': None,
            'basket_item': None
        }
    
    except Stock.DoesNotExist:
        return {
            'success': False,
            'message': f'Stock with ID {stock_id} not found.',
            'basket': None,
            'basket_item': None
        }
    
    except Exception as e:
        return {
            'success': False,
            'message': f'Error adding stock to basket: {str(e)}',
            'basket': None,
            'basket_item': None
        }
