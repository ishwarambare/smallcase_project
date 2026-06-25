"""
stocks/portfolio_agent.py

Autonomous Portfolio Agent — orchestrates multi-step analysis
for all stocks in a basket and synthesizes an LLM-powered report.

Architecture (Tool-Use pattern):
  PortfolioAgent.run(basket_id) →
    1. fetch_basket_data()    — DB query
    2. For each stock: run_full_analysis()  — yfinance + technicals
    3. synthesize_report()    — LLM via StockAnalysisAIService
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


class PortfolioAgent:
    """
    Autonomous agent that analyses an entire basket and produces
    a structured rebalancing intelligence report.
    """

    MAX_WORKERS = 4  # parallel stock analysis threads

    def run(self, basket_id: int, user) -> dict:
        """
        Main entry point.
        Returns a dict with:
          - basket_name, total_investment, total_value, pnl
          - stocks_analysis: list of per-stock analysis dicts
          - report: LLM-generated markdown report
          - error: str or None
          - cached: bool
        """
        # --- Step 1: Load basket from DB ---
        basket_data = self._fetch_basket_data(basket_id, user)
        if basket_data.get('error'):
            return basket_data

        # --- Step 2: Analyse each stock in parallel ---
        symbols = [item['symbol'] for item in basket_data['items']]
        logger.info(f"[PortfolioAgent] Running analysis on {len(symbols)} stocks for basket {basket_id}")

        stocks_analysis = []
        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            futures = {
                executor.submit(self._run_stock_analysis, sym): sym
                for sym in symbols
            }
            for future in as_completed(futures):
                sym = futures[future]
                try:
                    analysis = future.result(timeout=30)
                    stocks_analysis.append(analysis)
                except Exception as e:
                    logger.error(f"[PortfolioAgent] Analysis failed for {sym}: {e}")
                    stocks_analysis.append({'symbol': sym, 'error': str(e)})

        # Sort by score descending for a logical report order
        stocks_analysis.sort(key=lambda x: x.get('recommendation', {}).get('score', 0), reverse=True)

        # --- Step 3: LLM synthesis ---
        from .ai_service import stock_ai_service
        total_investment = basket_data['total_investment']
        total_value = basket_data['total_value']

        report_result = stock_ai_service.generate_portfolio_agent_report(
            basket_name=basket_data['basket_name'],
            stocks_analysis=stocks_analysis,
            total_investment=total_investment,
            total_value=total_value,
        )

        return {
            'basket_name': basket_data['basket_name'],
            'total_investment': total_investment,
            'total_value': total_value,
            'pnl': total_value - total_investment,
            'pnl_pct': ((total_value - total_investment) / total_investment * 100) if total_investment > 0 else 0,
            'stocks_analysis': stocks_analysis,
            'report': report_result.get('report'),
            'cached': report_result.get('cached', False),
            'error': report_result.get('error'),
        }

    def _fetch_basket_data(self, basket_id: int, user) -> dict:
        """Loads basket and its items from the database."""
        try:
            from .models import Basket
            basket = Basket.objects.prefetch_related('items__stock').get(
                id=basket_id, user=user
            )
            items = []
            total_investment = float(basket.investment_amount)
            total_value = 0.0

            for item in basket.items.all():
                current_value = item.get_current_value()
                total_value += current_value
                items.append({
                    'symbol': item.stock.symbol,
                    'name': item.stock.name,
                    'weight': float(item.weight_percentage),
                    'quantity': float(item.quantity),
                    'purchase_price': float(item.purchase_price),
                    'current_price': float(item.stock.current_price) if item.stock.current_price else 0,
                    'allocated_amount': float(item.allocated_amount),
                    'current_value': current_value,
                })

            return {
                'basket_name': basket.name,
                'total_investment': total_investment,
                'total_value': total_value,
                'items': items,
                'error': None,
            }
        except Exception as e:
            logger.error(f"[PortfolioAgent] Failed to fetch basket {basket_id}: {e}")
            return {'error': f"Could not load basket: {str(e)}"}

    def _run_stock_analysis(self, symbol: str) -> dict:
        """
        Tool: runs the full stock analysis pipeline for a single symbol.
        Mirrors what stock_detail view does.
        """
        from .stock_analysis import (
            get_stock_fundamentals,
            get_technical_indicators,
            get_news_sentiment,
            get_ownership_analysis,
            get_policy_alignment,
            get_global_impact,
            get_buy_recommendation,
            get_quant_metrics,
        )

        fundamentals = get_stock_fundamentals(symbol)
        indicators   = get_technical_indicators(symbol)
        news         = get_news_sentiment(symbol)
        ownership    = get_ownership_analysis(fundamentals)
        policy       = get_policy_alignment(
                           fundamentals.get('sector', ''),
                           news.get('articles', []))
        global_data  = get_global_impact(fundamentals.get('sector', ''))
        quant        = get_quant_metrics(symbol)
        recommendation = get_buy_recommendation(
                           fundamentals, indicators,
                           news=news, ownership=ownership,
                           policy=policy, global_impact=global_data)

        return {
            'symbol': symbol,
            'fundamentals': fundamentals,
            'indicators': indicators,
            'news': {'sentiment': news.get('sentiment'), 'sentiment_score': news.get('sentiment_score')},
            'ownership': {'score': ownership.get('score')},
            'policy': {'score': policy.get('score')},
            'quant': quant,
            'recommendation': recommendation,
        }


# Module-level singleton
portfolio_agent = PortfolioAgent()
