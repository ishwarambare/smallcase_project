"""
demand_supply/engine.py

GTF-style Demand-Supply Zone Detection Engine
==============================================

Implements the Get Together Finance (GTF) methodology for identifying
institutional demand and supply zones across multiple timeframes.

Core concepts:
  - Demand Zone: A base (consolidation) before a strong impulsive UP-move
  - Supply Zone: A base (consolidation) before a strong impulsive DOWN-move
  - Zone = rectangle from low-of-base to high-of-base
  - Proximal line = edge closest to current price (entry trigger)
  - Distal line = edge furthest from current price (stop-loss reference)

Scoring factors (GTF-aligned):
  1. Freshness — price hasn't returned to test the zone since formation (+30)
  2. Base tightness — fewer candles in the base = stronger zone (+25)
  3. Move strength — % move away and volume spike (+25)
  4. Multi-timeframe alignment — zone confirmed on higher TF too (+20)
"""

import logging
import math
import os
from datetime import datetime, timedelta, date
from decimal import Decimal

import pandas as pd
import diskcache

# Initialize local disk cache for API requests
CACHE_DIR = os.path.join(os.getcwd(), '.cache', 'zone_cache')
cache = diskcache.Cache(CACHE_DIR)

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# Constants
# ═════════════════════════════════════════════════════════════════════════════

# Minimum % move away from base to qualify as an impulsive move
MIN_IMPULSE_MOVE_PCT = 1.5

# Maximum candles allowed in a base (GTF prefers 1-3)
MAX_BASE_CANDLES = 5

# How close price needs to be to a zone to count as "in zone" (%)
ZONE_PROXIMITY_PCT = 5.0

# Lookback for swing detection
SWING_LOOKBACK = 2

from .nifty500 import get_sector_for_symbol


# ═════════════════════════════════════════════════════════════════════════════
# Candle Data Helpers
# ═════════════════════════════════════════════════════════════════════════════

def candles_to_dataframe(candles: list[dict]) -> pd.DataFrame:
    """
    Convert Fyers-format candle list to a DataFrame.
    Input:  [{'time': epoch, 'open': f, 'high': f, 'low': f, 'close': f, 'volume': i}, ...]
    Output: DataFrame with columns [open, high, low, close, volume, date] indexed by time.
    """
    if not candles:
        return pd.DataFrame()

    df = pd.DataFrame(candles)
    if 'time' in df.columns:
        df['date'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('date', inplace=True)
    df = df.sort_index()
    # Drop rows with NaN in OHLC columns (e.g. incomplete today's data from yfinance)
    df = df.dropna(subset=['open', 'high', 'low', 'close'])
    return df


def resample_to_timeframe(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """
    Resample daily or intraday OHLCV data to higher timeframes.
    """
    tf_map = {
        'weekly': 'W',
        'monthly': 'ME',
        'quarterly': 'QE',
        'daily': 'D',
        '125min': '125min',
        '75min': '75min'
    }
    rule = tf_map.get(timeframe, 'D')
    if rule == 'D':
        return df

    if timeframe in ['125min', '75min']:
        resampled = df.resample(rule, origin='start').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
        }).dropna()
        return resampled

    resampled = df.resample(rule).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum',
    }).dropna()

    return resampled


# ═════════════════════════════════════════════════════════════════════════════
# Core Zone Detection
# ═════════════════════════════════════════════════════════════════════════════

def _candle_body_pct(row) -> float:
    """Returns the body size as a % of the candle range."""
    rng = row['high'] - row['low']
    if rng == 0:
        return 0
    return abs(row['close'] - row['open']) / rng * 100


def _is_small_candle(row, avg_range: float) -> bool:
    """A candle is a 'Base Candle' if its body is less than 50% of its total range."""
    candle_range = row['high'] - row['low']
    if candle_range == 0:
        return True
    body = abs(row['close'] - row['open'])
    return (body / candle_range) <= 0.50


