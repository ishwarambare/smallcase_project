"""
stocks/stock_analysis.py

Complete stock intelligence engine:
  - Fundamentals (Yahoo Finance)
  - Technical Indicators (RSI, SMA, MACD, Bollinger, Volume)
  - News Sentiment (Yahoo Finance news + keyword scoring)
  - Market Depth & Ownership (bid/ask, institutional/promoter %)
  - Government Policy Alignment (rule-based sector mapping)
  - Global Market Impact (S&P500, Crude, USD/INR, Gold)
  - Unified Buy / Hold / Avoid recommendation
"""

import math
import datetime
import logging
import yfinance as yf
import pandas as pd
from .utils import get_yfinance_ticker

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Government Policy Themes — sector → policy mapping
# ---------------------------------------------------------------------------
POLICY_THEMES = {
    "Digital India / AI": {
        "sectors": ["Technology", "Communication Services", "Telecom", "Fintech"],
        "keywords": ["digital", "ai", "cloud", "data center", "5g", "broadband",
                     "cybersecurity", "software", "it", "saas", "automation"],
        "description": "Aligned with India's Digital India & AI Mission",
    },
    "PLI Scheme": {
        "sectors": ["Industrials", "Consumer Cyclical", "Technology", "Healthcare",
                    "Basic Materials", "Energy"],
        "keywords": ["pli", "production linked", "manufacturing", "make in india",
                     "export", "domestic production", "semiconductor", "ev", "battery"],
        "description": "Eligible under Production Linked Incentive (PLI) Scheme",
    },
    "Atmanirbhar Bharat / Defence": {
        "sectors": ["Industrials", "Aerospace", "Defence", "Space"],
        "keywords": ["defence", "defense", "drdo", "hal", "ordnance", "navy",
                     "army", "aerospace", "atmanirbhar", "indigenous"],
        "description": "Aligns with Atmanirbhar Bharat & defence indigenisation",
    },
    "Infrastructure Push": {
        "sectors": ["Basic Materials", "Industrials", "Utilities", "Real Estate"],
        "keywords": ["infrastructure", "road", "highway", "port", "railway", "metro",
                     "cement", "steel", "power", "transmission", "construction"],
        "description": "Benefits from India's ₹11 lakh Cr infrastructure push",
    },
    "Green Energy / EV": {
        "sectors": ["Utilities", "Energy", "Consumer Cyclical", "Industrials"],
        "keywords": ["solar", "renewable", "wind", "ev", "electric vehicle",
                     "green hydrogen", "battery", "clean energy", "net zero"],
        "description": "Aligned with India's green energy & EV transition goals",
    },
    "Financial Inclusion / GIFT City": {
        "sectors": ["Financial Services", "Banking", "Insurance", "Capital Markets"],
        "keywords": ["nbfc", "microfinance", "insurance", "gift city", "fintech",
                     "upi", "jan dhan", "rrb", "credit", "rbi"],
        "description": "Benefits from financial inclusion & GIFT City policies",
    },
    "Healthcare / Pharma Mission": {
        "sectors": ["Healthcare", "Pharmaceuticals"],
        "keywords": ["pharma", "drug", "medicine", "hospital", "healthcare",
                     "vaccine", "biosimilar", "api", "generic", "ayushman"],
        "description": "Supported under India's Pharma Vision & Ayushman Bharat",
    },
}

# Global indicator metadata: (symbol, name, sector impact map)
GLOBAL_INDICATORS = {
    "^GSPC": {"name": "S&P 500 (US)", "icon": "🇺🇸",
               "bullish_sectors": ["Technology", "Financial Services"],
               "description": "Rising US markets attract FII inflows into India"},
    "CL=F":  {"name": "Crude Oil", "icon": "🛢️",
               "bearish_sectors": ["Airlines", "Automobile", "Consumer Cyclical", "Paints"],
               "bullish_sectors": ["Energy", "Oil & Gas"],
               "description": "Higher crude raises input costs for import-heavy sectors"},
    "INR=X": {"name": "USD/INR", "icon": "💱",
               "bearish_sectors": ["Technology", "Pharmaceuticals"],
               "bullish_sectors": ["Importers", "Consumer Cyclical"],
               "description": "Weaker rupee hurts importers but helps IT exporters"},
    "GC=F":  {"name": "Gold", "icon": "🥇",
               "description": "Rising gold signals risk-off mood; FII may reduce equity exposure"},
}

POSITIVE_NEWS_WORDS = {
    "partnership", "expansion", "profit", "record", "approved", "growth", "wins",
    "beat", "acquisition", "contract", "launch", "upgrade", "rally", "surge",
    "investment", "deal", "order", "revenue", "dividend", "buyback", "milestone",
    "outperform", "strong", "gain", "positive", "success", "breakthrough"
}

NEGATIVE_NEWS_WORDS = {
    "fraud", "penalty", "loss", "recall", "downgrade", "probe", "miss", "fine",
    "decline", "sell-off", "crash", "investigation", "default", "debt", "crisis",
    "shutdown", "layoff", "warning", "risk", "concern", "weak", "fall", "drop",
    "negative", "failure", "ban", "controversy", "lawsuit"
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _safe(val, default=None):
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return default
    return val


def _get_close_series(df: pd.DataFrame) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=float)
    if isinstance(df.columns, pd.MultiIndex):
        close_cols = [c for c in df.columns if c[0] == "Close"]
        if not close_cols:
            return pd.Series(dtype=float)
        return df[close_cols[0]].dropna()
    if "Close" in df.columns:
        return df["Close"].dropna()
    return pd.Series(dtype=float)


def _pct_change_5d(symbol: str) -> float | None:
    """Returns 5-day % change for a given yfinance symbol."""
    try:
        df = yf.download(symbol, period="7d", progress=False, auto_adjust=True)
        close = _get_close_series(df)
        if len(close) >= 2:
            return round(((float(close.iloc[-1]) - float(close.iloc[0])) / float(close.iloc[0])) * 100, 2)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# 1. Fundamentals
