# Django Allauth Integration Guide

## 📋 Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Email Configuration](#email-configuration)
- [Social Authentication Setup](#social-authentication-setup)
- [OTP Password Reset](#otp-password-reset)
- [Usage](#usage)
- [Templates](#templates)
- [Troubleshooting](#troubleshooting)

---

## 🎯 Overview

This project now uses **Django Allauth** for comprehensive authentication features including:
- Email-based authentication (no username required)
- Social login (Google, GitHub)
- Email verification
- Password reset with OTP (email + SMS)
- Account management

---

## ✨ Features

### 1. **Email Authentication**
- Login with email instead of username
- Mandatory email verification
- Secure password requirements (min 8 characters)

### 2. **Social Authentication**
- **Google OAuth**: Sign in with Google account
- **GitHub OAuth**: Sign in with GitHub account
- Automatic account linking if email matches

### 3. **OTP-Based Password Reset**
- Receive OTP via **Email** or **SMS**
- 6-digit OTP with 5-minute expiry
- Rate limiting to prevent abuse
- Secure token-based password reset

### 4. **Security Features**
- Login attempt limiting (5 attempts)
- Account lockout (5 minutes)
- CSRF protection
- Secure session handling

---

## 🚀 Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run Migrations

```bash
python manage.py migrate
```

### 3. Create Site Object

Django Allauth requires a Site object. Create one in Django admin or shell:

```bash
python manage.py shell
```

```python
from django.contrib.sites.models import Site

# For local development
Site.objects.create(
    domain='localhost:8000',
    name='Smallcase Project (Local)'
)

# For production (update domain)
Site.objects.create(
    domain='your-domain.com',
    name='Smallcase Project'
)
```

### 4. Configure Environment Variables

Copy `.env.template` to `.env` and configure the necessary variables (see sections below).

---

## 📧 Email Configuration

### Option 1: Gmail SMTP (Recommended for Development)

1. **Enable 2-Step Verification**
   - Go to https://myaccount.google.com/security
   - Enable 2-Step Verification

2. **Generate App Password**
   - Go to https://myaccount.google.com/apppasswords
   - Select "Mail" and your device
   - Copy the generated password

3. **Configure `.env`**
```bash
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your.email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password_here
DEFAULT_FROM_EMAIL=your.email@gmail.com
```

**Limits**: 500 emails/day (free)

---

### Option 2: SendGrid (Recommended for Production)

1. **Sign up at SendGrid**
   - Go to https://sendgrid.com
   - Sign up for free account

2. **Create API Key**
   - Navigate to Settings → API Keys
   - Create a new API key with "Mail Send" permissions
   - Copy the API key

3. **Configure `.env`**
```bash
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=your_sendgrid_api_key
DEFAULT_FROM_EMAIL=your.email@example.com
```

**Limits**: 100 emails/day (free tier)

---

### Option 3: Console Backend (Development Only)

For development, emails are printed to console:

```bash
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

---

## 🔐 Social Authentication Setup

### Google OAuth Setup

1. **Go to Google Cloud Console**
   - https://console.cloud.google.com/

2. **Create a New Project**
   - Click "Select a project" → "New Project"
   - Name it "Smallcase Project" (or similar)

3. **Enable Google+ API**
   - Navigate to "APIs & Services" → "Library"
   - Search for "Google+ API"
   - Click "Enable"

4. **Create OAuth Credentials**
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth Client ID"
   - Application type: "Web application"
   - Name: "Smallcase Web App"

5. **Add Authorized Redirect URIs**
   ```
   For Local Development:
   http://localhost:8000/accounts/google/login/callback/
   http://localhost:1234/accounts/google/login/callback/
   
   For Production:
   https://your-domain.com/accounts/google/login/callback/
   ```

6. **Copy Credentials**
   - Copy the Client ID and Client Secret

7. **Configure `.env`**
   ```bash
   GOOGLE_OAUTH_CLIENT_ID=your_client_id_here
   GOOGLE_OAUTH_CLIENT_SECRET=your_client_secret_here
   ```

8. **Add to Django Admin**
   - Go to `/admin/socialaccount/socialapp/`
   - Click "Add Social Application"
   - Provider: Google
   - Name: Google
   - Client ID: (paste from Google Console)
   - Secret key: (paste from Google Console)
   - Sites: Select your site
   - Save

---

### GitHub OAuth Setup

1. **Go to GitHub Developer Settings**
   - https://github.com/settings/developers

2. **Create New OAuth App**
   - Click "New OAuth App"
   - Application name: "Smallcase Project"
   - Homepage URL: 
     - Local: `http://localhost:8000`
     - Production: `https://your-domain.com`
   - Authorization callback URL:
     - Local: `http://localhost:8000/accounts/github/login/callback/`
     - Production: `https://your-domain.com/accounts/github/login/callback/`

3. **Generate Client Secret**
   - Click "Generate a new client secret"
   - Copy the Client ID and Client Secret

4. **Configure `.env`**
   ```bash
   GITHUB_OAUTH_CLIENT_ID=your_client_id_here
   GITHUB_OAUTH_CLIENT_SECRET=your_client_secret_here
   ```

5. **Add to Django Admin**
   - Go to `/admin/socialaccount/socialapp/`
   - Click "Add Social Application"
   - Provider: GitHub
   - Name: GitHub
   - Client ID: (paste from GitHub)
   - Secret key: (paste from GitHub)
   - Sites: Select your site
   - Save

---

## 📱 SMS Configuration (Twilio)

### Setup Twilio for SMS OTP

1. **Sign up at Twilio**
   - Go to https://www.twilio.com
   - Sign up for free trial (get $15 credit)

2. **Get Credentials**
   - Go to https://console.twilio.com
   - Copy your Account SID and Auth Token

3. **Get a Phone Number**
   - Go to "Phone Numbers" → "Manage" → "Buy a number"
   - Select a phone number (free during trial)
   - Copy the phone number

4. **Configure `.env`**
   ```bash
   TWILIO_ACCOUNT_SID=your_account_sid
   TWILIO_AUTH_TOKEN=your_auth_token
   TWILIO_PHONE_NUMBER=+1234567890
   ```

**Limits**: $15 credit in free trial, then pay-as-you-go

---

## 🔑 OTP Password Reset

The OTP password reset feature supports both email and SMS:

### How It Works

1. **User requests password reset**
   - Visit `/forgot-password/`
   - Choose method: Email or SMS
   - Enter email address or phone number

2. **OTP is sent**
   - 6-digit OTP generated
   - Sent via email or SMS
   - Expires in 5 minutes
   - Cooldown: 1 minute between requests

3. **User enters OTP**
   - 3 attempts allowed
   - Auto-focus and paste support

4. **Reset password**
   - After successful OTP verification
   - Set new password (min 8 characters)
   - Redirects to login

### Security Features
- **Rate Limiting**: 1 minute cooldown between OTP requests
- **Attempt Limiting**: Max 3 attempts per OTP
- **Expiry**: OTP expires after 5 minutes
- **Token-based Reset**: Temporary token for password change (10 min expiry)

---

## 📝 Usage

### Available URLs

```python
# Django Allauth URLs
/accounts/signup/                  # User signup
/accounts/login/                   # User login
/accounts/logout/                  # User logout
/accounts/password/reset/          # Standard password reset
/accounts/confirm-email/<key>/     # Email confirmation

# Social Auth URLs
/accounts/google/login/            # Google login
/accounts/github/login/            # GitHub login

# Custom OTP Password Reset
/forgot-password/                  # OTP password reset page
```

### Using Social Login in Templates

```html
<!-- Google Login Button -->
<a href="{% url 'google_login' %}" class="btn-social">
    <img src="google-icon.png"> Login with Google
</a>

<!-- GitHub Login Button -->
<a href="{% url 'github_login' %}" class="btn-social">
    <img src="github-icon.png"> Login with GitHub
</a>
```

---

## 🎨 Templates

### Custom Email Templates

The project includes custom email templates in `user/templates/account/email/`:

- `email_confirmation_message.html` - Email confirmation
- `email_confirmation_subject.txt` - Email confirmation subject
- `password_reset_key_message.html` - Password reset email
- `password_reset_key_subject.txt` - Password reset subject

### OTP Email Template

Located at `user/templates/user/email/otp_email.html`:
- Modern gradient design
- Clear OTP display
- Expiry information
- Security warnings

---

## 🔧 Troubleshooting

### Email Not Sending

**Problem**: Emails not being sent

**Solutions**:
1. Check `EMAIL_BACKEND` setting
2. Verify Gmail App Password is correct
3. Check spam folder
4. Enable "Less secure app access" (not recommended)
5. Use SendGrid instead

---

### Social Login Not Working

**Problem**: Social login failing

**Solutions**:
1. Verify OAuth credentials in Django admin
2. Check redirect URIs match exactly
3. Ensure Site domain is correct
4. Check that social provider is enabled in `INSTALLED_APPS`

---

### OTP Not Sending

**Problem**: OTP not received

**Solutions**:
1. **Email OTP**: Check email configuration
2. **SMS OTP**: Verify Twilio credentials
3. Check console output (development mode)
4. Verify cooldown period hasn't been triggered

---

### Migration Errors

**Problem**: Database migration errors

**Solutions**:
```bash
# Clear migrations (DEVELOPMENT ONLY!)
python manage.py migrate --fake-initial

# Or reset database
rm db.sqlite3
python manage.py makemigrations
python manage.py migrate
```

---

## 🎯 Testing

### Test Email Configuration

```bash
python manage.py shell
```

```python
from django.core.mail import send_mail

send_mail(
    'Test Email',
    'This is a test email from Django.',
    'from@example.com',
    ['to@example.com'],
    fail_silently=False,
)
```

### Test OTP Generation

```bash
python manage.py shell
```

```python
from user.otp_utils import OTPManager

# Generate OTP
otp = OTPManager.generate_otp()
print(f"Generated OTP: {otp}")

# Send OTP email
OTPManager.send_otp_email('test@example.com', otp, 'password_reset')

# Verify OTP
result = OTPManager.verify_otp('test@example.com', otp, 'password_reset')
print(result)
```

---

## 📚 Additional Resources

- [Django Allauth Documentation](https://django-allauth.readthedocs.io/)
- [Google OAuth Setup](https://developers.google.com/identity/protocols/oauth2)
- [GitHub OAuth Apps](https://docs.github.com/en/developers/apps/building-oauth-apps)
- [Twilio Documentation](https://www.twilio.com/docs)
- [SendGrid Documentation](https://docs.sendgrid.com/)

---

## 🎉 Summary

You now have a fully functional authentication system with:
- ✅ Email-based authentication
- ✅ Social login (Google, GitHub)
- ✅ Email verification
- ✅ OTP password reset (Email + SMS)
- ✅ Secure session management
- ✅ Beautiful email templates
- ✅ Modern UI/UX

For any issues, refer to the troubleshooting section or check the official documentation.
