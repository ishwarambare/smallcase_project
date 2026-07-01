import pandas as pd
import pandas_ta as ta
import logging

logger = logging.getLogger(__name__)

def run_backtest(candles: list[dict], strategy_name: str, params: dict) -> dict:
    """
    Runs a backtest on historical candles based on the selected strategy.
    
    candles: [{'time': 123, 'open': 100, 'high': 110, 'low': 90, 'close': 105, 'volume': 1000}, ...]
    strategy_name: e.g., 'SUPERTREND', 'SMA_CROSS'
    params: e.g., {'length': 7, 'multiplier': 3.0} or {'fast': 50, 'slow': 200}
    
    Returns:
    {
        'trades': [
            {'type': 'buy', 'time': 12345, 'price': 100, 'pnl': 0},
            {'type': 'sell', 'time': 12350, 'price': 110, 'pnl': 10},
        ],
        'stats': {
            'total_pnl': 10,
            'win_rate': 100.0,
            'total_trades': 1,
            ...
        }
    }
    """
    if not candles or len(candles) < 20:
        return {'error': 'Not enough data for backtesting'}

    df = pd.DataFrame(candles)
    trades = []
    
    position = None # None, 'long'
    entry_price = 0
    entry_time = 0
    
    try:
        if strategy_name == 'SUPERTREND':
            length = int(params.get('length', 7))
            multiplier = float(params.get('multiplier', 3.0))
            
            df.ta.supertrend(length=length, multiplier=multiplier, append=True)
            dir_col = f'SUPERTd_{length}_{multiplier}'
            
            if dir_col not in df.columns:
                return {'error': 'Supertrend calculation failed'}
            
            # Simple strategy: Buy when direction flips to 1, Sell when flips to -1
            prev_dir = None
            
            for idx, row in df.iterrows():
                current_dir = row[dir_col]
                if pd.isna(current_dir):
                    continue
                    
                if prev_dir is not None:
                    # Flips from -1 to 1 => BUY
                    if prev_dir == -1 and current_dir == 1:
                        if position != 'long':
                            position = 'long'
                            entry_price = float(row['close'])
                            entry_time = int(row['time'])
                            trades.append({'type': 'buy', 'time': entry_time, 'price': entry_price})
                    
                    # Flips from 1 to -1 => SELL
                    elif prev_dir == 1 and current_dir == -1:
                        if position == 'long':
                            pnl = float(row['close'] - entry_price)
                            trades.append({'type': 'sell', 'time': int(row['time']), 'price': float(row['close']), 'pnl': pnl})
                            position = None
                            
                prev_dir = current_dir
                
        elif strategy_name == 'SMA_CROSS':
            fast = int(params.get('fast', 50))
            slow = int(params.get('slow', 200))
            
            df.ta.sma(length=fast, append=True)
            df.ta.sma(length=slow, append=True)
            
            fast_col = f'SMA_{fast}'
            slow_col = f'SMA_{slow}'
            
            if fast_col not in df.columns or slow_col not in df.columns:
                return {'error': 'SMA calculation failed'}
                
            prev_fast = None
            prev_slow = None
            
            for idx, row in df.iterrows():
                curr_fast = row[fast_col]
                curr_slow = row[slow_col]
                
                if pd.isna(curr_fast) or pd.isna(curr_slow):
                    continue
                    
                if prev_fast is not None and prev_slow is not None:
                    # Golden Cross (Fast crosses above Slow) => BUY
                    if prev_fast <= prev_slow and curr_fast > curr_slow:
                        if position != 'long':
                            position = 'long'
                            entry_price = float(row['close'])
                            entry_time = int(row['time'])
                            trades.append({'type': 'buy', 'time': entry_time, 'price': entry_price})
                            
                    # Death Cross (Fast crosses below Slow) => SELL
                    elif prev_fast >= prev_slow and curr_fast < curr_slow:
                        if position == 'long':
                            pnl = float(row['close'] - entry_price)
                            trades.append({'type': 'sell', 'time': int(row['time']), 'price': float(row['close']), 'pnl': pnl})
                            position = None
                            
                prev_fast = curr_fast
                prev_slow = curr_slow

        # Close open position at the end of the data to finalize PnL
        if position == 'long':
            last_row = df.iloc[-1]
            pnl = float(last_row['close'] - entry_price)
            trades.append({'type': 'sell', 'time': int(last_row['time']), 'price': float(last_row['close']), 'pnl': pnl, 'note': 'auto-close'})

    except Exception as e:
        logger.exception(f"Backtest error: {e}")
        return {'error': str(e)}

    # Calculate Stats
    completed_trades = [t for t in trades if 'pnl' in t]
    total_pnl = sum(t['pnl'] for t in completed_trades)
    wins = len([t for t in completed_trades if t['pnl'] > 0])
    total_completed = len(completed_trades)
    win_rate = (wins / total_completed * 100) if total_completed > 0 else 0

    return {
        'trades': trades,
        'stats': {
            'total_pnl': round(total_pnl, 2),
            'total_trades': total_completed,
            'win_rate': round(win_rate, 2),
            'wins': wins,
            'losses': total_completed - wins
        }
    }