# ---------------------------------------------------------------------------
def get_stock_fundamentals(symbol: str) -> dict:
    """Fetch key fundamental data from Yahoo Finance."""
    try:
        ticker = get_yfinance_ticker(symbol)

        try:
            info = ticker.info or {}
        except Exception as ie:
            print(f"[StockAnalysis] Info fetch failed for {symbol}: {ie}")
            logger.warning("Info fetch failed for %s: %s, attempting fast_info fallback", symbol, ie)
            try:
                finfo = ticker.fast_info
                # Fetch major holders for institutional/insider ownership fallback
                held_pct_insiders = None
                held_pct_institutions = None
                try:
                    mh = ticker.major_holders
                    if mh is not None and not mh.empty:
                        mh_dict = mh.to_dict().get('Value', {})
                        held_pct_insiders = mh_dict.get('insidersPercentHeld')
                        held_pct_institutions = mh_dict.get('institutionsPercentHeld')
                except Exception as mhe:
                    print(f"[StockAnalysis] Failed to fetch major holders for {symbol}: {mhe}")
                
                # Calculate fallback float shares
                float_shares = None
                if finfo.shares and held_pct_insiders is not None:
                    float_shares = finfo.shares * (1 - held_pct_insiders)
                
                info = {
                    "currentPrice": finfo.last_price,
                    "regularMarketPrice": finfo.last_price,
                    "previousClose": finfo.previous_close,
                    "open": finfo.open,
                    "regularMarketOpen": finfo.open,
                    "dayHigh": finfo.day_high,
                    "regularMarketDayHigh": finfo.day_high,
                    "dayLow": finfo.day_low,
                    "regularMarketDayLow": finfo.day_low,
                    "volume": finfo.last_volume,
                    "regularMarketVolume": finfo.last_volume,
                    "averageVolume": finfo.three_month_average_volume,
                    "marketCap": finfo.market_cap,
                    "sharesOutstanding": finfo.shares,
                    "fiftyTwoWeekHigh": finfo.year_high,
                    "fiftyTwoWeekLow": finfo.year_low,
                    "currency": finfo.currency,
                    "heldPercentInsiders": held_pct_insiders,
                    "heldPercentInstitutions": held_pct_institutions,
                    "floatShares": float_shares,
                }
            except Exception as fie:
                print(f"[StockAnalysis] fast_info fallback failed for {symbol}: {fie}")
                logger.error("fast_info fallback failed for %s: %s", symbol, fie)
                info = {}

        def s(key, default=None):
            return _safe(info.get(key, default), default)

        # Get financials, balance sheet and cashflow data
        hist_1y = None
        revenue_growth_yoy = None
        earnings_growth_yoy = None
        fcf_positive = None
        fcf_growing = None
        fcf_history = []
        assets_growing = None
        assets_higher_than_liabilities = None
        total_assets = None
        total_liab = None
        assets_history = []
        liabilities_history = []
        intrinsic_value = None

        try:
            financials = ticker.financials
            balance_sheet = ticker.balance_sheet
            cashflow = ticker.cashflow
        except Exception as fe:
            print(f"[StockAnalysis] Error getting financial sheets for {symbol}: {fe}")
            financials = None
            balance_sheet = None
            cashflow = None

        # 1. Revenue & Earnings growth from financials
        if financials is not None and not financials.empty:
            rev_row = None
            for idx in financials.index:
                if idx.lower() == 'total revenue':
                    rev_row = financials.loc[idx]
                    break
            net_inc_row = None
            for idx in financials.index:
                if idx.lower() == 'net income':
                    net_inc_row = financials.loc[idx]
                    break
            
            if rev_row is not None and not rev_row.dropna().empty:
                rev_list = rev_row.dropna().tolist()
                if len(rev_list) >= 2 and rev_list[1] > 0:
                    revenue_growth_yoy = round(((rev_list[0] - rev_list[1]) / rev_list[1]) * 100, 2)
            
            if net_inc_row is not None and not net_inc_row.dropna().empty:
                inc_list = net_inc_row.dropna().tolist()
                if len(inc_list) >= 2:
                    if inc_list[1] > 0:
                        earnings_growth_yoy = round(((inc_list[0] - inc_list[1]) / inc_list[1]) * 100, 2)
                    elif inc_list[1] < 0 and inc_list[0] > inc_list[1]:
                        earnings_growth_yoy = round(((inc_list[0] - inc_list[1]) / abs(inc_list[1])) * 100, 2)

        # 2. Assets & Liabilities from balance sheet
        if balance_sheet is not None and not balance_sheet.empty:
            assets_row = None
            for idx in balance_sheet.index:
                if idx.lower() == 'total assets':
                    assets_row = balance_sheet.loc[idx]
                    break
            liab_row = None
            for idx in balance_sheet.index:
                if idx.lower() in ['total liabilities', 'total liabilities net minority interest', 'total liabilities net minority interest']:
                    liab_row = balance_sheet.loc[idx]
                    break
            if liab_row is None:
                for idx in balance_sheet.index:
                    if 'liabilities' in idx.lower():
                        liab_row = balance_sheet.loc[idx]
                        break

            if assets_row is not None and not assets_row.dropna().empty:
                assets_list = assets_row.dropna().tolist()
                assets_history = [float(x) for x in assets_list[:4]]
                if len(assets_list) >= 1:
                    total_assets = float(assets_list[0])
                if len(assets_list) >= 2:
                    assets_growing = assets_list[0] > assets_list[1]
            
            if liab_row is not None and not liab_row.dropna().empty:
                liab_list = liab_row.dropna().tolist()
                liabilities_history = [float(x) for x in liab_list[:4]]
                if len(liab_list) >= 1:
                    total_liab = float(liab_list[0])
                    
            if total_assets is not None and total_liab is not None:
                assets_higher_than_liabilities = total_assets > total_liab

        # 3. Cash Flow from cashflow statement
        if cashflow is not None and not cashflow.empty:
            fcf_row = None
            for idx in cashflow.index:
                if idx.lower() == 'free cash flow':
                    fcf_row = cashflow.loc[idx]
                    break
            if fcf_row is not None and not fcf_row.dropna().empty:
                fcf_list = fcf_row.dropna().tolist()
                fcf_history = [float(x) for x in fcf_list[:4]]
                if len(fcf_list) >= 1:
                    fcf_positive = fcf_list[0] > 0
                if len(fcf_list) >= 2:
                    fcf_growing = fcf_list[0] > fcf_list[1]

        # 4. Fallback calculation for missing fundamental ratios (e.g. under info rate limits)
        eps_val = s("trailingEps")
        shares_outstanding = s("sharesOutstanding")
        
        # Fallback EPS
        if eps_val is None and financials is not None and not financials.empty and shares_outstanding:
            try:
                net_income = None
                for idx in financials.index:
                    if idx.lower() == 'net income':
                        net_income = financials.loc[idx].dropna().tolist()[0]
                        break
                if net_income:
                    eps_val = round(net_income / shares_outstanding, 2)
            except Exception:
                pass

        # Fallback P/E Ratio
        pe_ratio = s("trailingPE")
        current_price = s("currentPrice") or s("regularMarketPrice")
        if pe_ratio is None and current_price and eps_val and eps_val > 0:
            try:
                pe_ratio = round(current_price / eps_val, 2)
            except Exception:
                pass

        # Fallback Book Value
        bv_val = s("bookValue")
        if bv_val is None and balance_sheet is not None and not balance_sheet.empty and shares_outstanding:
            try:
                if total_assets is not None and total_liab is not None:
                    bv_val = round((total_assets - total_liab) / shares_outstanding, 2)
            except Exception:
                pass

        # Fallback Price/Book
        pb_ratio = s("priceToBook")
        if pb_ratio is None and current_price and bv_val and bv_val > 0:
            try:
                pb_ratio = round(current_price / bv_val, 2)
            except Exception:
                pass

        # Fallback Dividend Yield
        from django.core.cache import cache
        div_yield = s("dividendYield")
        if div_yield is None and current_price and current_price > 0:
            div_yield_cache_key = f"fallback_div_yield_{symbol}"
            div_yield = cache.get(div_yield_cache_key)
            if div_yield is None:
                try:
                    if hist_1y is None or hist_1y.empty:
                        hist_1y = ticker.history(period="1y")
                    if hist_1y is not None and not hist_1y.empty and "Dividends" in hist_1y.columns:
                        total_div = float(hist_1y["Dividends"].sum())
                        div_yield = round(total_div / current_price, 4)
                        cache.set(div_yield_cache_key, div_yield, 86400) # Cache for 24 hours
                except Exception:
                    pass

        # Fallback Forward P/E Ratio
        forward_pe = s("forwardPE")
        if forward_pe is None:
            if pe_ratio is not None:
                if earnings_growth_yoy is not None and earnings_growth_yoy > -50 and earnings_growth_yoy < 100:
                    try:
                        forward_eps = eps_val * (1 + earnings_growth_yoy / 100)
                        if forward_eps > 0:
                            forward_pe = round(current_price / forward_eps, 2)
                    except Exception:
                        pass
                if forward_pe is None:
                    forward_pe = pe_ratio

        # Fallback Beta
        beta = s("beta")
        if beta is None and current_price:
            beta_cache_key = f"fallback_beta_{symbol}"
            beta = cache.get(beta_cache_key)
            if beta is None:
                try:
                    if hist_1y is None or hist_1y.empty:
                        hist_1y = ticker.history(period="1y")
                    if hist_1y is not None and not hist_1y.empty and "Close" in hist_1y.columns:
                        index_ticker = "^NSEI" if symbol.endswith(".NS") or symbol.endswith(".BO") else "^GSPC"
                        
                        # Get index close from cache
                        index_close_cache_key = f"fallback_index_close_{index_ticker}"
                        index_close = cache.get(index_close_cache_key)
                        if index_close is None:
                            try:
                                df_index = yf.download(index_ticker, period="1y", interval="1d", progress=False, auto_adjust=True)
                                if df_index is not None and not df_index.empty:
                                    close_index = _get_close_series(df_index)
                                    close_index.index = close_index.index.tz_localize(None)
                                    index_close = close_index
                                    cache.set(index_close_cache_key, index_close, 86400) # Cache for 24 hours
                            except Exception as ie_err:
                                print(f"[StockAnalysis] Error downloading index close: {ie_err}")
                        
                        if index_close is not None and not index_close.empty:
                            close_stock = hist_1y["Close"].dropna()
                            close_stock.index = close_stock.index.tz_localize(None)
                            df_aligned = pd.concat([close_stock, index_close], axis=1, keys=["stock", "index"]).dropna()
                            if len(df_aligned) > 30:
                                returns = df_aligned.pct_change().dropna()
                                covariance = returns["stock"].cov(returns["index"])
                                index_variance = returns["index"].var()
                                if index_variance > 0:
                                    beta = round(float(covariance / index_variance), 2)
                                    cache.set(beta_cache_key, beta, 86400) # Cache for 24 hours
                except Exception as be:
                    print(f"[StockAnalysis] Error calculating fallback beta for {symbol}: {be}")

        # Intrinsic value via Graham Number
        if eps_val and bv_val and eps_val > 0 and bv_val > 0:
            try:
                intrinsic_value = round(math.sqrt(22.5 * float(eps_val) * float(bv_val)), 2)
            except Exception:
                pass

        debt_to_equity = s("debtToEquity")
        if debt_to_equity is not None:
            debt_to_equity = float(debt_to_equity) / 100.0 if float(debt_to_equity) > 5.0 else float(debt_to_equity)

        return {
            "symbol": symbol,
            "name": s("longName") or s("shortName") or symbol,
            "current_price": current_price,
            "previous_close": s("previousClose"),
            "open": s("open") or s("regularMarketOpen"),
            "day_high": s("dayHigh") or s("regularMarketDayHigh"),
            "day_low": s("dayLow") or s("regularMarketDayLow"),
            "volume": s("volume") or s("regularMarketVolume"),
            "avg_volume": s("averageVolume"),
            "market_cap": s("marketCap"),
            "pe_ratio": pe_ratio,
            "forward_pe": forward_pe,
            "eps": eps_val,
            "dividend_yield": div_yield,
            "beta": beta,
            "week_52_high": s("fiftyTwoWeekHigh"),
            "week_52_low": s("fiftyTwoWeekLow"),
            "book_value": bv_val,
            "price_to_book": pb_ratio,
            "sector": s("sector", "N/A"),
            "industry": s("industry", "N/A"),
            "description": s("longBusinessSummary", ""),
            "currency": s("currency", "INR"),
            "bid": s("bid"),
            "ask": s("ask"),
            "held_pct_institutions": s("heldPercentInstitutions"),
            "held_pct_insiders": s("heldPercentInsiders"),
            "float_shares": s("floatShares"),
            "shares_outstanding": s("sharesOutstanding"),
            "short_ratio": s("shortRatio"),
            "debt_to_equity": debt_to_equity,
            "revenue_growth_yoy": revenue_growth_yoy,
            "earnings_growth_yoy": earnings_growth_yoy,
            "fcf_positive": fcf_positive,
            "fcf_growing": fcf_growing,
            "fcf_history": fcf_history,
            "assets_growing": assets_growing,
            "assets_higher_than_liabilities": assets_higher_than_liabilities,
            "total_assets": total_assets,
            "total_liab": total_liab,
            "assets_history": assets_history,
            "liabilities_history": liabilities_history,
            "intrinsic_value": intrinsic_value,
        }
    except Exception as e:
        print(f"[StockAnalysis] Fundamentals error for {symbol}: {e}")
        logger.warning("Fundamentals failed for %s: %s", symbol, e, exc_info=True)
        return {
            "symbol": symbol,
            "name": symbol,
            "error": str(e),
            "current_price": None,
            "previous_close": None,
            "open": None,
            "day_high": None,
            "day_low": None,
            "volume": None,
            "avg_volume": None,
            "market_cap": None,
            "pe_ratio": None,
            "forward_pe": None,
            "eps": None,
            "dividend_yield": None,
            "beta": None,
            "week_52_high": None,
            "week_52_low": None,
            "book_value": None,
            "price_to_book": None,
            "sector": "N/A",
            "industry": "N/A",
            "description": "",
            "currency": "INR",
            "bid": None,
            "ask": None,
            "held_pct_institutions": None,
            "held_pct_insiders": None,
            "float_shares": None,
            "shares_outstanding": None,
            "short_ratio": None,
            "debt_to_equity": None,
            "revenue_growth_yoy": None,
            "earnings_growth_yoy": None,
            "fcf_positive": None,
            "fcf_growing": None,
            "fcf_history": [],
            "assets_growing": None,
            "assets_higher_than_liabilities": None,
            "total_assets": None,
            "total_liab": None,
            "assets_history": [],
            "liabilities_history": [],
            "intrinsic_value": None,
        }


