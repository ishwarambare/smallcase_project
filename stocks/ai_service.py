"""
AI Service Module for Chat Support
Supports both Groq (Llama 3) and Google Gemini with configurable provider selection.
"""

import os
import json
from abc import ABC, abstractmethod
from django.conf import settings


class AIProvider(ABC):
    """Abstract base class for AI providers"""
    
    @abstractmethod
    def generate_response(self, user_message: str, context: dict) -> str:
        """Generate a response based on user message and context"""
        pass
    
    def build_system_prompt(self, context: dict) -> str:
        """Build system prompt with user's portfolio context"""
        
        # Debug: Print context
        print(f"[AI Service] build_system_prompt - context baskets count: {len(context.get('baskets', []))}")
        
        # Check if user is admin
        is_admin = context.get('is_admin', False)
        has_baskets = bool(context.get('baskets'))
        
        print(f"[AI Service] has_baskets: {has_baskets}, is_admin: {is_admin}")
        
        # Build baskets info only if user has baskets
        baskets_info = ""
        total_info = ""
        
        if has_baskets:
            baskets_info = "\n\nUser's Investment Baskets:\n"
            for basket in context['baskets']:
                baskets_info += f"""
- Basket: {basket['name']}
  - Investment: ₹{basket['investment']:,.2f}
  - Current Value: ₹{basket['current_value']:,.2f}
  - Profit/Loss: ₹{basket['profit_loss']:,.2f} ({basket['profit_loss_percent']:.2f}%)
  - Stocks: {', '.join([f"{s['symbol']} ({s['weight']}%)" for s in basket['stocks']])}
"""
            
            if context.get('total_investment', 0) > 0:
                total_info = f"""
Total Portfolio Summary:
- Total Investment: ₹{context['total_investment']:,.2f}
- Total Current Value: ₹{context['total_value']:,.2f}
- Total Profit/Loss: ₹{context['total_profit_loss']:,.2f} ({context['total_profit_loss_percent']:.2f}%)
"""
        
        # Different prompts based on user type and basket status
        if is_admin:
            role_info = """
You are an AI assistant for the Smallcase platform admin team.
The current user is an ADMIN/SUPERUSER of the platform.
You can help them with:
1. General questions about the platform
2. Investment concepts and strategies
3. Platform features and functionality
4. Any administrative queries

If they ask about their personal portfolio and they don't have baskets, let them know they haven't created any baskets yet.
"""
        elif has_baskets:
            role_info = """
You are a helpful AI investment assistant for a stock portfolio management app called "Smallcase". 
Your role is to:
1. Answer questions about the user's investment portfolios and baskets
2. Provide insights about their stock holdings using fundamental analysis
3. Explain investment concepts in simple terms
4. Help users understand their portfolio performance
5. Suggest portfolio optimization when asked

IMPORTANT: Only discuss the user's baskets and investments that are provided in the context.
Do not make up or assume any investment data.

GOLDEN RULES FOR STOCK SELECTION:
Always keep these fundamental principles in mind when advising or suggesting any stocks or baskets:
1. Avoid Relying on Tips: Encourage learning fundamental analysis rather than blindly following tips.
2. Check Revenue & Profit Growth: Ensure both revenue (top line) and net income (bottom line) grow consistently YoY.
3. Analyze Assets vs. Liabilities: Total assets must be significantly higher than liabilities, with assets increasing over time.
4. Monitor Cash Flow: Ensure the company has positive and growing Free Cash Flow.
5. Read Annual Reports: Understand future growth plans by reading reports.
6. Identify Red Flags: Dropping revenues, negative cash flows, low promoter holdings, and massive debt/liabilities are red flags and should be avoided.
7. Core Valuation Metrics: Lower P/E (ideally under 20 compared to industry), low P/B (1 or 2 is very good), Debt-to-Equity (ideal below 1.0 or 2.0), and healthy Dividend Yield. Price below Graham Intrinsic Value is undervalued.
8. Promoter and Institutional Shareholding: High combined holdings by Promoters, DIIs, and FIIs (ideally > 50-60%) is a strong positive signal.
"""
        else:
            role_info = """
You are a helpful AI assistant for a stock portfolio management app called "Smallcase". 
The user does NOT have any investment baskets yet.

Your role is to:
1. Welcome them and explain how to create a basket
2. Explain investment concepts in simple terms (like fundamental analysis and the 8 Golden Rules of stock selection: revenue/profit growth, assets > liabilities, positive cash flow, low debt-to-equity, price < intrinsic value, high promoter holdings, and avoiding tips/hype)
3. Help them understand the platform features
4. Encourage them to create their first investment basket

IMPORTANT: Do NOT provide any portfolio or basket information since the user has no baskets.
If they ask about their portfolio, politely let them know they haven't created any baskets yet and guide them to create one.
"""
        
        system_prompt = f"""{role_info}

Be friendly, professional, and concise. Use ₹ for Indian Rupees.
If you don't know something specific, say so and offer to connect them with human support.

GOLDEN RULES OF RETREAT:
When suggest stock baskets or evaluating specific symbols, always evaluate them against the 8 Golden Rules of Stock Selection (Revenue/Profit Growth, Assets vs Liabilities, Free Cash Flow, Graham Intrinsic Value, P/E & P/B, Debt-to-Equity, Promoter Holdings). Remind the user about the importance of fundamental checklist check.

{baskets_info}
{total_info}

Current User: {context.get('user_email', 'Guest')}
User Name: {context.get('user_name', 'User')}
Is Admin: {'Yes' if is_admin else 'No'}
Has Baskets: {'Yes' if has_baskets else 'No'}
"""
        return system_prompt


