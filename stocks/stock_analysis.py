"""
stocks/stock_analysis.py

Fetches fundamentals and computes technical indicators for a stock.
Returns a recommendation: STRONG BUY / BUY / HOLD / AVOID / STRONG AVOID
"""

import math
import yfinance as yf
import pandas as pd


def get_stock_fundamentals(symbol: str) -> dict:
    """Fetch key fundamental data from Yahoo Finance."""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}

        def safe(key, default=None):
            val = info.get(key, default)
            if val is None or (isinstance(val, float) and math.isnan(val)):
                return default
            return val

        return {
            "symbol": symbol,
            "name": safe("longName") or safe("shortName") or symbol,
            "current_price": safe("currentPrice") or safe("regularMarketPrice"),
            "previous_close": safe("previousClose"),
            "open": safe("open") or safe("regularMarketOpen"),
            "day_high": safe("dayHigh") or safe("regularMarketDayHigh"),
            "day_low": safe("dayLow") or safe("regularMarketDayLow"),
            "volume": safe("volume") or safe("regularMarketVolume"),
            "avg_volume": safe("averageVolume"),
            "market_cap": safe("marketCap"),
            "pe_ratio": safe("trailingPE"),
            "forward_pe": safe("forwardPE"),
            "eps": safe("trailingEps"),
            "dividend_yield": safe("dividendYield"),
            "beta": safe("beta"),
            "week_52_high": safe("fiftyTwoWeekHigh"),
            "week_52_low": safe("fiftyTwoWeekLow"),
            "book_value": safe("bookValue"),
            "price_to_book": safe("priceToBook"),
            "sector": safe("sector", "N/A"),
            "industry": safe("industry", "N/A"),
            "description": safe("longBusinessSummary", ""),
            "currency": safe("currency", "INR"),
        }
    except Exception as e:
        print(f"[StockAnalysis] Error fetching fundamentals for {symbol}: {e}")
        return {"symbol": symbol, "name": symbol, "error": str(e)}


def _get_close_series(df: pd.DataFrame, symbol: str) -> pd.Series:
    """Extract Close price series from a yfinance DataFrame (handles MultiIndex)."""
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


def get_technical_indicators(symbol: str) -> dict:
    """
    Compute technical indicators from 1-year historical data.
    Returns a dict of indicator values + signals.
    """
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
        close = _get_close_series(df, symbol)

        if close.empty or len(close) < 30:
            result["error"] = "Not enough historical data"
            return result

        price = float(close.iloc[-1])

        # --- RSI (14-day) ---
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, float("nan"))
        rsi_series = 100 - (100 / (1 + rs))
        rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty else None

        result["rsi"] = round(rsi, 1) if rsi else None
        if rsi:
            if rsi < 30:
                result["rsi_signal"] = "bullish"      # Oversold → Buy
            elif rsi > 70:
                result["rsi_signal"] = "bearish"     # Overbought → Sell
            else:
                result["rsi_signal"] = "neutral"

        # --- SMA 50 ---
        if len(close) >= 50:
            sma50 = float(close.rolling(50).mean().iloc[-1])
            result["sma50"] = round(sma50, 2)
            result["sma50_signal"] = "bullish" if price > sma50 else "bearish"

        # --- SMA 200 ---
        if len(close) >= 200:
            sma200 = float(close.rolling(200).mean().iloc[-1])
            result["sma200"] = round(sma200, 2)
            result["sma200_signal"] = "bullish" if price > sma200 else "bearish"

        # --- MACD (12, 26, 9) ---
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_val = float(macd_line.iloc[-1])
        signal_val = float(signal_line.iloc[-1])
        result["macd"] = round(macd_val, 4)
        result["macd_signal_line"] = round(signal_val, 4)
        result["macd_signal"] = "bullish" if macd_val > signal_val else "bearish"

        # --- Bollinger Bands (20-day, 2σ) ---
        if len(close) >= 20:
            sma20 = close.rolling(20).mean()
            std20 = close.rolling(20).std()
            bb_upper = float((sma20 + 2 * std20).iloc[-1])
            bb_lower = float((sma20 - 2 * std20).iloc[-1])
            result["bb_upper"] = round(bb_upper, 2)
            result["bb_lower"] = round(bb_lower, 2)
            bb_range = bb_upper - bb_lower
            if bb_range > 0:
                position = (price - bb_lower) / bb_range
                if position < 0.2:
                    result["bb_signal"] = "bullish"   # Near lower band
                elif position > 0.8:
                    result["bb_signal"] = "bearish"  # Near upper band
                else:
                    result["bb_signal"] = "neutral"

        # --- Volume trend ---
        try:
            if isinstance(df.columns, pd.MultiIndex):
                vol_cols = [c for c in df.columns if c[0] == "Volume"]
                vol_series = df[vol_cols[0]].dropna() if vol_cols else pd.Series(dtype=float)
            else:
                vol_series = df["Volume"].dropna() if "Volume" in df.columns else pd.Series(dtype=float)

            if len(vol_series) >= 10:
                avg_vol_10 = float(vol_series.iloc[-10:].mean())
                current_vol = float(vol_series.iloc[-1])
                result["avg_volume_10"] = int(avg_vol_10)
                result["current_volume"] = int(current_vol)
                result["volume_signal"] = "bullish" if current_vol > avg_vol_10 * 1.2 else "neutral"
        except Exception:
            pass

    except Exception as e:
        result["error"] = str(e)
        print(f"[StockAnalysis] Error computing indicators for {symbol}: {e}")

    return result


