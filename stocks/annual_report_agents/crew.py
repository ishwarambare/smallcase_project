"""
stocks/annual_report_agents/crew.py

Orchestrates the 4-agent CrewAI Crew in sequential mode:
    Task 1 → Quant   (yfinance ratios)
    Task 2 → News    (DuckDuckGo sentiment)
    Task 3 → Gov     (ChromaDB RAG management commentary)
    Task 4 → CIO     (synthesize → BUY/HOLD/SELL)

Each Task receives the previous tasks' outputs as context automatically
(via CrewAI's sequential process). The final task output is the CIO decision.

Usage:
    from .crew import run_analysis_crew
    result = run_analysis_crew(symbol='TCS', company_name='Tata Consultancy Services')
"""

import json
import logging
import re
from crewai import Task, Crew, Process

from .agents import (
    create_quant_agent,
    create_news_agent,
    create_governance_agent,
    create_cio_agent,
)
from .tools import (
    fetch_financial_ratios,
    fetch_news_sentiment,
    query_governance_rag,
)

logger = logging.getLogger(__name__)


def run_analysis_crew(
    symbol: str,
    company_name: str = None,
    job_updater=None,
    thought_updater=None,
) -> dict:
    """
    Run the full 4-agent analysis crew for a given stock.

    This function:
      1. Calls each tool directly (yfinance, DuckDuckGo, ChromaDB) to gather data
      2. Feeds structured data into CrewAI tasks as context
      3. Runs the crew sequentially
      4. Returns per-agent results + final CIO decision

    Args:
        symbol:       Stock ticker (e.g. 'TCS', 'TCS.NS', 'AAPL')
        company_name: Optional full company name for news search
        job_updater:  Optional callable(step_msg) to update AnalysisJob.current_step

    Returns:
        {
            'quant':      {...},   # Agent 1 result
            'news':       {...},   # Agent 2 result
            'governance': {...},   # Agent 3 result
            'decision':   {...},   # Agent 4 CIO output
            'error':      str | None
        }
    """
    def _update(msg):
        logger.info(f"[Crew] {msg}")
        if job_updater:
            job_updater(msg)

    try:
        name = company_name or symbol

        # ── Step 1: Gather raw data for each agent ──────────────────────────
        _update("📊 Agent 1 (Quant): Fetching financial ratios from Yahoo Finance…")
        quant_data = fetch_financial_ratios(symbol)

        _update("📰 Agent 2 (News): Searching DuckDuckGo for recent news…")
        news_data = fetch_news_sentiment(symbol, company_name=name)

        _update("🏛️  Agent 3 (Governance): Querying annual report database…")
        gov_data = query_governance_rag(symbol)

        # ── Step 2: Build CrewAI Tasks with rich context ────────────────────
        quant_agent = create_quant_agent()
        news_agent  = create_news_agent()
        gov_agent   = create_governance_agent()
        cio_agent   = create_cio_agent()

        # Format quant data as readable string for the LLM
        quant_summary = _format_quant_for_llm(symbol, quant_data)
        news_summary  = _format_news_for_llm(symbol, news_data)
        gov_summary   = _format_gov_for_llm(symbol, gov_data)

        task_quant = Task(
            description=(
                f"Analyze the following pre-fetched financial ratios for {name} ({symbol}).\n\n"
                f"{quant_summary}\n\n"
                f"Apply the investment checklist:\n"
                f"  ✅ ROCE ≥ 20% = capital-efficient\n"
                f"  ✅ D/E ≤ 1.5 = manageable debt\n"
                f"  ✅ P/E ≤ 40x = not overly expensive\n\n"
                f"Provide a structured Quant verdict with pass/fail for each metric."
            ),
            expected_output=(
                "A structured quant verdict with: "
                "ROCE analysis, D/E analysis, P/E analysis, Revenue CAGR, "
                "and an overall QUANT VERDICT: PASS / BORDERLINE / FAIL"
            ),
            agent=quant_agent,
        )

        task_news = Task(
            description=(
                f"Analyze the following pre-fetched news sentiment data for {name} ({symbol}).\n\n"
                f"{news_summary}\n\n"
                f"Assess: Is market sentiment currently BULLISH, NEUTRAL, or BEARISH? "
                f"Identify the top 2-3 news catalysts (positive or negative) that are most "
                f"important for the investment thesis."
            ),
            expected_output=(
                "A news sentiment verdict with: "
                "overall sentiment label, key catalysts (positive/negative), "
                "and a NEWS VERDICT: POSITIVE / NEUTRAL / NEGATIVE"
            ),
            agent=news_agent,
        )

        task_governance = Task(
            description=(
                f"Analyze the following excerpts from {name}'s annual report for governance insights.\n\n"
                f"{gov_summary}\n\n"
                f"Focus on:\n"
                f"  1. Revenue and growth guidance from management\n"
                f"  2. Strategic plans (capacity expansion, new products, acquisitions)\n"
                f"  3. Corporate governance red flags (related party transactions, "
                f"     auditor issues, promoter pledging, litigation risks)\n\n"
                f"Provide a clear GOVERNANCE VERDICT: CLEAN / CAUTION / RED FLAG"
            ),
            expected_output=(
                "A governance verdict with: "
                "management growth commentary, strategic initiatives, "
                "identified red flags (if any), "
                "and a GOVERNANCE VERDICT: CLEAN / CAUTION / RED FLAG"
            ),
            agent=gov_agent,
        )

        task_cio = Task(
            description=(
                f"You are the Chief Investment Officer reviewing the analysis of {name} ({symbol}).\n\n"
                f"Read the outputs from:\n"
                f"  - Agent 1 (Quant Analyst): Financial ratios and checklist\n"
                f"  - Agent 2 (News Analyst): Market sentiment and catalysts\n"
                f"  - Agent 3 (Governance Analyst): Management quality and red flags\n\n"
                f"Make a final investment decision. Your output MUST follow this exact format:\n\n"
                f"DECISION: [BUY / HOLD / SELL]\n"
                f"CONFIDENCE: [HIGH / MEDIUM / LOW]\n"
                f"REASONING:\n"
                f"  • [Point 1]\n"
                f"  • [Point 2]\n"
                f"  • [Point 3]\n"
                f"RISKS:\n"
                f"  • [Risk 1]\n"
                f"  • [Risk 2]\n"
                f"TARGET HORIZON: [Short-term (0-6 months) / Medium-term (6-18 months) / Long-term (18+ months)]\n"
                f"SUMMARY: [One sentence executive summary]"
            ),
            expected_output=(
                "A final investment decision in the exact format specified: "
                "DECISION, CONFIDENCE, REASONING bullets, RISKS bullets, "
                "TARGET HORIZON, and SUMMARY."
            ),
            agent=cio_agent,
            context=[task_quant, task_news, task_governance],
        )

        # ── Step 3: Run the Crew ─────────────────────────────────────────────
        _update("🤖 Running 4-agent CrewAI crew (NVIDIA NIM)…")

        def crew_step_callback(step):
            if thought_updater:
                try:
                    # In newer crewai versions, step is often a tuple or an AgentStep object.
                    # We can try to extract thought or text if available.
                    thought_text = ""
                    if hasattr(step, 'thought') and step.thought:
                        thought_text = str(step.thought)
                    elif isinstance(step, tuple) and len(step) > 0:
                        thought_text = str(step[0].log if hasattr(step[0], 'log') else step[0])
                    else:
                        thought_text = str(step)
                    
                    if thought_text:
                        thought_updater(thought_text)
                except Exception as e:
                    pass

        crew = Crew(
            agents=[quant_agent, news_agent, gov_agent, cio_agent],
            tasks=[task_quant, task_news, task_governance, task_cio],
            process=Process.sequential,
            verbose=True,
            step_callback=crew_step_callback,
        )

        crew_output = crew.kickoff()

        # Extract task outputs
        quant_output = _safe_task_output(crew_output, 0, task_quant)
        news_output  = _safe_task_output(crew_output, 1, task_news)
        gov_output   = _safe_task_output(crew_output, 2, task_governance)
        cio_output   = _safe_task_output(crew_output, 3, task_cio)

        # Parse CIO output into structured dict
        decision_parsed = _parse_cio_decision(cio_output)

        _update("✅ All 4 agents completed. Decision ready.")

        return {
            'quant': {
                'raw_data': quant_data,
                'analysis': quant_output,
            },
            'news': {
                'raw_data': news_data,
                'analysis': news_output,
            },
            'governance': {
                'raw_context': gov_data.get('raw_context', ''),
                'analysis': gov_output,
            },
            'decision': {
                'raw_output': cio_output,
                **decision_parsed,
            },
            'error': None,
        }

    except Exception as e:
        logger.error(f"[Crew] Fatal error for {symbol}: {e}", exc_info=True)
        return {
            'quant': None,
            'news': None,
            'governance': None,
            'decision': None,
            'error': str(e),
        }