# ---------------------------------------------------------------------------
# 2. Technical Indicators
# ---------------------------------------------------------------------------
def get_technical_indicators(symbol: str) -> dict:
    result = {
        "rsi": None, "rsi_signal": "neutral",
        "sma50": None, "sma50_signal": "neutral",
        "sma200": None, "sma200_signal": "neutral",
        "macd": None, "macd_signal_line": None, "macd_signal": "neutral",
        "bb_upper": None, "bb_lower": None, "bb_signal": "neutral",
        "volume_signal": "neutral",
        "avg_volume_10": None,
        "current_volume": None,
        "error": None,
    }
    try:
        df = yf.download(symbol, period="1y", auto_adjust=True, progress=False)
        close = _get_close_series(df)
        if close.empty or len(close) < 30:
            result["error"] = "Not enough historical data"
            return result

        price = float(close.iloc[-1])

        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, float("nan"))
        rsi_val = float((100 - (100 / (1 + rs))).iloc[-1])
        result["rsi"] = round(rsi_val, 1)
        result["rsi_signal"] = "bullish" if rsi_val < 30 else ("bearish" if rsi_val > 70 else "neutral")

        # SMA 50
        if len(close) >= 50:
            sma50 = float(close.rolling(50).mean().iloc[-1])
            result["sma50"] = round(sma50, 2)
            result["sma50_signal"] = "bullish" if price > sma50 else "bearish"

        # SMA 200
        if len(close) >= 200:
            sma200 = float(close.rolling(200).mean().iloc[-1])
            result["sma200"] = round(sma200, 2)
            result["sma200_signal"] = "bullish" if price > sma200 else "bearish"

        # MACD
        macd_line = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        result["macd"] = round(float(macd_line.iloc[-1]), 4)
        result["macd_signal_line"] = round(float(signal_line.iloc[-1]), 4)
        result["macd_signal"] = "bullish" if result["macd"] > result["macd_signal_line"] else "bearish"

        # Bollinger Bands
        if len(close) >= 20:
            sma20 = close.rolling(20).mean()
            std20 = close.rolling(20).std()
            bb_upper = float((sma20 + 2 * std20).iloc[-1])
            bb_lower = float((sma20 - 2 * std20).iloc[-1])
            result["bb_upper"] = round(bb_upper, 2)
            result["bb_lower"] = round(bb_lower, 2)
            bb_range = bb_upper - bb_lower
            if bb_range > 0:
                pos = (price - bb_lower) / bb_range
                result["bb_signal"] = "bullish" if pos < 0.2 else ("bearish" if pos > 0.8 else "neutral")

        # Volume
        try:
            if isinstance(df.columns, pd.MultiIndex):
                vol_cols = [c for c in df.columns if c[0] == "Volume"]
                vol = df[vol_cols[0]].dropna() if vol_cols else pd.Series(dtype=float)
            else:
                vol = df["Volume"].dropna() if "Volume" in df.columns else pd.Series(dtype=float)
            if len(vol) >= 10:
                avg10 = float(vol.iloc[-10:].mean())
                cur = float(vol.iloc[-1])
                result["avg_volume_10"] = int(avg10)
                result["current_volume"] = int(cur)
                result["volume_signal"] = "bullish" if cur > avg10 * 1.2 else "neutral"
        except Exception:
            pass

    except Exception as e:
        result["error"] = str(e)
    return result