def _is_strong_move(row, avg_range: float, multiplier: float = 1.0) -> bool:
    """A candle is a 'strong move' if its range exceeds multiplier x avg_range."""
    candle_range = row['high'] - row['low']
    return candle_range > (avg_range * multiplier)


def find_demand_zones(df: pd.DataFrame) -> list[dict]:
    """
    Find demand zones in OHLCV data.

    A demand zone forms when:
    1. There's a consolidation (base) of 1-5 small candles
    2. Followed by a strong impulsive UP-move (breakout candle)
    3. The base rectangle (low of base → high of base) is the demand zone

    Returns list of zone dicts:
        {
            'proximal': float,     # Top of zone (closest to price for demand)
            'distal': float,       # Bottom of zone (furthest from price)
            'formed_date': str,    # ISO date when zone formed
            'base_candles': int,   # Number of candles in the base
            'move_pct': float,     # % move away from zone
            'move_volume': int,    # Volume on breakout candle
            'is_fresh': bool,      # Price hasn't returned to zone
        }
    """
    if df.empty or len(df) < 5:
        return []

    zones = []
    avg_range = (df['high'] - df['low']).mean()
    if avg_range == 0:
        return []

    data = df.reset_index()

    for i in range(SWING_LOOKBACK, len(data) - 1):
        breakout = data.iloc[i]

        # Check if this candle is a strong bullish move
        if not _is_strong_move(breakout, avg_range, 1.0):
            continue
        if breakout['close'] <= breakout['open']:
            continue  # Must be a green (bullish) candle

        move_pct = ((breakout['close'] - breakout['open']) / breakout['open']) * 100
        if move_pct < 0.5:  # Very relaxed threshold to capture more zones
            continue

        # Look backwards for the base (consolidation)
        base_start = max(0, i - MAX_BASE_CANDLES)
        base_candles = []
        leg_in_idx = -1

        for j in range(i - 1, base_start - 1, -1):
            candle = data.iloc[j]
            if _is_small_candle(candle, avg_range):
                base_candles.insert(0, candle)
            else:
                leg_in_idx = j
                break

        if len(base_candles) < 1:
            continue

        # Zone = Distal (lowest wick of pattern) to Proximal (highest body of base)
        base_lows = [c['low'] for c in base_candles]
        distal_candidates = base_lows.copy()
        
        if leg_in_idx != -1:
            distal_candidates.append(data.iloc[leg_in_idx]['low'])
            
        distal_candidates.append(breakout['low'])

        base_high_bodies = [max(c['open'], c['close']) for c in base_candles]
        
        zone_distal = min(distal_candidates)   # Bottom of zone (lowest wick)
        zone_proximal = max(base_high_bodies)  # Top of zone (highest body)

        if zone_proximal <= zone_distal:
            continue

        # Leg Out count & gap
        leg_out_count = 1
        leg_out_gap = bool(breakout['open'] > zone_proximal)
        
        # Check forward for more consecutive leg-out candles
        for k in range(i + 1, min(i + 4, len(data))):
            c = data.iloc[k]
            if _is_strong_move(c, avg_range, 1.0) and c['close'] > c['open']:
                leg_out_count += 1
            else:
                break
                
        # Check if zone is fresh (test count)
        future_data = data.iloc[i + leg_out_count:]
        test_count = 0
        in_test = False
        for _, c in future_data.iterrows():
            if c['low'] <= zone_proximal:
                if not in_test:
                    test_count += 1
                    in_test = True
            else:
                in_test = False
        
        is_fresh = bool(test_count == 0)

        # Get the formed date
        formed_date = base_candles[0].get('date', data.iloc[i].get('date'))
        if hasattr(formed_date, 'isoformat'):
            formed_date = formed_date.isoformat()[:10]
        else:
            formed_date = str(formed_date)[:10]

        zones.append({
            'proximal': round(float(zone_proximal), 2),
            'distal': round(float(zone_distal), 2),
            'formed_date': formed_date,
            'base_candles': len(base_candles),
            'move_pct': round(float(move_pct), 2),
            'move_volume': int(breakout.get('volume', 0)),
            'is_fresh': is_fresh,
            'test_count': test_count,
            'leg_out_count': leg_out_count,
            'leg_out_gap': leg_out_gap,
        })

    # De-duplicate overlapping zones — keep the strongest
    zones = _dedup_zones(zones)
    return zones