# ─── Private helpers ──────────────────────────────────────────────────────────

def _safe_task_output(crew_output, index: int, task: 'Task') -> str:
    """Safely extract task output string."""
    try:
        if hasattr(crew_output, 'tasks_output') and crew_output.tasks_output:
            return str(crew_output.tasks_output[index].raw)
    except Exception:
        pass
    try:
        return str(task.output.raw) if hasattr(task, 'output') and task.output else ''
    except Exception:
        return ''


def _format_quant_for_llm(symbol: str, data: dict) -> str:
    """Format raw yfinance data into a readable summary for the LLM."""
    if data.get('error'):
        return f"⚠️  Yahoo Finance data unavailable: {data['error']}"

    lines = [f"📊 FINANCIAL RATIOS — {symbol}"]
    lines.append(f"  Current Price:     ₹{data.get('current_price', 'N/A')}")
    lines.append(f"  Market Cap:        {_fmt_large(data.get('market_cap'))}")
    lines.append(f"  ROCE:              {data.get('roce', 'N/A')}% — {data.get('roce_verdict', '')}")
    lines.append(f"  P/E Ratio:         {data.get('pe_ratio', 'N/A')}x — {data.get('pe_verdict', '')}")
    lines.append(f"  Debt/Equity:       {data.get('de_ratio', 'N/A')} — {data.get('de_verdict', '')}")
    lines.append(f"  Net Profit Margin: {data.get('profit_margin_pct', 'N/A')}%")
    lines.append(f"  Revenue CAGR (3Y): {data.get('revenue_cagr_pct', 'N/A')}%")
    lines.append(f"  ROE:               {data.get('roe_pct', 'N/A')}%")
    lines.append(f"  ROCE Threshold:    {data.get('roce_threshold', 20)}%")
    return '\n'.join(lines)