# ---------------------------------------------------------------------------
# 3. News Sentiment
# ---------------------------------------------------------------------------
def get_news_sentiment(symbol: str) -> dict:
    """
    Fetch last 10 news articles and score overall sentiment.
    Returns news list + overall sentiment signal.
    """
    result = {
        "articles": [],
        "sentiment": "neutral",
        "sentiment_score": 0,
        "positive_count": 0,
        "negative_count": 0,
        "neutral_count": 0,
    }
    try:
        ticker = get_yfinance_ticker(symbol)
        raw_news = ticker.news or []

        pos_count = 0
        neg_count = 0

        for item in raw_news[:10]:
            content = item.get("content", {})
            title = content.get("title", "")
            summary = content.get("summary", "")
            pub_date = content.get("pubDate", "")
            provider = (content.get("provider") or {}).get("displayName", "")
            url = (content.get("canonicalUrl") or {}).get("url", "") or \
                  (content.get("clickThroughUrl") or {}).get("url", "")
            thumbnail = None
            thumb_data = content.get("thumbnail") or {}
            resolutions = thumb_data.get("resolutions", [])
            for res in resolutions:
                if res.get("tag") == "original" or (res.get("width", 0) >= 170):
                    thumbnail = res.get("url")
                    break

            # Format date
            date_str = ""
            if pub_date:
                try:
                    dt = datetime.datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                    date_str = dt.strftime("%d %b %Y")
                except Exception:
                    date_str = pub_date[:10]

            # Keyword sentiment
            text = (title + " " + summary).lower()
            words = set(text.split())
            pos_hits = words & POSITIVE_NEWS_WORDS
            neg_hits = words & NEGATIVE_NEWS_WORDS
            if len(pos_hits) > len(neg_hits):
                article_sentiment = "positive"
                pos_count += 1
            elif len(neg_hits) > len(pos_hits):
                article_sentiment = "negative"
                neg_count += 1
            else:
                article_sentiment = "neutral"

            result["articles"].append({
                "title": title,
                "summary": (summary[:220] + "…") if len(summary) > 220 else summary,
                "date": date_str,
                "provider": provider,
                "url": url,
                "thumbnail": thumbnail,
                "sentiment": article_sentiment,
            })

        neutral_count = len(result["articles"]) - pos_count - neg_count
        result["positive_count"] = pos_count
        result["negative_count"] = neg_count
        result["neutral_count"] = neutral_count

        if pos_count > neg_count + 1:
            result["sentiment"] = "positive"
            result["sentiment_score"] = 1
        elif neg_count > pos_count + 1:
            result["sentiment"] = "negative"
            result["sentiment_score"] = -1
        else:
            result["sentiment"] = "neutral"
            result["sentiment_score"] = 0

    except Exception as e:
        print(f"[StockAnalysis] News error for {symbol}: {e}")
    return result


