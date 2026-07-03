# stocks/annual_report_agents/__init__.py
"""
Annual Report AI Analysis — 4-Agent Pipeline

This package implements a multi-agent AI pipeline that analyzes company
annual reports and produces investment decisions.

Pipeline:
    1. PDF Ingestion  → LangChain splits PDF into chunks → ChromaDB
    2. Agent 1 Quant  → yfinance ROCE / Debt / P/E ratios
    3. Agent 2 News   → DuckDuckGo recent news + sentiment
    4. Agent 3 Gov    → ChromaDB RAG: management commentary & red flags
    5. Agent 4 CIO    → Synthesizes all → BUY / HOLD / SELL decision

Entry point: tasks.analyze_annual_report (Celery task)
"""