def _format_news_for_llm(symbol: str, data: dict) -> str:
    """Format news data into a readable summary."""
    if data.get('error') and not data.get('headlines'):
        return f"⚠️  News data unavailable: {data['error']}"

    lines = [
        f"📰 NEWS SENTIMENT — {symbol}",
        f"  Overall Sentiment: {data.get('sentiment_label', 'N/A')} "
        f"(score: {data.get('avg_sentiment', 0):+.2f})",
        "",
        "  Recent Headlines:",
    ]
    for i, h in enumerate(data.get('headlines', [])[:6], 1):
        sentiment_icon = '🟢' if h['label'] == 'POSITIVE' else ('🔴' if h['label'] == 'NEGATIVE' else '⚪')
        lines.append(f"  {i}. {sentiment_icon} {h['title']}")
        if h.get('snippet'):
            lines.append(f"     {h['snippet'][:150]}…")
    return '\n'.join(lines)


def _format_gov_for_llm(symbol: str, data: dict) -> str:
    """Format ChromaDB RAG excerpts into readable context."""
    chunks = data.get('chunks', [])
    if not chunks:
        return f"⚠️  No annual report indexed for {symbol}. Governance analysis limited."

    lines = [
        f"📄 ANNUAL REPORT EXCERPTS — {symbol}",
        f"  (Retrieved {len(chunks)} relevant passages from indexed documents)",
        "",
    ]
    for i, chunk in enumerate(chunks[:8], 1):
        lines.append(f"  [{i}] {chunk[:400]}…")
        lines.append("")
    return '\n'.join(lines)


def _parse_cio_decision(raw_output: str) -> dict:
    """
    Parse the CIO agent's structured output into a clean dict.
    Handles minor formatting variations gracefully.
    """
    if not raw_output:
        return {
            'decision': 'UNKNOWN',
            'confidence': 'LOW',
            'reasoning': [],
            'risks': [],
            'horizon': 'N/A',
            'summary': 'Analysis incomplete.',
        }

    text = raw_output

    # Extract DECISION
    decision = 'UNKNOWN'
    m = re.search(r'DECISION\s*:\s*(BUY|HOLD|SELL)', text, re.IGNORECASE)
    if m:
        decision = m.group(1).upper()

    # Extract CONFIDENCE
    confidence = 'MEDIUM'
    m = re.search(r'CONFIDENCE\s*:\s*(HIGH|MEDIUM|LOW)', text, re.IGNORECASE)
    if m:
        confidence = m.group(1).upper()

    # Extract REASONING bullets
    reasoning = []
    m = re.search(r'REASONING\s*:?\s*(.*?)(?=RISKS|TARGET|SUMMARY|$)', text, re.IGNORECASE | re.DOTALL)
    if m:
        block = m.group(1)
        bullets = re.findall(r'[•\-\*]\s*(.+)', block)
        reasoning = [b.strip() for b in bullets if b.strip()][:5]

    # Extract RISKS
    risks = []
    m = re.search(r'RISKS\s*:?\s*(.*?)(?=TARGET|SUMMARY|$)', text, re.IGNORECASE | re.DOTALL)
    if m:
        block = m.group(1)
        bullets = re.findall(r'[•\-\*]\s*(.+)', block)
        risks = [b.strip() for b in bullets if b.strip()][:3]

    # Extract TARGET HORIZON
    horizon = 'N/A'
    m = re.search(r'TARGET HORIZON\s*:\s*(.+)', text, re.IGNORECASE)
    if m:
        horizon = m.group(1).strip()

    # Extract SUMMARY
    summary = ''
    m = re.search(r'SUMMARY\s*:\s*(.+)', text, re.IGNORECASE | re.DOTALL)
    if m:
        summary = m.group(1).strip()[:500]

    return {
        'decision':   decision,
        'confidence': confidence,
        'reasoning':  reasoning,
        'risks':      risks,
        'horizon':    horizon,
        'summary':    summary,
    }


def _fmt_large(value) -> str:
    """Format large numbers (market cap etc.) into readable strings."""
    if value is None:
        return 'N/A'
    try:
        v = float(value)
        if v >= 1e12:
            return f"₹{v/1e12:.2f}T"
        if v >= 1e9:
            return f"₹{v/1e9:.2f}B"
        if v >= 1e6:
            return f"₹{v/1e6:.2f}M"
        return str(v)
    except Exception:
        return str(value)