def find_supply_zones(df: pd.DataFrame) -> list[dict]:
    """
    Find supply zones — mirror of demand zone logic.

    A supply zone forms when:
    1. There's a consolidation (base) of 1-5 small candles
    2. Followed by a strong impulsive DOWN-move (breakdown candle)
    3. The base rectangle is the supply zone

    Returns list of zone dicts with same schema as demand zones.
    """
    if df.empty or len(df) < 5:
        return []

    zones = []
    avg_range = (df['high'] - df['low']).mean()
    if avg_range == 0:
        return []

    data = df.reset_index()

    for i in range(SWING_LOOKBACK, len(data) - 1):
        breakdown = data.iloc[i]

        # Check if this candle is a strong bearish move
        if not _is_strong_move(breakdown, avg_range, 1.0):
            continue
        if breakdown['close'] >= breakdown['open']:
            continue  # Must be a red (bearish) candle

        move_pct = ((breakdown['open'] - breakdown['close']) / breakdown['open']) * 100
        if move_pct < 0.5:
            continue

        # Look backwards for the base
        base_start = max(0, i - MAX_BASE_CANDLES)
        base_candles = []
        leg_in_idx = -1

        for j in range(i - 1, base_start - 1, -1):
            candle = data.iloc[j]
            if _is_small_candle(candle, avg_range):
                base_candles.insert(0, candle)
            else:
                leg_in_idx = j
                break

        if len(base_candles) < 1:
            continue

        # Zone = Distal (highest wick of pattern) to Proximal (lowest body of base)
        base_highs = [c['high'] for c in base_candles]
        distal_candidates = base_highs.copy()
        
        if leg_in_idx != -1:
            distal_candidates.append(data.iloc[leg_in_idx]['high'])
            
        distal_candidates.append(breakdown['high'])

        base_low_bodies = [min(c['open'], c['close']) for c in base_candles]
        
        zone_distal = max(distal_candidates)   # Top of zone (highest wick)
        zone_proximal = min(base_low_bodies)   # Bottom of zone (lowest body)

        if zone_distal <= zone_proximal:
            continue

        # Leg Out count & gap
        leg_out_count = 1
        leg_out_gap = bool(breakdown['open'] < zone_proximal)
        
        # Check forward for more consecutive leg-out candles
        for k in range(i + 1, min(i + 4, len(data))):
            c = data.iloc[k]
            if _is_strong_move(c, avg_range, 1.0) and c['close'] < c['open']:
                leg_out_count += 1
            else:
                break
                
        # Check if zone is fresh (test count)
        future_data = data.iloc[i + leg_out_count:]
        test_count = 0
        in_test = False
        for _, c in future_data.iterrows():
            if c['high'] >= zone_proximal:
                if not in_test:
                    test_count += 1
                    in_test = True
            else:
                in_test = False
                
        is_fresh = bool(test_count == 0)

        formed_date = base_candles[0].get('date', data.iloc[i].get('date'))
        if hasattr(formed_date, 'isoformat'):
            formed_date = formed_date.isoformat()[:10]
        else:
            formed_date = str(formed_date)[:10]

        zones.append({
            'proximal': round(float(zone_proximal), 2),
            'distal': round(float(zone_distal), 2),
            'formed_date': formed_date,
            'base_candles': len(base_candles),
            'move_pct': round(float(move_pct), 2),
            'move_volume': int(breakdown.get('volume', 0)),
            'is_fresh': is_fresh,
            'test_count': test_count,
            'leg_out_count': leg_out_count,
            'leg_out_gap': leg_out_gap,
        })

    zones = _dedup_zones(zones)
    return zones


