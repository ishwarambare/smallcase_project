"""
Ultimate GTF Strategy Backtester (Python Script)
================================================
Intraday Multi-Asset GTF Strategy Backtesting Script for Top High-Liquidity NSE Stocks.

Outputs:
  - Terminal Consolidated Multi-Asset Backtest Report
  - Excel file: Backtest_Report_YYYYMMDD_HHMMSS.xlsx (Summary_Report & Detailed_Trades)
"""

import pandas as pd
import numpy as np
import math
import os
import sys
from datetime import datetime, time
from enum import Enum
import pytz
import logging

logger = logging.getLogger(__name__)

# =========================================================================
# ⚙️ SECTION 1: GLOBAL CONFIGURATION AND STATE
# =========================================================================

from datetime import datetime, time, timedelta
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

load_dotenv(os.path.join(os.getcwd(), '.env'))

STOCK_LIST_FILE = "stock_list.txt"
REPORT_FILE = f"Backtest_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
# END_DATE = datetime.now().strftime('%Y-%m-%d')
# START_DATE = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

END_DATE = "2026-06-30"
START_DATE = "2026-06-01"


CLIENT_ID = os.getenv('FYERS_CLIENT_ID', 'BTYO2GHCBU-200')
TOKEN_FILE = "fyers_access_token.txt"

# Timezones
utc_tz = pytz.utc
ist_tz = pytz.timezone('Asia/Kolkata')
EOD_CUTOFF_TIME_IST = time(14, 45)

# Timeframe Settings
HTF_INTERVAL = "60m"
LTF_INTERVAL = "15m"

IS_INTRADAY_STRATEGY = LTF_INTERVAL in ["5m", "15m", "30m", "60m"]

# Strategy Constants (GTF High Probability Config)
INITIAL_CAPITAL = 1000000.0 
RISK_PER_TRADE = 1000.0    # 1% Risk
MAX_BASE_CANDLES = 3 
BASE_CANDLE_RATIO = 0.33 
EMA_TP_PERIOD = 200 

MIN_TRADE_SCORE = 4.5 
MIN_WICK_TO_RANGE_RATIO = 0.4 
MAX_R_MULTIPLE = 2.0

ATR_LOOKBACK = 14 
MAX_ZONE_WIDTH_ATR_MULTIPLE = 1.5 

ALL_SUMMARY_RESULTS = []
ALL_COMPLETED_TRADES = []


# =========================================================================
# 🏗️ SECTION 2: CUSTOM CLASSES
# =========================================================================

class GTFZone:
    def __init__(self, index, zone_type, proximal, distal, is_demand, base_count, entry_price=0, sl_price=0):
        self.index = index
        self.type = zone_type
        self.proximal = float(proximal)
        self.distal = float(distal)
        self.is_demand = is_demand
        self.base_count = base_count 
        self.hit_count = 0 
        self.score = 0.0
        self.consumed = False
        self.entry = float(entry_price)
        self.sl = float(sl_price) 


class Trade:
    def __init__(self, index, entry_date, trade_type, entry_price, sl_price, tp_price, qty, score):
        self.index = index
        self.entry_date = entry_date
        self.type = trade_type
        self.entry = float(entry_price)
        self.sl = float(sl_price)
        self.tp = float(tp_price)
        self.qty = int(qty)
        self.score = float(score)
        self.status = 'OPEN'
        self.pnl = 0.0 


class PendingTrade:
    def __init__(self, zone, current_date, entry_price, sl_price, tp_price, qty, score):
        self.zone = zone
        self.entry_date = current_date
        self.type = 'BUY' if zone.is_demand else 'SELL'
        self.entry = float(entry_price)
        self.sl = float(sl_price)
        self.tp = float(tp_price)
        self.qty = int(qty)
        self.score = float(score)


class Location(Enum):
    VERY_HIGH = 1
    HIGH = 2
    EQUILIBRIUM = 3
    LOW = 4
    VERY_LOW = 5


