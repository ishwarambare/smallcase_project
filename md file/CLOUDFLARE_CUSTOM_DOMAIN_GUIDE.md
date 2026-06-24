# 🌐 Cloudflare Custom Domain + Gmail SMTP Setup Guide

This guide shows you how to:
1. Set up a custom domain with Cloudflare
2. Configure DNS records
3. Send emails via Gmail SMTP using your custom domain
4. Set up email forwarding (optional)

---

## 📋 Table of Contents
1. [Prerequisites](#prerequisites)
2. [Purchase a Domain](#step-1-purchase-a-domain)
3. [Add Domain to Cloudflare](#step-2-add-domain-to-cloudflare)
4. [Configure DNS Records](#step-3-configure-dns-records)
5. [Set Up Gmail with Custom Domain](#step-4-set-up-gmail-with-custom-domain)
6. [Configure Django](#step-5-configure-django)
7. [Deploy Application](#step-6-deploy-application)
8. [Testing](#step-7-testing)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

What you'll need:
- ✅ A domain name (purchase or already own)
- ✅ Cloudflare account (free)
- ✅ Gmail account
- ✅ Your Django project
- ✅ Hosting service (Railway, Heroku, etc.)

**Estimated Time**: 30-45 minutes  
**Cost**: Domain ($10-15/year), Everything else is FREE!

---

# Step 1: Purchase a Domain

## Option A: Buy from Cloudflare (Recommended)

### 1.1 Go to Cloudflare Registrar
1. Visit: https://www.cloudflare.com/products/registrar/
2. Sign in to your Cloudflare account (or create one)
3. Click **"Register Domain"**

### 1.2 Search for Domain
1. Enter your desired domain name (e.g., `smallcase.com`)
2. Click **"Search"**
3. Browse available extensions (.com, .io, .dev, etc.)
4. Select your domain

### 1.3 Purchase Domain
1. Add to cart
2. Typical cost: **$8.03/year for .com** (at-cost pricing!)
3. Enter billing information
4. Complete purchase

✅ **Benefit**: Domain is automatically added to Cloudflare!

---

## Option B: Buy from Other Registrars

Popular registrars:
- **Namecheap**: https://www.namecheap.com/ ($9-13/year)
- **Google Domains**: https://domains.google.com/ ($12/year)
- **GoDaddy**: https://www.godaddy.com/ ($12-20/year)
- **Porkbun**: https://porkbun.com/ ($9-11/year)

After purchase, you'll transfer to Cloudflare in Step 2.

✅ **Checkpoint**: You own a domain (e.g., `yourdomain.com`)

---

# Step 2: Add Domain to Cloudflare

## 2.1 Sign Up / Login to Cloudflare
1. Visit: https://dash.cloudflare.com/sign-up
2. Create account (free) or login
3. You'll see the Cloudflare dashboard

## 2.2 Add Your Domain

### If bought from Cloudflare:
- Domain is already added! Skip to Step 3.

### If bought elsewhere:
1. Click **"Add a Site"** button
2. Enter your domain name (e.g., `yourdomain.com`)
3. Click **"Add Site"**

## 2.3 Select Plan
1. Choose **"Free"** plan ($0/month)
2. Click **"Continue"**

## 2.4 Review DNS Records
1. Cloudflare will scan your existing DNS records
2. Review the imported records
3. Click **"Continue"**

## 2.5 Change Nameservers

### 2.5.1 Get Cloudflare Nameservers
Cloudflare will show you 2 nameservers:
```
alexa.ns.cloudflare.com
damien.ns.cloudflare.com
```
(Yours will be different)

### 2.5.2 Update at Your Registrar

**For Namecheap**:
1. Login to Namecheap
2. Go to Domain List → Manage
3. Find "Nameservers" section
4. Select **"Custom DNS"**
5. Enter Cloudflare's nameservers
6. Click **"Save"**

**For Google Domains**:
1. Login to Google Domains
2. Click on your domain
3. Go to **"DNS"** tab
4. Click **"Use custom name servers"**
5. Enter Cloudflare's nameservers
6. Click **"Save"**

**For GoDaddy**:
1. Login to GoDaddy
2. Go to My Products → Domains
3. Click **"DNS"** or **"Manage DNS"**
4. Click **"Change"** under Nameservers
5. Select **"Custom"**
6. Enter Cloudflare's nameservers
7. Click **"Save"**

### 2.5.3 Wait for Propagation
1. Click **"Done, check nameservers"** in Cloudflare
2. Wait for email confirmation (can take up to 24 hours, usually minutes)
3. Check status at: https://dash.cloudflare.com/

✅ **Checkpoint**: Domain is active on Cloudflare (you'll get email confirmation)

---

# Step 3: Configure DNS Records

## 3.1 Go to DNS Management
1. Login to Cloudflare dashboard
2. Select your domain
3. Click **"DNS"** in the left sidebar
4. Or visit: https://dash.cloudflare.com/ → Select domain → DNS → Records

## 3.2 Add Application Records

### For Railway Deployment:

#### A Record (for root domain):
1. Click **"Add record"**
2. **Type**: Select **"A"**
3. **Name**: `@` (represents yourdomain.com)
4. **IPv4 address**: Get from Railway:
   - Go to Railway dashboard
   - Select your project
   - Copy the IP address provided
   - **OR** use Railway's automatic DNS (see below)
5. **Proxy status**: ✅ Proxied (orange cloud)
6. **TTL**: Auto
7. Click **"Save"**

#### CNAME Record (for www):
1. Click **"Add record"**
2. **Type**: Select **"CNAME"**
3. **Name**: `www`
4. **Target**: 
   - Railway: `yourproject.up.railway.app`
   - Or your deployment URL
5. **Proxy status**: ✅ Proxied (orange cloud)
6. **TTL**: Auto
7. Click **"Save"**

### For Other Hosting:

**Vercel**:
```
Type: A
Name: @
Content: 76.76.21.21
Proxy: ✅ Proxied
```

**Heroku**:
```
Type: CNAME
Name: @
Content: yourapp.herokuapp.com
Proxy: ✅ Proxied
```

## 3.3 Add Email DNS Records (for Gmail)

### MX Records (for receiving emails):

> **Note**: These are only needed if you want to RECEIVE emails at your domain (e.g., contact@yourdomain.com)

1. Click **"Add record"**
2. **Type**: Select **"MX"**
3. **Name**: `@`
4. **Mail server**: `ASPMX.L.GOOGLE.COM`
5. **Priority**: `1`
6. **TTL**: Auto
7. Click **"Save"**

Add additional MX records (lower priority):
```
MX | @ | ALT1.ASPMX.L.GOOGLE.COM | Priority: 5
MX | @ | ALT2.ASPMX.L.GOOGLE.COM | Priority: 5
MX | @ | ALT3.ASPMX.L.GOOGLE.COM | Priority: 10
MX | @ | ALT4.ASPMX.L.GOOGLE.COM | Priority: 10
```

### SPF Record (for sending):

1. Click **"Add record"**
2. **Type**: Select **"TXT"**
3. **Name**: `@`
4. **Content**: `v=spf1 include:_spf.google.com ~all`
5. **TTL**: Auto
6. Click **"Save"**

### DKIM Record (for authentication):

We'll set this up in Step 4 after configuring Gmail.

✅ **Checkpoint**: DNS records configured

---

# Step 4: Set Up Gmail with Custom Domain

## Option A: Gmail with Email Forwarding (Easiest)

This allows you to:
- ✅ SEND emails from `noreply@yourdomain.com` using Gmail SMTP
- ✅ Use Gmail's infrastructure (reliable, free)
- ❌ Cannot RECEIVE emails at your custom domain (unless you set up forwarding)

### 4.1 Use Cloudflare Email Routing (Free!)

1. In Cloudflare dashboard, go to your domain
2. Click **"Email"** in left sidebar
3. Click **"Email Routing"**
4. Click **"Get started"** or **"Enable Email Routing"**
5. Add destination email:
   - **Destination**: Your Gmail address (e.g., `yourgmail@gmail.com`)
   - Click **"Save"**
6. Add custom addresses to forward:
   - Click **"Create address"**
   - **Custom address**: `contact@yourdomain.com`
   - **Action**: Forward to `yourgmail@gmail.com`
   - Click **"Save"**

Now emails sent to `contact@yourdomain.com` will forward to your Gmail!

### 4.2 Configure Gmail to Send From Custom Domain

1. **Open Gmail** (yourgmail@gmail.com)
2. Click **Settings** (gear icon) → **"See all settings"**
3. Go to **"Accounts and Import"** tab
4. Find **"Send mail as:"** section
5. Click **"Add another email address"**

6. **Add Email Address window**:
   - **Name**: `Smallcase Team` (or your app name)
   - **Email address**: `noreply@yourdomain.com` (or `contact@`)
   - ☐ Uncheck **"Treat as an alias"**
   - Click **"Next Step"**

7. **SMTP Server Configuration**:
   - **SMTP Server**: `smtp.gmail.com`
   - **Port**: `587`
   - **Username**: Your Gmail address (e.g., `yourgmail@gmail.com`)
   - **Password**: Your Gmail **App Password** (see Step 4.3)
   - ☑️ Check **"Secured connection using TLS"**
   - Click **"Add Account"**

8. **Verify Email Address**:
   - Gmail sends confirmation code
   - Check your Gmail inbox (the forwarding email)
   - Copy the confirmation code
   - Enter code and click **"Verify"**

### 4.3 Get Gmail App Password

1. Go to: https://myaccount.google.com/apppasswords
2. **App**: Select **"Mail"**
3. **Device**: Select **"Other (Custom name)"**
4. Enter: `Django Custom Domain`
5. Click **"Generate"**
6. Copy the 16-character password
7. Use this in Step 4.2 and in Django settings

✅ **Checkpoint**: You can send emails from `noreply@yourdomain.com` via Gmail!

---

## Option B: Google Workspace (Paid - Full Email Suite)

**Cost**: $6/user/month  
**Benefits**: Professional email, unlimited storage, Google Drive, Calendar

### Steps:
1. Sign up: https://workspace.google.com/
2. Add domain
3. Verify domain ownership (via DNS)
4. Set up email accounts (e.g., `contact@yourdomain.com`)
5. Configure MX records
6. Use workspace email for Django

---

# Step 5: Configure Django

## 5.1 Update `.env` File

```bash
# Email Configuration - Gmail with Custom Domain
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=yourgmail@gmail.com  # Your actual Gmail
EMAIL_HOST_PASSWORD=xxxx xxxx xxxx xxxx  # App password
DEFAULT_FROM_EMAIL=noreply@yourdomain.com  # Your custom domain email!
SERVER_EMAIL=noreply@yourdomain.com

# Domain Configuration
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com,.railway.app,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com,https://*.railway.app
```

## 5.2 Update Django Settings

Your `settings.py` should already have:
```python
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() in ('true', '1', 'yes')
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)
```

This is already set up! Just update your `.env` file.

---

# Step 6: Deploy Application

## 6.1 Update Railway (or your host)

1. Go to Railway dashboard
2. Select your project
3. Go to **"Settings"** → **"Domains"**
4. Click **"+ New Domain"**
5. Choose **"Custom Domain"**
6. Enter: `yourdomain.com`
7. Railway will provide DNS targets

8. **Add Environment Variables**:
   - Go to **"Variables"**
   - Add/Update:
     ```
     EMAIL_HOST_USER=yourgmail@gmail.com
     EMAIL_HOST_PASSWORD=xxxx xxxx xxxx xxxx
     DEFAULT_FROM_EMAIL=noreply@yourdomain.com
     ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
     ```

## 6.2 Update Cloudflare DNS

Go back to Cloudflare DNS and ensure your records match Railway's requirements.

## 6.3 Enable SSL/TLS

1. In Cloudflare dashboard → Your domain
2. Click **"SSL/TLS"** in left sidebar
3. Set encryption mode to: **"Full"** or **"Full (strict)"**
4. Wait for certificate to activate (few minutes)

✅ **Checkpoint**: Your site is accessible at `https://yourdomain.com`

---

# Step 7: Testing

## 7.1 Test Website Access

Visit your domain:
- https://yourdomain.com
- https://www.yourdomain.com

Both should work and show HTTPS lock icon.

## 7.2 Test Email Sending

### Via Django Shell:
```bash
python manage.py shell
```

```python
from django.core.mail import send_mail

send_mail(
    subject='Test from Custom Domain',
    message='This email is sent from noreply@yourdomain.com via Gmail SMTP!',
    from_email='noreply@yourdomain.com',
    recipient_list=['recipient@example.com'],
    fail_silently=False,
)
```

### Check:
1. ✅ Email received?
2. ✅ From address shows `noreply@yourdomain.com`?
3. ✅ Not in spam folder?

## 7.3 Test OTP Password Reset

1. Visit: `https://yourdomain.com/en/forgot-password/`
2. Select **"Email"** method
3. Enter your email
4. Check inbox - email should be from `noreply@yourdomain.com`!

✅ **Success**: Everything working with custom domain!

---

# Troubleshooting

## Issue 1: "Site Not Found" or 404

**Cause**: DNS not propagated yet

**Solutions**:
1. Wait 24-48 hours for full DNS propagation
2. Check DNS propagation: https://www.whatsmydns.net/
3. Clear browser cache
4. Try incognito mode

---

## Issue 2: "Your connection is not private" (SSL Error)

**Cause**: SSL certificate not ready

**Solutions**:
1. Wait 15-30 minutes for Cloudflare SSL
2. In Cloudflare → SSL/TLS → Set to **"Full"**
3. Check SSL status in Cloudflare dashboard
4. Force HTTPS: Cloudflare → SSL/TLS → Edge Certificates → Always Use HTTPS

---

## Issue 3: Emails Going to Spam

**Solutions**:
1. **Add SPF record** (Step 3.3)
2. **Set up DKIM**:
   - Gmail → Settings → Accounts → "Send mail as" → Edit info
   - Click "Add a signature"
3. **Add DMARC record**:
   ```
   Type: TXT
   Name: _dmarc
   Content: v=DMARC1; p=none; rua=mailto:dmarc@yourdomain.com
   ```
4. **Warm up domain**: Start with low volume, gradually increase
5. **Authenticate domain** in Gmail settings

---

## Issue 4: "Sender address rejected"

**Cause**: Gmail doesn't recognize custom domain

**Solutions**:
1. Verify email in Gmail (Step 4.2)
2. Check "Send mail as" in Gmail settings
3. Ensure App Password is correct
4. Try removing and re-adding the email

---

## Issue 5: Railway/Host Can't Find Domain

**Solutions**:
1. Check CNAME record in Cloudflare points to Railway
2. Ensure Proxy is enabled (orange cloud)
3. Add domain in Railway dashboard
4. Check ALLOWED_HOSTS in Django settings

---

# Advanced: DKIM Setup

For better email deliverability:

## 1. Generate DKIM Key in Gmail
1. Gmail → Settings → Accounts → Send mail as
2. Click on your custom email → Edit info
3. Follow instructions for DKIM

## 2. Add DKIM Record to Cloudflare
1. Gmail provides a DKIM record
2. Add to Cloudflare DNS:
   ```
   Type: TXT
   Name: google._domainkey
   Content: v=DKIM1; k=rsa; p=[your_public_key]
   ```

---

# Cost Summary

| Service | Cost | Frequency |
|---------|------|-----------|
| **Domain** (.com) | $8-15 | Per year |
| **Cloudflare** | FREE | Forever |
| **Cloudflare Email Routing** | FREE | Forever |
| **Gmail SMTP** | FREE | Forever (500 emails/day) |
| **Railway Hosting** | FREE tier | Monthly |
| **SSL Certificate** | FREE | Auto-renew |

**Total**: ~$10-15/year (just the domain!)

---

# Complete Checklist

Before going live:

- [ ] Domain purchased and active
- [ ] Nameservers changed to Cloudflare
- [ ] DNS A/CNAME records configured
- [ ] SSL/TLS enabled (Full mode)
- [ ] MX/SPF/DKIM records added
- [ ] Gmail custom domain verified
- [ ] App Password generated
- [ ] Django settings updated
- [ ] Environment variables set
- [ ] Application deployed
- [ ] Test email sending
- [ ] Test website access (HTTPS)
- [ ] Test OTP password reset
- [ ] Monitor email deliverability

---

# Quick Reference

## DNS Records Template

```
Type    | Name  | Content                          | Proxy
--------|-------|----------------------------------|-------
A       | @     | your_ip or Railway IP            | ✅ Yes
CNAME   | www   | yourapp.railway.app              | ✅ Yes
MX      | @     | ASPMX.L.GOOGLE.COM               | ❌ No
TXT     | @     | v=spf1 include:_spf.google.com ~all | ❌ No
```

## Environment Variables

```bash
EMAIL_HOST_USER=yourgmail@gmail.com
EMAIL_HOST_PASSWORD=your_16_char_app_password
DEFAULT_FROM_EMAIL=noreply@yourdomain.com
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

---

# Summary

You now have:
✅ Custom domain with Cloudflare (FREE CDN, SSL, DDoS protection)
✅ Professional email sending from `noreply@yourdomain.com`
✅ Gmail SMTP (reliable, free, 500 emails/day)
✅ Email forwarding to Gmail (receive emails)
✅ HTTPS enabled
✅ Production-ready setup!

**Your app is now live at**: `https://yourdomain.com` 🎉

**Emails sent from**: `noreply@yourdomain.com` 📧

Total setup time: 30-45 minutes  
Total cost: ~$10-15/year (just the domain!)

---

**Next Steps**:
1. Monitor email delivery rates
2. Set up email analytics
3. Configure email templates
4. Add custom error pages
5. Set up monitoring and alerts