def _dedup_zones(zones: list[dict], overlap_threshold_pct: float = 2.0) -> list[dict]:
    """
    Remove overlapping zones, keeping the one with stronger move_pct.
    Two zones 'overlap' if their proximal lines are within overlap_threshold_pct.
    """
    if not zones:
        return zones

    zones.sort(key=lambda z: z['proximal'])
    deduped = [zones[0]]

    for z in zones[1:]:
        prev = deduped[-1]
        mid_prev = (prev['proximal'] + prev['distal']) / 2
        mid_curr = (z['proximal'] + z['distal']) / 2

        if mid_prev == 0:
            deduped.append(z)
            continue

        overlap_pct = abs(mid_curr - mid_prev) / mid_prev * 100
        if overlap_pct < overlap_threshold_pct:
            # Keep the stronger zone
            if z['move_pct'] > prev['move_pct']:
                deduped[-1] = z
        else:
            deduped.append(z)

    return deduped


# ═════════════════════════════════════════════════════════════════════════════
# Zone Strength Scoring
# ═════════════════════════════════════════════════════════════════════════════

def score_zone_strength(zone: dict, avg_volume: float = 0) -> float:
    """
    Score a zone's strength based on the precise GTF Core Trade Score (0 to 7 points).
    """
    score = 0.0

    # 1. Freshness (Max 3 points)
    test_count = zone.get('test_count', 0)
    if test_count == 0:
        score += 3.0
    elif test_count == 1:
        score += 1.5
    # test_count >= 2 -> 0 points

    # 2. Strength / Leg Out (Max 2 points)
    leg_out = zone.get('leg_out_count', 1)
    has_gap = zone.get('leg_out_gap', False)
    if leg_out >= 2 or (leg_out == 1 and has_gap):
        score += 2.0
    elif leg_out == 1:
        score += 1.0

    # 3. Base Candles (Max 2 points)
    base_count = zone.get('base_candles', 3)
    if 1 <= base_count <= 3:
        score += 2.0
    elif 4 <= base_count <= 5:
        score += 1.0
    # > 5 candles -> 0 points

    return score


# ═════════════════════════════════════════════════════════════════════════════
# Price-in-Zone Check
# ═════════════════════════════════════════════════════════════════════════════

def is_price_in_demand_zone(current_price: float, zone: dict, threshold_pct: float = ZONE_PROXIMITY_PCT) -> bool:
    """
    Check if current price is at or near a demand zone.

    Rules (GTF methodology):
      - Demand zones are BELOW current price (support levels).
      - A demand zone ABOVE current price is invalid — it has already been
        consumed / price has moved through it and it is no longer a demand.
      - Valid: zone.proximal_line <= current_price <= zone.proximal_line * (1 + threshold_pct%)
    """
    proximal = zone['proximal']   # top of demand zone
    distal   = zone['distal']     # bottom of demand zone

    # RULE: Demand zone must be below current price (proximal <= price)
    if proximal > current_price:
        return False

    # Price should be within threshold% above the proximal line to count as "approaching"
    upper_bound = proximal * (1 + threshold_pct / 100)
    return distal <= current_price <= upper_bound


def is_price_in_supply_zone(current_price: float, zone: dict, threshold_pct: float = ZONE_PROXIMITY_PCT) -> bool:
    """
    Check if current price is at or near a supply zone.

    Rules (GTF methodology):
      - Supply zones are ABOVE current price (resistance levels).
      - A supply zone BELOW current price is invalid — it has already been
        broken through and is no longer acting as resistance.
      - Valid: zone.proximal_line * (1 - threshold_pct%) <= current_price <= zone.distal_line
    """
    proximal = zone['proximal']   # bottom of supply zone
    distal   = zone['distal']     # top of supply zone

    # RULE: Supply zone must be above current price (proximal >= price)
    if proximal < current_price:
        return False

    # Price should be within threshold% below the proximal line to count as "approaching"
    lower_bound = proximal * (1 - threshold_pct / 100)
    return lower_bound <= current_price <= distal


