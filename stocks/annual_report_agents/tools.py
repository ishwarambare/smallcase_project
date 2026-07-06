"""
stocks/annual_report_agents/tools.py

Custom CrewAI / LangChain tools used by the 4 agents:

  1. YFinanceTool       — pulls live financial ratios from Yahoo Finance
  2. DuckDuckGoNewsTool — recent news search + basic sentiment scoring
  3. ChromaDBRAGTool    — queries the agents ChromaDB collection for the stock
"""

import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

ROCE_THRESHOLD    = 20.0   # % — buy threshold used by Quant agent
DE_RATIO_MAX      = 1.5    # Debt/Equity — red flag above this value
PE_RATIO_MAX      = 40.0   # P/E — expensive territory above this


# ─── Tool 1: YFinance Financial Ratios ────────────────────────────────────────

def fetch_financial_ratios(symbol: str) -> dict:
    """
    Fetch key financial ratios from Yahoo Finance using yfinance.

    Calculates:
      - ROCE   = EBIT / Capital Employed × 100
      - D/E    = Total Debt / Shareholders Equity
      - P/E    = Current Market Price / EPS (TTM)
      - Revenue CAGR (3yr if available)
      - Market Cap, Net Profit Margin

    Returns a structured dict with all metrics + verdicts.
    """
    try:
        import yfinance as yf

        # For Indian stocks add .NS/.BO suffix if not present
        yf_symbol = symbol
        if not any(s in symbol for s in ['.NS', '.BO', '.', '-']):
            yf_symbol = f"{symbol}.NS"

        ticker = yf.Ticker(yf_symbol)
        info   = ticker.info or {}

        # ── Core ratios from yfinance info dict ──
        pe_ratio        = info.get('trailingPE') or info.get('forwardPE')
        de_ratio        = info.get('debtToEquity')           # already a ratio (not %)
        profit_margin   = info.get('profitMargins')
        revenue_growth  = info.get('revenueGrowth')
        return_on_equity = info.get('returnOnEquity')
        return_on_assets = info.get('returnOnAssets')
        market_cap      = info.get('marketCap')
        total_debt      = info.get('totalDebt')
        total_equity    = info.get('totalStockholderEquity') or info.get('bookValue')
        ebit            = info.get('ebit')
        current_price   = info.get('currentPrice') or info.get('regularMarketPrice')

        # ── ROCE Calculation ──
        # ROCE = EBIT / (Total Assets - Current Liabilities) × 100
        total_assets     = info.get('totalAssets')
        current_liab     = info.get('currentLiabilities')
        if ebit and total_assets and current_liab:
            capital_employed = total_assets - current_liab
            roce = (ebit / capital_employed * 100) if capital_employed > 0 else None
        elif return_on_equity:
            # Approximate: ROCE ≈ ROE × (Equity / Capital)
            roce = return_on_equity * 100
        else:
            roce = None

        # ── D/E Ratio normalization ──
        # yfinance returns D/E as percentage (e.g. 45.32 means 0.4532)
        if de_ratio and de_ratio > 10:
            de_ratio = de_ratio / 100

        # ── Revenue CAGR (3 year from financials) ──
        revenue_cagr = None
        try:
            financials = ticker.financials
            if financials is not None and not financials.empty:
                rev_row = financials.loc['Total Revenue'] if 'Total Revenue' in financials.index else None
                if rev_row is not None and len(rev_row) >= 3:
                    rev_latest = float(rev_row.iloc[0])
                    rev_3yr    = float(rev_row.iloc[min(2, len(rev_row)-1)])
                    if rev_3yr > 0:
                        revenue_cagr = ((rev_latest / rev_3yr) ** (1/3) - 1) * 100
        except Exception:
            pass

        # ── Build verdicts ──
        roce_verdict = None
        if roce is not None:
            if roce >= ROCE_THRESHOLD:
                roce_verdict = f"✅ STRONG — {roce:.1f}% exceeds {ROCE_THRESHOLD}% threshold"
            elif roce >= 12:
                roce_verdict = f"⚠️  MODERATE — {roce:.1f}% below {ROCE_THRESHOLD}% threshold"
            else:
                roce_verdict = f"❌ WEAK — {roce:.1f}% well below {ROCE_THRESHOLD}% threshold"

        de_verdict = None
        if de_ratio is not None:
            if de_ratio <= 0.5:
                de_verdict = f"✅ LOW DEBT — D/E ratio {de_ratio:.2f}"
            elif de_ratio <= DE_RATIO_MAX:
                de_verdict = f"⚠️  MODERATE DEBT — D/E ratio {de_ratio:.2f}"
            else:
                de_verdict = f"❌ HIGH DEBT — D/E ratio {de_ratio:.2f} exceeds {DE_RATIO_MAX}"

        pe_verdict = None
        if pe_ratio is not None:
            if pe_ratio <= 20:
                pe_verdict = f"✅ CHEAP — P/E {pe_ratio:.1f}x"
            elif pe_ratio <= PE_RATIO_MAX:
                pe_verdict = f"⚠️  FAIR — P/E {pe_ratio:.1f}x"
            else:
                pe_verdict = f"❌ EXPENSIVE — P/E {pe_ratio:.1f}x exceeds {PE_RATIO_MAX}x"

        return {
            'symbol':           yf_symbol,
            'current_price':    current_price,
            'market_cap':       market_cap,
            'pe_ratio':         round(pe_ratio, 2) if pe_ratio else None,
            'pe_verdict':       pe_verdict,
            'roce':             round(roce, 2) if roce else None,
            'roce_verdict':     roce_verdict,
            'de_ratio':         round(de_ratio, 2) if de_ratio else None,
            'de_verdict':       de_verdict,
            'profit_margin_pct': round(profit_margin * 100, 2) if profit_margin else None,
            'revenue_cagr_pct': round(revenue_cagr, 2) if revenue_cagr else None,
            'roe_pct':          round(return_on_equity * 100, 2) if return_on_equity else None,
            'roa_pct':          round(return_on_assets * 100, 2) if return_on_assets else None,
            'roce_threshold':   ROCE_THRESHOLD,
            'error':            None,
        }

    except Exception as e:
        logger.error(f"[YFinance] {symbol}: {e}", exc_info=True)
        return {'symbol': symbol, 'error': str(e)}


