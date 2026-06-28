# 📱 Complete SMS Setup Guide (Twilio)

This guide provides **detailed step-by-step instructions** for setting up SMS services for OTP password reset in your Django project.

---

## Table of Contents
1. [Twilio SMS Setup](#1-twilio-sms-setup-recommended)
2. [Alternative: MSG91 (India)](#2-alternative-msg91-for-india)
3. [Testing SMS](#3-testing-sms)
4. [Troubleshooting](#4-troubleshooting)

---

# 1. Twilio SMS Setup (Recommended)

**Free Trial**: $15 credit  
**Cost After Trial**: Pay-as-you-go (~$0.0075 per SMS in US)  
**Best For**: Global SMS delivery, Reliable service

---

## Step 1: Create Twilio Account

### 1.1 Sign Up
1. Visit: https://www.twilio.com/try-twilio
2. Click **"Sign up"** or **"Start for free"**
3. Fill in the registration form:
   - **First Name**
   - **Last Name**
   - **Email Address**
   - **Password** (create a strong password)
4. Click **"Start your free trial"**

### 1.2 Verify Email
1. Check your email inbox
2. Click the **verification link** from Twilio
3. Your email is now verified

### 1.3 Verify Phone Number
1. After email verification, Twilio will ask for your phone number
2. Enter your phone number (include country code)
   - Example: `+1234567890` for US
   - Example: `+919876543210` for India
3. Choose verification method: **Text message** or **Call**
4. Enter the **verification code** you receive
5. Click **"Submit"**

### 1.4 Complete Profile
1. Twilio will ask some questions:
   - **Which Twilio product are you here to use?**
     - Select: ✅ **"Messaging"** (SMS/MMS)
   - **What do you plan to build?**
     - Select: **"Verify users"** or **"Transactional Notifications"**
   - **How do you want to build with Twilio?**
     - Select: **"With code"**
   - **What is your preferred language?**
     - Select: **"Python"**
2. Click **"Get Started with Twilio"**

✅ **Checkpoint**: You're now in the Twilio Console Dashboard

---

## Step 2: Get Your Twilio Credentials

### 2.1 Find Account SID and Auth Token
1. You should be on the **Twilio Console** dashboard: https://console.twilio.com/
2. Look for the **"Account Info"** panel on the right side
3. You'll see:
   - **Account SID**: Starts with `AC...` (string of letters and numbers)
   - **Auth Token**: Click **"Show"** to reveal it
4. **Copy both values** and save them securely

**Example format**:
```
Account SID: ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Auth Token: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

✅ **Checkpoint**: You have your Account SID and Auth Token

---

## Step 3: Get a Twilio Phone Number

### 3.1 Get Your First Phone Number
1. From Twilio Console, look for the left sidebar
2. Click **"Phone Numbers"** → **"Manage"** → **"Buy a number"**
3. Or directly visit: https://console.twilio.com/us1/develop/phone-numbers/manage/search

### 3.2 Search for a Number
1. You'll see the **"Buy a number"** page
2. **Select Country**: Choose your target country (e.g., United States, India)
3. **Capabilities**: Ensure **"SMS"** is checked ✅
4. **Number Type**: 
   - For US/Canada: Choose **"Local"** (free with trial)
   - For other countries: Check available types
5. Click **"Search"**

### 3.3 Choose and Buy Number
1. Twilio will show available phone numbers
2. Look for one that supports **SMS** capability
3. Click **"Buy"** button next to your preferred number
4. Confirm the purchase (uses trial credit - FREE during trial)
5. Click **"Buy [phone number]"**

### 3.4 Copy Your Phone Number
1. After purchase, you'll see your new number
2. **Copy the number** (format: `+1234567890`)
3. Go to **"Active Numbers"** to see all your numbers
4. Or visit: https://console.twilio.com/us1/develop/phone-numbers/manage/incoming

✅ **Checkpoint**: You have a Twilio phone number (e.g., `+1234567890`)

---

## Step 4: Configure Your Django Project

### 4.1 Update `.env` File
Open your `.env` file and add these lines:

```bash
# SMS Configuration - Twilio
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_PHONE_NUMBER=+1234567890
```

**Replace**:
- `ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` → Your Account SID
- `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` → Your Auth Token
- `+1234567890` → Your Twilio phone number (with country code)

### 4.2 Verify Installation
Make sure Twilio package is installed:
```bash
pip install twilio
```

### 4.3 Restart Django Server
```bash
# Stop the server (Ctrl+C)
python manage.py runserver
```

---

## Step 5: Test SMS Sending

### 5.1 Test via Django Shell
```bash
python manage.py shell
```

```python
from twilio.rest import Client
from django.conf import settings

# Initialize Twilio client
client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

# Send test SMS
message = client.messages.create(
    body='Hello! This is a test SMS from Django via Twilio.',
    from_=settings.TWILIO_PHONE_NUMBER,
    to='+1234567890'  # Replace with your verified phone number
)

print(f"Message SID: {message.sid}")
print(f"Status: {message.status}")
```

**Important**: During trial, you can only send to **verified phone numbers**!

### 5.2 Verify Phone Numbers (Trial Mode)
1. Go to: https://console.twilio.com/us1/develop/phone-numbers/manage/verified
2. Click **"Add a new number"** (the red + button)
3. Enter the phone number you want to send test SMS to
4. Choose verification method (Call or SMS)
5. Enter verification code
6. Now you can send SMS to this number during trial

### 5.3 Test OTP Password Reset
1. Visit: http://localhost:1234/en/forgot-password/
2. Select **"SMS"** method
3. Enter your **verified phone number**
4. You should receive the OTP via SMS!

✅ **Success**: SMS received with OTP!

---

## Step 6: Upgrade Account (Optional - For Production)

### 6.1 When to Upgrade
- ✅ Trial credit running low ($15 consumed)
- ✅ Need to send to unverified numbers
- ✅ Ready for production deployment
- ✅ Need higher sending limits

### 6.2 How to Upgrade
1. Go to: https://console.twilio.com/us1/billing
2. Click **"Upgrade"** button
3. Add payment method (credit card)
4. Set up auto-recharge (optional)
5. Submit

### 6.3 Pricing (Pay-as-you-go)
After upgrade, typical costs:
- **US/Canada SMS**: ~$0.0079 per message
- **India SMS**: ~$0.0053 per message
- **Other countries**: Varies by region

**Check pricing**: https://www.twilio.com/en-us/sms/pricing

---

# 2. Alternative: MSG91 (For India)

**Better for**: India-specific SMS delivery  
**Free Trial**: Limited messages  
**Cost**: More economical for India

## Step 1: Create MSG91 Account

### 1.1 Sign Up
1. Visit: https://msg91.com/
2. Click **"Sign Up Free"**
3. Fill in details:
   - **Name**
   - **Email**
   - **Phone Number**
   - **Company Name**
4. Click **"Sign Up"**

### 1.2 Verify Account
1. Verify email via link sent to inbox
2. Verify phone number via OTP

### 1.3 Complete KYC (For India)
1. Upload required documents:
   - Aadhaar Card / PAN Card
   - Business registration (if applicable)
2. Wait for approval (usually 24-48 hours)

---

## Step 2: Get MSG91 Credentials

### 2.1 Get Auth Key
1. Login to MSG91 dashboard
2. Go to **"API"** section
3. Copy your **Auth Key**

### 2.2 Get Sender ID
1. Go to **"Sender ID"** section
2. Create a new Sender ID (e.g., "SMLCSE")
3. Wait for approval (required in India)

### 2.3 Configure Django
```bash
# SMS Configuration - MSG91
MSG91_AUTH_KEY=your_auth_key_here
MSG91_SENDER_ID=SMLCSE
```

---

## Step 3: Implement MSG91 in Django

Create custom SMS utility in `user/sms_utils.py`:

```python
import requests
from django.conf import settings

def send_sms_msg91(phone_number, message):
    """Send SMS using MSG91"""
    url = "https://api.msg91.com/api/v5/flow/"
    
    payload = {
        "authkey": settings.MSG91_AUTH_KEY,
        "mobiles": phone_number,
        "message": message,
        "sender": settings.MSG91_SENDER_ID,
        "route": "4",  # Transactional route
        "country": "91"  # India country code
    }
    
    response = requests.post(url, data=payload)
    return response.json()
```

---

# 3. Testing SMS

## Test OTP System

### 3.1 Test Email OTP (No Cost)
1. Visit: http://localhost:1234/en/forgot-password/
2. Select **"Email"** method
3. Enter your email
4. Check email for OTP (or console if using console backend)

### 3.2 Test SMS OTP (Uses Credits)
1. Visit: http://localhost:1234/en/forgot-password/
2. Select **"SMS"** method
3. Enter phone number (must be verified in Twilio trial)
4. Receive OTP via SMS
5. Enter OTP to reset password

---

# 4. Troubleshooting

## Twilio Issues

### Issue 1: "Unable to create record: Permission denied"
**Cause**: Trial account trying to send to unverified number

**Solution**:
1. Verify the recipient's phone number in Twilio Console
2. Or upgrade your account to send to any number

---

### Issue 2: "The 'From' number is not a valid phone number"
**Cause**: Incorrect phone number format

**Solution**:
- Use E.164 format: `+[country code][number]`
- Examples:
  - US: `+14155552671`
  - India: `+919876543210`
  - No spaces or special characters

---

### Issue 3: "Authenticate"
**Cause**: Wrong Account SID or Auth Token

**Solution**:
- Double-check credentials in `.env`
- Ensure no extra spaces
- Verify in Twilio Console

---

### Issue 4: SMS not received
**Causes & Solutions**:
1. **Phone not verified** (trial mode)
   - Verify phone at: https://console.twilio.com/us1/develop/phone-numbers/manage/verified
   
2. **Wrong phone number format**
   - Use E.164 format with country code
   
3. **Number opted out**
   - Check Twilio logs: https://console.twilio.com/us1/monitor/logs/sms
   
4. **Carrier issues**
   - Try different carrier/phone number

---

### Issue 5: "Insufficient credit"
**Solution**:
- Check balance: https://console.twilio.com/us1/billing
- Add more credit or upgrade account

---

## MSG91 Issues

### Issue 1: "Invalid Auth Key"
**Solution**:
- Verify auth key from dashboard
- Regenerate if necessary

### Issue 2: "Sender ID not approved"
**Solution**:
- Wait for approval (24-48 hours in India)
- Use default sender ID temporarily

### Issue 3: "DND number"
**Solution**:
- Can't send promotional SMS to DND numbers in India
- Use transactional route
- Or request user to disable DND

---

# Cost Comparison

| Provider | Free Trial | SMS Cost (India) | SMS Cost (US) | Best For |
|----------|-----------|------------------|---------------|----------|
| **Twilio** | $15 credit | ₹0.40 (~$0.0053) | $0.0079 | Global, Reliable |
| **MSG91** | Limited | ₹0.15-0.30 | N/A | India only |

---

# Production Checklist

Before going live with SMS:

- [ ] Upgrade Twilio account (if using trial)
- [ ] Verify all numbers removed (not needed in production)
- [ ] Set up auto-recharge for credits
- [ ] Configure proper error handling
- [ ] Add SMS rate limiting
- [ ] Monitor SMS logs regularly
- [ ] Set up alerts for failed messages
- [ ] Comply with SMS regulations (opt-in/opt-out)

---

# Security Best Practices

1. ✅ **Never commit credentials** to Git
2. ✅ **Use environment variables**
3. ✅ **Rotate credentials** periodically
4. ✅ **Monitor usage** for fraud
5. ✅ **Implement rate limiting** to prevent abuse
6. ✅ **Log all SMS activity**
7. ✅ **Use HTTPS** for webhook URLs

---

# Integration with Password Reset

Your OTP system is already integrated! The flow:

```
User visits /forgot-password/
    ↓
Selects SMS method
    ↓
Enters phone number
    ↓
OTPManager.send_otp_sms() sends OTP
    ↓
User receives SMS with OTP
    ↓
User enters OTP
    ↓
OTPManager.verify_otp() validates
    ↓
User resets password
```

---

# Quick Start Commands

```bash
# Install Twilio
pip install twilio

# Test SMS via Shell
python manage.py shell

# Then in shell:
from twilio.rest import Client
from django.conf import settings

client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
message = client.messages.create(
    body="Test SMS",
    from_=settings.TWILIO_PHONE_NUMBER,
    to="+1234567890"
)
print(message.sid)
```

---

# Next Steps

1. ✅ Complete Twilio setup
2. ✅ Test SMS OTP
3. ✅ Set up email SMTP (see `EMAIL_SMTP_SETUP_GUIDE.md`)
4. ✅ Configure OAuth (see `OAUTH_SETUP_GUIDE.md`)
5. ✅ Deploy to production

---

**Need help?** Check Twilio documentation: https://www.twilio.com/docs/sms