# ═════════════════════════════════════════════════════════════════════════════
# Multi-Timeframe Scanner
# ═════════════════════════════════════════════════════════════════════════════

def scan_stock_zones(symbol: str, fyers_svc=None) -> dict:
    """
    Scan a single stock for demand/supply zones across quarterly, monthly, weekly timeframes.

    Uses Fyers API for historical candle data if available, falls back to yfinance.

    Returns:
        {
            'symbol': str,
            'name': str,
            'sector': str,
            'current_price': float,
            'demand_zones': {'quarterly': [...], 'monthly': [...], 'weekly': [...]},
            'supply_zones': {'quarterly': [...], 'monthly': [...], 'weekly': [...]},
            'demand_overlap_count': int,
            'supply_overlap_count': int,
            'quarterly_demand': bool,
            'monthly_demand': bool,
            'weekly_demand': bool,
            'quarterly_supply': bool,
            'monthly_supply': bool,
            'weekly_supply': bool,
            'strongest_zone_score': int,
            'zone_details': dict,  # Full JSON for UI
        }
    """
    clean_symbol = symbol.replace('.NS', '').replace('.BO', '').strip().upper()
    logger.info("Scanning zones for %s", clean_symbol)

    # Fetch daily candle data (730 days for quarterly context)
    candles = _fetch_candles(clean_symbol, fyers_svc, days=730)
    if not candles:
        logger.warning("No candle data for %s, skipping", clean_symbol)
        return None

    df = candles_to_dataframe(candles)
    if df.empty:
        return None

    # Get current price
    current_price = float(df['close'].iloc[-1])

    # Average volume for scoring
    avg_volume = float(df['volume'].mean()) if 'volume' in df.columns else 0

    # Resample to different timeframes
    df_weekly = resample_to_timeframe(df, 'weekly')
    df_monthly = resample_to_timeframe(df, 'monthly')
    df_quarterly = resample_to_timeframe(df, 'quarterly')

    # Find zones for each timeframe
    result = {
        'demand_zones': {},
        'supply_zones': {},
    }

    # Macro timeframes
    for tf_name, tf_df in [('quarterly', df_quarterly), ('monthly', df_monthly), ('weekly', df_weekly), ('daily', df)]:
        d_zones = find_demand_zones(tf_df)
        s_zones = find_supply_zones(tf_df)

        for z in d_zones:
            z['strength_score'] = score_zone_strength(z, avg_volume)
            z['timeframe'] = tf_name
        for z in s_zones:
            z['strength_score'] = score_zone_strength(z, avg_volume)
            z['timeframe'] = tf_name

        result['demand_zones'][tf_name] = d_zones
        result['supply_zones'][tf_name] = s_zones
        
    # Intraday timeframes (75m, 125m)
    intraday_candles = _fetch_intraday_candles(clean_symbol, fyers_svc, days=60)
    if intraday_candles:
        idf = candles_to_dataframe(intraday_candles)
        if not idf.empty:
            df_125m = resample_to_timeframe(idf, '125min')
            df_75m = resample_to_timeframe(idf, '75min')
            
            for tf_name, tf_df in [('125min', df_125m), ('75min', df_75m)]:
                d_zones = find_demand_zones(tf_df)
                s_zones = find_supply_zones(tf_df)
                
                # average volume of 5min candles isn't directly comparable, but let's use it
                iavg_volume = float(tf_df['volume'].mean()) if 'volume' in tf_df.columns else 0
                for z in d_zones:
                    z['strength_score'] = score_zone_strength(z, iavg_volume)
                    z['timeframe'] = tf_name
                for z in s_zones:
                    z['strength_score'] = score_zone_strength(z, iavg_volume)
                    z['timeframe'] = tf_name

                result['demand_zones'][tf_name] = d_zones
                result['supply_zones'][tf_name] = s_zones

    # Calculate overlap counts
    demand_overlap = 0
    supply_overlap = 0

    q_demand = False
    m_demand = False
    w_demand = False
    d_demand = False
    min125_demand = False
    min75_demand = False
    
    q_supply = False
    m_supply = False
    w_supply = False
    d_supply = False
    min125_supply = False
    min75_supply = False

    for tf in ['quarterly', 'monthly', 'weekly', 'daily', '125min', '75min']:
        for z in result['demand_zones'].get(tf, []):
            if is_price_in_demand_zone(current_price, z):
                demand_overlap += 1
                if tf == 'quarterly':
                    q_demand = True
                elif tf == 'monthly':
                    m_demand = True
                elif tf == 'weekly':
                    w_demand = True
                elif tf == 'daily':
                    d_demand = True
                elif tf == '125min':
                    min125_demand = True
                elif tf == '75min':
                    min75_demand = True
                break  # Count each timeframe once

        for z in result['supply_zones'].get(tf, []):
            if is_price_in_supply_zone(current_price, z):
                supply_overlap += 1
                if tf == 'quarterly':
                    q_supply = True
                elif tf == 'monthly':
                    m_supply = True
                elif tf == 'weekly':
                    w_supply = True
                elif tf == 'daily':
                    d_supply = True
                elif tf == '125min':
                    min125_supply = True
                elif tf == '75min':
                    min75_supply = True
                break

    # Strongest zone score
    all_zone_scores = []
    for tf_zones in result['demand_zones'].values():
        all_zone_scores.extend(z.get('strength_score', 0) for z in tf_zones)
    for tf_zones in result['supply_zones'].values():
        all_zone_scores.extend(z.get('strength_score', 0) for z in tf_zones)
    strongest_score = max(all_zone_scores) if all_zone_scores else 0

    # Get stock info
    sector = get_sector_for_symbol(clean_symbol) or ''
    name = clean_symbol

    # Try to get name and sector from yfinance if not in map
    if not sector:
        sector = _get_sector_yfinance(clean_symbol)

    return {
        'symbol': clean_symbol,
        'name': name,
        'sector': sector,
        'current_price': round(current_price, 2),
        'demand_zones': result['demand_zones'],
        'supply_zones': result['supply_zones'],
        'demand_overlap_count': demand_overlap,
        'supply_overlap_count': supply_overlap,
        'quarterly_demand': q_demand,
        'monthly_demand': m_demand,
        'weekly_demand': w_demand,
        'daily_demand': d_demand,
        'min125_demand': min125_demand,
        'min75_demand': min75_demand,
        'quarterly_supply': q_supply,
        'monthly_supply': m_supply,
        'weekly_supply': w_supply,
        'daily_supply': d_supply,
        'min125_supply': min125_supply,
        'min75_supply': min75_supply,
        'strongest_zone_score': strongest_score,
        'zone_details': result,
    }