# =========================================================================
# 💡 SECTION 3: HELPER FUNCTIONS (FYERS API + YFINANCE/SYNTHETIC FALLBACK)
# =========================================================================

def get_fyers_data(fyers_model, ticker_symbol, interval, start_date, end_date):
    """
    Fetches historical data from Fyers API or secondary fallback providers.
    """
    if fyers_model:
        try:
            fyers_symbol = f"NSE:{ticker_symbol}-EQ" if not ticker_symbol.startswith("NSE:") else ticker_symbol
            interval_mapper = {"5m": "5", "15m": "15", "30m": "30", "60m": "60", "1d": "D", "1mo": "M"}
            
            if interval in interval_mapper:
                fyers_resolution = interval_mapper[interval]
                data = {
                    "symbol": fyers_symbol,
                    "resolution": fyers_resolution,
                    "date_format": "1",
                    "range_from": start_date,
                    "range_to": end_date,
                    "cont_flag": "1"
                }
                response = fyers_model.history(data=data)
                if response.get("code") == 200 and response.get("candles"):
                    candles = response["candles"]
                    df = pd.DataFrame(candles)
                    df.rename(columns={0: 'Date', 1: 'Open', 2: 'High', 3: 'Low', 4: 'Close', 5: 'Volume'}, inplace=True)
                    df['Date'] = pd.to_datetime(df['Date'], unit='s', utc=True)
                    df.set_index('Date', inplace=True)
                    if not df.empty:
                        return df
        except Exception as e:
            pass

    # Fallback to yfinance or engine generator
    try:
        from demand_supply.backtest_engine import fetch_historical_candles
        return fetch_historical_candles(ticker_symbol, interval, start_date, end_date)
    except Exception as e:
        print(f"Fallback candle fetch error for {ticker_symbol}: {e}")
        return pd.DataFrame()


def is_base(candle):
    try:
        body = candle['Body'].item()
        rng = candle['Range'].item()
    except AttributeError:
        body = candle['Body']
        rng = candle['Range']

    if rng == 0: return False
    return (body / rng) < BASE_CANDLE_RATIO and body > 0 


def check_zone_quality(current_atr, proximal, distal):
    zone_width = abs(proximal - distal)
    if MAX_ZONE_WIDTH_ATR_MULTIPLE == 999: return True 
    max_allowed_width = MAX_ZONE_WIDTH_ATR_MULTIPLE * current_atr
    return zone_width <= max_allowed_width


def get_base_extremes(data, current_index, base_count):
    base_start = current_index - base_count
    base_range_data = data.iloc[base_start:current_index]

    dem_prox = base_range_data['Close'].iloc[-1].item() 
    dem_dist = base_range_data['Low'].min().item() 

    sup_prox = base_range_data['Close'].iloc[-1].item() 
    sup_dist = base_range_data['High'].max().item() 

    return (dem_prox, dem_dist), (sup_prox, sup_dist)