def get_buy_recommendation(fundamentals: dict, indicators: dict) -> dict:
    """
    Score all signals and return a recommendation with reasons.
    Score: +1 bullish, -1 bearish, 0 neutral per indicator.
    """
    score = 0
    bullish_reasons = []
    bearish_reasons = []

    current_price = fundamentals.get("current_price")
    week_52_high = fundamentals.get("week_52_high")
    week_52_low = fundamentals.get("week_52_low")
    pe = fundamentals.get("pe_ratio")
    beta = fundamentals.get("beta")
    div_yield = fundamentals.get("dividend_yield")

    # --- Fundamental signals ---
    if current_price and week_52_low and week_52_high:
        range_52 = week_52_high - week_52_low
        if range_52 > 0:
            pos_in_range = (current_price - week_52_low) / range_52
            if pos_in_range < 0.35:
                score += 1
                bullish_reasons.append("Trading near 52-week low — potential value opportunity")
            elif pos_in_range > 0.85:
                score -= 1
                bearish_reasons.append("Trading near 52-week high — limited upside in short term")

    if pe is not None:
        if pe < 15:
            score += 1
            bullish_reasons.append(f"Low P/E ratio ({pe:.1f}) — stock may be undervalued")
        elif pe > 50:
            score -= 1
            bearish_reasons.append(f"High P/E ratio ({pe:.1f}) — stock may be overvalued")

    if div_yield and div_yield > 0.02:
        score += 1
        bullish_reasons.append(f"Healthy dividend yield ({div_yield * 100:.1f}%) — income stock")

    if beta is not None:
        if beta < 0.8:
            bullish_reasons.append(f"Low Beta ({beta:.2f}) — defensive, low market risk")
        elif beta > 1.5:
            bearish_reasons.append(f"High Beta ({beta:.2f}) — highly volatile, high risk")

    # --- Technical signals ---
    rsi = indicators.get("rsi")
    rsi_signal = indicators.get("rsi_signal", "neutral")
    if rsi_signal == "bullish":
        score += 1
        bullish_reasons.append(f"RSI at {rsi} — oversold, potential reversal upward")
    elif rsi_signal == "bearish":
        score -= 1
        bearish_reasons.append(f"RSI at {rsi} — overbought, potential pullback risk")

    sma50_signal = indicators.get("sma50_signal", "neutral")
    sma50 = indicators.get("sma50")
    if sma50_signal == "bullish":
        score += 1
        bullish_reasons.append(f"Price above 50-day SMA (₹{sma50}) — short-term uptrend")
    elif sma50_signal == "bearish":
        score -= 1
        bearish_reasons.append(f"Price below 50-day SMA (₹{sma50}) — short-term downtrend")

    sma200_signal = indicators.get("sma200_signal", "neutral")
    sma200 = indicators.get("sma200")
    if sma200_signal == "bullish":
        score += 1
        bullish_reasons.append(f"Price above 200-day SMA (₹{sma200}) — long-term uptrend")
    elif sma200_signal == "bearish":
        score -= 1
        bearish_reasons.append(f"Price below 200-day SMA (₹{sma200}) — long-term downtrend")

    macd_signal = indicators.get("macd_signal", "neutral")
    if macd_signal == "bullish":
        score += 1
        bullish_reasons.append("MACD above signal line — bullish momentum")
    elif macd_signal == "bearish":
        score -= 1
        bearish_reasons.append("MACD below signal line — bearish momentum")

    bb_signal = indicators.get("bb_signal", "neutral")
    if bb_signal == "bullish":
        score += 1
        bullish_reasons.append("Price near lower Bollinger Band — potential bounce zone")
    elif bb_signal == "bearish":
        score -= 1
        bearish_reasons.append("Price near upper Bollinger Band — may face resistance")

    if indicators.get("volume_signal") == "bullish":
        score += 1
        bullish_reasons.append("Volume spike above 10-day average — strong buying interest")

    # --- Final verdict ---
    if score >= 4:
        verdict = "STRONG BUY"
        verdict_color = "strong-buy"
        verdict_emoji = "🚀"
    elif score >= 2:
        verdict = "BUY"
        verdict_color = "buy"
        verdict_emoji = "✅"
    elif score >= -1:
        verdict = "HOLD"
        verdict_color = "hold"
        verdict_emoji = "⚖️"
    elif score >= -3:
        verdict = "AVOID"
        verdict_color = "avoid"
        verdict_emoji = "⚠️"
    else:
        verdict = "STRONG AVOID"
        verdict_color = "strong-avoid"
        verdict_emoji = "🚫"

    return {
        "verdict": verdict,
        "verdict_color": verdict_color,
        "verdict_emoji": verdict_emoji,
        "score": score,
        "max_score": 9,
        "bullish_reasons": bullish_reasons,
        "bearish_reasons": bearish_reasons,
    }