# ---------------------------------------------------------------------------
# 4. Ownership & Market Depth
# ---------------------------------------------------------------------------
def get_ownership_analysis(fundamentals: dict) -> dict:
    """Score institutional and insider ownership from already-fetched fundamentals."""
    result = {
        "bid": fundamentals.get("bid"),
        "ask": fundamentals.get("ask"),
        "spread": None,
        "spread_pct": None,
        "inst_holding_pct": None,
        "insider_holding_pct": None,
        "float_shares": fundamentals.get("float_shares"),
        "shares_outstanding": fundamentals.get("shares_outstanding"),
        "short_ratio": fundamentals.get("short_ratio"),
        "score": 0,
        "signals": [],
    }

    bid = fundamentals.get("bid")
    ask = fundamentals.get("ask")
    if bid and ask and bid > 0 and ask > 0:
        result["spread"] = round(ask - bid, 2)
        result["spread_pct"] = round(((ask - bid) / bid) * 100, 4)

    inst = fundamentals.get("held_pct_institutions")
    if inst is not None:
        result["inst_holding_pct"] = round(inst * 100, 2)
        if inst > 0.30:
            result["score"] += 1
            result["signals"].append(("bullish", f"Strong institutional interest ({result['inst_holding_pct']}% held by institutions)"))
        elif inst < 0.10:
            result["score"] -= 1
            result["signals"].append(("bearish", f"Low institutional interest ({result['inst_holding_pct']}% held by institutions)"))

    insider = fundamentals.get("held_pct_insiders")
    if insider is not None:
        result["insider_holding_pct"] = round(insider * 100, 2)
        if insider > 0.50:
            result["score"] += 1
            result["signals"].append(("bullish", f"High promoter holding ({result['insider_holding_pct']}%) — management confidence"))
        elif insider < 0.20:
            result["score"] -= 1
            result["signals"].append(("bearish", f"Low promoter holding ({result['insider_holding_pct']}%) — watch for stake sales"))

    sr = fundamentals.get("short_ratio")
    if sr and sr > 5:
        result["score"] -= 1
        result["signals"].append(("bearish", f"High short ratio ({sr:.1f}) — significant bearish bets"))

    return result


# ---------------------------------------------------------------------------
# 5. Government Policy Alignment
# ---------------------------------------------------------------------------
def get_policy_alignment(sector: str, news_articles: list) -> dict:
    """Match stock sector and news to Indian government policy themes."""
    result = {
        "matched_themes": [],
        "score": 0,
        "summary": "No strong policy tailwinds identified for this stock currently.",
    }

    sector_lower = (sector or "").lower()
    # Collect all news text
    all_news_text = " ".join(
        (a.get("title", "") + " " + a.get("summary", "")).lower()
        for a in news_articles
    )

    matched = []
    for theme_name, theme in POLICY_THEMES.items():
        # Sector match
        sector_match = any(s.lower() in sector_lower or sector_lower in s.lower()
                           for s in theme.get("sectors", []))
        # Keyword match in news
        kw_match = any(kw in all_news_text for kw in theme.get("keywords", []))

        if sector_match or kw_match:
            matched.append({
                "name": theme_name,
                "description": theme["description"],
                "match_type": "sector+news" if (sector_match and kw_match) else
                              ("sector" if sector_match else "news"),
            })

    if matched:
        result["matched_themes"] = matched
        result["score"] = 1  # flat +1 for any policy alignment
        result["summary"] = f"Aligned with {len(matched)} active government policy theme(s)"
    return result


# ---------------------------------------------------------------------------
# 6. Global Market Impact
# ---------------------------------------------------------------------------
def get_global_impact(sector: str) -> dict:
    """
    Fetch 5-day trend of S&P500, Crude Oil, USD/INR, Gold.
    Returns per-indicator trend + sector-specific impact assessment.
    """
    result = {
        "indicators": {},
        "score": 0,
        "signals": [],
    }
    sector_lower = (sector or "").lower()

    symbols = list(GLOBAL_INDICATORS.keys())
    try:
        df_all = yf.download(" ".join(symbols), period="7d", group_by="ticker",
                             progress=False, auto_adjust=True)
    except Exception as e:
        print(f"[StockAnalysis] Global data error: {e}")
        return result

    for sym, meta in GLOBAL_INDICATORS.items():
        try:
            if isinstance(df_all.columns, pd.MultiIndex):
                if sym not in df_all.columns.get_level_values(0):
                    continue
                close = df_all[sym]["Close"].dropna() if "Close" in df_all[sym].columns else pd.Series()
            else:
                close = _get_close_series(df_all)

            if len(close) < 2:
                continue

            first_val = float(close.iloc[0])
            last_val = float(close.iloc[-1])
            pct = round(((last_val - first_val) / first_val) * 100, 2) if first_val else 0
            trend = "up" if pct > 0.5 else ("down" if pct < -0.5 else "flat")

            # Determine impact for this sector
            impact = "neutral"
            signal_text = None

            if sym == "^GSPC":
                if trend == "up":
                    impact = "bullish"
                    signal_text = f"S&P 500 up {pct}% — positive FII sentiment toward Indian equities"
                elif trend == "down":
                    impact = "bearish"
                    signal_text = f"S&P 500 down {pct}% — risk-off may reduce FII inflows"

            elif sym == "CL=F":
                is_energy = any(x in sector_lower for x in ["energy", "oil", "gas"])
                is_impacted = any(x in sector_lower for x in ["airline", "automobile", "consumer", "paint", "chemical"])
                if trend == "up":
                    impact = "bullish" if is_energy else ("bearish" if is_impacted else "neutral")
                    if is_energy:
                        signal_text = f"Crude oil up {pct}% — positive for energy/oil sector"
                    elif is_impacted:
                        signal_text = f"Crude oil up {pct}% — raises input costs for this sector"
                elif trend == "down":
                    impact = "bearish" if is_energy else ("bullish" if is_impacted else "neutral")
                    if is_impacted:
                        signal_text = f"Crude oil down {pct}% — lower input costs benefit this sector"
                    elif is_energy:
                        signal_text = f"Crude oil down {pct}% — pressure on energy sector margins"

            elif sym == "INR=X":
                is_it = any(x in sector_lower for x in ["technology", "it", "software"])
                is_pharma = "health" in sector_lower or "pharma" in sector_lower
                is_exporter = is_it or is_pharma
                if trend == "up":  # Rupee weakening (more INR per USD)
                    impact = "bullish" if is_exporter else "bearish"
                    if is_exporter:
                        signal_text = f"Rupee weakened {pct}% — boosts export earnings for IT/Pharma"
                    else:
                        signal_text = f"Rupee weakened {pct}% — raises import costs"
                elif trend == "down":  # Rupee strengthening
                    impact = "bearish" if is_exporter else "bullish"
                    if is_exporter:
                        signal_text = f"Rupee strengthened {pct}% — may reduce export revenue in INR"

            elif sym == "GC=F":
                if trend == "up":
                    impact = "bearish"
                    signal_text = f"Gold up {pct}% — risk-off sentiment may divert capital from equities"
                elif trend == "down":
                    impact = "bullish"
                    signal_text = f"Gold down {pct}% — risk-on mood favors equity markets"

            result["indicators"][sym] = {
                "name": meta["name"],
                "icon": meta["icon"],
                "value": round(last_val, 2),
                "pct_change": pct,
                "trend": trend,
                "impact": impact,
                "description": meta["description"],
                "signal_text": signal_text,
            }

            if impact == "bullish":
                result["score"] += 1
                if signal_text:
                    result["signals"].append(("bullish", signal_text))
            elif impact == "bearish":
                result["score"] -= 1
                if signal_text:
                    result["signals"].append(("bearish", signal_text))

        except Exception as e:
            print(f"[StockAnalysis] Error processing {sym}: {e}")

    return result


