"""
stocks/annual_report_agents/pdf_ingestion.py

Step 1: PDF → LangChain chunks → ChromaDB

Uses LangChain's RecursiveCharacterTextSplitter to create semantically
meaningful chunks, then stores them in ChromaDB under the collection
'agents_{symbol}' (separate from the existing RAG pipeline collections).

The ChromaDB collection uses NVIDIA NIM embeddings if available, otherwise
falls back to the local all-MiniLM-L6-v2 sentence transformer.
"""

import os
import io
import re
import logging
from pathlib import Path
import langchain_text_splitters

logger = logging.getLogger(__name__)

AGENTS_CHUNK_SIZE    = 1000   # characters per chunk (larger = more context)
AGENTS_CHUNK_OVERLAP = 200    # overlap to avoid cutting mid-sentence


def _clean_symbol(symbol: str) -> str:
    """Sanitize stock symbol to a valid ChromaDB collection name."""
    return re.sub(r'[^a-zA-Z0-9_-]', '_', symbol).lower()


def _get_chroma_client():
    """Return a persistent ChromaDB client, stored in BASE_DIR/chroma_db/."""
    import chromadb
    from django.conf import settings
    db_path = str(Path(settings.BASE_DIR) / 'chroma_db')
    os.makedirs(db_path, exist_ok=True)
    return chromadb.PersistentClient(path=db_path)


def _safe_chroma_client():
    """
    Safely create a ChromaDB client, returning None on any failure.

    ChromaDB 1.1.x uses a Rust backend that can raise pyo3_runtime.PanicException
    (a hard crash not catchable as a regular Exception in all contexts). This wrapper
    catches everything so that the Governance agent can degrade gracefully instead of
    killing the Celery worker.
    """
    try:
        return _get_chroma_client()
    except Exception as e:
        logger.warning(f"[ChromaDB] Client creation failed: {e}")
        return None
    except BaseException as e:  # catches pyo3_runtime.PanicException
        logger.error(f"[ChromaDB] Rust panic during client init: {e}")
        return None


def _get_embedding_fn():
    """
    Return a ChromaDB embedding function.
    Priority: NVIDIA NIM → sentence-transformers → ChromaDB default
    """
    # Try NVIDIA NIM embeddings
    try:
        from django.conf import settings
        import os
        nvidia_key = getattr(settings, 'NVIDIA_API_KEY', os.environ.get('NVIDIA_API_KEY', ''))
        if nvidia_key:
            from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

            class NVIDIAEmbeddingFunction(EmbeddingFunction):
                def __init__(self, api_key: str, model_name: str = "nvidia/nv-embedqa-e5-v5"):
                    self.api_key = api_key
                    self.model_name = model_name
                    from openai import OpenAI
                    self.client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=self.api_key)

                def name(self) -> str:
                    return f"NVIDIAEmbeddingFunction-{self.model_name}"

                def __call__(self, input: Documents) -> Embeddings:
                    response = self.client.embeddings.create(
                        model=self.model_name,
                        input=input,
                        extra_body={"input_type": "passage"}
                    )
                    return [data.embedding for data in response.data]

            return NVIDIAEmbeddingFunction(api_key=nvidia_key)
    except Exception as e:
        logger.warning(f"Failed to initialize NVIDIA embeddings: {e}")

    # Try sentence-transformers (local, free)
    try:
        import chromadb.utils.embedding_functions as ef
        return ef.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
    except Exception:
        pass

    # ChromaDB built-in default
    return None