def _fetch_candles(symbol: str, fyers_svc=None, days: int = 730) -> list[dict]:
    """
    Fetch daily OHLCV candles. Tries Fyers first, falls back to yfinance.
    """
    cache_key = f"{symbol}_daily_{days}_{datetime.today().date()}"
    if cache_key in cache:
        return cache[cache_key]

    # Try Fyers first
    if fyers_svc and fyers_svc.is_active:
        print("Fyers data available, trying to fetch data from Fyers")
        try:
            fyers_symbol = f'NSE:{symbol}-EQ'
            date_to = datetime.today().strftime('%Y-%m-%d')
            date_from = (datetime.today() - timedelta(days=days)).strftime('%Y-%m-%d')

            candles = fyers_svc.get_historical_candles(
                symbol=fyers_symbol,
                resolution='D',
                date_from=date_from,
                date_to=date_to,
            )
            if candles:
                logger.info("Fetched %d candles from Fyers for %s", len(candles), symbol)
                cache.set(cache_key, candles, expire=6*3600)  # 6hr TTL
                return candles
        except Exception as e:
            print("Fyers fetch failed for", symbol, "error:", e)
            logger.warning("Fyers fetch failed for %s: %s, falling back to yfinance", symbol, e)

    # Fallback to yfinance
    try:
        print("Using yfinance to fetch data")
        import yfinance as yf
        yf_symbol = f"{symbol}.NS"

        # Use period parameter for simplicity
        period = '2y' if days > 365 else '1y'
        ticker = yf.Ticker(yf_symbol)
        hist = ticker.history(period=period, auto_adjust=True)

        if hist.empty:
            return []

        candles = []
        for idx, row in hist.iterrows():
            candles.append({
                'time': int(idx.timestamp()),
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'volume': int(row['Volume']),
            })
        logger.info("Fetched %d candles from yfinance for %s", len(candles), symbol)
        cache.set(cache_key, candles, expire=6*3600)  # 6hr TTL
        return candles
    except Exception as e:
        logger.warning("yfinance fetch also failed for %s: %s", symbol, e)
        return []

