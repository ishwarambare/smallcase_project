# Django Allauth Installation - Quick Setup Guide

## ✅ What's Been Completed

I've successfully integrated Django Allauth into your project with the following features:

### 1. **Configuration Files Updated**
- ✅ `settings.py` - Added Django Allauth, email, SMS, and OAuth settings
- ✅ `requirements.txt` - Added all necessary packages
- ✅ `urls.py` - Added Allauth and OTP password reset routes
- ✅ `.env.template` - Added all configuration variables

### 2. **New Files Created**
- ✅ `user/adapters.py` - Custom Allauth adapters
- ✅ `user/otp_utils.py` - OTP management utility
- ✅ `user/views.py` - Extended with OTP password reset views
- ✅ `user/urls.py` - Added OTP password reset routes
- ✅ `user/templates/user/forgot_password.j2` - Modern forgot password page
- ✅ `user/templates/user/email/otp_email.html` - OTP email template
- ✅ `user/templates/account/email/email_confirmation_message.html` - Email confirmation template
- ✅ `user/templates/account/email/password_reset_key_message.html` - Password reset email template
- ✅ `DJANGO_ALLAUTH_GUIDE.md` - Complete documentation

---

## 🚀 Next Steps - Manual Installation

Since your virtual environment needs the packages, please run these commands **in your project terminal**:

### Step 1: Stop the running server (if needed)
Press `Ctrl+C` in the terminal running `py manage.py runserver 1234`

### Step 2: Install packages
```bash
pip install django-allauth pyotp twilio django-otp qrcode
```

### Step 3: Run migrations
```bash
py manage.py makemigrations
py manage.py migrate
```

### Step 4: Create Site object
```bash
py manage.py shell
```

Then in the Python shell:
```python
from django.contrib.sites.models import Site

# For local development
site = Site.objects.create(
    id=1,
    domain='localhost:1234',
    name='Smallcase Project (Local)'
)
print(f"Created site: {site}")
exit()
```

### Step 5: Restart the server
```bash
py manage.py runserver 1234
```

---

## 📧 Email Configuration (Choose One)

### Option A: Console Backend (For Development/Testing)
**No setup needed!** Emails will print to your console.

Your `.env` file should have:
```bash
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

### Option B: Gmail SMTP (Recommended)

1. **Enable 2-Step Verification**
   - Go to: https://myaccount.google.com/security
   - Turn on 2-Step Verification

2. **Generate App Password**
   - Go to: https://myaccount.google.com/apppasswords
   - Select "Mail" and your device
   - Copy the 16-character password

3. **Update your `.env` file**:
```bash
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your.email@gmail.com
EMAIL_HOST_PASSWORD=your_16_char_app_password
DEFAULT_FROM_EMAIL=your.email@gmail.com
```

### Option C: SendGrid (For Production)

1. **Sign up**: https://sendgrid.com (100 emails/day free)
2. **Get API Key**: Settings → API Keys → Create API Key
3. **Update `.env`**:
```bash
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=your_sendgrid_api_key
DEFAULT_FROM_EMAIL=your.email@example.com
```

---

## 🔐 Social Authentication Setup

### Google OAuth (Optional but Recommended)

1. **Google Cloud Console**: https://console.cloud.google.com/
2. **Create project** → Enable Google+ API
3. **Create OAuth credentials**:
   - Application type: Web application
   - Authorized redirect URIs:
     ```
     http://localhost:1234/accounts/google/login/callback/
     ```

4. **Add to `.env`**:
```bash
GOOGLE_OAUTH_CLIENT_ID=your_client_id
GOOGLE_OAUTH_CLIENT_SECRET=your_client_secret
```

5. **Add in Django Admin**:
   - Go to: http://localhost:1234/admin/socialaccount/socialapp/
   - Add Social Application:
     - Provider: Google
     - Client ID: (from Google Console)
     - Secret: (from Google Console)
     - Sites: Select your site

### GitHub OAuth (Optional)

1. **GitHub Settings**: https://github.com/settings/developers
2. **New OAuth App**:
   - Homepage: `http://localhost:1234`
   - Callback: `http://localhost:1234/accounts/github/login/callback/`

3. **Add to `.env`**:
```bash
GITHUB_OAUTH_CLIENT_ID=your_client_id
GITHUB_OAUTH_CLIENT_SECRET=your_client_secret
```

4. **Add in Django Admin** (same process as Google)

---

## 📱 SMS Configuration (Optional - for SMS OTP)

### Twilio Setup

1. **Sign up**: https://www.twilio.com (get $15 free credit)
2. **Get credentials**: https://console.twilio.com
3. **Get phone number**: Console → Phone Numbers → Buy a number

4. **Add to `.env`**:
```bash
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=+1234567890
```

---

## 🧪 Testing the Integration

### 1. Test Email (Console Backend)
```bash
py manage.py shell
```

```python
from django.core.mail import send_mail

send_mail(
    'Test Email',
    'This is a test!',
    'from@example.com',
    ['to@example.com'],
)
# Check your console output
```

### 2. Test OTP Generation
```bash
py manage.py shell
```

```python
from user.otp_utils import OTPManager

# Generate OTP
otp = OTPManager.generate_otp()
print(f"OTP: {otp}")

# Send OTP via email
OTPManager.send_otp_email('test@example.com', otp, 'password_reset')

# Verify OTP
result = OTPManager.verify_otp('test@example.com', otp, 'password_reset')
print(result)
```

### 3. Test Web Pages
Visit these URLs:
- Signup: http://localhost:1234/en/signup/
- Login: http://localhost:1234/en/login/
- Forgot Password: http://localhost:1234/en/forgot-password/
- Allauth URLs: http://localhost:1234/accounts/login/

---

## 🎯 Available Features

### ✅ Email Authentication
- Sign up with email
- Email verification
- Login with email
- Password reset

### ✅ OTP Password Reset
- Choose between Email or SMS
- 6-digit OTP
- 5-minute expiry
- Rate limiting (1 min cooldown)
- 3 attempts limit

### ✅ Social Login
- Google Sign-In
- GitHub Sign-In
- Auto account linking

### ✅ Security Features
- CSRF protection
- Login attempt limiting
- Secure sessions
- Password strength requirements

---

## 📚 Key Files to Know

1. **Settings**: `smallcase_project/settings.py`
2. **OTP Utils**: `user/otp_utils.py`
3. **Adapters**: `user/adapters.py` 
4. **Views**: `user/views.py`
5. **Templates**: `user/templates/`
6. **Documentation**: `DJANGO_ALLAUTH_GUIDE.md`

---

## 🔧 Troubleshooting

### ImportError: No module named 'allauth'
**Solution**: Run `pip install django-allauth pyotp twilio django-otp qrcode`

### Email not sending
**Solution**: 
1. Check `EMAIL_BACKEND` in settings
2. Verify Gmail App Password
3. Check console output (if using console backend)

### Social login not working
**Solution**:
1. Create Site object (id=1)
2. Add social app in Django admin
3. Check redirect URIs match exactly

### OTP not received
**Solution**:
1. Check email configuration
2. Look in console output (development)
3. Verify Twilio credentials (for SMS)

---

## 📖 Full Documentation

For complete documentation, see: `DJANGO_ALLAUTH_GUIDE.md`

---

## ✨ Summary

You now have:
- ✅ Django Allauth fully integrated
- ✅ Email-based authentication
- ✅ OTP password reset (Email + SMS)
- ✅ Social authentication ready
- ✅ Beautiful email templates
- ✅ Modern forgot password UI
- ✅ Complete documentation

**Next**: Follow the "Next Steps - Manual Installation" above to complete the setup!
