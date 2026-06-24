# HTMX Implementation - Simplified Version

## Overview
This document explains the simplified HTMX implementation for adding stocks to baskets.

## How It Works

### 1. **User Clicks "Add Stock" Button**
   - Opens a modal with available stocks
   - Stocks are loaded via HTMX from `/basket/{id}/available-stocks/`

### 2. **User Clicks "Add" on a Stock**
   - HTMX sends POST request to `/basket/{id}/stock/add/`
   - Includes `stock_id` in the request

### 3. **Backend Processing** (`views.py`)
   ```python
   def basket_stock_add(request, basket_id):
       # Add stock to basket
       result = add_stock_to_basket(basket_id, stock_id, quantity=0)
       
       # Render updated table using Jinja2 template
       template = jinja_env.get_template('stocks/_stock_holdings_table.j2')
       html = template.render({...})
       
       # Return HTML to HTMX
       return HttpResponse(html)
   ```

### 4. **HTMX Swaps Content**
   - Replaces `#stock_holdings_table` with new HTML
   - **No page reload needed!**
   - Modal closes automatically
   - Success message shown

### 5. **Modal Reopening**
   - When modal opens again, `htmx.process()` re-initializes HTMX
   - This ensures the stock list loads properly

## Files Involved

### Backend
- **`stocks/views.py`**: `basket_stock_add()` function
- **`stocks/utils.py`**: `add_stock_to_basket()` utility

### Frontend Templates
- **`stocks/templates/stocks/_stock_holdings_table.j2`**: Main table template
- **`stocks/templates/stocks/_available_stocks_list.j2`**: Available stocks list

### JavaScript
- **`stocks/static/js/pages/_stock_holdings_table.js`**: Modal and HTMX handling
- **`stocks/static/js/pages/basket-detail.js`**: Chart and other functionality

## Key Points

1. **No Complex Code**: Just simple HTMX attributes and template rendering
2. **No Page Reload**: HTMX swaps content in place
3. **One Template**: Uses existing `_stock_holdings_table.j2` (no new files)
4. **Simple JavaScript**: Just `htmx.process()` to re-initialize after swap

## HTMX Attributes Used

```html
<!-- Load available stocks -->
<div hx-get="/basket/{id}/available-stocks/" 
     hx-trigger="load" 
     hx-indicator="#stocks-loading">
</div>

<!-- Add stock button -->
<button hx-post="/basket/{id}/stock/add/"
        hx-vals='{"stock_id": 123}'
        hx-target="#stock_holdings_table"
        hx-swap="innerHTML">
    Add
</button>
```

## That's It!
Simple, clean, and easy to understand. No complex event handling or custom headers needed.