def get_htf_zones(htf_data):
    htf_zones = []
    
    htf_data['Body'] = abs(htf_data['Close'] - htf_data['Open'])
    htf_data['Range'] = htf_data['High'] - htf_data['Low']
    
    body_max = np.maximum(htf_data['Open'], htf_data['Close'])
    body_min = np.minimum(htf_data['Open'], htf_data['Close'])
    htf_data['Upper_Wick'] = htf_data['High'] - body_max
    htf_data['Lower_Wick'] = body_min - htf_data['Low']
    
    htf_data['ATR'] = htf_data['Range'].rolling(2).mean() 
    start_bar = MAX_BASE_CANDLES + 2
    
    for i in range(start_bar, len(htf_data)):
        current_bar = htf_data.iloc[i]
        current_close = current_bar['Close'].item()
        current_open = current_bar['Open'].item()
        current_body = current_bar['Body'].item()
        current_range = current_bar['Range'].item()
        
        if current_range == 0: continue

        is_current_rally = (current_close > current_open) and (current_body / current_range) > BASE_CANDLE_RATIO
        is_current_drop = (current_close < current_open) and (current_body / current_range) > BASE_CANDLE_RATIO
        
        for base_count in range(1, MAX_BASE_CANDLES + 1):
            if i - base_count - 1 < 0: continue
            
            is_valid_base = all(is_base(htf_data.iloc[j]) for j in range(i - base_count, i))
            
            if is_valid_base:
                entry_move = htf_data.iloc[i - base_count - 1]
                entry_move_body = entry_move['Body'].item()
                entry_move_range = entry_move['Range'].item()
                if entry_move_range == 0: continue

                is_entry_rally = (entry_move['Close'].item() > entry_move['Open'].item()) and (entry_move_body / entry_move_range) > BASE_CANDLE_RATIO
                is_entry_drop = (entry_move['Close'].item() < entry_move['Open'].item()) and (entry_move_body / entry_move_range) > BASE_CANDLE_RATIO
                
                (dem_prox, dem_dist), (sup_prox, sup_dist) = get_base_extremes(htf_data, i, base_count)
                
                if is_current_rally and (is_entry_drop or is_entry_rally):
                    zone_type = "DBR" if is_entry_drop else "RBR"
                    new_zone = GTFZone(i, zone_type, dem_prox, dem_dist, True, base_count, entry_price=dem_prox, sl_price=dem_dist)
                    htf_zones.append(new_zone)
                
                elif is_current_drop and (is_entry_rally or is_entry_drop):
                    zone_type = "RBD" if is_entry_rally else "DBD"
                    new_zone = GTFZone(i, zone_type, sup_prox, sup_dist, False, base_count, entry_price=sup_prox, sl_price=sup_dist)
                    htf_zones.append(new_zone)

    return [z for z in htf_zones if z.hit_count <= 2]


def check_htf_confluence(current_price, fresh_htf_zones, is_demand_signal):
    for zone in fresh_htf_zones:
        if is_demand_signal == zone.is_demand:
            if zone.is_demand:
                if zone.distal <= current_price <= zone.proximal:
                    return zone
            else:
                if zone.proximal <= current_price <= zone.distal:
                    return zone
    return None


def check_trade_score(data, zone, current_index):
    score = 0.0

    if zone.hit_count == 0: score += 3.0 
    elif zone.hit_count == 1: score += 1.5 
    
    if 1 <= zone.base_count <= 3: score += 2.0 
    
    legout_index = zone.index
    if 0 < legout_index < len(data):
        legout = data.iloc[legout_index]
        prev_close = data.iloc[legout_index - 1]['Close'].item()
        is_gap_open = abs(legout['Open'].item() - prev_close) > legout['ATR'].item()
        
        is_two_exciting_candles = False
        if legout_index + 1 < len(data):
            legout_body = legout['Body'].item()
            legout_range = legout['Range'].item()
            next_body = data.iloc[legout_index + 1]['Body'].item()
            next_range = data.iloc[legout_index + 1]['Range'].item()
            
            if legout_range > 0 and next_range > 0:
                if (legout_body / legout_range) > 0.5 and (next_body / next_range) > 0.5:
                     is_two_exciting_candles = True

        if is_gap_open: score += 2.0 
        elif is_two_exciting_candles: score += 2.0 
        else: score += 1.0 

    try:
        current_ema_20 = data['EMA_20'].iloc[current_index].item()
        current_ema_50 = data['EMA_50'].iloc[current_index].item()

        if (zone.distal < current_ema_20 < zone.proximal) or (zone.distal < current_ema_50 < zone.proximal):
            score += 1.0
    except (ValueError, IndexError, KeyError):
        pass 

    return score