class GroqProvider(AIProvider):
    """Groq AI Provider using Llama 3"""
    
    def __init__(self):
        from groq import Groq
        api_key = os.environ.get('GROQ_API_KEY', getattr(settings, 'GROQ_API_KEY', None))
        if not api_key:
            raise ValueError("GROQ_API_KEY is not set")
        self.client = Groq(api_key=api_key)
        self.model = os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile')
    
    def generate_response(self, user_message: str, context: dict) -> str:
        try:
            system_prompt = self.build_system_prompt(context)
            
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                model=self.model,
                temperature=0.7,
                max_tokens=1024,
            )
            
            return chat_completion.choices[0].message.content
            
        except Exception as e:
            print(f"Groq API Error: {e}")
            return f"I'm having trouble connecting right now. Please try again or contact human support. Error: {str(e)}"


class GeminiProvider(AIProvider):
    """Google Gemini AI Provider"""
    
    def __init__(self):
        import google.generativeai as genai
        api_key = os.environ.get('GEMINI_API_KEY', getattr(settings, 'GEMINI_API_KEY', None))
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set")
        genai.configure(api_key=api_key)
        model_name = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
        self.model = genai.GenerativeModel(model_name)
    
    def generate_response(self, user_message: str, context: dict) -> str:
        try:
            system_prompt = self.build_system_prompt(context)
            
            full_prompt = f"{system_prompt}\n\nUser: {user_message}\n\nAssistant:"
            
            response = self.model.generate_content(
                full_prompt,
                generation_config={
                    "temperature": 0.7,
                    "max_output_tokens": 1024,
                }
            )
            
            return response.text
            
        except Exception as e:
            print(f"Gemini API Error: {e}")
            return f"I'm having trouble connecting right now. Please try again or contact human support. Error: {str(e)}"


