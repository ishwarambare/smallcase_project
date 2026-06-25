# stocks/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Prefetch
from django.core.cache import cache
from decimal import Decimal
from .models import Stock, Basket, BasketItem
from .utils import (
    populate_indian_stocks,
    update_stock_prices,
    calculate_equal_weight_basket,
    create_basket_with_stocks
)
from django.middleware.csrf import get_token
from django.http import JsonResponse
from functools import wraps

User = get_user_model()  # Get the custom User model


# Custom decorator for AJAX requests that need authentication
def ajax_login_required(view_func):
    """Decorator for AJAX views that require authentication - returns JSON instead of redirecting"""
    from django.views.decorators.csrf import csrf_exempt
    
    @wraps(view_func)
    @csrf_exempt
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper



# ============ Stock and Basket Views ============

# @login_required
def home(request):
    """Home page showing all stocks and baskets"""
    # OPTIMIZATION: Remove automatic price updates on page load
    # Users can manually trigger updates with the "Update Prices" button
    
    # OPTIMIZATION: Use select_related and prefetch_related to reduce queries
    stocks = Stock.objects.all().order_by('symbol')
    
    baskets = []
    total_invested = 0
    total_current_value = 0
    total_profit_loss = 0
    
    if request.user.is_authenticated:
        # Filter baskets to show only user's baskets
        baskets = Basket.objects.filter(user=request.user).prefetch_related(
            Prefetch('items', queryset=BasketItem.objects.select_related('stock'))
        ).order_by('-created_at')
        
        # Calculate total invested using database aggregation
        total_invested = baskets.aggregate(Sum('investment_amount'))['investment_amount__sum'] or 0
        
        # OPTIMIZATION: Cache basket calculations
        for basket in baskets:
            cache_key = f'basket_value_{basket.id}_{basket.updated_at.timestamp()}'
            basket_value = cache.get(cache_key)
            if basket_value is None:
                basket_value = basket.get_total_value()
                cache.set(cache_key, basket_value, 300)  # Cache for 5 minutes
            total_current_value += basket_value
        
        total_profit_loss = total_current_value - float(total_invested)

    context = {
        'stocks': stocks,
        'baskets': baskets,
        'total_invested': total_invested,
        'total_current_value': total_current_value,
        'total_profit_loss': total_profit_loss,
    }
    return render(request, 'stocks/home.j2', context)


def stock_detail(request, symbol):
    """Stock detail page — full intelligence: fundamentals, technicals, news,
    ownership, policy alignment, global impact, quant metrics, and unified recommendation."""
    from .stock_analysis import (
        get_stock_fundamentals, get_technical_indicators,
        get_news_sentiment, get_ownership_analysis,
        get_policy_alignment, get_global_impact,
        get_buy_recommendation, get_quant_metrics,
    )

    db_stock = Stock.objects.filter(symbol=symbol).first()

    # Cache for 15 minutes (all yfinance calls together are slow)
    cache_key = f'stock_detail_v2_{symbol}'
    cached = cache.get(cache_key)
    if cached:
        context = cached
    else:
        # Fetch all data
        fundamentals = get_stock_fundamentals(symbol)
        indicators   = get_technical_indicators(symbol)
        news         = get_news_sentiment(symbol)
        ownership    = get_ownership_analysis(fundamentals)
        policy       = get_policy_alignment(
                           fundamentals.get('sector', ''),
                           news.get('articles', []))
        global_data  = get_global_impact(fundamentals.get('sector', ''))
        quant        = get_quant_metrics(symbol)
        recommendation = get_buy_recommendation(
                           fundamentals, indicators,
                           news=news, ownership=ownership,
                           policy=policy, global_impact=global_data)

        # DB fallbacks
        if db_stock and not fundamentals.get('current_price'):
            fundamentals['current_price'] = float(db_stock.current_price) if db_stock.current_price else None
        if db_stock and not fundamentals.get('name'):
            fundamentals['name'] = db_stock.name

        # Day change
        price = fundamentals.get('current_price')
        prev_close = fundamentals.get('previous_close')
        day_change = day_change_pct = None
        if price and prev_close and prev_close > 0:
            day_change = round(price - prev_close, 2)
            day_change_pct = round((day_change / prev_close) * 100, 2)

        # 52-week position
        week52_pct = None
        w52h = fundamentals.get('week_52_high')
        w52l = fundamentals.get('week_52_low')
        if price and w52h and w52l and (w52h - w52l) > 0:
            week52_pct = round(((price - w52l) / (w52h - w52l)) * 100, 1)

        context = {
            'symbol': symbol,
            'db_stock': db_stock,
            'fundamentals': fundamentals,
            'indicators': indicators,
            'news': news,
            'ownership': ownership,
            'policy': policy,
            'global_data': global_data,
            'quant': quant,
            'recommendation': recommendation,
            'day_change': day_change,
            'day_change_pct': day_change_pct,
            'week52_pct': week52_pct,
        }
        cache.set(cache_key, context, 900)

    return render(request, 'stocks/stock_detail.j2', context)



def stock_history_api(request):
    """API endpoint: returns historical close prices for a stock symbol."""
    from .utils import fetch_stock_historical_data, TIME_PERIODS
    symbol = request.GET.get('symbol', '').strip()
    period = request.GET.get('period', '1m')
    if period not in TIME_PERIODS:
        period = '1m'
    if not symbol:
        return JsonResponse({'success': False, 'error': 'No symbol provided'})
    cache_key = f'stock_hist_{symbol}_{period}'
    cached = cache.get(cache_key)
    if cached:
        return JsonResponse(cached)
    data = fetch_stock_historical_data(symbol, period)
    if not data:
        return JsonResponse({'success': False, 'error': 'No data available'})
    result = {
        'success': True,
        'symbol': symbol,
        'dates': [d['date'] for d in data],
        'prices': [d['value'] for d in data],
    }
    cache.set(cache_key, result, 900)
    return JsonResponse(result)


@login_required
def populate_stocks(request):
    """Populate database with Indian stocks"""
    created_count = populate_indian_stocks()
    messages.success(request, f'Successfully added {created_count} new stocks!')
    return redirect('home')


@login_required
def update_prices(request):
    """Update all stock prices"""
    count = update_stock_prices()
    messages.success(request, f'Successfully updated prices for {count} stocks!')
    # Clear basket value cache after price update
    cache.clear()
    return redirect('home')




@login_required
def basket_create(request):
    """Create a new basket"""
    # OPTIMIZATION: Don't auto-update prices, let users trigger manually
    
    stocks = Stock.objects.all().order_by('symbol')

    if request.method == 'POST':
        print('',request.POST)
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        investment_amount = request.POST.get('investment_amount')
        selected_stocks = request.POST.getlist('stocks')

        # Validation
        if not name or not investment_amount or not selected_stocks:
            messages.error(request, 'Please fill all required fields')
            return redirect('basket_create')
        
        # Validate minimum 2 stocks
        if len(selected_stocks) < 2:
            messages.error(request, 'A basket must contain at least 2 stocks')
            return redirect('basket_create')

        try:
            investment_amount = float(investment_amount)
            if investment_amount <= 0:
                messages.error(request, 'Investment amount must be positive')
                return redirect('basket_create')
        except ValueError:
            messages.error(request, 'Invalid investment amount')
            return redirect('basket_create')

        # Create basket
        basket = create_basket_with_stocks(
            name=name,
            description=description,
            investment_amount=investment_amount,
            stock_symbols=selected_stocks,
            user=request.user
        )

        if basket:
            messages.success(request, f'Basket "{name}" created successfully!')
            return redirect('basket_detail', basket_id=basket.id)
        else:
            messages.error(request, 'Failed to create basket. Please try again.')
            return redirect('basket_create')

    # Handle pre-filled values from duplication
    prefill_name = request.GET.get('name', '')
    prefill_description = request.GET.get('description', '')
    prefill_investment = request.GET.get('investment_amount', '50000')
    prefill_stocks = request.GET.get('stocks', '').split(',') if request.GET.get('stocks') else []
    
    context = {
        'stocks': stocks,
        'csrf_token': get_token(request),
        'prefill_name': prefill_name,
        'prefill_description': prefill_description,
        'prefill_investment': prefill_investment,
        'prefill_stocks': prefill_stocks,
    }
    return render(request, 'stocks/basket_create.j2', context)