def check_wick_rejection(current_bar, zone_type):
    rng = current_bar['Range'].item()
    if rng == 0: return True 

    if zone_type in ["DBR", "RBR"]: 
        lower_wick = current_bar['Lower_Wick'].item()
        return (lower_wick / rng) >= MIN_WICK_TO_RANGE_RATIO
    elif zone_type in ["RBD", "DBD"]: 
        upper_wick = current_bar['Upper_Wick'].item()
        return (upper_wick / rng) >= MIN_WICK_TO_RANGE_RATIO

    return False


def check_location_filter(current_price, fresh_htf_zones):
    fresh_demands = [z for z in fresh_htf_zones if z.is_demand and z.hit_count == 0]
    fresh_supplies = [z for z in fresh_htf_zones if not z.is_demand and z.hit_count == 0]

    if not fresh_demands or not fresh_supplies: return Location.EQUILIBRIUM 

    nearest_sz_prox = max([z.proximal for z in fresh_supplies])
    nearest_dz_prox = min([z.proximal for z in fresh_demands])

    if nearest_sz_prox <= nearest_dz_prox: return Location.EQUILIBRIUM
    
    curve_range = nearest_sz_prox - nearest_dz_prox
    one_fifth = curve_range / 5
    
    if current_price > (nearest_sz_prox - one_fifth): return Location.VERY_HIGH
    elif current_price > (nearest_sz_prox - 2 * one_fifth): return Location.HIGH
    elif current_price > (nearest_dz_prox + 2 * one_fifth): return Location.EQUILIBRIUM
    elif current_price > (nearest_dz_prox + one_fifth): return Location.LOW
    else: return Location.VERY_LOW


def get_dynamic_tp(entry_price, sl_price, data, current_index, zone_type):
    risk_distance = abs(entry_price - sl_price)
    r_multiple = MAX_R_MULTIPLE 

    if zone_type in ["DBR", "RBR"]: tp_target = entry_price + (risk_distance * r_multiple)
    else: tp_target = entry_price - (risk_distance * r_multiple)
    
    return tp_target


# =========================================================================
# 🚀 SECTION 4: MAIN BACKTEST LOGIC
# =========================================================================

def init_fyers():
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.getcwd(), '.env'))

    access_token = os.getenv('FYERS_ACCESS_TOKEN')
    if not access_token and os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'r') as f:
                access_token = f.read().strip()
        except Exception:
            pass

    if not access_token:
        print("--- Info: Fyers Access Token not found. Using secondary market candle fallback ---")
        return None

    # Sync token file for convenience
    try:
        with open(TOKEN_FILE, 'w') as f:
            f.write(access_token)
    except Exception:
        pass

    if ':' in access_token:
        client_id = access_token.split(':')[0]
    else:
        client_id = os.getenv('FYERS_CLIENT_ID') or os.getenv('FYERS_APP_ID') or CLIENT_ID

    try:
        from fyers_apiv3 import fyersModel
        fyers_instance = fyersModel.FyersModel(client_id=client_id, token=access_token, log_path=os.getcwd())
        profile = fyers_instance.get_profile()
        if profile.get("code") == 200 and "data" in profile:
            user_name = profile["data"].get("name", "Fyers User")
            print(f"--- Fyers API Login Successful! Welcome, {user_name} (Client: {client_id}) ---")
            return fyers_instance
        else:
            print(f"--- Fyers API Warning: {profile.get('message', 'Auth error')}. Using fallback ---")
            return None
    except Exception as e:
        print(f"--- Fyers API Init Error: {e}. Using fallback ---")
        return None



