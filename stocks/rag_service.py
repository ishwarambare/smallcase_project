"""
stocks/rag_service.py

Financial Document RAG (Retrieval-Augmented Generation) Pipeline.

Architecture:
  1. Ingest PDF → extract text → chunk (500 tokens, 50 overlap)
  2. Embed chunks → store in ChromaDB (file-based, no server needed)
  3. On query: embed question → retrieve top-5 chunks → LLM answers

Dependencies (added to requirements.txt):
  - pypdf>=4.0.0      (pure-Python PDF parser)
  - chromadb>=0.4.0   (local vector DB)

ChromaDB stores data in BASE_DIR/chroma_db/
Collections are named per-symbol: "rag_{symbol_clean}"
"""

import os
import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CHUNK_SIZE = 500       # characters per chunk
CHUNK_OVERLAP = 80     # character overlap between chunks
TOP_K = 5              # chunks to retrieve per query


def _clean_symbol(symbol: str) -> str:
    """Sanitize symbol to a valid ChromaDB collection name."""
    return re.sub(r'[^a-zA-Z0-9_-]', '_', symbol).lower()


def _get_chroma_client():
    """Return a persistent ChromaDB client stored in BASE_DIR/chroma_db/."""
    try:
        import chromadb
        from django.conf import settings
        db_path = str(Path(settings.BASE_DIR) / 'chroma_db')
        os.makedirs(db_path, exist_ok=True)
        return chromadb.PersistentClient(path=db_path)
    except ImportError:
        raise ImportError(
            "chromadb is not installed. Run: pip install chromadb"
        )


def _get_embedding_fn():
    """
    Returns an embedding function for ChromaDB.
    Preference order:
      1. Google Gemini text-embedding-004 (if GEMINI_API_KEY set)
      2. sentence-transformers/all-MiniLM (if installed, zero-cost local)
      3. ChromaDB's built-in default embedding (always available)
    """
    try:
        import chromadb.utils.embedding_functions as ef
        gemini_key = os.environ.get('GEMINI_API_KEY', '')
        if gemini_key:
            return ef.GoogleGenerativeAiEmbeddingFunction(
                api_key=gemini_key,
                model_name="models/text-embedding-004"
            )
    except Exception:
        pass

    try:
        import chromadb.utils.embedding_functions as ef
        return ef.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
    except Exception:
        pass

    # ChromaDB default (uses its own bundled model)
    return None


def _chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(start + CHUNK_SIZE, text_len)
        chunks.append(text[start:end].strip())
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return [c for c in chunks if len(c) > 50]  # discard tiny chunks