@login_required
def basket_detail(request, basket_id):
    """View basket details"""
    from django.template.loader import get_template
    
    basket = get_object_or_404(Basket, id=basket_id, user=request.user)
    # OPTIMIZATION: Use select_related to avoid N+1 queries
    items = basket.items.select_related('stock').all()

    # OPTIMIZATION: Update prices in bulk only if they're stale (>5 mins old)
    from datetime import timedelta
    from django.utils import timezone
    from .utils import update_stock_prices_bulk
    
    stale_stocks = [
        item.stock for item in items
        if not item.stock.current_price or 
        item.stock.last_updated < timezone.now() - timedelta(minutes=5)
    ]
    
    if stale_stocks:
        symbols = [stock.symbol for stock in stale_stocks]
        update_stock_prices_bulk(symbols)
        # Refresh items from database to get updated prices
        items = basket.items.select_related('stock').all()

    # Calculate metrics with caching
    cache_key = f'basket_metrics_{basket.id}_{basket.updated_at.timestamp()}'
    metrics = cache.get(cache_key)
    
    if metrics is None:
        total_current_value = basket.get_total_value()
        total_profit_loss = basket.get_profit_loss()
        profit_loss_percentage = basket.get_profit_loss_percentage()
        metrics = {
            'total_current_value': total_current_value,
            'total_profit_loss': total_profit_loss,
            'profit_loss_percentage': profit_loss_percentage,
        }
        cache.set(cache_key, metrics, 300)  # Cache for 5 minutes
    
    # Load the stock holdings table template partial
    stock_holdings_template = get_template("stocks/_stock_holdings_table.j2")
    
    # Prepare context for the partial template
    holdings_context = {
        'basket': basket,
        'items': items,
        'total_current_value': metrics['total_current_value'],
        'total_profit_loss': metrics['total_profit_loss'],
    }
    
    # Render the stock holdings table HTML
    stock_holdings_html = stock_holdings_template.render(holdings_context)
    
    context = {
        'basket': basket,
        'items': items,
        'stock_holdings_html': stock_holdings_html,  # Pass rendered HTML to main template
        **metrics
    }
    return render(request, 'stocks/basket_detail.j2', context)


@login_required
def basket_chart_data(request, basket_id):
    """API endpoint to get basket performance vs indices data for chart"""
    from django.http import JsonResponse
    from .utils import fetch_index_historical_data, calculate_basket_historical_performance, INDIAN_INDICES
    
    basket = get_object_or_404(Basket, id=basket_id, user=request.user)
    
    # Get period from request, default to 1 month
    period = request.GET.get('period', '1m')
    
    # Validate period
    valid_periods = ['1d', '7d', '1m', '3m', '6m', '1y', '3y', '5y']
    if period not in valid_periods:
        period = '1m'
    
    # OPTIMIZATION: Cache chart data for 1 hour
    cache_key = f'chart_data_{basket.id}_{period}'
    cached_data = cache.get(cache_key)
    if cached_data:
        return JsonResponse(cached_data)
    
    # Fetch Nifty 50 historical data
    nifty_data = fetch_index_historical_data('^NSEI', period)
    
    # Fetch basket historical performance
    basket_data = calculate_basket_historical_performance(basket, period)
    
    if not nifty_data or not basket_data:
        return JsonResponse({
            'success': False,
            'error': 'Unable to fetch historical data'
        })
    
    # Normalize both to indexed values starting at 100
    # This shows: "If I invested ₹100, what would it be worth now?"
    if nifty_data:
        nifty_start_value = nifty_data[0]['value']
        nifty_indexed = [
            {
                'date': item['date'],
                'value': (item['value'] / nifty_start_value) * 100  # Index to 100
            }
            for item in nifty_data
        ]
    else:
        nifty_indexed = []
    
    if basket_data:
        basket_start_value = basket_data[0]['value']
        basket_indexed = [
            {
                'date': item['date'],
                'value': (item['value'] / basket_start_value) * 100  # Index to 100
            }
            for item in basket_data
        ]
    else:
        basket_indexed = []
    
    # Align dates (use dates where both have data)
    nifty_dates = {item['date']: item['value'] for item in nifty_indexed}
    basket_dates = {item['date']: item['value'] for item in basket_indexed}
    common_dates = sorted(set(nifty_dates.keys()) & set(basket_dates.keys()))
    
    # Build aligned datasets
    aligned_nifty = [nifty_dates[date] for date in common_dates]
    aligned_basket = [basket_dates[date] for date in common_dates]
    
    # Ensure both start at exactly 100 (re-normalize to first common date)
    if aligned_basket and aligned_nifty:
        first_basket = aligned_basket[0]
        first_nifty = aligned_nifty[0]
        
        # Re-index both to start at exactly 100
        aligned_basket = [(val / first_basket) * 100 for val in aligned_basket]
        aligned_nifty = [(val / first_nifty) * 100 for val in aligned_nifty]
    
    # Calculate final values for summary
    final_basket_value = aligned_basket[-1] if aligned_basket else 100
    final_nifty_value = aligned_nifty[-1] if aligned_nifty else 100
    
    response_data = {
        'success': True,
        'period': period,
        'labels': common_dates,
        'datasets': {
            'basket': {
                'label': basket.name,
                'data': aligned_basket,
                'color': 'rgb(102, 126, 234)',
                'final_value': round(final_basket_value, 2)
            },
            'nifty': {
                'label': 'Nifty 50',
                'data': aligned_nifty,
                'color': 'rgb(255, 99, 132)',
                'final_value': round(final_nifty_value, 2)
            }
        },
        'summary': {
            'basket_final': round(final_basket_value, 2),
            'nifty_final': round(final_nifty_value, 2),
            'basket_return_pct': round(final_basket_value - 100, 2),
            'nifty_return_pct': round(final_nifty_value - 100, 2)
        }
    }
    
    # Cache for 1 hour
    cache.set(cache_key, response_data, 3600)
    
    return JsonResponse(response_data)


