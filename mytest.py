import requests

# BSE scrip codes — find at bseindia.com
# Reliance=500325, TCS=532540, HDFC Bank=500180
SCRIP_CODE = "532540"  # TCS
COMPANY    = "TCS"

# Step 1: Get annual report file list
# url = f"https://www.bseindia.com/bseplus/AnnualReport/{SCRIP_CODE}/annualreports.aspx"
url = f"https://www.bseindia.com/bseplus/AnnualReport/532540/annualreports.aspx"

# Step 2: Direct PDF download (once you have the filename)
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
pdf_url = f"https://www.bseindia.com/bseplus/AnnualReport/{SCRIP_CODE}/{SCRIP_CODE}_AnnualReport_2024.pdf"

r = requests.get(pdf_url, headers=headers)
with open(f"{COMPANY}_annual_report.pdf", "wb") as f:
    f.write(r.content)
print(f"Downloaded: {COMPANY}_annual_report.pdf")