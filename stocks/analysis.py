import pandas as pd
import pandas_ta as ta
import logging

logger = logging.getLogger(__name__)

def compute_indicators(candles: list[dict], indicators: list[str]) -> dict:
    """
    Computes technical indicators using pandas-ta.
    candles: list of dicts [{'time': 123, 'open': 100, 'high': 110, 'low': 90, 'close': 105, 'volume': 1000}, ...]
    indicators: list of strings e.g. ['SMA:50', 'EMA:200', 'RSI:14', 'MACD', 'SUPERTREND:7:3']
    
    Returns a dict mapping indicator string to a list of dicts suitable for lightweight-charts:
    {
        'SMA:50': [{'time': 123, 'value': 102.5}, ...],
        'SUPERTREND:7:3': [{'time': 123, 'value': 104, 'direction': 1}, ...]
    }
    """
    if not candles:
        return {}

    df = pd.DataFrame(candles)
    # pandas-ta needs columns lowercase mostly, we have them from lightweight-charts format
    # Ensure time is kept for output mapping
    result = {}

    try:
        for ind in indicators:
            parts = ind.split(':')
            name = parts[0].upper()
            
            if name == 'SMA':
                length = int(parts[1]) if len(parts) > 1 else 50
                col_name = f'SMA_{length}'
                df.ta.sma(length=length, append=True)
                if col_name in df.columns:
                    result[ind] = [{'time': int(t), 'value': float(v)} for t, v in zip(df['time'], df[col_name]) if pd.notna(v)]

            elif name == 'EMA':
                length = int(parts[1]) if len(parts) > 1 else 50
                col_name = f'EMA_{length}'
                df.ta.ema(length=length, append=True)
                if col_name in df.columns:
                    result[ind] = [{'time': int(t), 'value': float(v)} for t, v in zip(df['time'], df[col_name]) if pd.notna(v)]
                    
            elif name == 'RSI':
                length = int(parts[1]) if len(parts) > 1 else 14
                col_name = f'RSI_{length}'
                df.ta.rsi(length=length, append=True)
                if col_name in df.columns:
                    result[ind] = [{'time': int(t), 'value': float(v)} for t, v in zip(df['time'], df[col_name]) if pd.notna(v)]
                    
            elif name == 'MACD':
                fast = int(parts[1]) if len(parts) > 1 else 12
                slow = int(parts[2]) if len(parts) > 2 else 26
                signal = int(parts[3]) if len(parts) > 3 else 9
                df.ta.macd(fast=fast, slow=slow, signal=signal, append=True)
                macd_col = f'MACD_{fast}_{slow}_{signal}'
                hist_col = f'MACDh_{fast}_{slow}_{signal}'
                sig_col = f'MACDs_{fast}_{slow}_{signal}'
                
                # We return a structured list for MACD since it has 3 lines
                if macd_col in df.columns:
                    macd_data = []
                    for t, m, h, s in zip(df['time'], df[macd_col], df[hist_col], df[sig_col]):
                        if pd.notna(m):
                            macd_data.append({
                                'time': int(t),
                                'macd': float(m),
                                'histogram': float(h),
                                'signal': float(s)
                            })
                    result[ind] = macd_data

            elif name == 'SUPERTREND':
                length = int(parts[1]) if len(parts) > 1 else 7
                multiplier = float(parts[2]) if len(parts) > 2 else 3.0
                df.ta.supertrend(length=length, multiplier=multiplier, append=True)
                
                # pandas-ta supertrend creates columns like:
                # SUPERT_7_3.0, SUPERTd_7_3.0 (direction 1/-1), SUPERTl_7_3.0 (long), SUPERTs_7_3.0 (short)
                st_col = f'SUPERT_{length}_{multiplier}'
                dir_col = f'SUPERTd_{length}_{multiplier}'
                
                if st_col in df.columns and dir_col in df.columns:
                    st_data = []
                    for t, v, d in zip(df['time'], df[st_col], df[dir_col]):
                        if pd.notna(v):
                            st_data.append({
                                'time': int(t),
                                'value': float(v),
                                'direction': int(d) if pd.notna(d) else 1
                            })
                    result[ind] = st_data

    except Exception as e:
        logger.exception(f"Error computing indicators: {e}")
        
    return result