def _extract_pdf_text(file_path: str) -> str:
    """Extract plain text from a PDF file using pypdf."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return '\n'.join(pages)
    except ImportError:
        raise ImportError("pypdf is not installed. Run: pip install pypdf")
    except Exception as e:
        logger.error(f"[RAG] PDF extraction error: {e}")
        raise


class RAGService:
    """
    Manages the ingestion and querying of financial documents.
    """

    def ingest_document(self, symbol: str, document_id: int,
                        file_path: str, doc_title: str,
                        doc_type: str = 'other') -> dict:
        """
        Extracts text from a PDF, chunks it, embeds and stores in ChromaDB.
        Updates the StockDocument.is_indexed and .chunk_count fields.

        Returns: {'success': bool, 'chunk_count': int, 'error': str|None}
        """
        try:
            text = _extract_pdf_text(file_path)
            if not text.strip():
                return {'success': False, 'chunk_count': 0, 'error': 'No text found in PDF'}

            chunks = _chunk_text(text)
            if not chunks:
                return {'success': False, 'chunk_count': 0, 'error': 'Could not extract chunks'}

            client = _get_chroma_client()
            emb_fn = _get_embedding_fn()

            collection_name = f"rag_{_clean_symbol(symbol)}"
            if emb_fn:
                collection = client.get_or_create_collection(
                    name=collection_name,
                    embedding_function=emb_fn
                )
            else:
                collection = client.get_or_create_collection(name=collection_name)

            # Add chunks with metadata
            ids       = [f"doc{document_id}_chunk{i}" for i in range(len(chunks))]
            metadatas = [
                {
                    'doc_id': str(document_id),
                    'doc_title': doc_title,
                    'doc_type': doc_type,
                    'symbol': symbol,
                    'chunk_index': str(i),
                }
                for i in range(len(chunks))
            ]

            # Delete old chunks for this document first (idempotent re-index)
            try:
                existing = collection.get(
                    where={"doc_id": str(document_id)}
                )
                if existing['ids']:
                    collection.delete(ids=existing['ids'])
            except Exception:
                pass

            collection.add(documents=chunks, ids=ids, metadatas=metadatas)

            # Update DB model
            try:
                from .models import StockDocument
                doc = StockDocument.objects.get(id=document_id)
                doc.is_indexed = True
                doc.chunk_count = len(chunks)
                doc.save(update_fields=['is_indexed', 'chunk_count'])
            except Exception as db_err:
                logger.warning(f"[RAG] Could not update StockDocument {document_id}: {db_err}")

            logger.info(f"[RAG] Indexed {len(chunks)} chunks for {symbol} doc {document_id}")
            return {'success': True, 'chunk_count': len(chunks), 'error': None}

        except Exception as e:
            logger.error(f"[RAG] Ingest error for {symbol}: {e}")
            return {'success': False, 'chunk_count': 0, 'error': str(e)}

    def query(self, symbol: str, question: str, doc_type: str = None) -> dict:
        """
        Retrieves top-K chunks for the question and calls LLM to answer.
        Returns: {'answer': str, 'sources': list, 'error': str|None}
        """
        try:
            client = _get_chroma_client()
            emb_fn = _get_embedding_fn()
            collection_name = f"rag_{_clean_symbol(symbol)}"

            # Check collection exists
            try:
                if emb_fn:
                    collection = client.get_collection(
                        name=collection_name,
                        embedding_function=emb_fn
                    )
                else:
                    collection = client.get_collection(name=collection_name)
            except Exception:
                return {
                    'answer': None,
                    'sources': [],
                    'error': f'No documents indexed for {symbol}. Please upload documents first.'
                }

            # Build where filter
            where = None
            if doc_type:
                where = {"doc_type": doc_type}

            # Retrieve top chunks
            results = collection.query(
                query_texts=[question],
                n_results=min(TOP_K, collection.count()),
                where=where,
            )

            if not results or not results['documents'] or not results['documents'][0]:
                return {
                    'answer': 'No relevant content found for your question.',
                    'sources': [],
                    'error': None
                }

            chunks_text = results['documents'][0]
            metas = results['metadatas'][0] if results.get('metadatas') else []

            # Build context block
            context = '\n\n---\n\n'.join(
                f"[{m.get('doc_title', 'Document')} – {m.get('doc_type', '')}]\n{c}"
                for c, m in zip(chunks_text, metas)
            )

            # Call LLM
            answer = self._answer_with_llm(symbol, question, context)
            sources = [
                {'title': m.get('doc_title', 'Unknown'), 'type': m.get('doc_type', '')}
                for m in metas
            ]
            # Deduplicate sources
            seen = set()
            unique_sources = []
            for s in sources:
                key = s['title']
                if key not in seen:
                    seen.add(key)
                    unique_sources.append(s)

            return {'answer': answer, 'sources': unique_sources, 'error': None}

        except Exception as e:
            logger.error(f"[RAG] Query error for {symbol}: {e}")
            return {'answer': None, 'sources': [], 'error': str(e)}

    def _answer_with_llm(self, symbol: str, question: str, context: str) -> str:
        """Calls LLM with retrieved context to answer the question."""
        from .ai_service import stock_ai_service

        prompt = f"""You are a financial research assistant. A user is asking about {symbol} 
based on official company documents (annual reports, earnings call transcripts, etc.).

Use ONLY the provided document excerpts to answer. If the answer is not in the excerpts, 
say "I couldn't find specific information about this in the available documents."

DOCUMENT EXCERPTS:
{context}

USER QUESTION: {question}

Provide a concise, factual answer based on the documents. Mention the source document when relevant."""

        answer = stock_ai_service._call_llm(prompt, max_tokens=500)
        return answer or "I'm unable to generate a response right now. Please try again."

    def list_documents(self, symbol: str) -> list:
        """Returns list of indexed documents for a symbol from the DB."""
        try:
            from .models import StockDocument
            docs = StockDocument.objects.filter(
                stock__symbol=symbol, is_indexed=True
            ).values('id', 'title', 'document_type', 'uploaded_at', 'chunk_count')
            return list(docs)
        except Exception:
            return []

    def get_collection_stats(self, symbol: str) -> dict:
        """Returns ChromaDB collection stats for a symbol."""
        try:
            client = _get_chroma_client()
            collection_name = f"rag_{_clean_symbol(symbol)}"
            collection = client.get_collection(name=collection_name)
            return {'count': collection.count(), 'name': collection_name}
        except Exception:
            return {'count': 0, 'name': None}


# Module-level singleton
rag_service = RAGService()
