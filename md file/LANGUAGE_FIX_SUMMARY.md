# Quick Fix Summary: Language Switching on Railway

## The Problem
Language change functionality works locally but fails on Railway deployment.

## The Solution (3 Changes)

### 1. Dockerfile - Add gettext Package
```dockerfile
# Line 15: Add gettext to system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    gettext \  # ← NEW
    && rm -rf /var/lib/apt/lists/*
```

### 2. Dockerfile - Compile Translations
```dockerfile
# Line 26: Add before collectstatic
RUN python manage.py compilemessages  # ← NEW
```

### 3. settings.py - Configure Sessions for Railway
```python
# Added after line 252: Session configuration
IS_RAILWAY = os.environ.get('RAILWAY_ENVIRONMENT') is not None

if IS_RAILWAY:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = 'Lax'
else:
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SAMESITE = 'Lax'

SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 1209600  # 2 weeks
```

## Deploy Instructions
1. Commit changes: `git add . && git commit -m "Fix language switching on Railway"`
2. Push to Railway: `git push origin main`
3. Railway will auto-deploy with the fixes

## What Was Wrong?
- ❌ Translation files (.mo) weren't being compiled in Docker
- ❌ gettext package missing from Docker image
- ❌ Session cookies not configured for HTTPS

## What We Fixed?
- ✅ Added gettext to Dockerfile
- ✅ Added compilemessages step to Dockerfile
- ✅ Configured session cookies for Railway HTTPS

## Test After Deployment
1. Open your Railway URL
2. Click language switcher (top-right globe icon)
3. Select Hindi or Marathi
4. Page should reload in selected language
5. Navigate to other pages - language should persist

For detailed information, see: `docs/LANGUAGE_SWITCHING_FIX.md`