# ---------------------------------------------------------------------------
# 7. Unified Recommendation
# ---------------------------------------------------------------------------
def get_buy_recommendation(fundamentals: dict, indicators: dict,
                            news: dict = None, ownership: dict = None,
                            policy: dict = None, global_impact: dict = None) -> dict:
    """
    Score all signals and return a unified verdict with reasons.
    Incorporates the 8 Golden Rules & Fundamental Scorecard.
    Max total score: ±25
    """
    score = 0
    bullish_reasons = []
    bearish_reasons = []
    red_flags = []
    scorecard = {}

    price = fundamentals.get("current_price")
    week_52_high = fundamentals.get("week_52_high")
    week_52_low = fundamentals.get("week_52_low")
    pe = fundamentals.get("pe_ratio")
    pb = fundamentals.get("price_to_book")
    beta = fundamentals.get("beta")
    div_yield = fundamentals.get("dividend_yield")
    
    # New metrics from fundamentals
    revenue_growth = fundamentals.get("revenue_growth_yoy")
    earnings_growth = fundamentals.get("earnings_growth_yoy")
    fcf_positive = fundamentals.get("fcf_positive")
    fcf_growing = fundamentals.get("fcf_growing")
    assets_growing = fundamentals.get("assets_growing")
    assets_higher = fundamentals.get("assets_higher_than_liabilities")
    total_assets = fundamentals.get("total_assets")
    total_liab = fundamentals.get("total_liab")
    intrinsic_value = fundamentals.get("intrinsic_value")
    debt_to_equity = fundamentals.get("debt_to_equity")
    insider_holding = fundamentals.get("held_pct_insiders")
    inst_holding = fundamentals.get("held_pct_institutions")

    # Always pass the "Avoid tips" check since we are using this scorecard
    scorecard["avoid_tips"] = {
        "passed": True,
        "text": "Passed: You are using structured fundamental analysis instead of stock tips."
    }

    # --- 1. Revenue & Profit Growth ---
    rev_ok = False
    prof_ok = False
    if revenue_growth is not None:
        if revenue_growth > 0:
            rev_ok = True
        else:
            red_flags.append(f"Dropping Revenues: Revenue shrank by {abs(revenue_growth)}% YoY")
    else:
        rev_ok = True  # neutral if data missing
        
    if earnings_growth is not None:
        if earnings_growth > 0:
            prof_ok = True
        else:
            red_flags.append(f"Dropping Profits: Net income shrank by {abs(earnings_growth)}% YoY")
    else:
        prof_ok = True

    if rev_ok and prof_ok:
        score += 2
        bullish_reasons.append("Consistent Growth: Both YoY revenue & profit are growing")
        scorecard["revenue_profit_growth"] = {
            "passed": True,
            "text": f"Passed: Revenue grew by {revenue_growth or 0}% and Profit by {earnings_growth or 0}% YoY."
        }
    else:
        score -= 2
        bearish_reasons.append("Revenue or net income is declining YoY")
        scorecard["revenue_profit_growth"] = {
            "passed": False,
            "text": f"Failed: Declining growth. Rev YoY: {revenue_growth or 0}%, Profit YoY: {earnings_growth or 0}%."
        }

    # --- 2. Assets vs Liabilities ---
    if total_assets is not None and total_liab is not None:
        if assets_higher:
            score += 2
            bullish_reasons.append(f"Financial Stability: Total assets (₹{total_assets/1e9:.1f} Cr) exceed liabilities (₹{total_liab/1e9:.1f} Cr)")
            scorecard["assets_liabilities"] = {
                "passed": True,
                "text": f"Passed: Assets (₹{total_assets/1e9:.1f} Cr) exceed liabilities (₹{total_liab/1e9:.1f} Cr)."
            }
        else:
            score -= 3
            red_flags.append("Liabilities exceed Assets: High threat of insolvency/bankruptcy")
            bearish_reasons.append("Total liabilities exceed total assets")
            scorecard["assets_liabilities"] = {
                "passed": False,
                "text": "Failed: Liabilities exceed total assets (financial instability)."
            }
    else:
        scorecard["assets_liabilities"] = {
            "passed": True,
            "text": "Passed (Neutral): Insufficient asset/liability history."
        }

    # --- 3. Cash Flow Check ---
    if fcf_positive is not None:
        if fcf_positive:
            score += 2
            growth_text = "and growing" if fcf_growing else "but declining YoY"
            if not fcf_growing:
                bearish_reasons.append("Free cash flow is declining YoY")
            bullish_reasons.append(f"Cash Flow: Company has positive free cash flow {growth_text}")
            scorecard["cash_flow"] = {
                "passed": True,
                "text": f"Passed: Free Cash Flow is positive (FCF growing: {fcf_growing})."
            }
        else:
            score -= 3
            red_flags.append("Negative Free Cash Flow: Business burns cash; relies on external funding")
            bearish_reasons.append("Negative free cash flow")
            scorecard["cash_flow"] = {
                "passed": False,
                "text": "Failed: Free Cash Flow is negative (risk of cash crunch)."
            }
    else:
        scorecard["cash_flow"] = {
            "passed": True,
            "text": "Passed (Neutral): Free cash flow data unavailable."
        }

    # --- 4. Intrinsic Value ---
    if price and intrinsic_value:
        if price < intrinsic_value:
            score += 2
            bullish_reasons.append(f"Undervalued: Price (₹{price:.1f}) is below Graham value (₹{intrinsic_value:.1f})")
            scorecard["intrinsic_value"] = {
                "passed": True,
                "text": f"Passed: Undervalued. Stock price ₹{price:.1f} is below Graham Intrinsic Value ₹{intrinsic_value:.1f}."
            }
        else:
            scorecard["intrinsic_value"] = {
                "passed": False,
                "text": f"Failed: Premium pricing. Stock price ₹{price:.1f} is above Graham Intrinsic Value ₹{intrinsic_value:.1f}."
            }
    else:
        scorecard["intrinsic_value"] = {
            "passed": True,
            "text": "Passed (Neutral): Intrinsic value cannot be calculated."
        }

    # --- 5. P/E and P/B Valuations ---
    pe_pb_ok = True
    if pe is not None:
        if pe < 20:
            score += 1
            bullish_reasons.append(f"Valuation: Reasonable P/E ratio ({pe:.1f}x)")
        else:
            pe_pb_ok = False
            bearish_reasons.append(f"P/E ratio is premium ({pe:.1f}x)")
    if pb is not None:
        if pb <= 2.0:
            score += 1
            bullish_reasons.append(f"Valuation: Excellent P/B ratio ({pb:.1f}x)")
        else:
            pe_pb_ok = False
            bearish_reasons.append(f"P/B ratio is high ({pb:.1f}x)")
            
    if pe_pb_ok:
        scorecard["valuation"] = {
            "passed": True,
            "text": f"Passed: Good valuations. P/E: {pe or 'N/A'}x, P/B: {pb or 'N/A'}x."
        }
    else:
        scorecard["valuation"] = {
            "passed": False,
            "text": f"Failed: Premium valuations. P/E: {pe or 'N/A'}x, P/B: {pb or 'N/A'}x."
        }

    # --- 6. Debt-to-Equity ---
    if debt_to_equity is not None:
        if debt_to_equity <= 1.0:
            score += 2
            bullish_reasons.append(f"Healthy leverage: Low Debt-to-Equity ratio ({debt_to_equity:.2f})")
            scorecard["debt_to_equity"] = {
                "passed": True,
                "text": f"Passed: Excellent leverage. Debt-to-Equity is {debt_to_equity:.2f} (ideal under 1.0)."
            }
        elif debt_to_equity <= 2.0:
            score += 1
            bullish_reasons.append(f"Moderate leverage: Debt-to-Equity ratio ({debt_to_equity:.2f}) is manageable")
            scorecard["debt_to_equity"] = {
                "passed": True,
                "text": f"Passed: Moderate leverage. Debt-to-Equity is {debt_to_equity:.2f} (acceptable under 2.0)."
            }
        else:
            score -= 3
            red_flags.append(f"Massive Debt: Extremely high Debt-to-Equity ratio of {debt_to_equity:.2f}")
            bearish_reasons.append(f"High Debt-to-Equity ratio ({debt_to_equity:.2f}) increases interest expense")
            scorecard["debt_to_equity"] = {
                "passed": False,
                "text": f"Failed: Excessive leverage. Debt-to-Equity is {debt_to_equity:.2f} (above 2.0 limit)."
            }
    else:
        scorecard["debt_to_equity"] = {
            "passed": True,
            "text": "Passed (Neutral): Debt-to-equity ratio data unavailable."
        }

    # --- 7. Management & Shareholding ---
    insider_pct = (insider_holding * 100) if insider_holding else None
    inst_pct = (inst_holding * 100) if inst_holding else None
    
    sh_ok = True
    if insider_pct is not None:
        if insider_pct < 15:
            sh_ok = False
            red_flags.append(f"Low Promoter Holding: Promoters hold only {insider_pct:.1f}% of the company")
            bearish_reasons.append(f"Low promoter holding ({insider_pct:.1f}%) suggests weak founder commitment")
        elif insider_pct >= 35:
            score += 1
            bullish_reasons.append(f"Promoter Confidence: Healthy promoter stake ({insider_pct:.1f}%)")
            
    if inst_pct is not None:
        if inst_pct >= 25:
            score += 1
            bullish_reasons.append(f"Institutional backing: DIIs/FIIs hold {inst_pct:.1f}%")
            
    if sh_ok:
        scorecard["shareholding"] = {
            "passed": True,
            "text": f"Passed: Promoter stake is {insider_pct or 'N/A'}% and Institutional stake is {inst_pct or 'N/A'}%."
        }
    else:
        scorecard["shareholding"] = {
            "passed": False,
            "text": f"Failed: Poor shareholding structure. Promoter stake: {insider_pct or 'N/A'}%."
        }

    # --- Legacy Fundamental, Technical & Global checks (capped weight) ---
    if price and week_52_low and week_52_high:
        rng = week_52_high - week_52_low
        if rng > 0:
            pos = (price - week_52_low) / rng
            if pos < 0.35:
                score += 1
                bullish_reasons.append("Trading near 52-week low — potential value opportunity")
            elif pos > 0.85:
                score -= 1
                bearish_reasons.append("Trading near 52-week high — limited near-term upside")

    if beta is not None:
        if beta < 0.8:
            bullish_reasons.append(f"Low beta ({beta:.2f}) — defensive, low market correlation")
        elif beta > 1.5:
            bearish_reasons.append(f"High beta ({beta:.2f}) — highly volatile, amplifies market moves")

    # --- Technical signals ---
    rsi = indicators.get("rsi")
    if indicators.get("rsi_signal") == "bullish":
        score += 1
        bullish_reasons.append(f"RSI {rsi} — oversold, historically a mean-reversion entry point")
    elif indicators.get("rsi_signal") == "bearish":
        score -= 1
        bearish_reasons.append(f"RSI {rsi} — overbought territory, potential short-term correction")

    sma50 = indicators.get("sma50")
    if indicators.get("sma50_signal") == "bullish":
        score += 1
        bullish_reasons.append(f"Price above 50-day SMA (₹{sma50}) — short-term uptrend intact")
    elif indicators.get("sma50_signal") == "bearish":
        score -= 1
        bearish_reasons.append(f"Price below 50-day SMA (₹{sma50}) — short-term downtrend")

    sma200 = indicators.get("sma200")
    if indicators.get("sma200_signal") == "bullish":
        score += 1
        bullish_reasons.append(f"Price above 200-day SMA (₹{sma200}) — long-term uptrend")
    elif indicators.get("sma200_signal") == "bearish":
        score -= 1
        bearish_reasons.append(f"Price below 200-day SMA (₹{sma200}) — long-term downtrend")

    if indicators.get("macd_signal") == "bullish":
        score += 1
        bullish_reasons.append("MACD crossed above signal line — bullish momentum building")
    elif indicators.get("macd_signal") == "bearish":
        score -= 1
        bearish_reasons.append("MACD below signal line — bearish momentum persists")

    if indicators.get("bb_signal") == "bullish":
        score += 1
        bullish_reasons.append("Price near lower Bollinger Band — likely support/bounce zone")
    elif indicators.get("bb_signal") == "bearish":
        score -= 1
        bearish_reasons.append("Price near upper Bollinger Band — resistance zone, caution")

    if indicators.get("volume_signal") == "bullish":
        score += 1
        bullish_reasons.append("Above-average volume — strong buying conviction")

    # --- News sentiment ---
    if news:
        ns = news.get("sentiment_score", 0)
        score += ns
        if ns > 0:
            bullish_reasons.append(f"Positive news sentiment ({news['positive_count']} positive vs {news['negative_count']} negative articles)")
        elif ns < 0:
            bearish_reasons.append(f"Negative news sentiment ({news['negative_count']} negative vs {news['positive_count']} positive articles)")

    # --- Policy ---
    if policy:
        ps = policy.get("score", 0)
        score += ps
        if ps > 0:
            themes = ", ".join(t["name"] for t in policy.get("matched_themes", []))
            bullish_reasons.append(f"Govt policy tailwind — aligned with: {themes}")

    # --- Global impact ---
    if global_impact:
        gs = global_impact.get("score", 0)
        score += gs
        for sig_type, sig_text in global_impact.get("signals", []):
            if sig_type == "bullish":
                bullish_reasons.append(sig_text)
            else:
                bearish_reasons.append(sig_text)

    # --- Verdict (adjusted for ±25 range) ---
    if score >= 10:
        verdict, color, emoji = "STRONG BUY", "strong-buy", "🚀"
    elif score >= 4:
        verdict, color, emoji = "BUY", "buy", "✅"
    elif score >= -2:
        verdict, color, emoji = "HOLD", "hold", "⚖️"
    elif score >= -7:
        verdict, color, emoji = "AVOID", "avoid", "⚠️"
    else:
        verdict, color, emoji = "STRONG AVOID", "strong-avoid", "🚫"

    return {
        "verdict": verdict,
        "verdict_color": color,
        "verdict_emoji": emoji,
        "score": score,
        "max_score": 25,
        "bullish_reasons": bullish_reasons,
        "bearish_reasons": bearish_reasons,
        "red_flags": red_flags,
        "scorecard": scorecard,
    }


