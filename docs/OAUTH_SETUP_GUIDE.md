# 🔐 Complete OAuth Setup Guide (Google & GitHub)

This guide provides **detailed step-by-step instructions** for setting up social authentication (OAuth) for your Django project.

---

## Table of Contents
1. [Google OAuth Setup](#1-google-oauth-setup)
2. [GitHub OAuth Setup](#2-github-oauth-setup)
3. [Configure Django Admin](#3-configure-django-admin)
4. [Testing OAuth](#4-testing-oauth)
5. [Troubleshooting](#5-troubleshooting)

---

# 1. Google OAuth Setup

**Allows users to**: Sign in with their Google account  
**Free**: Yes  
**Time to setup**: 10-15 minutes

---

## Step 1: Create Google Cloud Project

### 1.1 Go to Google Cloud Console
1. Visit: https://console.cloud.google.com/
2. **Sign in** with your Google account
3. You'll see the Google Cloud Console dashboard

### 1.2 Create New Project
1. Click on the **project dropdown** at the top (next to "Google Cloud")
2. Click **"New Project"** button (top right of the popup)
3. Fill in project details:
   - **Project name**: `Smallcase Project` (or your app name)
   - **Organization**: Leave default (No organization)
   - **Location**: Leave default
4. Click **"Create"**
5. Wait for project creation (takes few seconds)
6. **Select your new project** from the project dropdown

✅ **Checkpoint**: You're now in your new project

---

## Step 2: Enable Google+ API

### 2.1 Navigate to APIs & Services
1. Click the **hamburger menu** (☰) in top-left
2. Navigate to: **"APIs & Services"** → **"Library"**
3. Or directly visit: https://console.cloud.google.com/apis/library

### 2.2 Search and Enable API
1. In the search box, type: `Google+ API`
2. Click on **"Google+ API"** (or "Google People API")
3. Click the **"Enable"** button
4. Wait for it to enable (few seconds)

> **Note**: If Google+ API is deprecated, enable **"Google People API"** instead

✅ **Checkpoint**: API is enabled

---

## Step 3: Configure OAuth Consent Screen

### 3.1 Go to OAuth Consent Screen
1. From left sidebar: **"APIs & Services"** → **"OAuth consent screen"**
2. Or visit: https://console.cloud.google.com/apis/credentials/consent

### 3.2 Choose User Type
1. Select **"External"** (unless you have Google Workspace)
2. Click **"Create"**

### 3.3 Fill in App Information
**Page 1 - App information**:
1. **App name**: `Smallcase Project` (your app name)
2. **User support email**: Select your email from dropdown
3. **App logo**: (Optional) Upload if you have one
4. **Application home page**: 
   - Local: `http://localhost:1234`
   - Production: `https://yourdomain.com`
5. **Application privacy policy link**: (Optional for testing)
6. **Application terms of service link**: (Optional for testing)
7. **Authorized domains**: 
   - For local: Leave empty
   - For production: Add `yourdomain.com`
8. **Developer contact information**: Your email address
9. Click **"Save and Continue"**

**Page 2 - Scopes**:
1. Click **"Add or Remove Scopes"**
2. Select these scopes:
   - ✅ `.../auth/userinfo.email`
   - ✅ `.../auth/userinfo.profile`
   - ✅ `openid`
3. Click **"Update"**
4. Click **"Save and Continue"**

**Page 3 - Test users** (Only for External type):
1. Click **"Add Users"**
2. Add your email addresses (for testing)
3. Click **"Add"**
4. Click **"Save and Continue"**

**Page 4 - Summary**:
1. Review your settings
2. Click **"Back to Dashboard"**

✅ **Checkpoint**: OAuth consent screen configured

---

## Step 4: Create OAuth Credentials

### 4.1 Go to Credentials
1. From left sidebar: **"APIs & Services"** → **"Credentials"**
2. Or visit: https://console.cloud.google.com/apis/credentials

### 4.2 Create OAuth Client ID
1. Click **"+ Create Credentials"** button (top)
2. Select **"OAuth client ID"**
3. Fill in details:
   - **Application type**: Select **"Web application"**
   - **Name**: `Django Web App` (or any name)
   
4. **Authorized JavaScript origins**:
   - Click **"+ Add URI"**
   - For local development: `http://localhost:1234`
   - For production: `https://yourdomain.com`

5. **Authorized redirect URIs**:
   - Click **"+ Add URI"**
   - Add these URLs:
   
   **For Local Development**:
   ```
   http://localhost:1234/accounts/google/login/callback/
   http://127.0.0.1:1234/accounts/google/login/callback/
   ```
   
   **For Production**:
   ```
   https://yourdomain.com/accounts/google/login/callback/
   ```
   
   > **Important**: Include the trailing slash `/`

6. Click **"Create"**

### 4.3 Copy Your Credentials
1. A popup will appear with your credentials:
   - **Client ID**: Long string like `123456-abc.apps.googleusercontent.com`
   - **Client Secret**: Shorter string
2. **Copy both** and save them securely
3. Click **"OK"**

✅ **Checkpoint**: You have Google OAuth credentials

---

# 2. GitHub OAuth Setup

**Allows users to**: Sign in with their GitHub account  
**Free**: Yes  
**Time to setup**: 5-10 minutes

---

## Step 1: Go to GitHub Developer Settings

### 1.1 Navigate to Settings
1. Visit: https://github.com/settings/developers
2. **Sign in** to your GitHub account
3. Click **"OAuth Apps"** in the left sidebar
4. Or directly visit: https://github.com/settings/developers

✅ **Checkpoint**: You're in OAuth Apps section

---

## Step 2: Create New OAuth App

### 2.1 Register Application
1. Click **"New OAuth App"** button (top right)
2. Or click **"Register a new application"** if it's your first app

### 2.2 Fill in Application Details

**Application name**:
```
Smallcase Project
```
(Or your app name)

**Homepage URL**:
- For local development:
  ```
  http://localhost:1234
  ```
- For production:
  ```
  https://yourdomain.com
  ```

**Application description** (Optional):
```
Portfolio management application with social authentication
```

**Authorization callback URL**:
- For local development:
  ```
  http://localhost:1234/accounts/github/login/callback/
  ```
- For production:
  ```
  https://yourdomain.com/accounts/github/login/callback/
  ```

> **Important**: 
> - Include `http://` or `https://`
> - Include the trailing slash `/`
> - Must match exactly what Django Allauth expects

### 2.3 Register the Application
1. Click **"Register application"** button
2. You'll be redirected to your new app's page

✅ **Checkpoint**: OAuth app created

---

## Step 3: Get Your Credentials

### 3.1 Copy Client ID
1. On your app's page, you'll see:
   - **Client ID**: Visible immediately
2. **Copy the Client ID**

### 3.2 Generate Client Secret
1. Look for **"Client secrets"** section
2. Click **"Generate a new client secret"** button
3. **IMPORTANT**: Copy the secret **immediately**!
   - Format: `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxx`
4. You **won't be able to see it again**

✅ **Checkpoint**: You have GitHub OAuth credentials

---

# 3. Configure Django Admin

Now we'll add the OAuth credentials to your Django application.

---

## Step 1: Update Environment Variables

### 1.1 Edit `.env` File
Open your `.env` file and add these lines:

```bash
# Google OAuth
GOOGLE_OAUTH_CLIENT_ID=123456789-abcdefghijklmnop.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxxxxxxxxxx

# GitHub OAuth
GITHUB_OAUTH_CLIENT_ID=Iv1.abcdef1234567890
GITHUB_OAUTH_CLIENT_SECRET=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Replace** with your actual credentials from Step 1 & 2

### 1.2 Restart Django Server
```bash
# Stop server (Ctrl+C)
python manage.py runserver 1234
```

---

## Step 2: Add Social Apps in Django Admin

### 2.1 Access Django Admin
1. Visit: http://localhost:1234/admin/
2. **Login** with your superuser account
3. If you don't have one, create it:
   ```bash
   python manage.py createsuperuser
   ```

### 2.2 Navigate to Social Applications
1. Scroll down to find **"SOCIAL ACCOUNTS"** section
2. Click on **"Social applications"**
3. Or visit: http://localhost:1234/admin/socialaccount/socialapp/

---

## Step 3: Add Google OAuth

### 3.1 Create New Social Application
1. Click **"Add Social Application"** button (top right)
2. Fill in the form:

**Provider**: Select **"Google"** from dropdown

**Name**:
```
Google
```

**Client id**:
```
123456789-abcdefghijklmnop.apps.googleusercontent.com
```
(Paste your Google Client ID)

**Secret key**:
```
GOCSPX-xxxxxxxxxxxxxxxxxxxxx
```
(Paste your Google Client Secret)

**Key**: Leave empty

**Sites**:
1. In the **"Available sites"** box, you'll see your site (e.g., `example.com`)
2. **Click on it** to select
3. Click the **arrow →** to move it to **"Chosen sites"**

3. Click **"Save"**

✅ **Checkpoint**: Google OAuth configured in Django

---

## Step 4: Add GitHub OAuth

### 4.1 Create Another Social Application
1. Click **"Add Social Application"** again
2. Fill in the form:

**Provider**: Select **"GitHub"** from dropdown

**Name**:
```
GitHub
```

**Client id**:
```
Iv1.abcdef1234567890
```
(Paste your GitHub Client ID)

**Secret key**:
```
ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
(Paste your GitHub Client Secret)

**Key**: Leave empty

**Sites**:
1. Select your site from "Available sites"
2. Move it to "Chosen sites" using the arrow →

3. Click **"Save"**

✅ **Checkpoint**: GitHub OAuth configured in Django

---

# 4. Testing OAuth

## Test Google Login

### 4.1 Visit Login Page
1. Go to: http://localhost:1234/en/login/
2. You should see the **"Continue with Google"** button

### 4.2 Click Google Login
1. Click **"Continue with Google"**
2. You'll be redirected to Google
3. Choose your Google account
4. **Important**: If you see "This app isn't verified":
   - Click **"Advanced"**
   - Click **"Go to Smallcase Project (unsafe)"**
   - This is normal for testing (your app isn't published yet)
5. Review permissions
6. Click **"Allow"** or **"Continue"**

### 4.3 Verify Login
1. You should be redirected back to your app
2. You should be **logged in** automatically
3. Check Django admin → Users to see the new user created

✅ **Success**: Google login working!

---

## Test GitHub Login

### 4.1 Visit Login Page
1. Go to: http://localhost:1234/en/login/
2. Click **"Continue with GitHub"**

### 4.2 Authorize Application
1. You'll be redirected to GitHub
2. If first time:
   - Review permissions
   - Click **"Authorize [Your App Name]"**
3. If already authorized, you'll be logged in directly

### 4.3 Verify Login
1. Redirected back to your app
2. Logged in automatically
3. Check Users in admin panel

✅ **Success**: GitHub login working!

---

# 5. Troubleshooting

## Google OAuth Issues

### Issue 1: "Redirect URI mismatch"
**Error**: `The redirect URI in the request doesn't match a registered redirect URI`

**Solution**:
1. Check your redirect URI in Google Console matches **exactly**:
   ```
   http://localhost:1234/accounts/google/login/callback/
   ```
2. Ensure trailing slash `/`
3. Check for `http://` vs `https://`
4. Port number must match (`:1234`)

---

### Issue 2: "App isn't verified"
**This is normal for development!**

**Solution**:
1. Click **"Advanced"**
2. Click **"Go to [App Name] (unsafe)"**
3. For production, submit app for verification (takes time)

---

### Issue 3: "Access blocked: Authorization Error"
**Cause**: App trying to access restricted scopes

**Solution**:
1. Ensure only using: `email`, `profile`, `openid`
2. Check OAuth consent screen scopes
3. Re-create credentials if needed

---

### Issue 4: Social app not in Django admin
**Solution**:
1. Check `INSTALLED_APPS` has:
   ```python
   'allauth.socialaccount.providers.google',
   ```
2. Run migrations: `python manage.py migrate`
3. Restart server

---

## GitHub OAuth Issues

### Issue 1: "The redirect_uri MUST match the registered callback URL"
**Solution**:
1. Verify callback URL in GitHub OAuth app settings
2. Must be exact match:
   ```
   http://localhost:1234/accounts/github/login/callback/
   ```
3. Include protocol (`http://`)
4. Include trailing slash (`/`)

---

### Issue 2: "Bad verification code"
**Solution**:
1. Clear browser cookies
2. Try in incognito/private window
3. Re-generate client secret in GitHub
4. Update secret in Django admin

---

### Issue 3: "SocialApp matching query does not exist"
**Solution**:
1. Go to Django admin
2. Add Social Application for GitHub
3. Ensure **Site** is selected in "Chosen sites"

---

## General Issues

### Issue 1: "Site matching query does not exist"
**Solution**:
```bash
python manage.py shell
```
```python
from django.contrib.sites.models import Site
site = Site.objects.get(id=1)
site.domain = 'localhost:1234'
site.name = 'Smallcase Project'
site.save()
```

---

### Issue 2: Buttons not showing on login page
**Solution**:
1. Check `urls.py` has: `path('accounts/', include('allauth.urls'))`
2. Verify social apps are in Django admin
3. Clear browser cache
4. Check template uses correct URL: `{{ url('google_login') }}`

---

### Issue 3: "Method not allowed"
**Solution**:
1. Ensure using GET request (link/button, not form POST)
2. Check URL configuration
3. Verify middleware is installed

---

# Production Checklist

Before deploying OAuth to production:

- [ ] Update OAuth redirect URIs to production domain
- [ ] Update `.env` with production URLs
- [ ] Submit Google app for verification (optional, for public apps)
- [ ] Test OAuth flow on production
- [ ] Monitor OAuth logs
- [ ] Set up proper error handling
- [ ] Configure OAuth app branding (logo, colors)
- [ ] Review permissions requested
- [ ] Add privacy policy and terms of service
- [ ] Test account linking (email match)

---

# Security Best Practices

1. ✅ **Never commit** OAuth credentials to Git
2. ✅ **Use environment variables** for all secrets
3. ✅ **Restrict redirect URIs** to your domains only
4. ✅ **Request minimum scopes** needed
5. ✅ **Monitor OAuth logs** for suspicious activity
6. ✅ **Rotate credentials** periodically
7. ✅ **Enable 2FA** on provider accounts
8. ✅ **Validate state parameter** (Django Allauth does this)

---

# OAuth Flow Diagram

```
User clicks "Login with Google/GitHub"
         ↓
Redirects to Google/GitHub
         ↓
User authenticates with provider
         ↓
User approves app permissions
         ↓
Provider redirects to callback URL
         ↓
Django Allauth receives auth code
         ↓
Exchanges code for access token
         ↓
Retrieves user profile info
         ↓
Creates/updates user in database
         ↓
Logs user into Django
         ↓
Redirects to home page
```

---

# Quick Reference

## Google OAuth URLs
- **Console**: https://console.cloud.google.com/
- **Credentials**: https://console.cloud.google.com/apis/credentials
- **Consent Screen**: https://console.cloud.google.com/apis/credentials/consent

## GitHub OAuth URLs
- **Settings**: https://github.com/settings/developers
- **OAuth Apps**: https://github.com/settings/developers
- **Documentation**: https://docs.github.com/en/developers/apps/building-oauth-apps

## Django URLs
- **Login Page**: http://localhost:1234/en/login/
- **Admin Panel**: http://localhost:1234/admin/
- **Social Apps**: http://localhost:1234/admin/socialaccount/socialapp/

---

# Next Steps

1. ✅ Test both Google and GitHub login
2. ✅ Set up email SMTP (see `EMAIL_SMTP_SETUP_GUIDE.md`)
3. ✅ Configure SMS (see `SMS_SETUP_GUIDE.md`)
4. ✅ Add more OAuth providers if needed (Facebook, Twitter, etc.)
5. ✅ Customize account linking behavior
6. ✅ Deploy to production

---

**Your social authentication is now ready!** 🎉

Users can now sign in with Google or GitHub in addition to traditional email/password authentication.
