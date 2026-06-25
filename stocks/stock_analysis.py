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
import yfinance as yf
import pandas as pd


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
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}

        def s(key, default=None):
            return _safe(info.get(key, default), default)

        return {
            "symbol": symbol,
            "name": s("longName") or s("shortName") or symbol,
            "current_price": s("currentPrice") or s("regularMarketPrice"),
            "previous_close": s("previousClose"),
            "open": s("open") or s("regularMarketOpen"),
            "day_high": s("dayHigh") or s("regularMarketDayHigh"),
            "day_low": s("dayLow") or s("regularMarketDayLow"),
            "volume": s("volume") or s("regularMarketVolume"),
            "avg_volume": s("averageVolume"),
            "market_cap": s("marketCap"),
            "pe_ratio": s("trailingPE"),
            "forward_pe": s("forwardPE"),
            "eps": s("trailingEps"),
            "dividend_yield": s("dividendYield"),
            "beta": s("beta"),
            "week_52_high": s("fiftyTwoWeekHigh"),
            "week_52_low": s("fiftyTwoWeekLow"),
            "book_value": s("bookValue"),
            "price_to_book": s("priceToBook"),
            "sector": s("sector", "N/A"),
            "industry": s("industry", "N/A"),
            "description": s("longBusinessSummary", ""),
            "currency": s("currency", "INR"),
            # Ownership fields (used by ownership analysis)
            "bid": s("bid"),
            "ask": s("ask"),
            "held_pct_institutions": s("heldPercentInstitutions"),
            "held_pct_insiders": s("heldPercentInsiders"),
            "float_shares": s("floatShares"),
            "shares_outstanding": s("sharesOutstanding"),
            "short_ratio": s("shortRatio"),
        }
    except Exception as e:
        print(f"[StockAnalysis] Fundamentals error for {symbol}: {e}")
        return {"symbol": symbol, "name": symbol, "error": str(e)}


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
        ticker = yf.Ticker(symbol)
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
    Max total score: ±17
    """
    score = 0
    bullish_reasons = []
    bearish_reasons = []

    price = fundamentals.get("current_price")
    week_52_high = fundamentals.get("week_52_high")
    week_52_low = fundamentals.get("week_52_low")
    pe = fundamentals.get("pe_ratio")
    beta = fundamentals.get("beta")
    div_yield = fundamentals.get("dividend_yield")

    # --- Fundamental signals ---
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

    if pe is not None:
        if pe < 15:
            score += 1
            bullish_reasons.append(f"Low P/E ({pe:.1f}x) — stock appears undervalued vs. peers")
        elif pe > 50:
            score -= 1
            bearish_reasons.append(f"High P/E ({pe:.1f}x) — premium valuation, execution risk")

    if div_yield and div_yield > 0.02:
        score += 1
        bullish_reasons.append(f"Healthy dividend yield ({div_yield*100:.1f}%) — passive income")

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

    # --- Ownership ---
    if ownership:
        os_ = ownership.get("score", 0)
        score += os_
        for sig_type, sig_text in ownership.get("signals", []):
            if sig_type == "bullish":
                bullish_reasons.append(sig_text)
            else:
                bearish_reasons.append(sig_text)

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

    # --- Verdict (adjusted for ±17 range) ---
    if score >= 7:
        verdict, color, emoji = "STRONG BUY", "strong-buy", "🚀"
    elif score >= 3:
        verdict, color, emoji = "BUY", "buy", "✅"
    elif score >= -2:
        verdict, color, emoji = "HOLD", "hold", "⚖️"
    elif score >= -5:
        verdict, color, emoji = "AVOID", "avoid", "⚠️"
    else:
        verdict, color, emoji = "STRONG AVOID", "strong-avoid", "🚫"

    return {
        "verdict": verdict,
        "verdict_color": color,
        "verdict_emoji": emoji,
        "score": score,
        "max_score": 17,
        "bullish_reasons": bullish_reasons,
        "bearish_reasons": bearish_reasons,
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
        ticker = yf.Ticker(symbol)

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
