import urllib.request, csv, io
req = urllib.request.Request('https://niftyindices.com/IndexConstituent/ind_nifty500list.csv', headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as response:
        content = response.read().decode('utf-8')
        reader = csv.reader(io.StringIO(content))
        symbols = []
        sector_map = {}
        next(reader) # skip header
        for row in reader:
            if len(row) > 2:
                sym = row[2].strip()
                ind = row[1].strip()
                symbols.append(sym)
                sector_map[sym] = ind
        print(f'Total downloaded: {len(symbols)}')
        if len(symbols) >= 500:
            with open('demand_supply/nifty500.py', 'w', encoding='utf-8') as f:
                f.write('"""\ndemand_supply/nifty500.py\n\nComplete Nifty 500 constituent list and sector mapping (NSE symbols).\nSource: NSE India — Nifty 500 Index\n"""\n\n')
                f.write('NIFTY_500 = [\n')
                for i in range(0, len(symbols), 10):
                    f.write('    ' + ', '.join(f'"{s}"' for s in symbols[i:i+10]) + ',\n')
                f.write(']\n\n')
                f.write('NIFTY_500 = sorted(set(NIFTY_500))\n\n')
                f.write('NIFTY_500_SECTORS = {\n')
                for sym, sec in sorted(sector_map.items()):
                    # Escape quotes in sector names just in case
                    sec_safe = sec.replace('"', '\\"')
                    f.write(f'    "{sym}": "{sec_safe}",\n')
                f.write('}\n\n')
                f.write('def get_nifty500_symbols():\n    """Return the Nifty 500 stock symbols as a sorted list."""\n    return list(NIFTY_500)\n\n')
                f.write('def get_sector_for_symbol(symbol):\n    """Return the sector for a Nifty 500 symbol, or None."""\n    return NIFTY_500_SECTORS.get(symbol.replace(".NS", "").replace(".BO", "").upper())\n')
            print('Successfully updated nifty500.py')
        else:
            print('Error: not enough symbols found.')
except Exception as e:
    print(f'Error downloading list: {e}')