# ─── Tool 2: DuckDuckGo News + Sentiment ──────────────────────────────────────

POSITIVE_WORDS = [
    'growth', 'profit', 'record', 'beat', 'strong', 'surge', 'expand',
    'deal', 'win', 'upgrade', 'bullish', 'outperform', 'dividend',
    'revenue', 'acquisition', 'partnership', 'increase', 'milestone',
]
NEGATIVE_WORDS = [
    'loss', 'decline', 'fall', 'miss', 'weak', 'debt', 'default',
    'lawsuit', 'fraud', 'scandal', 'downgrade', 'bearish', 'underperform',
    'layoff', 'restructure', 'investigation', 'concern', 'risk', 'drop',
]


def _score_sentiment(text: str) -> float:
    """
    Simple lexical sentiment score in [-1.0, 1.0].
    Positive words push towards +1, negative words towards -1.
    """
    text_lower = text.lower()
    pos = sum(1 for w in POSITIVE_WORDS if w in text_lower)
    neg = sum(1 for w in NEGATIVE_WORDS if w in text_lower)
    total = pos + neg
    if total == 0:
        return 0.0
    return round((pos - neg) / total, 3)


def fetch_news_sentiment(symbol: str, company_name: str = None) -> dict:
    """
    Searches DuckDuckGo for recent news about the stock and scores sentiment.

    Returns:
        {
            'headlines': [{'title': ..., 'url': ..., 'sentiment': ...}],
            'avg_sentiment': float,   # -1.0 to +1.0
            'sentiment_label': str,   # BULLISH / NEUTRAL / BEARISH
            'summary': str,
            'error': str | None
        }
    """
    try:
        from ddgs import DDGS

        search_query = f"{company_name or symbol} stock news earnings 2024 2025"

        headlines = []
        with DDGS() as ddgs:
            results = list(ddgs.text(
                keywords=search_query,
                max_results=10,
                timelimit='m',   # past month
            ))

        for r in results[:8]:
            title = r.get('title', '')
            url   = r.get('href', r.get('url', ''))
            body  = r.get('body', '')
            text  = f"{title} {body}"
            score = _score_sentiment(text)
            headlines.append({
                'title':     title[:200],
                'url':       url,
                'snippet':   body[:300] if body else '',
                'sentiment': score,
                'label':     'POSITIVE' if score > 0.1 else ('NEGATIVE' if score < -0.1 else 'NEUTRAL'),
            })

        if not headlines:
            return {
                'headlines': [],
                'avg_sentiment': 0.0,
                'sentiment_label': 'NEUTRAL',
                'summary': 'No recent news found.',
                'error': None,
            }

        avg_sentiment = round(sum(h['sentiment'] for h in headlines) / len(headlines), 3)
        if avg_sentiment > 0.1:
            label = 'BULLISH 🟢'
        elif avg_sentiment < -0.1:
            label = 'BEARISH 🔴'
        else:
            label = 'NEUTRAL ⚪'

        positive_count = sum(1 for h in headlines if h['label'] == 'POSITIVE')
        negative_count = sum(1 for h in headlines if h['label'] == 'NEGATIVE')

        summary = (
            f"Analyzed {len(headlines)} recent news articles. "
            f"{positive_count} positive, {negative_count} negative. "
            f"Overall sentiment: {label} (score: {avg_sentiment:+.2f})."
        )

        return {
            'headlines':      headlines,
            'avg_sentiment':  avg_sentiment,
            'sentiment_label': label,
            'summary':        summary,
            'error':          None,
        }

    except Exception as e:
        logger.error(f"[News] {symbol}: {e}", exc_info=True)
        return {
            'headlines': [],
            'avg_sentiment': 0.0,
            'sentiment_label': 'NEUTRAL',
            'summary': 'News fetch failed.',
            'error': str(e),
        }


