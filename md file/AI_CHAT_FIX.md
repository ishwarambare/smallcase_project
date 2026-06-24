# AI Chat Error Fix - JSON Parsing Issue

## Problem
The chat widget was encountering the following error:
```
❌ Error getting AI response: SyntaxError: Unexpected token '<', "<!DOCTYPE "... is not valid JSON
```

This error occurred when the frontend JavaScript tried to call the AI chat API endpoint at `/api/ai/chat/`.

## Root Cause
The issue was caused by **authentication handling** in the `ai_chat` view function:

1. The `ai_chat` endpoint was using the `@login_required` decorator
2. When an unauthenticated user (or a user whose session expired) tried to call this API endpoint via AJAX, Django's `@login_required` decorator would redirect to the login page
3. The AJAX request received an **HTML login page** response (starting with `<!DOCTYPE ...>`) instead of the expected JSON
4. The JavaScript code tried to parse this HTML as JSON, causing the "Unexpected token '<'" error

## Solution
Created a custom `@ajax_login_required` decorator that:
- Checks if the user is authenticated
- Returns a **JSON response** with an error message (instead of an HTML redirect)
- Sets appropriate HTTP status code (401 Unauthorized)

### Changes Made

#### 1. Added Custom Decorator (`stocks/views.py`)
```python
# Custom decorator for AJAX requests that need authentication
def ajax_login_required(view_func):
    """Decorator for AJAX views that require authentication - returns JSON instead of redirecting"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper
```

#### 2. Updated AI Chat Endpoint
Changed the decorator on the `ai_chat` function from:
```python
@login_required
def ai_chat(request):
    ...
```

To:
```python
@ajax_login_required
def ai_chat(request):
    ...
```

## Result
Now when the AI chat endpoint is called:
- **Authenticated users**: Get proper AI responses in JSON format
- **Unauthenticated users**: Get a JSON error response instead of an HTML redirect
- The JavaScript can properly parse the response without errors

## Testing
To test the fix:
1. Open the chat widget while logged in
2. Send a message to the AI
3. Verify that you receive a proper AI response without console errors

If you're logged out:
1. The chat should show a proper authentication error message
2. No "Unexpected token" errors should appear in the console

## Future Improvements
Consider applying the `@ajax_login_required` decorator to other API endpoints in the application that also use `@login_required`, to ensure consistent AJAX error handling across all API endpoints.