@login_required
def basket_performance(request, basket_id):
    """Performance analysis page showing historical returns"""
    from datetime import datetime, timedelta
    from .utils import fetch_index_historical_data, calculate_basket_historical_performance
    
    basket = get_object_or_404(Basket, id=basket_id, user=request.user)
    
    # OPTIMIZATION: Cache performance data for 1 hour
    cache_key = f'performance_{basket.id}'
    performance_data = cache.get(cache_key)
    
    if performance_data is None:
        # Define time periods to analyze
        periods = [
            {'code': '1m', 'label': '1 Month', 'days': 30},
            {'code': '3m', 'label': '3 Months', 'days': 90},
            {'code': '6m', 'label': '6 Months', 'days': 180},
            {'code': '1y', 'label': '1 Year', 'days': 365},
            {'code': '2y', 'label': '2 Years', 'days': 730},
            {'code': '3y', 'label': '3 Years', 'days': 1095},
            {'code': '5y', 'label': '5 Years', 'days': 1825},
        ]
        
        performance_data = []
        
        for period in periods:
            # Fetch historical data for this period
            basket_hist = calculate_basket_historical_performance(basket, period['code'])
            nifty_hist = fetch_index_historical_data('^NSEI', period['code'])
            
            if basket_hist and nifty_hist:
                # Create date dictionaries for alignment
                basket_dates = {item['date']: item['value'] for item in basket_hist}
                nifty_dates = {item['date']: item['value'] for item in nifty_hist}
                
                # Find common dates
                common_dates = sorted(set(basket_dates.keys()) & set(nifty_dates.keys()))
                
                if common_dates:
                    # Get aligned values
                    basket_values = [basket_dates[date] for date in common_dates]
                    nifty_values = [nifty_dates[date] for date in common_dates]
                    
                    # Use first and last from common dates
                    basket_start = basket_values[0]
                    basket_end = basket_values[-1]
                    nifty_start = nifty_values[0]
                    nifty_end = nifty_values[-1]
                    
                    # Calculate indexed values (₹100 invested then → ₹X today)
                    # Both start from the same date, ensuring fair comparison
                    basket_value = (basket_end / basket_start) * 100
                    nifty_value = (nifty_end / nifty_start) * 100
                    
                    # Calculate returns
                    basket_return = basket_value - 100
                    nifty_return = nifty_value - 100
                    
                    # Determine who performed better
                    outperformance = basket_value - nifty_value
                    
                    performance_data.append({
                        'period': period['label'],
                        'code': period['code'],
                        'basket_value': round(basket_value, 2),
                        'nifty_value': round(nifty_value, 2),
                        'basket_return': round(basket_return, 2),
                        'nifty_return': round(nifty_return, 2),
                        'outperformance': round(outperformance, 2),
                        'basket_wins': basket_value > nifty_value
                    })
        
        # Cache for 1 hour
        cache.set(cache_key, performance_data, 3600)
    
    context = {
        'basket': basket,
        'performance_data': performance_data,
    }
    
    return render(request, 'stocks/basket_performance.j2', context)


@login_required
def basket_delete(request, basket_id):
    """Delete a basket"""
    basket = get_object_or_404(Basket, id=basket_id, user=request.user)
    basket_name = basket.name
    basket.delete()
    
    # Clear caches related to this basket
    cache.delete_many([
        f'basket_value_{basket_id}*',
        f'basket_metrics_{basket_id}*',
        f'chart_data_{basket_id}*',
        f'performance_{basket_id}'
    ])
    
    messages.success(request, f'Basket "{basket_name}" deleted successfully!')
    return redirect('home')


@login_required
def preview_basket(request):
    """Preview basket allocation before creating"""
    if request.method == 'POST':
        investment_amount = request.POST.get('investment_amount')
        selected_stocks = request.POST.getlist('stocks')

        try:
            investment_amount = float(investment_amount)
            allocations = calculate_equal_weight_basket(selected_stocks, investment_amount)

            context = {
                'allocations': allocations,
                'investment_amount': investment_amount,
                'num_stocks': len(allocations),
            }
            return render(request, 'stocks/preview_basket.html', context)
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
            return redirect('basket_create')

    return redirect('basket_create')