class AIService:
    """Main AI Service that manages provider selection"""
    
    _instance = None
    _provider = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_provider(self) -> AIProvider:
        """Get the configured AI provider"""
        provider_name = os.environ.get('AI_PROVIDER', getattr(settings, 'AI_PROVIDER', 'groq')).lower()
        
        if provider_name == 'gemini':
            return GeminiProvider()
        else:  # Default to Groq
            return GroqProvider()
    
    def generate_response(self, user_message: str, user) -> str:
        """Generate AI response with user's portfolio context"""
        from .models import Basket
        
        print(f"[AI Service] generate_response called for user: {user.email if user else 'None'}")
        
        # Build context from user's baskets
        context = {
            'user_email': user.email if user else 'Guest',
            'user_name': user.username or user.email.split('@')[0] if user else 'User',
            'is_admin': user.is_staff or user.is_superuser if user else False,
            'baskets': [],
            'total_investment': 0,
            'total_value': 0,
            'total_profit_loss': 0,
            'total_profit_loss_percent': 0,
        }
        
        if user and user.is_authenticated:
            # Get only the user's baskets
            try:
                baskets = Basket.objects.filter(user=user).prefetch_related('items__stock')
                print(f"[AI Service] Found {baskets.count()} baskets for user {user.email}")
                
                for basket in baskets:
                    print(f"[AI Service] Processing basket: {basket.name}")
                    try:
                        current_value = basket.get_total_value() or 0
                        profit_loss = basket.get_profit_loss() or 0
                        profit_loss_percent = basket.get_profit_loss_percentage() or 0
                        
                        basket_data = {
                            'name': basket.name or 'Unnamed Basket',
                            'investment': float(basket.investment_amount or 0),
                            'current_value': float(current_value),
                            'profit_loss': float(profit_loss),
                            'profit_loss_percent': float(profit_loss_percent),
                            'stocks': []
                        }
                        
                        for item in basket.items.all():
                            try:
                                basket_data['stocks'].append({
                                    'symbol': item.stock.symbol if item.stock else 'N/A',
                                    'name': item.stock.name if item.stock else 'Unknown',
                                    'weight': float(item.weight_percentage or 0),
                                    'quantity': float(item.quantity or 0),
                                    'purchase_price': float(item.purchase_price or 0),
                                    'current_price': float(item.stock.current_price) if item.stock and item.stock.current_price else 0,
                                })
                            except Exception as item_err:
                                print(f"[AI Service] Error processing basket item: {item_err}")
                                import traceback
                                traceback.print_exc()
                                continue
                        
                        print(f"[AI Service] About to append basket_data for: {basket_data['name']}")
                        context['baskets'].append(basket_data)
                        print(f"[AI Service] Successfully appended! Total baskets in context: {len(context['baskets'])}")
                        context['total_investment'] += basket_data['investment']
                        context['total_value'] += basket_data['current_value']
                    except Exception as basket_err:
                        print(f"[AI Service] Error processing basket {basket.id}: {basket_err}")
                        import traceback
                        traceback.print_exc()
                        continue
                
                context['total_profit_loss'] = context['total_value'] - context['total_investment']
                if context['total_investment'] > 0:
                    context['total_profit_loss_percent'] = (context['total_profit_loss'] / context['total_investment']) * 100
            except Exception as e:
                print(f"Error fetching baskets: {e}")
                # Continue with empty baskets
        
        try:
            provider = self.get_provider()
            return provider.generate_response(user_message, context)
        except ValueError as e:
            # API key not configured - return a helpful message
            return self._get_fallback_response(user_message, context)
        except Exception as e:
            print(f"AI Service Error: {e}")
            return self._get_fallback_response(user_message, context)
    
    def _get_fallback_response(self, user_message: str, context: dict) -> str:
        """Fallback response when AI is not configured"""
        user_message_lower = user_message.lower()
        is_admin = context.get('is_admin', False)
        has_baskets = bool(context.get('baskets'))
        
        # Simple rule-based responses for common questions
        if any(word in user_message_lower for word in ['hi', 'hello', 'hey']):
            name = context.get('user_name', 'there')
            if is_admin:
                return f"Hello {name}! 👋 Welcome back, Admin! I'm your AI assistant. How can I help you today?"
            elif has_baskets:
                return f"Hello {name}! 👋 I'm your portfolio assistant. How can I help you today? You can ask me about your baskets, stock performance, or investment strategies."
            else:
                return f"Hello {name}! 👋 Welcome to Smallcase! I noticed you haven't created any investment baskets yet. Would you like me to guide you on how to create your first basket?"
        
        elif any(word in user_message_lower for word in ['portfolio', 'basket', 'investment', 'stock']):
            if has_baskets:
                total = context.get('total_investment', 0)
                value = context.get('total_value', 0)
                pl = context.get('total_profit_loss', 0)
                pl_pct = context.get('total_profit_loss_percent', 0)
                emoji = "📈" if pl >= 0 else "📉"
                
                return f"""Here's your portfolio summary {emoji}:

💰 Total Investment: ₹{total:,.2f}
💵 Current Value: ₹{value:,.2f}
{'✅' if pl >= 0 else '❌'} Profit/Loss: ₹{pl:,.2f} ({pl_pct:.2f}%)

You have {len(context['baskets'])} basket(s). Would you like details on a specific one?"""
            else:
                return """You don't have any investment baskets yet! 📊

To create your first basket:
1. Go to the **Baskets** section
2. Click **Create New Basket**
3. Add stocks and set your investment amount

Would you like me to explain more about how baskets work? 🚀"""
        
        elif 'help' in user_message_lower:
            if has_baskets:
                return """I can help you with:
📊 Portfolio performance and analysis
💼 Basket details and stock holdings
📈 Profit/Loss calculations
💡 Investment insights

Just ask me anything about your investments!"""
            else:
                return """I can help you with:
🆕 Creating your first investment basket
📚 Understanding investment concepts
🎯 Platform features and navigation
💡 Getting started tips

What would you like to know?"""
        
        else:
            if is_admin:
                return "Thanks for your message! As an admin, you have access to all platform features. How can I assist you today? 🛠️"
            else:
                return "Thanks for your message! I'm here to help with your investment queries. A human support agent will review this and get back to you soon. 🙏"


