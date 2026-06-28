# Language Switching Fix for Railway Deployment

## Problem Summary
The language change functionality was not working when the project was deployed to Railway server, even though it worked perfectly in local development.

## Root Causes Identified

### 1. Missing Compiled Translation Files
- **Issue**: Django's `compilemessages` command was not being run during the Docker build process
- **Impact**: The `.mo` (compiled translation) files were not present in the production Docker image
- **Why It Matters**: Django needs `.mo` files to display translations. Without them, only the default language (English) is available

### 2. Session Cookie Configuration
- **Issue**: Session cookies were not properly configured for HTTPS on Railway
- **Impact**: Language preferences (stored in Django sessions) were not persisting
- **Why It Matters**: Django's i18n stores the user's language preference in the session cookie

### 3. Missing System Dependency
- **Issue**: The `gettext` package was not installed in the Docker image
- **Impact**: The `compilemessages` command would fail during build
- **Why It Matters**: `gettext` is required to compile .po files into .mo files

## Fixes Applied

### Fix 1: Updated Dockerfile
**File**: `Dockerfile`

#### Added gettext System Dependency
```dockerfile
# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    gettext \  # ← ADDED: Required for compilemessages
    && rm -rf /var/lib/apt/lists/*
```

#### Added compilemessages Command
```dockerfile
# Copy project files
COPY . .

# Compile translation files for multi-language support
RUN python manage.py compilemessages  # ← ADDED: Compiles .po → .mo files

# Collect static files
RUN python manage.py collectstatic --noinput
```

### Fix 2: Updated Session Configuration
**File**: `smallcase_project/settings.py`

Added proper session cookie configuration that adapts to Railway vs local environment:

```python
# ============ Session Configuration ============
# Configure session cookies to work properly on Railway with HTTPS
# Language preference is stored in session, so this is critical for i18n
IS_RAILWAY = os.environ.get('RAILWAY_ENVIRONMENT') is not None

if IS_RAILWAY:
    # Production (Railway) - Use secure cookies with HTTPS
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'  # Allow language change redirects
    CSRF_COOKIE_SAMESITE = 'Lax'
else:
    # Local development - Allow http cookies
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    CSRF_COOKIE_SAMESITE = 'Lax'

# Session engine - database-backed sessions for persistence
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 1209600  # 2 weeks
SESSION_SAVE_EVERY_REQUEST = False  # Only save when modified (better performance)
```

## How Language Switching Works in Django

1. **User clicks language button** → JavaScript toggles dropdown
2. **User selects language** → Form submits to `/i18n/setlang/` endpoint
3. **Django's set_language view**:
   - Stores language code in session: `request.session[LANGUAGE_SESSION_KEY] = lang_code`
   - Sets session cookie with language preference
   - Redirects back to the current page
4. **LocaleMiddleware** reads the session on subsequent requests
5. **Django activates the selected language** and loads `.mo` translation files
6. **Templates render** with `{{ _('text') }}` using the selected language

## Why It Failed on Railway

| Component | Local (Working) | Railway (Failed) | Fix Applied |
|-----------|----------------|------------------|-------------|
| Translation files (.mo) | Present in filesystem | Missing (not compiled) | ✅ Added `compilemessages` |
| gettext package | Installed on dev machine | Not in Docker image | ✅ Added to apt-get install |
| Session cookies | HTTP cookies work | HTTPS required | ✅ Configured secure cookies |
| CSRF cookies | HTTP works | HTTPS required | ✅ Configured secure cookies |

## Testing the Fix

### Before Deploying to Railway
1. **Test locally** that language switching still works
2. **Build Docker image locally**:
   ```bash
   docker build -t smallcase-test .
   docker run -p 8000:8000 smallcase-test
   ```
3. **Verify**:
   - Check `/locale/hi/LC_MESSAGES/django.mo` exists in container
   - Check `/locale/mr/LC_MESSAGES/django.mo` exists in container
   - Test language switching at http://localhost:8000

### After Deploying to Railway
1. **Push changes** to your git repository
2. **Railway will auto-deploy** the new build
3. **Test language switching** on your Railway URL
4. **Check browser DevTools**:
   - Network tab → Look for `/i18n/setlang/` POST request
   - Application tab → Check cookies for `sessionid`
   - Verify cookie has `Secure` and `HttpOnly` flags

## Expected Behavior After Fix

✅ Language switcher dropdown appears in top-right corner  
✅ Clicking language button shows English, Hindi, Marathi options  
✅ Selecting a language reloads the page with new language  
✅ Language preference persists across page navigation  
✅ Language preference persists across browser sessions (2 weeks)  
✅ Works identically on local development and Railway production  

## Additional Notes

### Railway Environment Variable
The fix uses `RAILWAY_ENVIRONMENT` to detect Railway deployment. Railway automatically sets this variable in production.

### Session Security
- In production (Railway): Secure cookies over HTTPS only
- In development: Non-secure cookies over HTTP allowed
- Both: `SameSite=Lax` allows redirects after language change

### Translation File Workflow
1. `.po` files (editable text) → source control (git)
2. `.mo` files (compiled binary) → not in git, generated during build
3. Django reads `.mo` files at runtime for translations

## Troubleshooting

If language switching still doesn't work after deploying:

1. **Check Railway logs** for compilemessages errors:
   ```
   railway logs
   ```

2. **Verify gettext installed**:
   ```bash
   railway run bash
   which msgfmt  # Should show /usr/bin/msgfmt
   ```

3. **Check .mo files exist**:
   ```bash
   railway run bash
   ls -la locale/hi/LC_MESSAGES/
   ls -la locale/mr/LC_MESSAGES/
   ```

4. **Check session table exists**:
   ```bash
   railway run python manage.py migrate
   ```

5. **Test session creation**:
   ```python
   # In Railway run python manage.py shell
   from django.contrib.sessions.models import Session
   Session.objects.count()  # Should be > 0 if sessions work
   ```

## Related Files Modified
- ✅ `Dockerfile` - Added gettext + compilemessages
- ✅ `smallcase_project/settings.py` - Added session configuration
- 📝 `LANGUAGE_SWITCHING_FIX.md` - This documentation

## References
- [Django i18n Documentation](https://docs.djangoproject.com/en/stable/topics/i18n/)
- [Django Sessions Documentation](https://docs.djangoproject.com/en/stable/topics/http/sessions/)
- [Docker + Django Best Practices](https://docs.docker.com/samples/django/)