# ─── Tool 3: ChromaDB RAG Query ───────────────────────────────────────────────

def query_governance_rag(symbol: str, questions: list[str] = None) -> dict:
    """
    Queries the ChromaDB 'agents_{symbol}' collection with governance-focused
    questions about management commentary and corporate governance.

    Args:
        symbol: Stock ticker
        questions: List of questions to ask (defaults to standard governance checklist)

    Returns:
        {'chunks': list[str], 'raw_context': str, 'error': str|None}
    """
    from .pdf_ingestion import query_agents_collection

    if not questions:
        questions = [
            "What did management say about future revenue growth and guidance?",
            "What are the company's strategic plans for capacity expansion?",
            "Are there any corporate governance concerns, related party transactions, or red flags?",
            "What is the management commentary on profitability and margins?",
            "What risks does management highlight for the business?",
            "What is the CEO/MD's message about the company's outlook?",
        ]

    all_chunks = []
    for q in questions[:4]:  # limit to 4 queries to avoid too many embeddings
        chunks = query_agents_collection(symbol, q, n_results=3)
        all_chunks.extend(chunks)

    # Deduplicate while preserving order
    seen     = set()
    unique   = []
    for c in all_chunks:
        key = c[:100]
        if key not in seen:
            seen.add(key)
            unique.append(c)

    raw_context = '\n\n---\n\n'.join(unique[:12])  # max 12 unique chunks

    return {
        'chunks':      unique[:12],
        'raw_context': raw_context,
        'error':       None if unique else 'No documents indexed for this stock yet.',
    }
