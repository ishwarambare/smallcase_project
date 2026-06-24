import requests
import io
import csv
import sys

NSE_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
OUTPUT_FILE = "sample_stocks.csv"

def fetch_and_update():
    print("Fetching Indian stock market list from NSE archives...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(NSE_URL, headers=headers, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching the NSE stock list: {e}")
        sys.exit(1)
        
    print("Download successful. Parsing stock symbols...")
    try:
        csv_data = response.content.decode('utf-8')
        f = io.StringIO(csv_data)
        reader = csv.reader(f)
        
        # Read header row
        header = next(reader, None)
        if not header:
            print("Error: Empty CSV received from NSE.")
            sys.exit(1)
            
        # Clean header column names to find 'SYMBOL' and 'NAME OF COMPANY'
        cleaned_header = [col.strip().upper() for col in header]
        try:
            symbol_index = cleaned_header.index('SYMBOL')
        except ValueError:
            print("Error: Could not find 'SYMBOL' column in the CSV.")
            sys.exit(1)
            
        try:
            name_index = cleaned_header.index('NAME OF COMPANY')
        except ValueError:
            name_index = symbol_index
            
        stocks_data = []
        for row in reader:
            if not row or len(row) <= symbol_index:
                continue
            symbol = row[symbol_index].strip()
            name = row[name_index].strip() if len(row) > name_index else symbol
            if symbol and symbol != 'SYMBOL':
                stocks_data.append((symbol, name))
                
        # Sort stocks alphabetically by symbol
        stocks_data.sort(key=lambda x: x[0])
        
        print(f"Found {len(stocks_data)} stock symbols. Writing to {OUTPUT_FILE}...")
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8', newline='') as out_f:
            writer = csv.writer(out_f)
            writer.writerow(['symbol', 'name'])
            for symbol, name in stocks_data:
                writer.writerow([symbol, name])
                
        print(f"Success! Updated {OUTPUT_FILE} with {len(stocks_data)} Indian market stocks.")
        
    except Exception as e:
        print(f"Error processing stock symbols: {e}")
        sys.exit(1)

if __name__ == "__main__":
    fetch_and_update()