def _fetch_intraday_candles(symbol: str, fyers_svc=None, days: int = 60) -> list[dict]:
    """
    Fetch 5-minute OHLCV candles. Tries Fyers first, falls back to yfinance.
    Uses max 60 days to comply with yfinance limits.
    """
    cache_key = f"{symbol}_intraday_{days}_{datetime.today().date()}"
    if cache_key in cache:
        return cache[cache_key]

    if fyers_svc and fyers_svc.is_active:
        try:
            fyers_symbol = f'NSE:{symbol}-EQ'
            date_to = datetime.today().strftime('%Y-%m-%d')
            date_from = (datetime.today() - timedelta(days=days)).strftime('%Y-%m-%d')

            candles = fyers_svc.get_historical_candles(
                symbol=fyers_symbol,
                resolution='5',
                date_from=date_from,
                date_to=date_to,
            )
            if candles:
                cache.set(cache_key, candles, expire=6*3600)  # 6hr TTL
                return candles
        except Exception as e:
            logger.warning("Fyers intraday fetch failed for %s: %s", symbol, e)

    # Fallback to yfinance
    try:
        import yfinance as yf
        yf_symbol = f"{symbol}.NS"
        ticker = yf.Ticker(yf_symbol)
        hist = ticker.history(period=f'{days}d', interval='5m', auto_adjust=True)

        if hist.empty:
            return []

        candles = []
        for idx, row in hist.iterrows():
            candles.append({
                'time': int(idx.timestamp()),
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'volume': int(row['Volume']),
            })
        cache.set(cache_key, candles, expire=6*3600)  # 6hr TTL
        return candles
    except Exception as e:
        logger.warning("yfinance intraday fetch failed for %s: %s", symbol, e)
        return []