# ---------------------------------------------------------------------------
# 8. Advanced Quant Metrics (Sharpe, Sortino, ADV, PCR, IV)
# ---------------------------------------------------------------------------
def get_quant_metrics(symbol: str) -> dict:
    """
    Compute professional-grade quant metrics:
      - Sharpe Ratio (1-year daily returns vs risk-free rate)
      - Sortino Ratio (1-year downside deviation)
      - Average Daily Volume – 30 day (liquidity check)
      - Put/Call Ratio (options market sentiment)
      - Implied Volatility – near ATM option
    """
    result = {
        "sharpe_ratio": None,
        "sharpe_signal": "neutral",
        "sortino_ratio": None,
        "sortino_signal": "neutral",
        "adv_30": None,
        "adv_signal": "neutral",
        "put_call_ratio": None,
        "pcr_signal": "neutral",
        "implied_volatility": None,
        "iv_signal": "neutral",
        "error": None,
    }
    try:
        import numpy as np
        ticker = get_yfinance_ticker(symbol)

        # --- Sharpe & Sortino from 1-year daily returns ---
        df = yf.download(symbol, period="1y", auto_adjust=True, progress=False)
        close = _get_close_series(df)
        if len(close) >= 60:
            daily_ret = close.pct_change().dropna()
            ann_ret = float(daily_ret.mean()) * 252
            ann_std = float(daily_ret.std()) * (252 ** 0.5)
            risk_free = 0.065  # RBI repo rate proxy (~6.5%)

            # Sharpe
            if ann_std > 0:
                sharpe = round((ann_ret - risk_free) / ann_std, 2)
                result["sharpe_ratio"] = sharpe
                result["sharpe_signal"] = "bullish" if sharpe > 1.0 else ("bearish" if sharpe < 0 else "neutral")

            # Sortino — only downside deviation
            downside = daily_ret[daily_ret < 0]
            downside_std = float(downside.std()) * (252 ** 0.5) if len(downside) > 5 else 0
            if downside_std > 0:
                sortino = round((ann_ret - risk_free) / downside_std, 2)
                result["sortino_ratio"] = sortino
                result["sortino_signal"] = "bullish" if sortino > 1.5 else ("bearish" if sortino < 0 else "neutral")

            # ADV-30
            try:
                if isinstance(df.columns, pd.MultiIndex):
                    vol_cols = [c for c in df.columns if c[0] == "Volume"]
                    vol = df[vol_cols[0]].dropna() if vol_cols else pd.Series(dtype=float)
                else:
                    vol = df["Volume"].dropna() if "Volume" in df.columns else pd.Series(dtype=float)
                if len(vol) >= 30:
                    adv30 = int(vol.iloc[-30:].mean())
                    result["adv_30"] = adv30
                    # Liquidity thresholds: >500K = good, <100K = illiquid
                    result["adv_signal"] = "bullish" if adv30 >= 500_000 else ("bearish" if adv30 < 100_000 else "neutral")
            except Exception:
                pass

        # --- Put/Call Ratio and IV from options chain ---
        try:
            expirations = ticker.options
            if expirations:
                # Use nearest expiry
                near_exp = expirations[0]
                chain = ticker.option_chain(near_exp)
                calls = chain.calls
                puts = chain.puts

                # PCR by open interest
                total_call_oi = calls["openInterest"].fillna(0).sum()
                total_put_oi  = puts["openInterest"].fillna(0).sum()
                if total_call_oi > 0:
                    pcr = round(total_put_oi / total_call_oi, 2)
                    result["put_call_ratio"] = pcr
                    # PCR > 1.2 → bearish, < 0.7 → bullish, middle = neutral
                    result["pcr_signal"] = "bearish" if pcr > 1.2 else ("bullish" if pcr < 0.7 else "neutral")

                # Near ATM IV from calls
                try:
                    cur_price = float(_get_close_series(df).iloc[-1]) if not close.empty else None
                    if cur_price:
                        calls_sorted = calls.copy()
                        calls_sorted["dist"] = (calls_sorted["strike"] - cur_price).abs()
                        atm_row = calls_sorted.nsmallest(1, "dist")
                        iv_val = atm_row["impliedVolatility"].values[0] if not atm_row.empty else None
                        if iv_val and not math.isnan(iv_val):
                            result["implied_volatility"] = round(float(iv_val) * 100, 1)
                            # IV > 40% = high uncertainty; < 20% = stable
                            result["iv_signal"] = "bearish" if result["implied_volatility"] > 40 else ("bullish" if result["implied_volatility"] < 20 else "neutral")
                except Exception:
                    pass
        except Exception as opt_err:
            print(f"[QuantMetrics] Options error for {symbol}: {opt_err}")

    except Exception as e:
        result["error"] = str(e)
        print(f"[QuantMetrics] Error for {symbol}: {e}")

    return result