# Singleton instance
ai_service = AIService()


# ============================================================
# Stock Analysis AI Service — Separate from chat AI
# ============================================================

class StockAnalysisAIService:
    """
    LLM-powered service for:
      1. Generating a 3-paragraph fundamental summary (Overview / Bullish / Risks)
      2. Enhancing news sentiment with LLM classification
      3. Synthesizing portfolio rebalancing recommendations
    Uses the same AI_PROVIDER env setting as the chat service.
    Results are cached in Django's cache for 6 hours.
    """

    CACHE_TTL = 6 * 60 * 60  # 6 hours

    def _call_llm(self, prompt: str, max_tokens: int = 800) -> str | None:
        """Internal helper — calls the configured LLM provider."""
        provider_name = os.environ.get('AI_PROVIDER', 'groq').lower()
        try:
            if provider_name == 'gemini':
                import google.generativeai as genai
                api_key = os.environ.get('GEMINI_API_KEY', '')
                if not api_key:
                    return None
                genai.configure(api_key=api_key)
                model_name = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
                model = genai.GenerativeModel(model_name)
                resp = model.generate_content(
                    prompt,
                    generation_config={"temperature": 0.4, "max_output_tokens": max_tokens}
                )
                return resp.text.strip()
            else:  # groq default
                from groq import Groq
                api_key = os.environ.get('GROQ_API_KEY', '')
                if not api_key:
                    return None
                client = Groq(api_key=api_key)
                model = os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile')
                resp = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=model,
                    temperature=0.4,
                    max_tokens=max_tokens,
                )
                return resp.choices[0].message.content.strip()
        except Exception as e:
            print(f"[StockAnalysisAI] LLM call error: {e}")
            return None

    def generate_fundamental_summary(self, symbol: str, fundamentals: dict,
                                     indicators: dict, recommendation: dict) -> dict:
        """
        Calls LLM to produce a structured 3-section summary for a stock.
        Returns dict with keys: overview, bullish_summary, risk_summary, cached
        """
        from django.core.cache import cache
        cache_key = f'ai_fund_summary_{symbol}'
        cached = cache.get(cache_key)
        if cached:
            cached['cached'] = True
            return cached

        # Build a compact data block for the LLM
        price   = fundamentals.get('current_price', 'N/A')
        pe      = fundamentals.get('pe_ratio', 'N/A')
        fwd_pe  = fundamentals.get('forward_pe', 'N/A')
        mcap    = fundamentals.get('market_cap', 'N/A')
        beta    = fundamentals.get('beta', 'N/A')
        div_y   = fundamentals.get('dividend_yield', 'N/A')
        pb      = fundamentals.get('price_to_book', 'N/A')
        eps     = fundamentals.get('eps', 'N/A')
        sector  = fundamentals.get('sector', 'N/A')
        desc    = (fundamentals.get('description') or '')[:500]
        verdict = recommendation.get('verdict', 'HOLD')
        score   = recommendation.get('score', 0)
        max_score = recommendation.get('max_score', 25)
        bull_r  = '; '.join(recommendation.get('bullish_reasons', [])[:5])
        bear_r  = '; '.join(recommendation.get('bearish_reasons', [])[:5])
        rsi     = indicators.get('rsi', 'N/A')
        sma50s  = indicators.get('sma50_signal', 'N/A')
        macds   = indicators.get('macd_signal', 'N/A')
        
        # New scorecard fields
        rev_g   = fundamentals.get('revenue_growth_yoy', 'N/A')
        ear_g   = fundamentals.get('earnings_growth_yoy', 'N/A')
        debt_eq = fundamentals.get('debt_to_equity', 'N/A')
        fcf     = fundamentals.get('fcf_history', [])
        fcf_str = fcf[0] if fcf else 'N/A'
        graham  = fundamentals.get('intrinsic_value', 'N/A')
        red_f   = '; '.join(recommendation.get('red_flags', [])) or 'None'

        prompt = f"""You are a senior equity research analyst. Analyze {symbol} ({fundamentals.get('name', symbol)}) 
and write a concise, factual 3-section report. Use data provided — do NOT make up numbers.

STOCK DATA:
- Sector: {sector}
- Price: ₹{price} | P/E: {pe} | Fwd P/E: {fwd_pe} | P/B: {pb}
- Market Cap: {mcap} | EPS: {eps} | Dividend Yield: {div_y} | Beta: {beta}
- Debt-to-Equity: {debt_eq}
- YoY Revenue Growth: {rev_g}% | YoY Net Income Growth: {ear_g}%
- Latest Free Cash Flow: {fcf_str}
- Graham Intrinsic Value: ₹{graham}
- RSI: {rsi} | SMA50 trend: {sma50s} | MACD: {macds}
- AI Fundamental Score: {score}/{max_score} → Verdict: {verdict}
- Critical Red Flags: {red_f}
- Bullish signals: {bull_r}
- Risk signals: {bear_r}
- Business: {desc}

GOLDEN RULES CRITERIA FOR EVALUATION:
1. Growth: Check if both Revenue and Profit are growing consistently YoY.
2. Stability: Assets should exceed Liabilities. Debt-to-Equity should be under 1.0 or 2.0.
3. Cash Flow: Free Cash Flow must be positive.
4. Valuation: Price should ideally be below the Graham Intrinsic Value.
5. Identify Red Flags (dropping revenue/profit, negative cash flow, massive debt) and highlight them.

Write EXACTLY 3 sections with these headings (use ## heading syntax):
## Business Overview
(2-3 sentences summarizing the company's core business and competitive position)

## Bullish Signals
(3-4 bullet points starting with ✅ highlighting the strongest reasons to be optimistic, including growth, FCF, and low valuations if applicable)

## Key Risks
(3-4 bullet points starting with ⚠️ highlighting the main risks an investor should watch, especially any active Red Flags, dropping metrics, or high debt)

Keep each section concise. Use ₹ for prices. Be factual and balanced."""

        raw = self._call_llm(prompt, max_tokens=600)
        if not raw:
            return {"overview": None, "bullish_summary": None, "risk_summary": None, "cached": False}

        # Parse sections
        result = {"overview": "", "bullish_summary": "", "risk_summary": "", "cached": False}
        current = None
        lines = raw.split('\n')
        for line in lines:
            line_strip = line.strip()
            if '## Business Overview' in line_strip:
                current = 'overview'
            elif '## Bullish Signals' in line_strip:
                current = 'bullish_summary'
            elif '## Key Risks' in line_strip:
                current = 'risk_summary'
            elif current and line_strip:
                result[current] = result[current] + line_strip + '\n'

        # Trim whitespace
        for k in ['overview', 'bullish_summary', 'risk_summary']:
            result[k] = result[k].strip()

        cache.set(cache_key, result, self.CACHE_TTL)
        return result

    def enhance_news_sentiment(self, symbol: str, articles: list) -> list:
        """
        Sends news titles to LLM for accurate sentiment classification.
        Returns articles list with 'llm_sentiment' and 'llm_reason' added.
        Results cached per symbol for 3 hours.
        """
        from django.core.cache import cache
        cache_key = f'ai_news_sentiment_{symbol}'
        cached = cache.get(cache_key)
        if cached:
            return cached

        if not articles:
            return articles

        # Build compact list of titles + summaries
        news_block = "\n".join(
            f"{i+1}. TITLE: {a.get('title', '')[:120]}"
            for i, a in enumerate(articles[:10])
        )

        prompt = f"""You are a financial news analyst specializing in Indian equities.
Classify each news headline about {symbol} into EXACTLY one of: Positive, Negative, or Neutral.
For each, also give a 5-word reason.

Headlines:
{news_block}

Respond ONLY with a JSON array like:
[
  {{"id": 1, "sentiment": "Positive", "reason": "Strong revenue beat surprise"}},
  {{"id": 2, "sentiment": "Negative", "reason": "Probe reduces investor confidence"}},
  ...
]
Output ONLY the JSON array. No extra text."""

        raw = self._call_llm(prompt, max_tokens=400)
        if not raw:
            return articles

        try:
            # Extract JSON from response
            import re
            json_match = re.search(r'\[.*\]', raw, re.DOTALL)
            if not json_match:
                return articles
            classifications = json.loads(json_match.group())
            cls_map = {item['id']: item for item in classifications}

            enhanced = []
            for i, article in enumerate(articles):
                cls = cls_map.get(i + 1, {})
                article = dict(article)
                article['llm_sentiment'] = cls.get('sentiment', '').lower() or article.get('sentiment', 'neutral')
                article['llm_reason'] = cls.get('reason', '')
                enhanced.append(article)

            cache.set(cache_key, enhanced, 3 * 60 * 60)
            return enhanced
        except Exception as e:
            print(f"[StockAnalysisAI] News enhance parse error: {e}")
            return articles

    def generate_portfolio_agent_report(self, basket_name: str, stocks_analysis: list,
                                         total_investment: float, total_value: float) -> dict:
        """
        Autonomous Portfolio Agent — synthesizes multi-stock analysis
        into a cohesive rebalancing recommendation report.
        """
        from django.core.cache import cache
        cache_key = f'ai_agent_report_{basket_name}_{int(total_investment)}'
        cached = cache.get(cache_key)
        if cached:
            cached['cached'] = True
            return cached

        # Build compact analysis per stock
        stock_summaries = []
        for sa in stocks_analysis:
            s = sa.get('symbol', '?')
            rec = sa.get('recommendation', {})
            fund = sa.get('fundamentals', {})
            fcf = fund.get('fcf_history', [])
            fcf_val = fcf[0] if fcf else 'N/A'
            stock_summaries.append(
                f"- {s}: Score {rec.get('score', 0)}/25 ({rec.get('verdict', 'N/A')}), "
                f"P/E={fund.get('pe_ratio', 'N/A')}, P/B={fund.get('price_to_book', 'N/A')}, "
                f"YoY Rev Growth={fund.get('revenue_growth_yoy', 'N/A')}%, "
                f"YoY Profit Growth={fund.get('earnings_growth_yoy', 'N/A')}%, "
                f"FCF={fcf_val}, Debt/Equity={fund.get('debt_to_equity', 'N/A')}, "
                f"Graham Intrinsic Value=₹{fund.get('intrinsic_value', 'N/A')}, "
                f"Red Flags={', '.join(rec.get('red_flags', [])) or 'None'}"
            )

        pnl = total_value - total_investment
        pnl_pct = (pnl / total_investment * 100) if total_investment > 0 else 0
        stocks_block = '\n'.join(stock_summaries)

        prompt = f"""You are an autonomous AI portfolio manager for an Indian retail investor.

PORTFOLIO: {basket_name}
Total Investment: ₹{total_investment:,.0f}
Current Value: ₹{total_value:,.0f}
Profit/Loss: ₹{pnl:,.0f} ({pnl_pct:.1f}%)

INDIVIDUAL STOCK ANALYSIS:
{stocks_block}

Generate a comprehensive portfolio intelligence report with these EXACT sections:

## Portfolio Health Score
Give an overall score out of 10 and 2-sentence assessment. Evaluate the overall basket against the 8 Golden Rules:
1. Growing Revenues & Profits
2. Assets exceed Liabilities
3. Positive and growing Free Cash Flow
4. Sound valuations (low P/E, P/B, Debt-to-Equity)
5. Stock price below Graham Intrinsic Value

## Top Actions
List 3-5 specific action items starting with 🔴 REDUCE, 🟡 HOLD, or 🟢 ADD for each relevant stock with reasoning. Focus heavily on warning users about any stocks with active Red Flags (like dropping revenue/profit, negative cash flow, or high debt).

## Risk Alerts
List 2-3 key portfolio-level risks to watch (e.g. concentrations in high-debt stocks, cash-burning companies, or sectors with poor tailwinds).

## Rebalancing Suggestion
One paragraph on how to rebalance for better risk-adjusted returns based on the fundamental checklist.

## Market Timing
One sentence on whether now is a good time to add to this basket given current signals.

Be specific, use stock symbols, be direct. Use ₹ for prices."""

        raw = self._call_llm(prompt, max_tokens=800)
        if not raw:
            return {
                "report": None, "cached": False,
                "error": "AI provider unavailable. Check API key configuration."
            }

        result = {"report": raw, "cached": False, "error": None}
        cache.set(cache_key, result, 2 * 60 * 60)  # 2-hour cache for agent
        return result


# Singleton instance for stock analysis AI
stock_ai_service = StockAnalysisAIService()