@login_required
def basket_item_edit(request, item_id):
    """Edit basket item - update weight or quantity, rebalancing other stocks to maintain 100% total"""
    from django.http import JsonResponse
    
    if request.method == 'POST':
        item = get_object_or_404(BasketItem, id=item_id)
        basket = item.basket
        
        # Verify basket belongs to user
        if basket.user != request.user:
            return JsonResponse({'success': False, 'error': 'Unauthorized'})
        
        try:
            update_type = request.POST.get('update_type')  # 'weight' or 'quantity'
            
            if update_type == 'weight':
                # Update weight, recalculate quantity
                new_weight = Decimal(request.POST.get('weight_percentage'))
                
                if new_weight <= 0 or new_weight > 100:
                    return JsonResponse({'success': False, 'error': 'Weight must be between 0 and 100'})
                
                old_weight = item.weight_percentage
                weight_change = new_weight - old_weight
                
                # Get all other items in the basket
                other_items = basket.items.exclude(id=item.id)
                
                if not other_items.exists():
                    # Only one stock in basket, just update it
                    item.weight_percentage = new_weight
                    item.allocated_amount = (new_weight / 100) * basket.investment_amount
                    # Round to whole number
                    item.quantity = int(item.allocated_amount / item.purchase_price)
                    # Adjust allocated amount based on whole quantity
                    item.allocated_amount = item.quantity * item.purchase_price
                    # Recalculate actual weight based on whole quantity
                    item.weight_percentage = (item.allocated_amount / basket.investment_amount) * 100
                    item.save()
                else:
                    # Calculate total weight of other items
                    other_total_weight = sum(other_item.weight_percentage for other_item in other_items)
                    
                    # Remaining weight for other stocks
                    remaining_weight = Decimal('100') - new_weight
                    
                    if remaining_weight < 0:
                        return JsonResponse({'success': False, 'error': 'Total weight cannot exceed 100%'})
                    
                    # Update current item
                    item.weight_percentage = new_weight
                    item.allocated_amount = (new_weight / 100) * basket.investment_amount
                    # Round to whole number
                    item.quantity = int(item.allocated_amount / item.purchase_price)
                    # Adjust allocated amount based on whole quantity
                    item.allocated_amount = item.quantity * item.purchase_price
                    # Recalculate actual weight based on whole quantity
                    item.weight_percentage = (item.allocated_amount / basket.investment_amount) * 100
                    item.save()
                    
                    # Redistribute remaining weight proportionally among other items
                    if other_total_weight > 0:
                        for other_item in other_items:
                            # Calculate proportional weight
                            proportion = other_item.weight_percentage / other_total_weight
                            other_item.weight_percentage = remaining_weight * proportion
                            other_item.allocated_amount = (other_item.weight_percentage / 100) * basket.investment_amount
                            # Round to whole number
                            other_item.quantity = int(other_item.allocated_amount / other_item.purchase_price)
                            # Adjust allocated amount based on whole quantity
                            other_item.allocated_amount = other_item.quantity * other_item.purchase_price
                            # Recalculate actual weight based on whole quantity
                            other_item.weight_percentage = (other_item.allocated_amount / basket.investment_amount) * 100
                            other_item.save()
                    else:
                        # If other items had 0 weight, distribute equally
                        equal_weight = remaining_weight / len(other_items)
                        for other_item in other_items:
                            other_item.weight_percentage = equal_weight
                            other_item.allocated_amount = (other_item.weight_percentage / 100) * basket.investment_amount
                            # Round to whole number
                            other_item.quantity = int(other_item.allocated_amount / other_item.purchase_price)
                            # Adjust allocated amount based on whole quantity
                            other_item.allocated_amount = other_item.quantity * other_item.purchase_price
                            # Recalculate actual weight based on whole quantity
                            other_item.weight_percentage = (other_item.allocated_amount / basket.investment_amount) * 100
                            other_item.save()
                
            elif update_type == 'quantity':
                # Update quantity, recalculate all weights (quantity must be whole number)
                # Other stocks keep their quantities, only weights change
                new_quantity = int(request.POST.get('quantity'))
                
                if new_quantity <= 0:
                    return JsonResponse({'success': False, 'error': 'Quantity must be positive'})
                
                # Update this item's quantity and allocated amount
                item.quantity = new_quantity
                item.allocated_amount = new_quantity * item.purchase_price
                item.save()
                
                # Calculate total allocated amount across all stocks (including updated one)
                all_items = basket.items.all()
                total_allocated = sum(Decimal(str(basket_item.quantity)) * basket_item.purchase_price 
                                     for basket_item in all_items)
                
                # Update basket investment amount to match actual holdings
                basket.investment_amount = total_allocated
                basket.save()
                
                # Recalculate weights for all items based on new total
                for basket_item in all_items:
                    # Keep quantity as is, just recalculate weight
                    basket_item.weight_percentage = (basket_item.allocated_amount / total_allocated) * 100 if total_allocated > 0 else 0
                    basket_item.save()
            
            else:
                return JsonResponse({'success': False, 'error': 'Invalid update type'})
            
            # Clear caches
            cache.delete_many([
                f'basket_value_{basket.id}*',
                f'basket_metrics_{basket.id}*',
            ])
            
            # Get all items with updated values to return
            all_items = basket.items.all()
            items_data = []
            for basket_item in all_items:
                items_data.append({
                    'id': basket_item.id,
                    'weight_percentage': float(basket_item.weight_percentage),
                    'quantity': int(basket_item.quantity),
                    'allocated_amount': float(basket_item.allocated_amount),
                    'current_value': basket_item.get_current_value(),
                    'profit_loss': basket_item.get_profit_loss(),
                })
            
            # Calculate updated portfolio metrics
            total_current_value = basket.get_total_value()
            total_profit_loss = basket.get_profit_loss()
            profit_loss_percentage = basket.get_profit_loss_percentage()
            
            # Return updated values for all items and basket
            return JsonResponse({
                'success': True,
                'items': items_data,
                'investment_amount': float(basket.investment_amount),
                'total_current_value': total_current_value,
                'total_profit_loss': total_profit_loss,
                'profit_loss_percentage': profit_loss_percentage,
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


from django.views.decorators.csrf import csrf_exempt
# @login_required
@csrf_exempt
def basket_stock_delete(request, basket_id, stock_id):
    """Delete a stock from basket and return updated HTML"""
    from django.http import JsonResponse
    from django.template.loader import get_template
    from .utils import remove_stock_from_basket
    print(request.method)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
        
    # Verify basket ownership and existence
    basket = get_object_or_404(Basket, id=basket_id, user=request.user)
    
    # Use the utility function to remove the stock and recalculate everything
    result = remove_stock_from_basket(basket_id, stock_id)
    
    if not result['success']:
        return JsonResponse(result)
        
    # Refresh basket metrics
    # Clear caches
    cache.delete_many([
        f'basket_value_{basket.id}*',
        f'basket_metrics_{basket.id}*',
        f'chart_data_{basket.id}*',
        f'performance_{basket.id}'
    ])
    
    # Get updated items for rendering
    items = basket.items.select_related('stock').all()
    
    total_current_value = basket.get_total_value()
    total_profit_loss = basket.get_profit_loss()
    profit_loss_percentage = basket.get_profit_loss_percentage()
    
    # Render the updated stock holdings table
    stock_holdings_template = get_template("stocks/_stock_holdings_table.j2")
    
    holdings_context = {
        'basket': basket,
        'items': items,
        'total_current_value': total_current_value,
        'total_profit_loss': total_profit_loss,
    }
    
    stock_holdings_html = stock_holdings_template.render(holdings_context)
    
    # Return JSON response with new HTML and metrics
    return JsonResponse({
        'success': True,
        'message': result['message'],
        'stock_holdings_html': stock_holdings_html,
        'new_investment_amount': float(basket.investment_amount),
        'total_current_value': total_current_value,
        'total_profit_loss': total_profit_loss,
        'profit_loss_percentage': profit_loss_percentage
    })


@csrf_exempt
def basket_stock_add(request, basket_id):
    """Add a stock to basket via AJAX and return updated HTML"""
    from django.http import JsonResponse
    from django.template.loader import get_template
    from .utils import add_stock_to_basket
    import json
    print('---------------------')
    print(request.body, basket_id)
    print('---------------------')
    print(request.POST)
    print('---------------------')
    print(request.method)
    print('---------------------')
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    # Verify basket ownership and existence
    basket = get_object_or_404(Basket, id=basket_id, user=request.user)
    
    try:
        # Parse JSON body
        data = json.loads(request.body) if request.body else request.POST
        stock_id = data.get('stock_id')
        
        if not stock_id:
            return JsonResponse({'success': False, 'error': 'Stock ID is required'})
        
        # Use the utility function to add the stock
        result = add_stock_to_basket(basket_id, stock_id, quantity=0)
        
        if not result['success']:
            return JsonResponse(result)
        
        # Clear caches
        cache.delete_many([
            f'basket_value_{basket.id}*',
            f'basket_metrics_{basket.id}*',
            f'chart_data_{basket.id}*',
            f'performance_{basket.id}'
        ])
        
        # Refresh basket from database
        basket.refresh_from_db()
        
        # Get updated items for rendering
        items = basket.items.select_related('stock').all()
        
        total_current_value = basket.get_total_value()
        total_profit_loss = basket.get_profit_loss()
        profit_loss_percentage = basket.get_profit_loss_percentage()
        
        # Render the updated stock holdings table
        stock_holdings_template = get_template("stocks/_stock_holdings_table.j2")
        
        holdings_context = {
            'basket': basket,
            'items': items,
            'total_current_value': total_current_value,
            'total_profit_loss': total_profit_loss,
        }
        
        stock_holdings_html = stock_holdings_template.render(holdings_context)
        
        # Return JSON response with new HTML and metrics
        print('---------------------')
        print(reverse('basket_stock_add', args=[basket.id]))
        print('---------------------')
        return JsonResponse({
            'success': True,
            'message': result['message'],
            'stock_holdings_html': stock_holdings_html,
            'new_investment_amount': float(basket.investment_amount),
            'total_current_value': total_current_value,
            'total_profit_loss': total_profit_loss,
            'profit_loss_percentage': profit_loss_percentage,
            # URL for basket_stock_add view
            'add_stock_url': reverse('basket_stock_add', args=[basket.id])
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
def basket_get_available_stocks(request, basket_id):
    """Get stocks that are not in the current basket"""
    basket = get_object_or_404(Basket, id=basket_id, user=request.user)
    
    # Get stock IDs already in basket
    basket_stock_ids = basket.items.values_list('stock_id', flat=True)
    
    # Get all available stocks not in basket
    available_stocks = Stock.objects.exclude(id__in=basket_stock_ids).order_by('symbol')
    
    stocks_data = [{
        'id': stock.id,
        'symbol': stock.symbol,
        'name': stock.name,
        'current_price': float(stock.current_price) if stock.current_price else None
    } for stock in available_stocks]
    


    # Return JSON response with new HTML and metrics
    print('---------------------')

    from django.urls import reverse
    print(reverse('basket_stock_add', args=[basket.id]))
    print('---------------------')
    # URL for basket_stock_add view
    add_stock_url = reverse('basket_stock_add', args=[basket.id])
    print('---------------------')
    # URL for basket_stock_add view
    return JsonResponse({
        'success': True,
        'stocks': stocks_data,
        'add_stock_url': add_stock_url
    })


    return JsonResponse({
        'success': True,
        'stocks': stocks_data,
        'add_stock_url': reversed('basket_stock_add', args=[basket.id])
    })


@login_required
def basket_duplicate(request, basket_id):
    """Duplicate a basket - redirect to create page with pre-filled values"""
    basket = get_object_or_404(Basket, id=basket_id, user=request.user)
    
    # Get all stock symbols from the basket
    stock_symbols = ','.join([item.stock.symbol for item in basket.items.all()])
    
    # Redirect to create page with query parameters
    from django.http import HttpResponseRedirect
    from urllib.parse import urlencode
    
    params = {
        'duplicate': 'true',
        'name': f"{basket.name} (Copy)",
        'description': basket.description,
        'investment_amount': str(basket.investment_amount),
        'stocks': stock_symbols,
    }
    
    url = f"{request.build_absolute_uri('/basket/create/')}?{urlencode(params)}"
    return HttpResponseRedirect(url)


@login_required
def basket_edit_investment(request, basket_id):
    """Edit basket investment amount - recalculates all allocations"""
    from django.http import JsonResponse
    
    if request.method == 'POST':
        basket = get_object_or_404(Basket, id=basket_id, user=request.user)
        
        try:
            new_investment = Decimal(request.POST.get('investment_amount'))
            
            if new_investment <= 0:
                return JsonResponse({'success': False, 'error': 'Investment amount must be positive'})
            
            old_investment = basket.investment_amount
            basket.investment_amount = new_investment
            basket.save()
            
            # Recalculate all items based on new investment amount
            items = basket.items.all()
            items_data = []
            
            for item in items:
                # Keep the same weight percentage, recalculate allocated amount
                item.allocated_amount = (item.weight_percentage / 100) * new_investment
                # Recalculate quantity based on new allocated amount (round to whole number)
                item.quantity = int(item.allocated_amount / item.purchase_price)
                
                # Adjust allocated amount to reflect whole quantity
                item.allocated_amount = item.quantity * item.purchase_price
                
                # Recalculate actual weight based on whole quantity
                item.weight_percentage = (item.allocated_amount / new_investment) * 100
                
                item.save()
                
                items_data.append({
                    'id': item.id,
                    'weight_percentage': float(item.weight_percentage),
                    'quantity': int(item.quantity),
                    'allocated_amount': float(item.allocated_amount),
                    'current_value': item.get_current_value(),
                    'profit_loss': item.get_profit_loss(),
                })
            
            # Clear caches
            cache.delete_many([
                f'basket_value_{basket.id}*',
                f'basket_metrics_{basket.id}*',
            ])
            
            # Calculate new totals
            total_current_value = basket.get_total_value()
            total_profit_loss = basket.get_profit_loss()
            
            return JsonResponse({
                'success': True,
                'investment_amount': float(new_investment),
                'items': items_data,
                'total_current_value': total_current_value,
                'total_profit_loss': total_profit_loss,
                'profit_loss_percentage': basket.get_profit_loss_percentage(),
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


def contact_us(request):
    """Contact Us page"""
    from django.shortcuts import render
    from django.middleware.csrf import get_token
    from django.contrib import messages
    from user.forms import ContactForm
    
    # Create form instance (empty form for GET, bound form for POST)
    form = ContactForm(request.POST if request.method == 'POST' else None)
    
    context = {
        'csrf_token': get_token(request),
        'form': form
    }
    return render(request, 'stocks/contact.j2', context)


def i18n_demo(request):
    """Multi-language demo page"""
    return render(request, 'stocks/i18n_demo.j2')


# ==========================================
# Chat API Views
# ==========================================

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
from .models import ChatGroup, ChatGroupMember, ChatMessage


def get_or_create_support_chat(user, is_ai_only=False):
    """Get or create a support chat for the user"""
    # Check if user already has a support chat of this type
    membership = ChatGroupMember.objects.filter(
        user=user,
        group__group_type='support',
        group__is_ai_only=is_ai_only,  # Match same support type
        is_active=True
    ).select_related('group').first()
    
    if membership:
        return membership.group
    
    # Create a new support chat for this user
    avatar_emoji = '🤖' if is_ai_only else '👨‍💼'
    chat_type = 'AI Support' if is_ai_only else 'Human Support'
    
    group = ChatGroup.objects.create(
        name=f"{chat_type} - {user.email}",
        group_type='support',
        created_by=user,
        avatar=avatar_emoji,
        is_ai_only=is_ai_only  # Mark as AI-only if requested
    )
    
    # Add user as member
    ChatGroupMember.objects.create(
        group=group,
        user=user,
        role='member'
    )
    
    # Add initial system message
    ChatMessage.objects.create(
        group=group,
        content="Hello! How can we help you today? 👋",
        message_type='system'
    )
    
    return group


@ajax_login_required
def chat_send_message(request):
    """API to send a chat message"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})
    
    try:
        data = json.loads(request.body) if request.body else request.POST
        content = data.get('content', '').strip()
        group_id = data.get('group_id')
        
        if not content:
            return JsonResponse({'success': False, 'error': 'Message cannot be empty'})
        
        # Get or create support chat if no group specified
        if group_id:
            group = get_object_or_404(ChatGroup, id=group_id, is_active=True)
            
            # Prevent admins from sending to AI-only chats
            if group.is_ai_only and (request.user.is_staff or request.user.is_superuser):
                return JsonResponse({'success': False, 'error': 'Cannot send messages to AI-only support chats'})
            
            # Verify user is member of this group
            if not ChatGroupMember.objects.filter(group=group, user=request.user, is_active=True).exists():
                return JsonResponse({'success': False, 'error': 'Not a member of this group'})
        else:
            # Get support_type from request (from frontend)
            support_type = data.get('support_type', 'ai')
            is_ai_only = (support_type == 'ai')
            group = get_or_create_support_chat(request.user, is_ai_only=is_ai_only)
        
        
        # Note: We rely on frontend to not call AI for admin support chats
        # Backend blocking removed because existing chats have is_ai_only=False by default
        
        # Check if this is an AI response
        is_ai_response = data.get('is_ai_response', False)
        
        # Create message
        # For AI responses, set sender=None so they show as "Support Team" (AI)
        message = ChatMessage.objects.create(
            group=group,
            sender=None if is_ai_response else request.user,  # AI messages have no sender
            content=content,
            message_type='text'
        )
        
        # Update group's updated_at timestamp
        group.save()
        
        return JsonResponse({
            'success': True,
            'message': {
                'id': message.id,
                'content': message.content,
                'sender': message.get_sender_name(),
                'sender_id': request.user.id,
                'message_type': message.message_type,
                'created_at': message.created_at.strftime('%H:%M'),
                'is_own': True
            },
            'group_id': group.id
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@ajax_login_required
def chat_get_messages(request):
    """API to get chat messages for a group"""
    group_id = request.GET.get('group_id')
    last_message_id = request.GET.get('last_message_id')
    
    try:
        # Get or create support chat if no group specified
        if group_id:
            group = get_object_or_404(ChatGroup, id=group_id, is_active=True)
            
            # Check if user is a member
            is_member = ChatGroupMember.objects.filter(
                group=group, user=request.user, is_active=True
            ).exists()
            
            if not is_member:
                # Allow admin/staff to join support chats automatically (including AI-only chats for VIEWING)
                if (request.user.is_staff or request.user.is_superuser) and group.group_type == 'support':
                    # Auto-add admin as support member (even for AI-only chats - they can view but not send)
                    ChatGroupMember.objects.create(
                        group=group,
                        user=request.user,
                        role='admin'
                    )
                    # Add system message about support joining (only for non-AI-only chats)
                    if not group.is_ai_only:
                        ChatMessage.objects.create(
                            group=group,
                            content=f"Support team member joined the chat",
                            message_type='system'
                        )
                else:
                    return JsonResponse({'success': False, 'error': 'Not a member of this group'})
        else:
            # For initial load, check if frontend specified support type preference
            support_type = request.GET.get('support_type', 'admin')  # 'ai' or 'admin'
            is_ai_only = (support_type == 'ai')
            group = get_or_create_support_chat(request.user, is_ai_only=is_ai_only)
        
        # Get messages
        messages_qs = ChatMessage.objects.filter(
            group=group,
            is_deleted=False
        ).select_related('sender').order_by('created_at')
        
        # If last_message_id provided, only get new messages
        if last_message_id:
            messages_qs = messages_qs.filter(id__gt=last_message_id)
        else:
            # Limit to last 50 messages for initial load
            messages_qs = messages_qs[:50]
        
        # Mark messages as read
        ChatMessage.objects.filter(
            group=group,
            is_read=False
        ).exclude(sender=request.user).update(is_read=True)
        
        messages_data = []
        for msg in messages_qs:
            messages_data.append({
                'id': msg.id,
                'content': msg.content,
                'sender': msg.get_sender_name(),
                'sender_id': msg.sender.id if msg.sender else None,
                'message_type': msg.message_type,
                'created_at': msg.created_at.strftime('%H:%M'),
                'is_own': msg.sender == request.user if msg.sender else False
            })
        
        return JsonResponse({
            'success': True,
            'messages': messages_data,
            'group_id': group.id,
            'group_name': group.name,
            'group_avatar': group.avatar,
            'is_ai_only': group.is_ai_only  # Include this so frontend knows if AI should respond
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@ajax_login_required
def chat_get_groups(request):
    """API to get user's chat groups"""
    try:
        groups_data = []
        already_added_ids = set()
        
        # Get groups where user is a member
        memberships = ChatGroupMember.objects.filter(
            user=request.user,
            is_active=True
        ).select_related('group').order_by('-group__updated_at')
        
        for membership in memberships:
            group = membership.group
            already_added_ids.add(group.id)
            last_message = group.get_last_message()
            unread_count = group.get_unread_count(request.user)
            
            groups_data.append({
                'id': group.id,
                'name': group.name,
                'avatar': group.avatar,
                'group_type': group.group_type,
                'members_count': group.get_members_count(),
                'last_message': last_message.content[:50] if last_message else None,
                'last_message_time': last_message.created_at.strftime('%H:%M') if last_message else None,
                'last_message_timestamp': last_message.created_at.timestamp() if last_message else 0,  # For sorting
                'unread_count': unread_count,
                'role': membership.role,
                'is_member': True
            })
        
        # For admin/staff users: also show ALL support chats they can respond to (including AI-only for viewing)
        if request.user.is_staff or request.user.is_superuser:
            support_chats = ChatGroup.objects.filter(
                group_type='support',
                is_active=True
                # Note: Removed is_ai_only=False filter so admins can see ALL support chats
            ).exclude(id__in=already_added_ids).order_by('-updated_at')
            
            for group in support_chats:
                last_message = group.get_last_message()
                # Count messages not from staff as "unread" for support
                unread_count = group.messages.filter(is_read=False).count()
                
                groups_data.append({
                    'id': group.id,
                    'name': group.name,
                    'avatar': group.avatar,
                    'group_type': group.group_type,
                    'members_count': group.get_members_count(),
                    'last_message': last_message.content[:50] if last_message else None,
                    'last_message_time': last_message.created_at.strftime('%H:%M') if last_message else None,
                    'last_message_timestamp': last_message.created_at.timestamp() if last_message else 0,  # For sorting
                    'unread_count': unread_count,
                    'role': 'support',  # Special role for support staff
                    'is_member': False  # Not yet a member, but can join
                })
        
        # Sort all groups by last message timestamp (most recent first)
        groups_data.sort(key=lambda g: g.get('last_message_timestamp', 0), reverse=True)
        
        return JsonResponse({
            'success': True,
            'groups': groups_data
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@ajax_login_required
def chat_create_group(request):
    """API to create a new chat group"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})
    
    try:
        data = json.loads(request.body) if request.body else request.POST
        name = data.get('name', '').strip()
        description = data.get('description', '')
        member_ids = data.get('member_ids', [])
        avatar = data.get('avatar', '👥')
        
        if not name:
            return JsonResponse({'success': False, 'error': 'Group name is required'})
        
        # Create group
        group = ChatGroup.objects.create(
            name=name,
            description=description,
            group_type='group',
            created_by=request.user,
            avatar=avatar
        )
        
        # Add creator as admin
        ChatGroupMember.objects.create(
            group=group,
            user=request.user,
            role='admin'
        )
        
        # Add other members
        if member_ids:
            for member_id in member_ids:
                try:
                    user = User.objects.get(id=member_id)
                    ChatGroupMember.objects.create(
                        group=group,
                        user=user,
                        role='member'
                    )
                except User.DoesNotExist:
                    pass
        
        # Add system message
        ChatMessage.objects.create(
            group=group,
            content=f"Group '{name}' created by {request.user.username or request.user.email}",
            message_type='system'
        )
        
        return JsonResponse({
            'success': True,
            'group': {
                'id': group.id,
                'name': group.name,
                'avatar': group.avatar,
                'members_count': group.get_members_count()
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@ajax_login_required
def chat_add_member(request):
    """API to add a member to a group"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})
    
    try:
        data = json.loads(request.body) if request.body else request.POST
        group_id = data.get('group_id')
        user_email = data.get('email', '').strip()
        
        if not group_id or not user_email:
            return JsonResponse({'success': False, 'error': 'Group ID and email are required'})
        
        group = get_object_or_404(ChatGroup, id=group_id, is_active=True)
        
        # Verify requester is admin of the group
        requester_membership = ChatGroupMember.objects.filter(
            group=group,
            user=request.user,
            is_active=True
        ).first()
        
        if not requester_membership or requester_membership.role not in ['admin', 'moderator']:
            return JsonResponse({'success': False, 'error': 'Only admins can add members'})
        
        # Find user by email
        try:
            new_user = User.objects.get(email=user_email)
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User not found'})
        
        # Check if already a member
        if ChatGroupMember.objects.filter(group=group, user=new_user).exists():
            return JsonResponse({'success': False, 'error': 'User is already a member'})
        
        # Add member
        ChatGroupMember.objects.create(
            group=group,
            user=new_user,
            role='member'
        )
        
        # Add system message
        ChatMessage.objects.create(
            group=group,
            content=f"{new_user.username or new_user.email} was added to the group",
            message_type='system'
        )
        
        return JsonResponse({
            'success': True,
            'message': f'{new_user.email} added to the group'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@ajax_login_required
def chat_get_members(request):
    """API to get members of a group"""
    group_id = request.GET.get('group_id')
    
    if not group_id:
        return JsonResponse({'success': False, 'error': 'Group ID is required'})
    
    try:
        group = get_object_or_404(ChatGroup, id=group_id, is_active=True)
        
        # Verify user is member
        if not ChatGroupMember.objects.filter(group=group, user=request.user, is_active=True).exists():
            return JsonResponse({'success': False, 'error': 'Not a member of this group'})
        
        members = ChatGroupMember.objects.filter(
            group=group,
            is_active=True
        ).select_related('user').order_by('role', 'joined_at')
        
        members_data = []
        for member in members:
            members_data.append({
                'id': member.user.id,
                'email': member.user.email,
                'username': member.user.username or member.user.email.split('@')[0],
                'role': member.role,
                'joined_at': member.joined_at.strftime('%Y-%m-%d'),
                'is_current_user': member.user == request.user
            })
        
        return JsonResponse({
            'success': True,
            'members': members_data,
            'group_name': group.name
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@ajax_login_required
def chat_leave_group(request):
    """API to leave a chat group"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})
    
    try:
        data = json.loads(request.body) if request.body else request.POST
        group_id = data.get('group_id')
        
        if not group_id:
            return JsonResponse({'success': False, 'error': 'Group ID is required'})
        
        group = get_object_or_404(ChatGroup, id=group_id)
        
        membership = ChatGroupMember.objects.filter(
            group=group,
            user=request.user,
            is_active=True
        ).first()
        
        if not membership:
            return JsonResponse({'success': False, 'error': 'Not a member of this group'})
        
        # Don't allow leaving support chats
        if group.group_type == 'support':
            return JsonResponse({'success': False, 'error': 'Cannot leave support chat'})
        
        # Deactivate membership
        membership.is_active = False
        membership.save()
        
        # Add system message
        ChatMessage.objects.create(
            group=group,
            content=f"{request.user.username or request.user.email} left the group",
            message_type='system'
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Left the group successfully'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@ajax_login_required
def chat_search_users(request):
    """API to search users for adding to groups"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'success': True, 'users': []})
    
    try:
        users = User.objects.filter(
            email__icontains=query
        ).exclude(id=request.user.id)[:10]
        
        users_data = []
        for user in users:
            users_data.append({
                'id': user.id,
                'email': user.email,
                'username': user.username or user.email.split('@')[0]
            })
        
        return JsonResponse({
            'success': True,
            'users': users_data
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ============ AI Chat Support ============

@ajax_login_required
def ai_chat(request):
    """API endpoint for AI-powered chat responses"""
    print(f"[DEBUG ai_chat] Request method: {request.method}")
    print(f"[DEBUG ai_chat] Request headers: {dict(request.headers)}")
    print(f"[DEBUG ai_chat] Request body: {request.body[:200] if request.body else 'Empty'}")
    print(f"[DEBUG ai_chat] User authenticated: {request.user.is_authenticated}")
    
    if request.method != 'POST':
        print(f"[DEBUG ai_chat] ERROR: Method is {request.method}, not POST")
        return JsonResponse({'success': False, 'error': 'POST required'})

    
    try:
        data = json.loads(request.body) if request.body else {}
        user_message = data.get('message', '').strip()
        
        print(f"[DEBUG ai_chat] Parsed message: {user_message}")
        
        if not user_message:
            return JsonResponse({'success': False, 'error': 'Message is required'})
        
        # Debug: Print user info
        print(f"AI Chat - User: {request.user.email}, ID: {request.user.id}")
        
        # Debug: Check baskets for this user
        from .models import Basket
        user_baskets = Basket.objects.filter(user=request.user)
        print(f"AI Chat - User has {user_baskets.count()} baskets")
        for b in user_baskets:
            print(f"  - Basket: {b.name}, ID: {b.id}")
        
        # Import AI service
        from .ai_service import ai_service
        
        # Generate AI response with user's portfolio context
        ai_response = ai_service.generate_response(user_message, request.user)
        
        return JsonResponse({
            'success': True,
            'response': ai_response,
            'is_ai': True
        })
        
    except Exception as e:
        print(f"AI Chat Error: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False, 
            'error': str(e),
            'response': "I'm having trouble right now. Please try again or contact human support."
        })


# ==========================================
# Tiny URL for Basket Sharing
# ==========================================

import string
import random
from .models import TinyURL


def generate_short_code(length=6):
    """Generate a random short code for URLs"""
    characters = string.ascii_letters + string.digits
    while True:
        code = ''.join(random.choice(characters) for _ in range(length))
        # Check if this code already exists
        if not TinyURL.objects.filter(short_code=code).exists():
            return code


@login_required
def create_tiny_url(request, basket_id):
    """Create a tiny URL for basket sharing"""
    basket = get_object_or_404(Basket, id=basket_id, user=request.user)
    
    # Check if a tiny URL already exists for this basket
    existing_tiny_url = TinyURL.objects.filter(
        basket=basket,
        is_active=True
    ).first()
    
    if existing_tiny_url and not existing_tiny_url.is_expired():
        # Return existing URL
        short_url = request.build_absolute_uri(f'/s/{existing_tiny_url.short_code}')
        return JsonResponse({
            'success': True,
            'short_code': existing_tiny_url.short_code,
            'short_url': short_url,
            'original_url': existing_tiny_url.original_url,
            'click_count': existing_tiny_url.click_count
        })
    
    # Create new tiny URL
    original_url = request.build_absolute_uri(f'/basket/{basket_id}/')
    short_code = generate_short_code()
    
    tiny_url = TinyURL.objects.create(
        short_code=short_code,
        original_url=original_url,
        basket=basket,
        created_by=request.user,
        is_active=True
    )
    
    short_url = request.build_absolute_uri(f'/s/{short_code}')
    
    return JsonResponse({
        'success': True,
        'short_code': short_code,
        'short_url': short_url,
        'original_url': original_url,
        'click_count': 0
    })


def redirect_tiny_url(request, short_code):
    """Redirect from short URL to original basket URL"""
    tiny_url = get_object_or_404(TinyURL, short_code=short_code, is_active=True)
    
    # Check if expired
    if tiny_url.is_expired():
        messages.error(request, 'This link has expired.')
        return redirect('home')
    
    # Increment click count
    tiny_url.increment_clicks()
    
    # Redirect to the basket detail page
    # Extract basket_id from the original URL or use the basket relation
    if tiny_url.basket:
        return redirect('basket_detail', basket_id=tiny_url.basket.id)
    else:
        # Fallback to original URL if basket is not linked
        return redirect(tiny_url.original_url)


@login_required
def tiny_url_stats(request, short_code):
    """Get statistics for a tiny URL"""
    tiny_url = get_object_or_404(TinyURL, short_code=short_code, created_by=request.user)
    
    return JsonResponse({
        'success': True,
        'short_code': tiny_url.short_code,
        'original_url': tiny_url.original_url,
        'click_count': tiny_url.click_count,
        'created_at': tiny_url.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'expires_at': tiny_url.expires_at.strftime('%Y-%m-%d %H:%M:%S') if tiny_url.expires_at else None,
        'is_active': tiny_url.is_active,
        'is_expired': tiny_url.is_expired()
    })


# ============================================================
# AI Stock Summary API (async — loaded after page render)
# ============================================================

def ai_stock_summary(request, symbol):
    """
    Async endpoint: returns LLM-generated 3-section fundamental summary.
    Called by JS after stock_detail page renders to avoid slowing initial load.
    """
    from django.core.cache import cache
    from .ai_service import stock_ai_service

    # Reuse cached stock data from stock_detail view
    cache_key = f'stock_detail_v2_{symbol}'
    cached_ctx = cache.get(cache_key)

    if not cached_ctx:
        # Fetch minimal data if not cached yet
        from .stock_analysis import get_stock_fundamentals, get_technical_indicators, get_buy_recommendation, get_news_sentiment, get_ownership_analysis, get_policy_alignment, get_global_impact
        fundamentals = get_stock_fundamentals(symbol)
        indicators   = get_technical_indicators(symbol)
        news         = get_news_sentiment(symbol)
        ownership    = get_ownership_analysis(fundamentals)
        policy       = get_policy_alignment(fundamentals.get('sector', ''), news.get('articles', []))
        global_data  = get_global_impact(fundamentals.get('sector', ''))
        recommendation = get_buy_recommendation(fundamentals, indicators, news=news, ownership=ownership, policy=policy, global_impact=global_data)
    else:
        fundamentals   = cached_ctx.get('fundamentals', {})
        indicators     = cached_ctx.get('indicators', {})
        recommendation = cached_ctx.get('recommendation', {})

    summary = stock_ai_service.generate_fundamental_summary(
        symbol=symbol,
        fundamentals=fundamentals,
        indicators=indicators,
        recommendation=recommendation,
    )

    return JsonResponse({
        'success': True,
        'symbol': symbol,
        'overview': summary.get('overview'),
        'bullish_summary': summary.get('bullish_summary'),
        'risk_summary': summary.get('risk_summary'),
        'cached': summary.get('cached', False),
    })


# ============================================================
# AI News Sentiment Enhancement API
# ============================================================

def ai_news_sentiment(request, symbol):
    """
    Returns LLM-enhanced sentiment for each news article of a stock.
    """
    from django.core.cache import cache
    from .ai_service import stock_ai_service

    cache_key = f'stock_detail_v2_{symbol}'
    cached_ctx = cache.get(cache_key)
    articles = cached_ctx.get('news', {}).get('articles', []) if cached_ctx else []

    if not articles:
        from .stock_analysis import get_news_sentiment
        news = get_news_sentiment(symbol)
        articles = news.get('articles', [])

    enhanced = stock_ai_service.enhance_news_sentiment(symbol, articles)
    return JsonResponse({'success': True, 'articles': enhanced})


# ============================================================
# Autonomous Portfolio Agent API
# ============================================================

@ajax_login_required
def portfolio_agent_run(request, basket_id):
    """
    POST: Triggers the autonomous portfolio agent for a basket.
    Returns the full analysis + LLM-generated rebalancing report as JSON.
    Can take 30-120s for large baskets (runs stock analysis in parallel threads).
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)

    from .portfolio_agent import portfolio_agent

    try:
        result = portfolio_agent.run(basket_id=basket_id, user=request.user)
        if result.get('error') and not result.get('report'):
            return JsonResponse({'success': False, 'error': result['error']})

        return JsonResponse({
            'success': True,
            'basket_name': result.get('basket_name'),
            'total_investment': result.get('total_investment'),
            'total_value': result.get('total_value'),
            'pnl': result.get('pnl'),
            'pnl_pct': result.get('pnl_pct'),
            'report': result.get('report'),
            'cached': result.get('cached', False),
            'stocks_count': len(result.get('stocks_analysis', [])),
            'stocks_analysis': [
                {
                    'symbol': s.get('symbol'),
                    'verdict': s.get('recommendation', {}).get('verdict'),
                    'score': s.get('recommendation', {}).get('score'),
                    'sharpe': s.get('quant', {}).get('sharpe_ratio'),
                }
                for s in result.get('stocks_analysis', [])
            ],
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ============================================================
# RAG Document Upload API
# ============================================================

@ajax_login_required
def rag_upload_document(request, symbol):
    """
    POST: Upload a PDF document for a stock (admin-only by default, but can
    be opened to all users by removing the staff check below).
    Kicks off async indexing via RAG pipeline.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)

    # Admin-only upload restriction
    if not request.user.is_staff and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Staff access required to upload documents'}, status=403)

    uploaded_file = request.FILES.get('file')
    if not uploaded_file:
        return JsonResponse({'success': False, 'error': 'No file uploaded'})

    if not uploaded_file.name.lower().endswith('.pdf'):
        return JsonResponse({'success': False, 'error': 'Only PDF files are supported'})

    title = request.POST.get('title', uploaded_file.name.replace('.pdf', ''))
    doc_type = request.POST.get('document_type', 'other')
    fiscal_year = request.POST.get('fiscal_year', '')

    db_stock = Stock.objects.filter(symbol=symbol).first()
    if not db_stock:
        return JsonResponse({'success': False, 'error': f'Stock {symbol} not found in database'})

    from .models import StockDocument
    from .pgvector_rag_service import pgvector_rag_service as rag_service

    # Save to DB
    doc = StockDocument.objects.create(
        stock=db_stock,
        title=title,
        document_type=doc_type,
        file=uploaded_file,
        uploaded_by=request.user,
        fiscal_year=fiscal_year,
        is_indexed=False,
    )

    # Index synchronously (for small PDFs this is fast; large PDFs may take ~10s)
    result = rag_service.ingest_document(
        symbol=symbol,
        document_id=doc.id,
        file_path=doc.file.path,
        doc_title=title,
        doc_type=doc_type,
    )

    if result['success']:
        return JsonResponse({
            'success': True,
            'document_id': doc.id,
            'title': doc.title,
            'chunk_count': result['chunk_count'],
            'message': f"Document indexed successfully with {result['chunk_count']} chunks.",
        })
    else:
        doc.delete()  # Clean up on failure
        return JsonResponse({'success': False, 'error': result.get('error', 'Indexing failed')})


# ============================================================
# RAG Query API — "Chat with a Stock"
# ============================================================

@ajax_login_required
def rag_query_document(request, symbol):
    """
    POST: Query indexed documents for a stock using natural language.
    Body: {'question': 'What did management say about expansion?', 'doc_type': 'earnings_call'}
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)

    import json as json_lib
    try:
        body = json_lib.loads(request.body)
    except Exception:
        body = request.POST

    question = body.get('question', '').strip()
    doc_type  = body.get('doc_type', None) or None

    if not question:
        return JsonResponse({'success': False, 'error': 'Question is required'})
    if len(question) > 500:
        return JsonResponse({'success': False, 'error': 'Question too long (max 500 chars)'})

    from .pgvector_rag_service import pgvector_rag_service as rag_service

    result = rag_service.query(symbol=symbol, question=question, doc_type=doc_type)

    if result.get('error'):
        return JsonResponse({'success': False, 'error': result['error']})

    return JsonResponse({
        'success': True,
        'answer': result.get('answer'),
        'sources': result.get('sources', []),
    })


# ============================================================
# RAG Re-index API (admin) — fixes ChromaDB data loss
# ============================================================

@ajax_login_required
def rag_reindex_documents(request, symbol):
    """
    POST: Force re-index all documents for a stock from their saved PDF files.
    Admin-only. Useful when ChromaDB data is lost but DB records remain.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)

    if not request.user.is_staff and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Staff access required'}, status=403)

    from .pgvector_rag_service import pgvector_rag_service as rag_service
    result = rag_service.reindex_symbol(symbol=symbol)

    return JsonResponse({
        'success': result['success'],
        'indexed': result['indexed'],
        'errors': result['errors'],
        'message': f"Re-indexed {result['indexed']} document(s) for {symbol}." + (
            f" Errors: {'; '.join(result['errors'][:3])}" if result['errors'] else ""
        ),
    })


# ============================================================
# RAG Document List API
# ============================================================

def rag_list_documents(request, symbol):
    """
    GET: Returns list of indexed documents for a stock.
    Public endpoint — no auth required to view what docs are available.
    """
    from .pgvector_rag_service import pgvector_rag_service as rag_service
    from .models import StockDocument

    try:
        docs = StockDocument.objects.filter(stock__symbol=symbol).order_by('-uploaded_at')
        doc_list = [
            {
                'id': d.id,
                'title': d.title,
                'document_type': d.document_type,
                'document_type_display': d.get_document_type_display(),
                'fiscal_year': d.fiscal_year,
                'is_indexed': d.is_indexed,
                'chunk_count': d.chunk_count,
                'uploaded_at': d.uploaded_at.strftime('%d %b %Y'),
            }
            for d in docs
        ]
        return JsonResponse({'success': True, 'documents': doc_list, 'symbol': symbol})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@ajax_login_required
def rag_delete_document(request, symbol, doc_id):
    """
    POST: Delete an uploaded financial document.
    Admin-only.
    """
    import os
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)

    if not request.user.is_staff and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Staff access required'}, status=403)

    from .models import StockDocument
    doc = get_object_or_404(StockDocument, id=doc_id, stock__symbol=symbol)
    
    title = doc.title
    
    # Delete file if exists
    if doc.file and os.path.exists(doc.file.path):
        try:
            os.remove(doc.file.path)
        except Exception as e:
            logger.warning(f"Could not delete document file: {e}")
            
    doc.delete()

    return JsonResponse({
        'success': True,
        'message': f"Document '{title}' deleted successfully."
    })