def ingest_pdf_for_agents(
    symbol: str,
    document_id: int,
    job_updater=None,
) -> dict:
    """
    Extract text from a PDF, chunk it with LangChain, and store in ChromaDB.

    Args:
        symbol: Stock ticker (e.g. 'TCS')
        document_id: StockDocument.pk
        job_updater: Optional callable(step_msg) to update job progress

    Returns:
        {'success': bool, 'chunk_count': int, 'error': str|None}
    """
    def _update(msg):
        logger.info(f"[PDF Ingest] {msg}")
        if job_updater:
            job_updater(msg)

    try:
        from stocks.models import StockDocument

        # Load document from DB
        try:
            doc = StockDocument.objects.get(id=document_id)
        except StockDocument.DoesNotExist:
            return {'success': False, 'chunk_count': 0,
                    'error': f'StockDocument {document_id} not found'}

        _update(f"📄 Loading PDF: {doc.title}")

        # Read raw PDF bytes from storage
        try:
            with doc.file.open('rb') as f:
                pdf_bytes = f.read()
            pdf_source = io.BytesIO(pdf_bytes)
        except Exception as e:
            return {'success': False, 'chunk_count': 0,
                    'error': f'Failed to read file: {e}'}

        # Extract text using pypdf
        _update("🔍 Extracting text from PDF pages…")
        from pypdf import PdfReader
        reader   = PdfReader(pdf_source)
        raw_text = '\n'.join(
            page.extract_text() or ''
            for page in reader.pages
        )
        if not raw_text.strip():
            return {'success': False, 'chunk_count': 0,
                    'error': 'No extractable text found in PDF (may be image-only)'}

        _update(f"✂️  Splitting {len(raw_text):,} chars into chunks…")

        # LangChain text splitter — semantically aware splitting
        splitter = langchain_text_splitters.RecursiveCharacterTextSplitter(
            chunk_size=AGENTS_CHUNK_SIZE,
            chunk_overlap=AGENTS_CHUNK_OVERLAP,
            separators=['\n\n', '\n', '. ', ' ', ''],
        )
        chunks = splitter.split_text(raw_text)
        chunks = [c.strip() for c in chunks if len(c.strip()) > 50]

        if not chunks:
            return {'success': False, 'chunk_count': 0,
                    'error': 'Text splitting produced no usable chunks'}

        _update(f"🗄️  Storing {len(chunks)} chunks in ChromaDB…")

        # Store in ChromaDB under 'agents_{symbol}' collection
        client    = _get_chroma_client()
        emb_fn    = _get_embedding_fn()
        coll_name = f"agents_{_clean_symbol(symbol)}"

        if emb_fn:
            collection = client.get_or_create_collection(
                name=coll_name,
                embedding_function=emb_fn,
            )
        else:
            collection = client.get_or_create_collection(name=coll_name)

        # Delete old entries for this document to allow re-indexing
        try:
            old = collection.get(where={'doc_id': str(document_id)})
            if old and old.get('ids'):
                collection.delete(ids=old['ids'])
        except Exception:
            pass  # First-time index, nothing to delete

        # Batch insert
        ids        = [f"agent_doc{document_id}_chunk{i}" for i in range(len(chunks))]
        metadatas  = [
            {
                'doc_id':    str(document_id),
                'doc_title': doc.title,
                'doc_type':  doc.document_type,
                'symbol':    symbol,
                'chunk_idx': str(i),
            }
            for i in range(len(chunks))
        ]

        BATCH = 50
        for start in range(0, len(chunks), BATCH):
            end = min(start + BATCH, len(chunks))
            collection.add(
                documents=chunks[start:end],
                ids=ids[start:end],
                metadatas=metadatas[start:end],
            )

        total_in_db = collection.count()
        _update(f"✅ Indexed {len(chunks)} chunks (collection total: {total_in_db})")

        return {'success': True, 'chunk_count': len(chunks), 'error': None}

    except Exception as e:
        logger.error(f"[PDF Ingest] Fatal error for {symbol}: {e}", exc_info=True)
        return {'success': False, 'chunk_count': 0, 'error': str(e)}


def query_agents_collection(symbol: str, query: str, n_results: int = 6) -> list[str]:
    """
    Query the agents ChromaDB collection for the given symbol.
    Used by Agent 3 (Governance) to answer RAG questions.

    Returns a list of relevant text chunks, or [] if ChromaDB is unavailable.
    """
    try:
        client = _safe_chroma_client()
        if client is None:
            logger.warning(f"[ChromaDB Query] Skipping — client unavailable for {symbol}")
            return []

        emb_fn    = _get_embedding_fn()
        coll_name = f"agents_{_clean_symbol(symbol)}"

        try:
            if emb_fn:
                collection = client.get_collection(name=coll_name, embedding_function=emb_fn)
            else:
                collection = client.get_collection(name=coll_name)
        except Exception:
            # Collection doesn't exist yet — no annual report indexed
            logger.info(f"[ChromaDB Query] No collection '{coll_name}' — no annual report indexed yet")
            return []

        total = collection.count()
        if total == 0:
            return []

        results = collection.query(
            query_texts=[query],
            n_results=min(n_results, total),
        )
        return results['documents'][0] if results.get('documents') else []

    except BaseException as e:  # catches pyo3_runtime.PanicException too
        logger.error(f"[ChromaDB Query] {symbol}: {e}")
        return []
