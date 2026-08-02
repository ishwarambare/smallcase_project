# generate_token.py
# Fyers API Access Token Generator Script

# pyrefly: ignore [missing-import]
from fyers_apiv3 import fyersModel
import webbrowser
import os

# =========================================================================
# === 1. FILL IN YOUR DETAILS HERE ===
# =========================================================================

CLIENT_ID = "ITPQ7TNSHD-100"  # Replace with your actual Fyers Client ID
SECRET_KEY = "1234567891"     # Replace with your actual Fyers Secret Key
REDIRECT_URI = "http://127.0.0.1"

# =========================================================================
# === 2. SCRIPT TO GENERATE THE AUTH CODE & TOKEN ===
# =========================================================================

def main():
    print("--- Fyers API v3 Token Generator ---")
    session = fyersModel.SessionModel(
        client_id=CLIENT_ID,
        secret_key=SECRET_KEY, 
        redirect_uri=REDIRECT_URI, 
        response_type="code",
        grant_type="authorization_code"
    )

    auth_url = session.generate_authcode()
    print(f"Opening login page in your browser...\nURL: {auth_url}\n")
    webbrowser.open(auth_url)

    print("\n--- ACTION REQUIRED ---")
    print("1. Log in to Fyers in the browser window that just opened.")
    print("2. You will be redirected to http://127.0.0.1/?auth_code=... (Normal behavior).")
    print("3. Copy the full URL from your browser's address bar.")
    
    auth_code_url = input("\nPaste the full redirect URL here and press Enter: ")

    try:
        auth_code = auth_code_url.split('auth_code=')[1].split('&')[0]
        print(f"\nExtracted auth_code: {auth_code[:10]}...")
    except Exception as e:
        print(f"Error: Could not parse auth_code from URL: {e}")
        return

    session.set_token(auth_code)
    response = session.generate_token()

    if "access_token" in response:
        access_token = response["access_token"]
        print("\n--- SUCCESS! ---")
        print("Your ACCESS_TOKEN is:")
        print(access_token)
        
        with open("fyers_access_token.txt", "w") as f:
            f.write(access_token)
        print("\nToken saved to 'fyers_access_token.txt'")
    else:
        print("\n--- FAILED TO GENERATE TOKEN ---")
        print(f"Error: {response.get('message', 'Unknown error')}")

if __name__ == '__main__':
    main()
