"""
stocks/annual_report_agents/agents.py

Defines the 4 CrewAI Agent objects:

  Agent 1 — Quant Analyst  : Pulls live financial ratios from Yahoo Finance
  Agent 2 — News Analyst   : Searches DuckDuckGo for sentiment
  Agent 3 — Governance     : Queries ChromaDB for management commentary
  Agent 4 — CIO            : Synthesizes all agent outputs → final decision

Each agent is backed by NVIDIA NIM (meta/llama-3.1-70b-instruct).
"""

import logging
from crewai import Agent

logger = logging.getLogger(__name__)


def _get_nvidia_llm():
    """Return NVIDIA NIM LLM for CrewAI agents."""
    from crewai import LLM
    from django.conf import settings
    import os

    nvidia_base_url = getattr(settings, 'NVIDIA_BASE_URL', 'https://integrate.api.nvidia.com/v1')
    nvidia_api_key = getattr(settings, 'NVIDIA_API_KEY', os.environ.get('NVIDIA_API_KEY', ''))
    nvidia_default_model = getattr(settings, 'NVIDIA_DEFAULT_MODEL', 'meta/llama-3.1-70b-instruct')

    return LLM(
        model=f"openai/{nvidia_default_model}",
        base_url=nvidia_base_url,
        api_key=nvidia_api_key,
        temperature=0.1,
        max_tokens=2048,
    )


def create_quant_agent() -> Agent:
    """
    Agent 1 — Quantitative Analyst

    Role: Pull live financial ratios from Yahoo Finance and evaluate them
    against a strict investment checklist (ROCE ≥ 20%, D/E ≤ 1.5, P/E ≤ 40).
    """
    return Agent(
        role='Quantitative Analyst',
        goal=(
            'Fetch and analyze key financial metrics for the stock. '
            'Calculate ROCE, Debt-to-Equity ratio, P/E ratio, and Revenue CAGR. '
            'Flag stocks that fail the 20% ROCE threshold or show dangerous debt levels.'
        ),
        backstory=(
            'You are a seasoned quant analyst who has spent 15 years screening stocks '
            'at tier-1 hedge funds. Your job is to apply a rigorous mathematical checklist '
            'to every company you evaluate. You never let emotion cloud your judgment — '
            'only the numbers matter. Your primary screen is ROCE ≥ 20%, which separates '
            'capital-efficient businesses from mediocre ones.'
        ),
        llm=_get_nvidia_llm(),
        verbose=True,
        allow_delegation=False,
        max_iter=3,
    )


def create_news_agent() -> Agent:
    """
    Agent 2 — News & Sentiment Analyst

    Role: Search the internet for recent news about the company and assess
    market sentiment using DuckDuckGo.
    """
    return Agent(
        role='News & Sentiment Analyst',
        goal=(
            'Search for the most recent news about the company and score market sentiment. '
            'Identify any major catalysts (acquisitions, partnerships, earnings surprises) '
            'or risks (lawsuits, management exits, regulatory probes) in the last 30 days.'
        ),
        backstory=(
            'You are a financial journalist turned buy-side analyst. You have a sixth sense '
            'for distinguishing signal from noise in financial media. You can read 20 headlines '
            'and immediately identify the 3 that actually matter for an investment thesis. '
            'You understand that markets are forward-looking and sentiment today can predict '
            'price movement tomorrow.'
        ),
        llm=_get_nvidia_llm(),
        verbose=True,
        allow_delegation=False,
        max_iter=3,
    )


def create_governance_agent() -> Agent:
    """
    Agent 3 — Corporate Governance & Management Analyst

    Role: Query the indexed annual report in ChromaDB to extract management
    commentary, growth guidance, and identify corporate governance red flags.
    """
    return Agent(
        role='Corporate Governance & Management Analyst',
        goal=(
            'Query the company\'s annual report to extract: '
            '(1) management\'s revenue and profitability guidance, '
            '(2) capacity expansion or strategic investment plans, '
            '(3) any corporate governance red flags (related-party transactions, '
            'auditor qualifications, promoter pledging, litigation). '
            'Provide a clear governance verdict: CLEAN / CAUTION / RED FLAG.'
        ),
        backstory=(
            'You are a forensic accountant and corporate governance specialist. '
            'You have uncovered accounting frauds and promoter manipulation schemes '
            'that fooled thousands of retail investors. You read annual reports the '
            'way others read thrillers — always looking for what\'s hidden between the lines. '
            'You know that management\'s tone in the annual report often predicts the '
            'company\'s next 3 years better than any financial model.'
        ),
        llm=_get_nvidia_llm(),
        verbose=True,
        allow_delegation=False,
        max_iter=3,
    )


def create_cio_agent() -> Agent:
    """
    Agent 4 — Chief Investment Officer (CIO / Fund Manager)

    Role: Read the outputs from all 3 specialist agents and produce the
    final investment decision: BUY / HOLD / SELL with full reasoning.
    """
    return Agent(
        role='Chief Investment Officer',
        goal=(
            'Read the analysis from the Quant Analyst, News Analyst, and Governance Analyst. '
            'Synthesize all findings into a final investment decision with clear reasoning. '
            'Output format must be:\n'
            'DECISION: [BUY / HOLD / SELL]\n'
            'CONFIDENCE: [HIGH / MEDIUM / LOW]\n'
            'REASONING: [3-5 bullet points]\n'
            'RISKS: [2-3 key risks]\n'
            'TARGET HORIZON: [Short-term / Medium-term / Long-term]'
        ),
        backstory=(
            'You are a seasoned CIO who has managed a $500M Indian equity fund for 20 years. '
            'You have seen bull markets, bear markets, and everything in between. '
            'Your investment philosophy: buy capital-efficient businesses run by honest '
            'management at reasonable valuations with tailwinds. '
            'You weight governance and management quality above all — a cheap stock with '
            'bad governance is a value trap. You are concise, decisive, and never hedge '
            'your final recommendation with vague language.'
        ),
        llm=_get_nvidia_llm(),
        verbose=True,
        allow_delegation=False,
        max_iter=5,
    )
