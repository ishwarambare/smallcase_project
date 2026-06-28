# HTMX Quick Reference - Add Stock Feature

## Quick Commands

### Test the Feature
1. Navigate to basket detail page: `http://localhost:1234/basket/{id}/`
2. Click "➕ Add Stock" button
3. Click "Add" on any stock
4. Stock should appear in table instantly (no page reload)

### Debug Issues
```bash
# Check Django server logs
# Look for errors in terminal where server is running

# Check browser console
# Press F12 → Console tab
# Look for JavaScript errors

# Check HTMX requests
# Press F12 → Network tab
# Filter by "XHR" or "Fetch"
# Look for POST to /basket/{id}/stock/add/
```

---

## HTMX Attributes Cheat Sheet

### Load Content on Page Load
```html
<div hx-get="/api/endpoint/" 
     hx-trigger="load"
     hx-indicator="#loading">
</div>
```

### POST Request on Button Click
```html
<button hx-post="/api/endpoint/"
        hx-vals='{"key": "value"}'
        hx-target="#target-element"
        hx-swap="innerHTML">
    Click Me
</button>
```

### After Request Event Handler
```html
<button hx-on::after-request="
    if(event.detail.successful) {
        console.log('Success!');
    }
">
    Submit
</button>
```

### Common Swap Methods
- `innerHTML` - Replace inner content
- `outerHTML` - Replace entire element
- `beforebegin` - Insert before element
- `afterend` - Insert after element
- `delete` - Delete element

---

## JavaScript Functions

### Re-initialize HTMX
```javascript
// After content is swapped, re-initialize HTMX
const element = document.getElementById('my-element');
htmx.process(element);  // Scan for HTMX attributes
htmx.trigger(element, 'load');  // Trigger hx-get request
```

### Show Message
```javascript
function showMessage(message, type) {
    const container = document.getElementById('message-container');
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.textContent = message;
    container.appendChild(alert);
    
    setTimeout(() => alert.remove(), 5000);
}
```

---

## Django View Pattern

### HTMX-Aware View
```python
@login_required
def my_view(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'})
    
    # Process request
    # ...
    
    # For HTMX requests, return HTML
    if request.htmx:
        from django.template import engines
        jinja_env = engines['jinja2'].env
        template = jinja_env.get_template('my_template.j2')
        html = template.render({'data': data})
        return HttpResponse(html)
    
    # For regular requests, return JSON
    return JsonResponse({'success': True})
```

---

## Common Patterns

### Modal with HTMX
```html
<!-- Modal -->
<div id="my-modal" style="display: none;">
    <div id="modal-content"
         hx-get="/api/load-content/"
         hx-trigger="load">
        Loading...
    </div>
</div>

<!-- Open button -->
<button onclick="openModal()">Open</button>

<script>
function openModal() {
    const modal = document.getElementById('my-modal');
    modal.style.display = 'block';
    
    // Re-initialize HTMX
    const content = document.getElementById('modal-content');
    htmx.process(content);
    htmx.trigger(content, 'load');
}
</script>
```

### Form with HTMX
```html
<form hx-post="/api/submit/"
      hx-target="#result"
      hx-swap="innerHTML">
    <input name="name" required>
    <button type="submit">Submit</button>
</form>

<div id="result"></div>
```

### Infinite Scroll
```html
<div hx-get="/api/more-items/?page=2"
     hx-trigger="revealed"
     hx-swap="afterend">
    Load More...
</div>
```

---

## Debugging Tips

### Check if HTMX is Working
```javascript
// In browser console
console.log(typeof htmx);  // Should be 'object'
```

### Check if Request is from HTMX
```python
# In Django view
print(request.htmx)  # Should be True for HTMX requests
print(request.headers.get('HX-Request'))  # Should be 'true'
```

### View HTMX Events
```javascript
// Listen to all HTMX events
document.body.addEventListener('htmx:afterSwap', (e) => {
    console.log('HTMX swapped:', e.detail);
});

document.body.addEventListener('htmx:beforeRequest', (e) => {
    console.log('HTMX request:', e.detail);
});
```

---

## Performance Tips

1. **Use `hx-indicator`** to show loading state
2. **Cache responses** on backend when possible
3. **Use `hx-swap-oob`** for out-of-band updates
4. **Debounce search inputs** with `hx-trigger="keyup delay:500ms"`
5. **Use `hx-boost`** for progressive enhancement

---

## Common Errors & Solutions

### Error: "htmx is not defined"
**Solution:** Include HTMX script in base template
```html
<script src="https://unpkg.com/htmx.org@1.9.10"></script>
```

### Error: "Element not found after swap"
**Solution:** Use `htmx:afterSwap` event
```javascript
document.body.addEventListener('htmx:afterSwap', (e) => {
    // Element is now in DOM
    const element = document.getElementById('my-element');
});
```

### Error: "HTMX not triggering on new elements"
**Solution:** Call `htmx.process()`
```javascript
htmx.process(document.getElementById('new-content'));
```

---

## Resources

- **HTMX Docs**: https://htmx.org/docs/
- **HTMX Examples**: https://htmx.org/examples/
- **django-htmx**: https://django-htmx.readthedocs.io/

---

## Project-Specific URLs

```
GET  /basket/{id}/available-stocks/  → Load available stocks
POST /basket/{id}/stock/add/         → Add stock to basket
POST /basket/{id}/stock/{stock_id}/delete/  → Delete stock from basket
```

---

**Happy coding! 🚀**