def run_backtest(fyers_model, ticker, start_date, end_date):
    current_capital = INITIAL_CAPITAL
    trade_id_counter = 0
    all_zones = []
    open_trades = []
    closed_trades = []
    pending_trades = [] 

    print(f"\n--- Starting GTF Backtest Execution for {ticker} (HTF: {HTF_INTERVAL}, LTF: {LTF_INTERVAL}) ---")

    # Include 60-day lookback before start_date so HTF zones and EMA indicators are pre-calculated
    try:
        start_dt = pd.to_datetime(start_date).date()
        fetch_start_date = (pd.to_datetime(start_date) - timedelta(days=60)).strftime('%Y-%m-%d')
    except Exception:
        fetch_start_date = start_date
        start_dt = None

    ltf_data = get_fyers_data(fyers_model, ticker, LTF_INTERVAL, fetch_start_date, end_date)
    htf_data = get_fyers_data(fyers_model, ticker, HTF_INTERVAL, fetch_start_date, end_date)

    if ltf_data.empty or htf_data.empty:
        print(f"Error: Could not fetch enough data for {ticker}.")
        return None

    if start_dt is None:
        start_dt = ltf_data.index[0].date()

    
    global MAX_ZONE_WIDTH_ATR_MULTIPLE
    temp_max_zone = MAX_ZONE_WIDTH_ATR_MULTIPLE
    MAX_ZONE_WIDTH_ATR_MULTIPLE = 999 
    fresh_htf_zones = get_htf_zones(htf_data)
    MAX_ZONE_WIDTH_ATR_MULTIPLE = temp_max_zone
    
    print(f"Found {len(fresh_htf_zones)} reusable {HTF_INTERVAL} zones for confluence.")

    data = ltf_data.copy()
    data['Body'] = abs(data['Close'] - data['Open'])
    data['Range'] = data['High'] - data['Low']
    body_max = np.maximum(data['Open'], data['Close'])
    body_min = np.minimum(data['Open'], data['Close'])
    data['Upper_Wick'] = data['High'] - body_max
    data['Lower_Wick'] = body_min - data['Low'] 
    
    data['ATR'] = data['Range'].rolling(ATR_LOOKBACK).mean() 
    data['EMA_20'] = data['Close'].ewm(span=20, adjust=False).mean()
    data['EMA_50'] = data['Close'].ewm(span=50, adjust=False).mean()
    data['EMA_200'] = data['Close'].ewm(span=EMA_TP_PERIOD, adjust=False).mean() 

    start_bar = max(MAX_BASE_CANDLES + 2, ATR_LOOKBACK + 2)
    if start_bar >= len(data):
        print(f"Error: Not enough LTF data bars available for {ticker}.")
        return None

    for i in range(start_bar, len(data)):
        current_date = data.index[i]
        current_bar = data.iloc[i]
        
        if pd.isna(data['ATR'].iloc[i]):
            continue
            
        bar_atr = data['ATR'].iloc[i].item()

        try:
            if current_date.date() < start_dt:
                continue
        except AttributeError:
            pass

        current_close = current_bar['Close'].item()
        current_open = current_bar['Open'].item()
        current_body = current_bar['Body'].item()
        current_range = current_bar['Range'].item()
        
        if current_range > 0:
            is_current_rally = (current_close > current_open) and (current_body / current_range) > BASE_CANDLE_RATIO
            is_current_drop = (current_close < current_open) and (current_body / current_range) > BASE_CANDLE_RATIO
            
            for base_count in range(1, MAX_BASE_CANDLES + 1):
                if i - base_count - 1 < 0: continue
                
                is_valid_base = all(is_base(data.iloc[j]) for j in range(i - base_count, i))
                
                if is_valid_base:
                    entry_move = data.iloc[i - base_count - 1]
                    entry_move_body = entry_move['Body'].item()
                    entry_move_range = entry_move['Range'].item()
                    if entry_move_range == 0: continue

                    is_entry_rally = (entry_move['Close'].item() > entry_move['Open'].item()) and (entry_move_body / entry_move_range) > BASE_CANDLE_RATIO
                    is_entry_drop = (entry_move['Close'].item() < entry_move['Open'].item()) and (entry_move_body / entry_move_range) > BASE_CANDLE_RATIO
                    
                    (dem_prox, dem_dist), (sup_prox, sup_dist) = get_base_extremes(data, i, base_count)
                    
                    if is_current_rally and (is_entry_drop or is_entry_rally):
                        if check_zone_quality(bar_atr, dem_prox, dem_dist):
                            zone_type = "DBR" if is_entry_drop else "RBR"
                            new_zone = GTFZone(i, zone_type, dem_prox, dem_dist, True, base_count)
                            all_zones.append(new_zone)
                    
                    elif is_current_drop and (is_entry_rally or is_entry_drop):
                        if check_zone_quality(bar_atr, sup_prox, sup_dist):
                            zone_type = "RBD" if is_entry_rally else "DBD"
                            new_zone = GTFZone(i, zone_type, sup_prox, sup_dist, False, base_count)
                            all_zones.append(new_zone)
        
        trades_to_activate = []
        pending_to_invalidate = []
        
        for p_trade in pending_trades:
            confirmed = False
            if p_trade.type == 'BUY':
                if current_close > p_trade.entry: confirmed = True
            elif p_trade.type == 'SELL':
                if current_close < p_trade.entry: confirmed = True
                    
            if confirmed:
                trades_to_activate.append(p_trade)
            else:
                if (p_trade.type == 'BUY' and current_bar['Low'].item() <= p_trade.sl) or \
                   (p_trade.type == 'SELL' and current_bar['High'].item() >= p_trade.sl):
                    pending_to_invalidate.append(p_trade)
                    p_trade.zone.consumed = True 
                    
        for p_trade in trades_to_activate:
            trade_id_counter += 1
            new_trade = Trade(trade_id_counter, p_trade.entry_date, p_trade.type, p_trade.entry, p_trade.sl, p_trade.tp, p_trade.qty, p_trade.score)
            open_trades.append(new_trade)
            pending_trades.remove(p_trade)
            p_trade.zone.consumed = True 

        for p_trade in pending_to_invalidate:
            if p_trade in pending_trades:
                pending_trades.remove(p_trade)

        fresh_zones = [z for z in all_zones if not z.consumed and z.index < i]
        location = check_location_filter(current_close, fresh_htf_zones)

        for zone in fresh_zones:
            proximal_hit = False
            current_low_val = current_bar['Low'].item()
            current_high_val = current_bar['High'].item()
            entry_price = zone.proximal 

            if zone.is_demand and current_low_val <= entry_price:
                proximal_hit = True
            elif not zone.is_demand and current_high_val >= entry_price:
                proximal_hit = True

            if proximal_hit:
                zone.hit_count += 1
                htf_confluence_zone = check_htf_confluence(entry_price, fresh_htf_zones, zone.is_demand)
                is_htf_aligned = htf_confluence_zone is not None
                zone.score = check_trade_score(data, zone, i)

                is_tradable_score = zone.score >= MIN_TRADE_SCORE 
                is_tradable_location = not (zone.is_demand and location in [Location.VERY_HIGH, Location.HIGH] or 
                                            not zone.is_demand and location in [Location.VERY_LOW, Location.LOW])
                is_tradable_rejection = check_wick_rejection(current_bar, zone.type)
                
                if not all([is_htf_aligned, is_tradable_score, is_tradable_location, is_tradable_rejection]):
                    zone.consumed = True 
                    continue
                    
                try:
                    current_time_ist = current_date.astimezone(ist_tz).time()
                    if IS_INTRADAY_STRATEGY and current_time_ist >= EOD_CUTOFF_TIME_IST:
                        zone.consumed = True 
                        continue
                except Exception:
                    pass

                sl_price = zone.distal
                risk_distance = abs(entry_price - sl_price)
                if risk_distance <= 0.01: 
                    zone.consumed = True
                    continue

                qty = math.floor(RISK_PER_TRADE / risk_distance)
                if qty <= 0:
                    zone.consumed = True
                    continue
                    
                trade_value = qty * entry_price
                if IS_INTRADAY_STRATEGY and trade_value > (current_capital * 5.0):
                    zone.consumed = True 
                    continue
                elif (not IS_INTRADAY_STRATEGY) and trade_value > current_capital:
                    zone.consumed = True
                    continue
                    
                tp_price = get_dynamic_tp(entry_price, sl_price, data, i, zone.type)

                if zone.score >= 7.0:
                    trade_id_counter += 1
                    new_trade = Trade(trade_id_counter, current_date, 'BUY' if zone.is_demand else 'SELL', entry_price, sl_price, tp_price, qty, zone.score)
                    open_trades.append(new_trade)
                    zone.consumed = True 
                else:
                    p_trade = PendingTrade(zone, current_date, entry_price, sl_price, tp_price, qty, zone.score)
                    pending_trades.append(p_trade)

                if is_htf_aligned and htf_confluence_zone is not None:
                    htf_confluence_zone.hit_count += 1

        trades_to_close = []
        for trade in open_trades:
            high = data.iloc[i]['High'].item()
            low = data.iloc[i]['Low'].item()
            close_status = None
            pnl = 0.0
            exit_price = 0.0
            
            try:
                current_time_ist = current_date.astimezone(ist_tz).time()
            except Exception:
                current_time_ist = time(12, 0)

            try:
                is_diff_day = (trade.entry_date.date() != current_date.date())
            except Exception:
                is_diff_day = False

            if IS_INTRADAY_STRATEGY and trade.type == 'SELL' and is_diff_day:
                close_status = 'OVERNIGHT_SHORT_FAIL'
                exit_price = current_bar['Open'].item()
                pnl = trade.qty * (trade.entry - exit_price)

            elif (trade.type == 'BUY' and low <= trade.sl) or \
                 (trade.type == 'SELL' and high >= trade.sl):
                close_status = 'SL'
                pnl = -RISK_PER_TRADE 
                exit_price = trade.sl
            
            elif (trade.type == 'BUY' and high >= trade.tp) or \
                 (trade.type == 'SELL' and low <= trade.tp):
                close_status = 'TP'
                pnl = trade.qty * abs(trade.tp - trade.entry)
                exit_price = trade.tp
            
            elif IS_INTRADAY_STRATEGY and trade.type == 'SELL' and not is_diff_day:
                if current_time_ist >= EOD_CUTOFF_TIME_IST:
                    close_status = 'FORCED_EOD_CLOSE'
                    exit_price = current_bar['Close'].item()
                    pnl = trade.qty * (trade.entry - exit_price)

            if close_status:
                trade.status = close_status
                pnl_realized = float(pnl)
                trade.pnl = pnl_realized 
                current_capital += pnl_realized
                trades_to_close.append(trade)
                closed_trades.append(trade)
                
                r_achieved = pnl_realized / RISK_PER_TRADE if RISK_PER_TRADE > 0 else 0.0

                try:
                    entry_time_ist = trade.entry_date.astimezone(ist_tz).strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    entry_time_ist = str(trade.entry_date)

                try:
                    exit_time_ist = current_date.astimezone(ist_tz).strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    exit_time_ist = str(current_date)

                ALL_COMPLETED_TRADES.append({
                    'Ticker': ticker, 'ID': trade.index, 'Zone_Score': round(trade.score, 1),
                    'Entry Date': entry_time_ist, 
                    'Exit Date': exit_time_ist,
                    'Type': trade.type, 'Entry Price': round(trade.entry, 2), 'Exit Price': round(exit_price, 2),
                    'Stop Loss': round(trade.sl, 2), 'Take Profit': round(trade.tp, 2), 'R_Achieved': round(r_achieved, 2),
                    'Qty': trade.qty, 'Status': close_status, 'PnL': round(pnl_realized, 2), 'Capital After': round(current_capital, 2)
                })

        for trade in trades_to_close:
            open_trades.remove(trade)

    total_trades = len(closed_trades)
    winning_trades = [t for t in closed_trades if t.status == 'TP' or (t.status == 'FORCED_EOD_CLOSE' and t.pnl > 0)]
    win_rate = (len(winning_trades) / total_trades) * 100 if total_trades else 0.0
    total_pnl = current_capital - INITIAL_CAPITAL
    
    print(f"\n--- Backtest Complete for {ticker} ---")
    print(f"Total P&L: Rs. {total_pnl:.2f} | Win Rate: {win_rate:.2f}% | Total Trades: {total_trades}")

    
    return {
        'Ticker': ticker, 'Total Trades': total_trades, 'Win Rate': win_rate, 
        'Total P&L': total_pnl, 'Final Capital': current_capital, 'Status': 'COMPLETED'
    }