def _get_sector_yfinance(symbol: str) -> str:
    """Get sector info from yfinance (cached per session)."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(f"{symbol}.NS")
        info = ticker.info or {}
        return info.get('sector', 'Unknown')
    except Exception:
        return 'Unknown'


# ═════════════════════════════════════════════════════════════════════════════
# Sector Strength Analysis
# ═════════════════════════════════════════════════════════════════════════════

def analyze_sector_strength(scan_results: list[dict]) -> list[dict]:
    """
    Analyze sector strength from a list of scanned stock results.

    Groups stocks by sector, calculates:
    - % of stocks in demand zones (demand_strength)
    - % of stocks in supply zones (supply_strength)
    - Average overlap count
    - Top stocks per sector

    Returns sorted list of sector dicts (strongest demand first).
    """
    sector_data = {}

    for result in scan_results:
        if not result:
            continue
        sector = result.get('sector', 'Unknown')
        if sector not in sector_data:
            sector_data[sector] = {
                'sector': sector,
                'total_stocks': 0,
                'in_demand': 0,
                'in_supply': 0,
                'total_demand_overlap': 0,
                'total_supply_overlap': 0,
                'stocks': [],
            }

        sd = sector_data[sector]
        sd['total_stocks'] += 1
        if result['demand_overlap_count'] > 0:
            sd['in_demand'] += 1
        if result['supply_overlap_count'] > 0:
            sd['in_supply'] += 1
        sd['total_demand_overlap'] += result['demand_overlap_count']
        sd['total_supply_overlap'] += result['supply_overlap_count']
        sd['stocks'].append(result)

    # Calculate percentages and sort
    sectors = []
    for sector, data in sector_data.items():
        total = data['total_stocks']
        if total == 0:
            continue

        data['demand_strength_pct'] = round((data['in_demand'] / total) * 100, 1)
        data['supply_strength_pct'] = round((data['in_supply'] / total) * 100, 1)
        data['avg_demand_overlap'] = round(data['total_demand_overlap'] / total, 2)
        data['avg_supply_overlap'] = round(data['total_supply_overlap'] / total, 2)

        # Pick top stocks by overlap count and strength
        data['top_stocks'] = pick_top_stocks_per_sector(data['stocks'], top_n=3)

        # Remove full stocks list from output (too large)
        data.pop('stocks', None)
        sectors.append(data)

    # Sort by demand strength descending
    sectors.sort(key=lambda s: s['demand_strength_pct'], reverse=True)
    return sectors


def pick_top_stocks_per_sector(stocks: list[dict], top_n: int = 3) -> list[dict]:
    """
    From a sector's stocks, pick the top N by:
    1. Demand overlap count (primary sort)
    2. Strongest zone score (secondary sort)
    """
    scored = []
    for s in stocks:
        composite_score = (
            s.get('demand_overlap_count', 0) * 100 +
            s.get('strongest_zone_score', 0)
        )
        scored.append((composite_score, s))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [
        {
            'symbol': s['symbol'],
            'current_price': s['current_price'],
            'demand_overlap_count': s['demand_overlap_count'],
            'supply_overlap_count': s['supply_overlap_count'],
            'strongest_zone_score': s['strongest_zone_score'],
            'quarterly_demand': s['quarterly_demand'],
            'monthly_demand': s['monthly_demand'],
            'weekly_demand': s['weekly_demand'],
        }
        for _, s in scored[:top_n]
    ]


# ═════════════════════════════════════════════════════════════════════════════
# Batch Scanner
# ═════════════════════════════════════════════════════════════════════════════

def batch_scan(symbols: list[str], fyers_svc=None, progress_callback=None) -> dict:
    """
    Scan multiple stocks and return full results with sector analysis.

    Args:
        symbols: List of NSE symbols (e.g. ['RELIANCE', 'TCS', ...])
        fyers_svc: Optional FyersService instance
        progress_callback: Optional callable(current, total, symbol) for progress updates

    Returns:
        {
            'scan_results': [list of per-stock results],
            'sector_strength': [list of sector analysis dicts],
            'total_scanned': int,
            'stocks_in_demand': int,
            'stocks_in_supply': int,
            'scan_time_seconds': float,
        }
    """
    import time
    start = time.time()

    results = []
    errors = []
    total = len(symbols)

    for idx, symbol in enumerate(symbols):
        try:
            if progress_callback:
                progress_callback(idx + 1, total, symbol)

            result = scan_stock_zones(symbol, fyers_svc)
            if result:
                results.append(result)
        except Exception as e:
            logger.error("Error scanning %s: %s", symbol, e)
            errors.append({'symbol': symbol, 'error': str(e)})

    # Analyze sectors
    sector_strength = analyze_sector_strength(results)

    elapsed = time.time() - start

    return {
        'scan_results': results,
        'sector_strength': sector_strength,
        'total_scanned': len(results),
        'total_attempted': total,
        'stocks_in_demand': sum(1 for r in results if r['demand_overlap_count'] > 0),
        'stocks_in_supply': sum(1 for r in results if r['supply_overlap_count'] > 0),
        'errors': errors,
        'scan_time_seconds': round(elapsed, 2),
    }
