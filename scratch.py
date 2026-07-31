import re

with open(r'C:\Users\ishwa\.gemini\antigravity-ide\brain\cb8a6dd9-6098-4272-b4e0-cfa255ff11eb\.system_generated\steps\47\content.md', 'r', encoding='utf-8') as f:
    content = f.read()

strings = re.findall(r'\"([^\"]*import [^\"]+)\"', content)
for s in strings:
    s = s.encode('utf-8').decode('unicode_escape')
    if 'def ' in s or 'import plotly' in s or 'import matplotlib' in s or 'import mplfinance' in s:
        print('--- Code Block found ---')
        print(s)
