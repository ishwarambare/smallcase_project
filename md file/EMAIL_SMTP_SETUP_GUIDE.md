# 📧 Complete Email SMTP Setup Guide

This guide provides **detailed step-by-step instructions** for setting up email services for your Django project.

---

## Table of Contents
1. [Gmail SMTP Setup](#1-gmail-smtp-setup-recommended-for-development)
2. [SendGrid Setup](#2-sendgrid-setup-recommended-for-production)
3. [Other Email Providers](#3-other-email-providers)

---

# 1. Gmail SMTP Setup (Recommended for Development)

**Free Tier**: 500 emails per day  
**Best For**: Development, Testing, Personal Projects

## Step 1: Enable 2-Step Verification

### 1.1 Go to Google Account Security
1. Open your browser and visit: https://myaccount.google.com/security
2. **Sign in** with your Gmail account
3. Look for the **"How you sign in to Google"** section

### 1.2 Enable 2-Step Verification
1. Click on **"2-Step Verification"**
2. Click **"Get Started"** button
3. Google will ask you to **sign in again** for security
4. Follow the on-screen prompts:
   - Enter your phone number
   - Choose to receive verification code via **Text message** or **Phone call**
   - Enter the verification code you receive
5. Click **"Turn On"** to enable 2-Step Verification

✅ **Checkpoint**: You should see "2-Step Verification is on" message

---

## Step 2: Generate App Password

### 2.1 Access App Passwords
1. Go back to: https://myaccount.google.com/security
2. **OR** directly visit: https://myaccount.google.com/apppasswords
3. Under **"How you sign in to Google"** section
4. Click on **"App passwords"** (at the bottom of the 2-Step Verification section)

> **Note**: If you don't see "App passwords", ensure 2-Step Verification is enabled

### 2.2 Create New App Password
1. You'll see **"App passwords"** page
2. In the **"Select app"** dropdown:
   - Choose **"Mail"**
3. In the **"Select device"** dropdown:
   - Choose **"Other (Custom name)"**
   - Type: `Django App` or `Smallcase Project`
4. Click **"Generate"** button

### 2.3 Copy Your App Password
1. Google will show a **16-character password** in a yellow box
2. **IMPORTANT**: Copy this password immediately!
3. Format: `xxxx xxxx xxxx xxxx` (with spaces)
4. Store it securely - **you won't be able to see it again**

✅ **Checkpoint**: You have a 16-character app password

---

## Step 3: Configure Your Django Project

### 3.1 Update `.env` File
Open your `.env` file and add/update these lines:

```bash
# Email Configuration - Gmail SMTP
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your.email@gmail.com
EMAIL_HOST_PASSWORD=xxxx xxxx xxxx xxxx
DEFAULT_FROM_EMAIL=your.email@gmail.com
```

**Replace**:
- `your.email@gmail.com` → Your actual Gmail address
- `xxxx xxxx xxxx xxxx` → The 16-character app password (you can include or remove spaces)

### 3.2 Restart Your Django Server
```bash
# Stop the current server (Ctrl+C)
# Then restart:
python manage.py runserver
```

---

## Step 4: Test Email Sending

### 4.1 Test via Django Shell
```bash
python manage.py shell
```

Then run:
```python
from django.core.mail import send_mail

send_mail(
    subject='Test Email from Django',
    message='This is a test email sent from Django using Gmail SMTP.',
    from_email='your.email@gmail.com',
    recipient_list=['recipient@example.com'],
    fail_silently=False,
)
```

### 4.2 Check for Success
- If successful, you'll see no errors
- Check the recipient's inbox (might be in spam folder)
- Exit: `exit()`

✅ **Success**: Email received!

---

## Troubleshooting Gmail SMTP

### Issue 1: "Username and Password not accepted"
**Solutions**:
- Verify 2-Step Verification is enabled
- Regenerate app password
- Check for typos in email/password
- Ensure no extra spaces in password

### Issue 2: "SMTPAuthenticationError"
**Solutions**:
- Make sure you're using **app password**, not your regular Gmail password
- Verify `EMAIL_USE_TLS=True`
- Check `EMAIL_PORT=587`

### Issue 3: Email not received
**Solutions**:
- Check recipient's spam folder
- Verify "from" email matches your Gmail
- Check Gmail's "Sent" folder to confirm it was sent
- Try different recipient email

### Issue 4: "Less secure app access"
**Solution**: 
- You DON'T need this anymore if using app passwords
- App passwords are the secure method

---

# 2. SendGrid Setup (Recommended for Production)

**Free Tier**: 100 emails per day  
**Best For**: Production, Transactional Emails, Better Deliverability

## Step 1: Create SendGrid Account

### 1.1 Sign Up
1. Visit: https://sendgrid.com/
2. Click **"Start for Free"** or **"Sign Up"** button
3. Fill in the registration form:
   - **Email**: Your work/personal email
   - **Password**: Create a strong password
   - **First Name & Last Name**
4. Click **"Create Account"**

### 1.2 Verify Email
1. Check your email inbox
2. Click the **verification link** from SendGrid
3. This activates your account

### 1.3 Complete Profile
1. After verifying, you'll be asked to complete your profile
2. Fill in:
   - **Company Name**: Your project name (e.g., "Smallcase Project")
   - **Company Website**: Can use `localhost` for testing
   - **Role**: Select "Developer" or appropriate role
   - **Use Case**: Select "Transactional Emails"
3. Click **"Get Started"** or **"Continue"**

✅ **Checkpoint**: You're logged into SendGrid dashboard

---

## Step 2: Create API Key

### 2.1 Navigate to API Keys
1. From SendGrid dashboard
2. Click on **"Settings"** in left sidebar
3. Click **"API Keys"**
4. Or directly visit: https://app.sendgrid.com/settings/api_keys

### 2.2 Create New API Key
1. Click **"Create API Key"** button (top right)
2. Fill in details:
   - **API Key Name**: `Django Smallcase Project` or `Development`
   - **API Key Permissions**: 
     - **Option 1**: Select **"Full Access"** (easiest)
     - **Option 2**: Select **"Restricted Access"** → Enable only **"Mail Send"**
3. Click **"Create & View"**

### 2.3 Copy API Key
1. SendGrid will show your API key **ONCE**
2. **CRITICAL**: Copy it immediately!
3. Format: `SG.xxxxxxxxxxxxxxxxxx.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
4. Store it securely - you cannot view it again

✅ **Checkpoint**: You have your SendGrid API key

---

## Step 3: Verify Sender Identity

### 3.1 Single Sender Verification (Easiest)
1. In SendGrid dashboard, go to **"Settings"** → **"Sender Authentication"**
2. Click **"Verify a Single Sender"**
3. Click **"Create New Sender"**
4. Fill in form:
   - **From Name**: Your app name (e.g., "Smallcase Team")
   - **From Email Address**: Your email (e.g., `noreply@yourdomain.com` or your Gmail)
   - **Reply To**: Your support email
   - **Company Address**: Your address
   - **City, State, Zip**: Your location
   - **Country**: Your country
5. Click **"Create"**

### 3.2 Verify Email
1. Check inbox of the email you specified
2. Click the **verification link** from SendGrid
3. Verification complete!

✅ **Checkpoint**: Sender verified (you'll see a checkmark)

---

## Step 4: Configure Django Project

### 4.1 Update `.env` File
```bash
# Email Configuration - SendGrid SMTP
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=SG.xxxxxxxxxxxxxxxxxx.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
DEFAULT_FROM_EMAIL=noreply@yourdomain.com
```

**Replace**:
- `EMAIL_HOST_PASSWORD` → Your SendGrid API key
- `DEFAULT_FROM_EMAIL` → The verified sender email

### 4.2 Restart Server
```bash
python manage.py runserver
```

---

## Step 5: Test SendGrid Email

### 5.1 Test via Shell
```bash
python manage.py shell
```

```python
from django.core.mail import send_mail

send_mail(
    subject='Test Email via SendGrid',
    message='This email is sent through SendGrid API.',
    from_email='your-verified-email@example.com',
    recipient_list=['recipient@example.com'],
    fail_silently=False,
)
```

### 5.2 Verify in SendGrid Dashboard
1. Go to **"Activity"** in SendGrid dashboard
2. You should see your email in the activity feed
3. Check recipient inbox

✅ **Success**: Email delivered through SendGrid!

---

## Troubleshooting SendGrid

### Issue 1: "Authentication failed"
**Solutions**:
- Verify API key is correct (no typos)
- Ensure `EMAIL_HOST_USER=apikey` (literal word "apikey")
- Check API key has "Mail Send" permission

### Issue 2: "Sender email not verified"
**Solutions**:
- Complete Single Sender Verification
- Verify the sender email address
- Use the exact verified email in `DEFAULT_FROM_EMAIL`

### Issue 3: Email in spam
**Solutions**:
- Use domain authentication (advanced)
- Ensure "From" email matches verified sender
- Add unsubscribe link in emails

---

# 3. Other Email Providers

## 3.1 Mailgun
**Free Tier**: 5,000 emails/month for first 3 months

### Setup Steps:
1. **Sign up**: https://www.mailgun.com/
2. **Verify domain** or use sandbox domain
3. **Get SMTP credentials**:
   - Host: `smtp.mailgun.org`
   - Port: `587`
   - Username: From Mailgun dashboard
   - Password: From Mailgun dashboard

### Django Configuration:
```bash
EMAIL_HOST=smtp.mailgun.org
EMAIL_PORT=587
EMAIL_HOST_USER=your_mailgun_smtp_username
EMAIL_HOST_PASSWORD=your_mailgun_smtp_password
```

---

## 3.2 Amazon SES
**Free Tier**: 62,000 emails/month (when sent from EC2)

### Setup Steps:
1. **AWS Account**: Create at https://aws.amazon.com/
2. **Verify email** in SES console
3. **Request production access** (starts in sandbox)
4. **Get SMTP credentials** from IAM

### Django Configuration:
```bash
EMAIL_HOST=email-smtp.us-east-1.amazonaws.com
EMAIL_PORT=587
EMAIL_HOST_USER=your_aws_smtp_username
EMAIL_HOST_PASSWORD=your_aws_smtp_password
```

---

## 3.3 Outlook/Office 365
**Free Tier**: Included with Outlook.com account

### Setup Steps:
1. Use your Outlook.com or Office 365 email
2. Enable SMTP in account settings

### Django Configuration:
```bash
EMAIL_HOST=smtp-mail.outlook.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your_email@outlook.com
EMAIL_HOST_PASSWORD=your_password
```

---

# Quick Reference Table

| Provider | Free Limit | Reliability | Best For | Setup Difficulty |
|----------|-----------|-------------|----------|------------------|
| **Gmail** | 500/day | Good | Development, Testing | ⭐⭐ Easy |
| **SendGrid** | 100/day | Excellent | Production | ⭐⭐⭐ Medium |
| **Mailgun** | 5,000/month | Excellent | Production | ⭐⭐⭐ Medium |
| **Amazon SES** | 62,000/month | Excellent | Large Scale | ⭐⭐⭐⭐ Hard |
| **Outlook** | Varies | Good | Personal | ⭐⭐ Easy |

---

# Recommendations

## For Development/Testing:
✅ **Use Gmail SMTP**
- Easy to set up
- 500 emails/day is plenty for testing
- Free and reliable

## For Production:
✅ **Use SendGrid or Mailgun**
- Better deliverability
- Detailed analytics
- Professional service
- Less likely to end up in spam

## For Large Scale:
✅ **Use Amazon SES**
- Very cost-effective at scale
- Highly reliable
- Requires more setup

---

# Security Best Practices

1. ✅ **Never commit** email credentials to Git
2. ✅ **Use environment variables** (`.env` file)
3. ✅ **Use app passwords** for Gmail (not your main password)
4. ✅ **Rotate API keys** periodically
5. ✅ **Restrict API permissions** to minimum needed
6. ✅ **Monitor email activity** for suspicious usage

---

# Next Steps

After setting up email:
1. ✅ Test OTP password reset: `/forgot-password/`
2. ✅ Test email verification for new signups
3. ✅ Configure social authentication (see `OAUTH_SETUP_GUIDE.md`)
4. ✅ Set up SMS for OTP (see `SMS_SETUP_GUIDE.md`)

---

**Need help?** Check troubleshooting sections or refer to `DJANGO_ALLAUTH_GUIDE.md`