# =========================================================================
# 🏁 SECTION 5: SCRIPT EXECUTION 
# =========================================================================

def execute_multi_backtest():
    fyers_model = init_fyers()

    try:
        with open(STOCK_LIST_FILE, 'r') as f:
            tickers = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except FileNotFoundError:
        print(f"ERROR: {STOCK_LIST_FILE} not found. Creating default 31 stocks list...")
        tickers = [
            "RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS", "ITC", "LT", "AXISBANK", "SBIN", "BHARTIARTL",
            "TATASTEEL", "BAJFINANCE", "BAJAJ-AUTO", "INDUSINDBK", "HINDUNILVR", "KOTAKBANK", "TATAMOTORS", "MARUTI",
            "SUNPHARMA", "TITAN", "ULTRACEMCO", "NTPC", "POWERGRID", "COALINDIA", "HCLTECH", "WIPRO",
            "TECHM", "ASIANPAINT", "ADANIENT", "ADANIPORTS", "HDFCLIFE"
        ]
        with open(STOCK_LIST_FILE, "w") as f:
            f.write("\n".join(tickers))


    if not tickers:
        print(f"ERROR: {STOCK_LIST_FILE} is empty.")
        return

    print(f"\n--- Starting Multi-Asset Backtest on {len(tickers)} Top High-Liquidity Symbols (HTF: {HTF_INTERVAL}, LTF: {LTF_INTERVAL}) ---")
    
    for ticker in tickers:
        result = run_backtest(fyers_model, ticker, START_DATE, END_DATE) 
        if result:
            ALL_SUMMARY_RESULTS.append(result)

    if not ALL_SUMMARY_RESULTS:
        print("\nNo completed backtests to report.")
        return

    summary_df = pd.DataFrame(ALL_SUMMARY_RESULTS)
    summary_df = summary_df.sort_values(by='Total P&L', ascending=False).reset_index(drop=True)
    trades_df = pd.DataFrame(ALL_COMPLETED_TRADES)
    total_portfolio_pnl = summary_df['Total P&L'].sum()
    
    print("\n" + "="*80)
    print("CONSOLIDATED MULTI-ASSET BACKTEST REPORT")
    print(f"Total Portfolio P&L (Sum of all stocks): Rs. {total_portfolio_pnl:,.2f}")
    print("="*80)

    summary_formatted = summary_df.copy()
    summary_formatted['Total P&L'] = summary_formatted['Total P&L'].apply(lambda x: f"Rs. {x:,.2f}")
    summary_formatted['Win Rate'] = summary_formatted['Win Rate'].apply(lambda x: f"{x:.2f}%")

    if 'Final Capital' in summary_formatted.columns:
        summary_formatted = summary_formatted.drop(columns=['Final Capital'])
    
    print(summary_formatted.to_string(index=True))
    print("="*80)

    try:
        import openpyxl
        with pd.ExcelWriter(REPORT_FILE, engine='openpyxl') as writer:
            summary_df.to_excel(writer, sheet_name='Summary_Report', index=False)
            trades_df.to_excel(writer, sheet_name='Detailed_Trades', index=False)
        print(f"\n[SUCCESS] Detailed Excel Report Saved: {os.path.abspath(REPORT_FILE)}")

    except Exception as e:
        print(f"\nNote saving Excel: {e}. Please ensure 'openpyxl' is installed: pip install openpyxl")


if __name__ == '__main__':
    execute_multi_backtest()
