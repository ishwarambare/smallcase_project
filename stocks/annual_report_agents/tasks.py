"""
stocks/annual_report_agents/tasks.py

Celery task entry point for the 4-agent annual report analysis pipeline.

Usage (Django view):
    from stocks.annual_report_agents.tasks import analyze_annual_report
    task = analyze_annual_report.delay(job_id=job.pk, symbol='TCS', doc_id=doc.pk)

Worker command (Windows):
    celery -A smallcase_project worker --loglevel=info --pool=solo

The task:
  1. Updates AnalysisJob status → 'ingesting'
  2. Calls pdf_ingestion.ingest_pdf_for_agents() → ChromaDB
  3. Updates status → 'analyzing'
  4. Runs crew.run_analysis_crew() → 4 agents produce results
  5. Writes per-agent results back to AnalysisJob fields
  6. Sets status → 'done' (or 'error' on failure)
"""

import logging
from datetime import datetime

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name='stocks.annual_report_agents.tasks.analyze_annual_report',
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
)
def analyze_annual_report(self, job_id: int, symbol: str, doc_id: int = None):
    """
    Main Celery task: run the full 4-agent annual report analysis pipeline.

    Args:
        job_id:  AnalysisJob.pk (created by the Django view before dispatching)
        symbol:  Stock ticker (e.g. 'TCS', 'AAPL')
        doc_id:  StockDocument.pk (optional — if None, uses already-indexed data)
    """
    # Import here to avoid circular imports at module load time
    import django
    django.setup()   # noqa — safe to call multiple times; idempotent

    from django.utils import timezone
    from stocks.models import AnalysisJob, Stock

    def _update_job(job, status=None, step=None, **field_updates):
        """Helper: atomically update job fields and save."""
        if status:
            job.status = status
        if step:
            job.current_step = step
        for field, value in field_updates.items():
            setattr(job, field, value)
        job.save(update_fields=['status', 'current_step'] + list(field_updates.keys()))

    # ── Load the job ─────────────────────────────────────────────────────────
    try:
        job = AnalysisJob.objects.select_related('stock', 'document').get(pk=job_id)
    except AnalysisJob.DoesNotExist:
        logger.error(f"[Task] AnalysisJob {job_id} not found — aborting.")
        return {'error': f'Job {job_id} not found'}

    # Record Celery task ID
    job.celery_task_id = self.request.id or ''
    job.save(update_fields=['celery_task_id'])

    company_name = job.stock.name if job.stock else symbol

    try:
        # ── PHASE 1: PDF Ingestion ────────────────────────────────────────
        from stocks.models import StockDocument
        docs = StockDocument.objects.filter(stock=job.stock)

        if docs.exists():
            _update_job(job, status='ingesting', step='📄 Ingesting all PDFs into ChromaDB…')

            from .pdf_ingestion import ingest_pdf_for_agents

            def progress_cb(msg):
                _update_job(job, step=msg)

            for d in docs:
                ingest_result = ingest_pdf_for_agents(
                    symbol=symbol,
                    document_id=d.pk,
                    job_updater=progress_cb,
                )

                if not ingest_result['success']:
                    logger.warning(
                        f"[Task] PDF ingest failed for job {job_id}, doc {d.pk}: {ingest_result['error']}. "
                    )
        else:
            _update_job(job, step='ℹ️  No PDF found for this stock — using existing indexed data if any')

        # ── PHASE 2: Run 4-Agent Crew ────────────────────────────────────
        _update_job(job, status='analyzing', step='🤖 Starting 4-agent AI crew (NVIDIA NIM)…')

        from .crew import run_analysis_crew

        def crew_progress_cb(msg):
            _update_job(job, step=msg)

        def thought_updater(thought: str):
            try:
                from stocks.models import AnalysisJob
                j = AnalysisJob.objects.get(pk=job_id)
                thoughts = j.agent_thoughts if isinstance(j.agent_thoughts, list) else []
                thoughts.append(thought)
                j.agent_thoughts = thoughts
                j.save(update_fields=['agent_thoughts'])
            except Exception as e:
                logger.error(f"[Task] Failed to save thought: {e}")

        result = run_analysis_crew(
            symbol=symbol,
            company_name=company_name,
            job_updater=crew_progress_cb,
            thought_updater=thought_updater,
        )

        if result.get('error'):
            raise RuntimeError(result['error'])

        # ── PHASE 3: Save agent results to DB ────────────────────────────
        _update_job(
            job,
            status='done',
            step='✅ Analysis complete!',
            quant_result=result.get('quant'),
            news_result=result.get('news'),
            governance_result=result.get('governance'),
            final_decision=result.get('decision'),
            completed_at=timezone.now(),
        )

        logger.info(
            f"[Task] Job {job_id} complete. "
            f"Decision: {result.get('decision', {}).get('decision', 'N/A')}"
        )
        return {
            'job_id':   job_id,
            'status':   'done',
            'decision': result.get('decision', {}).get('decision', 'N/A'),
        }

    except Exception as exc:
        logger.error(f"[Task] Job {job_id} failed: {exc}", exc_info=True)
        _update_job(
            job,
            status='error',
            step='❌ Analysis failed — see error message',
            error_message=str(exc)[:1000],
        )

        # Avoid raising exceptions to prevent celery pool=solo ExceptionInfo bug on Windows
        return {'status': 'error', 'error': str(exc)}
