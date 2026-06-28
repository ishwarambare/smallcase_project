# HTMX Implementation Guide - Add Stock to Basket

This document explains step-by-step how I implemented the "Add Stock to Basket" feature using HTMX without page reload.

## Table of Contents
1. [Problem Statement](#problem-statement)
2. [Solution Overview](#solution-overview)
3. [Implementation Steps](#implementation-steps)
4. [Code Explanation](#code-explanation)
5. [How It Works](#how-it-works)
6. [Troubleshooting](#troubleshooting)

---

## Problem Statement

**Issue:** When adding a stock to a basket, the stock wasn't appearing in the table without a page refresh.

**Requirements:**
- Add stock to basket dynamically (no page reload)
- Update the table to show the new stock
- Keep the code simple and maintainable
- Use only existing templates (no new files)

---

## Solution Overview

I used **HTMX** to:
1. Load available stocks in a modal
2. Send POST request to add stock
3. Swap the updated table HTML without page reload
4. Re-initialize HTMX for subsequent operations

**Key Technologies:**
- HTMX (for AJAX and DOM swapping)
- Jinja2 (for template rendering)
- Django (backend)

---

## Implementation Steps

### Step 1: Backend View (`stocks/views.py`)

Created a view that handles adding stock and returns updated HTML:

```python
@login_required
def basket_stock_add(request, basket_id):
    """Add a stock to basket and update the table without page reload"""
    from django.http import JsonResponse, HttpResponse
    from .utils import add_stock_to_basket
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})
    
    # Verify basket ownership
    basket = get_object_or_404(Basket, id=basket_id, user=request.user)
    
    try:
        # Get stock_id from POST data
        stock_id = request.POST.get('stock_id')
        
        if not stock_id:
            return JsonResponse({'success': False, 'error': 'Stock ID is required'})
        
        # Add stock using utility function
        result = add_stock_to_basket(basket_id, stock_id, quantity=0)
        
        if not result['success']:
            # Return error for HTMX
            if request.htmx:
                return HttpResponse(
                    f'<div style="color: #ef4444; padding: 10px;">{result["message"]}</div>', 
                    status=400
                )
            return JsonResponse(result)
        
        # Clear caches
        cache.delete_many([
            f'basket_value_{basket.id}*',
            f'basket_metrics_{basket.id}*',
            f'chart_data_{basket.id}*',
            f'performance_{basket.id}'
        ])
        
        # For HTMX requests, render the updated table
        if request.htmx:
            # Refresh basket from database
            basket.refresh_from_db()
            
            # Get updated items
            items = basket.items.select_related('stock').all()
            total_current_value = basket.get_total_value()
            total_profit_loss = basket.get_profit_loss()
            
            # Render Jinja2 template
            from django.template import engines
            jinja_env = engines['jinja2'].env
            template = jinja_env.get_template('stocks/_stock_holdings_table.j2')
            
            html = template.render({
                'basket': basket,
                'items': items,
                'total_current_value': total_current_value,
                'total_profit_loss': total_profit_loss,
                'url': lambda name, args=None: f'/{name}/' if not args else f'/{name}/{"/".join(map(str, args))}/',
            })
            
            return HttpResponse(html)
        
        # For non-HTMX requests
        return JsonResponse({
            'success': True,
            'message': result['message'],
        })
        
    except Exception as e:
        if request.htmx:
            return HttpResponse(
                f'<div style="color: #ef4444; padding: 10px;">Error: {str(e)}</div>', 
                status=500
            )
        return JsonResponse({'success': False, 'error': str(e)})
```

**Key Points:**
- Checks if request is from HTMX using `request.htmx`
- Renders Jinja2 template with updated data
- Returns HTML (not JSON) for HTMX to swap
- Handles errors gracefully

---

### Step 2: Template - Stock Holdings Table (`_stock_holdings_table.j2`)

The template includes a modal with HTMX attributes:

```html
<!-- Container for the table (HTMX target) -->
<div id="stock_holdings_table">
    <!-- Stock Holdings Table -->
    <div class="stock-holdings-header">
        <h2>Stock Holdings ({{ items|length }} stocks)</h2>
        <button class="btn btn-primary" onclick="openAddStockModal()">
            ➕ Add Stock
        </button>
    </div>

    <table class="stocks-table">
        <!-- Table content here -->
    </table>

    <!-- Add Stock Modal -->
    <div id="add-stock-modal" class="modal-overlay" style="display: none;">
        <div class="modal-content">
            <div class="modal-header">
                <h3>Add Stock to Basket</h3>
                <button onclick="closeAddStockModal()">×</button>
            </div>
            <div class="modal-body">
                <!-- Search input -->
                <input type="text" id="stock-search-input" 
                       placeholder="Search stocks..."
                       onkeyup="filterAvailableStocks()">
                
                <!-- Available stocks list (loaded via HTMX) -->
                <div id="available-stocks-list"
                     hx-get="{{ url('basket_available_stocks', args=[basket.id]) }}"
                     hx-trigger="load"
                     hx-indicator="#stocks-loading">
                    <div id="stocks-loading">Loading stocks...</div>
                </div>
            </div>
        </div>
    </div>
</div>
```

**HTMX Attributes Explained:**
- `hx-get`: URL to fetch available stocks
- `hx-trigger="load"`: Trigger request when element loads
- `hx-indicator`: Show loading indicator

---

### Step 3: Template - Available Stocks List (`_available_stocks_list.j2`)

Each stock has an "Add" button with HTMX:

```html
{% for stock in stocks %}
<div class="stock-item">
    <div>
        <strong>{{ stock.symbol }}</strong><br>
        <small>{{ stock.name }}</small>
    </div>
    <div>
        <span>₹{{ stock.current_price|round(2) }}</span>
        
        <!-- Add button with HTMX -->
        <button class="btn btn-primary btn-small stock-add-btn"
                hx-post="{{ url('basket_stock_add', args=[basket_id]) }}"
                hx-vals='{"stock_id": {{ stock.id }}}'
                hx-target="#stock_holdings_table"
                hx-swap="innerHTML"
                hx-indicator="#add-stock-spinner-{{ stock.id }}"
                hx-on::after-request="
                    if(event.detail.successful) { 
                        this.disabled = true; 
                        this.textContent = 'Added ✓'; 
                        this.style.backgroundColor = '#10b981';
                        setTimeout(() => closeAddStockModal(), 800);
                        showMessage('Stock added successfully!', 'success');
                    } else {
                        const errorMsg = event.detail.xhr?.responseText || 'Failed to add stock';
                        showMessage(errorMsg, 'error');
                    }
                ">
            Add
            <span id="add-stock-spinner-{{ stock.id }}" class="htmx-indicator">
                <!-- Spinner SVG -->
            </span>
        </button>
    </div>
</div>
{% endfor %}
```

**HTMX Attributes Explained:**
- `hx-post`: URL to add stock
- `hx-vals`: JSON data to send (stock_id)
- `hx-target`: Element to update (#stock_holdings_table)
- `hx-swap="innerHTML"`: Replace inner HTML of target
- `hx-indicator`: Show spinner during request
- `hx-on::after-request`: JavaScript to run after request

---

### Step 4: JavaScript - Modal Handling (`_stock_holdings_table.js`)

Simple JavaScript to open/close modal and re-initialize HTMX:

```javascript
// Open modal and load stocks
function openAddStockModal() {
    const modal = document.getElementById('add-stock-modal');
    modal.style.display = 'flex';
    
    // Clear search input
    const searchInput = document.getElementById('stock-search-input');
    if (searchInput) {
        searchInput.value = '';
    }
    
    // Re-process HTMX on the stocks list
    // This is needed because the modal was replaced by HTMX swap
    const stocksList = document.getElementById('available-stocks-list');
    if (stocksList) {
        htmx.process(stocksList);  // Re-initialize HTMX
        htmx.trigger(stocksList, 'load');  // Trigger load
    }
}

// Close modal
function closeAddStockModal() {
    const modal = document.getElementById('add-stock-modal');
    modal.style.display = 'none';
}

// Filter stocks by search term
function filterAvailableStocks() {
    const searchTerm = document.getElementById('stock-search-input').value.toLowerCase();
    const stockItems = document.querySelectorAll('#available-stocks-list .stock-item');
    
    stockItems.forEach(item => {
        const symbol = item.getAttribute('data-symbol');
        const name = item.getAttribute('data-name');
        
        if (symbol.includes(searchTerm) || name.includes(searchTerm)) {
            item.style.display = 'flex';
        } else {
            item.style.display = 'none';
        }
    });
}

// Close modal on click outside or Escape key
document.addEventListener('click', function(event) {
    const modal = document.getElementById('add-stock-modal');
    if (event.target === modal) {
        closeAddStockModal();
    }
});

document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        closeAddStockModal();
    }
});
```

**Key Functions:**
- `openAddStockModal()`: Opens modal and re-initializes HTMX
- `closeAddStockModal()`: Closes modal
- `filterAvailableStocks()`: Filters stocks by search term
- `htmx.process()`: Re-initializes HTMX on element
- `htmx.trigger()`: Triggers HTMX request

---

## How It Works

### Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ 1. User clicks "Add Stock" button                          │
│    → openAddStockModal() is called                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Modal opens and HTMX loads available stocks             │
│    → hx-get="/basket/{id}/available-stocks/"               │
│    → hx-trigger="load"                                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Backend returns list of available stocks                │
│    → basket_get_available_stocks() view                    │
│    → Renders _available_stocks_list.j2                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. User clicks "Add" on a stock                            │
│    → hx-post="/basket/{id}/stock/add/"                     │
│    → hx-vals='{"stock_id": 123}'                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Backend adds stock and returns updated table HTML       │
│    → basket_stock_add() view                               │
│    → add_stock_to_basket() utility                         │
│    → Renders _stock_holdings_table.j2                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. HTMX swaps the table HTML                               │
│    → hx-target="#stock_holdings_table"                     │
│    → hx-swap="innerHTML"                                    │
│    → Table updates with new stock!                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. Success message shown, modal closes                     │
│    → hx-on::after-request event handler                    │
│    → closeAddStockModal() after 800ms                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Code Explanation

### Why `htmx.process()` is needed?

When HTMX swaps content, it replaces the entire `#stock_holdings_table` div, including the modal. This means:
- The modal is a fresh copy from the template
- HTMX hasn't processed it yet
- The `hx-get` attribute won't work

**Solution:** Call `htmx.process(element)` to tell HTMX to scan and initialize the element.

```javascript
htmx.process(stocksList);  // Initialize HTMX on this element
htmx.trigger(stocksList, 'load');  // Trigger the hx-get request
```

### Why render Jinja2 template in Django view?

HTMX expects HTML response, not JSON. So we:
1. Get the Jinja2 template engine
2. Render the template with updated data
3. Return HTML response

```python
jinja_env = engines['jinja2'].env
template = jinja_env.get_template('stocks/_stock_holdings_table.j2')
html = template.render({...})
return HttpResponse(html)
```

### Why `hx-swap="innerHTML"`?

This tells HTMX to replace the **inner content** of `#stock_holdings_table`, not the element itself.

```html
<!-- Before swap -->
<div id="stock_holdings_table">
    <table>Old content</table>
</div>

<!-- After swap -->
<div id="stock_holdings_table">
    <table>New content with added stock</table>
</div>
```

---

## Troubleshooting

### Issue: Stocks not loading when modal opens second time

**Cause:** HTMX not re-initialized after swap

**Solution:** Call `htmx.process()` in `openAddStockModal()`

```javascript
htmx.process(stocksList);
htmx.trigger(stocksList, 'load');
```

### Issue: Page reloads after adding stock

**Cause:** Backend returning `HX-Refresh: true` header

**Solution:** Remove the header and return HTML instead

```python
# ❌ Don't do this
response['HX-Refresh'] = 'true'

# ✅ Do this
return HttpResponse(html)
```

### Issue: Stock added but table not updating

**Cause:** Wrong HTMX target or swap method

**Solution:** Check `hx-target` and `hx-swap` attributes

```html
hx-target="#stock_holdings_table"  <!-- Correct ID -->
hx-swap="innerHTML"  <!-- Replace inner content -->
```

---

## Summary

This implementation is:
- ✅ **Simple**: No complex JavaScript or event handling
- ✅ **Clean**: Uses existing templates, no new files
- ✅ **Fast**: No page reload, instant updates
- ✅ **Maintainable**: Easy to understand and modify

**Key Takeaways:**
1. HTMX handles AJAX and DOM updates automatically
2. `htmx.process()` re-initializes HTMX after content swap
3. Backend returns HTML (not JSON) for HTMX
4. Jinja2 templates can be rendered in Django views
5. Keep it simple - let HTMX do the heavy lifting!

---

## Files Modified

1. **`stocks/views.py`** - `basket_stock_add()` function
2. **`stocks/static/js/pages/_stock_holdings_table.js`** - Modal handling
3. **`stocks/static/js/pages/basket-detail.js`** - Removed complex code

## Files Used (No Changes)

1. **`stocks/templates/stocks/_stock_holdings_table.j2`** - Main table template
2. **`stocks/templates/stocks/_available_stocks_list.j2`** - Available stocks list

---

**That's it! Simple, clean, and effective HTMX implementation.** 🚀
