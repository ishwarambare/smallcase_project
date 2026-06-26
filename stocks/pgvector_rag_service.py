"""
stocks/pgvector_rag_service.py

Database-backed Financial Document RAG (Retrieval-Augmented Generation) Pipeline.
This service replaces the external ChromaDB with the Django database (using DocumentChunk model).
It supports SQLite and PostgreSQL out of the box, with zero database extension requirements.
"""

import os
import logging
import numpy as np
from pathlib import Path
from django.db import transaction
from .models import Stock, StockDocument, DocumentChunk

logger = logging.getLogger(__name__)

CHUNK_SIZE = 500       # characters per chunk
CHUNK_OVERLAP = 80     # character overlap between chunks
TOP_K = 5              # chunks to retrieve per query


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


def _extract_pdf_text(file_source) -> str:
    """Extract plain text from a PDF file (path or file-like stream) using pypdf."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(file_source)
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


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """
    Generates embedding vectors for a list of texts.
    Uses local ONNX MiniLM model from chromadb utilities.
    """
    import chromadb.utils.embedding_functions as ef
    fn = ef.ONNXMiniLM_L6_V2()
    embeddings = fn(texts)
    # Convert elements to standard Python float lists for JSON compatibility
    return [[float(val) for val in emb] for emb in embeddings]


def cosine_similarity(query_emb: np.ndarray, doc_embs: np.ndarray) -> np.ndarray:
    """Computes cosine similarity between a query vector and document vectors."""
    dot_product = np.dot(doc_embs, query_emb)
    norm_query = np.linalg.norm(query_emb)
    norm_docs = np.linalg.norm(doc_embs, axis=1)
    
    denominator = norm_query * norm_docs
    denominator[denominator == 0] = 1e-8
    return dot_product / denominator


class PGVectorRAGService:
    """
    Manages the ingestion and querying of financial documents using the Django DB.
    """

    def ingest_document(self, symbol: str, document_id: int,
                         file_path: str, doc_title: str,
                         doc_type: str = 'other') -> dict:
        """
        Extracts text from a PDF, chunks it, embeds and stores in Django DB.
        Updates the StockDocument.is_indexed and .chunk_count fields.

        Returns: {'success': bool, 'chunk_count': int, 'error': str|None}
        """
        try:
            # 1. Retrieve the document and load file content from storage
            doc = None
            try:
                doc = StockDocument.objects.get(id=document_id)
            except StockDocument.DoesNotExist:
                pass

            import io
            if doc and doc.file:
                try:
                    with doc.file.open('rb') as f:
                        pdf_source = io.BytesIO(f.read())
                except Exception as e:
                    logger.warning(f"[RAG] Failed to open file from storage for doc {document_id}, trying file_path: {e}")
                    pdf_source = file_path
            else:
                pdf_source = file_path

            # Validate local file path if source is string path
            if isinstance(pdf_source, str):
                if not os.path.exists(pdf_source):
                    return {'success': False, 'chunk_count': 0, 'error': f'File not found: {pdf_source}'}

            # 1. Extract text from PDF source
            text = _extract_pdf_text(pdf_source)
            if not text.strip():
                return {'success': False, 'chunk_count': 0, 'error': 'No text found in PDF'}

            # 2. Chunk text
            chunks = _chunk_text(text)
            if not chunks:
                return {'success': False, 'chunk_count': 0, 'error': 'Could not extract chunks'}

            # 3. Generate embeddings
            embeddings = get_embeddings(chunks)

            # 4. Save to Database inside a transaction
            with transaction.atomic():
                # Get the document
                doc = StockDocument.objects.get(id=document_id)
                
                # Delete existing chunks for this document (idempotent re-index)
                DocumentChunk.objects.filter(document=doc).delete()
                
                # Bulk create DocumentChunks
                chunk_objects = []
                for idx, (chunk_text, emb) in enumerate(zip(chunks, embeddings)):
                    chunk_objects.append(
                        DocumentChunk(
                            document=doc,
                            chunk_index=idx,
                            content=chunk_text,
                            embedding=emb
                        )
                    )
                DocumentChunk.objects.bulk_create(chunk_objects)
                
                # Update document stats
                doc.is_indexed = True
                doc.chunk_count = len(chunks)
                doc.save(update_fields=['is_indexed', 'chunk_count'])

            logger.info(f"[RAG] Indexed {len(chunks)} chunks for {symbol} doc {document_id}")
            return {'success': True, 'chunk_count': len(chunks), 'error': None}

        except Exception as e:
            logger.error(f"[RAG] Ingest error for {symbol}: {e}", exc_info=True)
            return {'success': False, 'chunk_count': 0, 'error': str(e)}

    def reindex_symbol(self, symbol: str) -> dict:
        """
        Re-indexes ALL documents for a symbol from their saved files.
        Returns: {'success': bool, 'indexed': int, 'errors': list}
        """
        docs = StockDocument.objects.filter(stock__symbol=symbol)
        indexed = 0
        errors = []
        for doc in docs:
            try:
                result = self.ingest_document(
                    symbol=symbol,
                    document_id=doc.id,
                    file_path='',
                    doc_title=doc.title,
                    doc_type=doc.document_type,
                )
                if result['success']:
                    indexed += 1
                else:
                    errors.append(f"Doc {doc.id} ({doc.title}): {result['error']}")
            except Exception as e:
                errors.append(f"Doc {doc.id} ({doc.title}): {str(e)}")
        return {'success': len(errors) == 0, 'indexed': indexed, 'errors': errors}

    def query(self, symbol: str, question: str, doc_type: str = None) -> dict:
        """
        Retrieves top-K chunks for the question and calls LLM to answer.
        Auto-reindexes from DB if chunks are missing.
        Returns: {'answer': str, 'sources': list, 'error': str|None}
        """
        try:
            # 1. Fetch chunks from DB
            db_docs = StockDocument.objects.filter(stock__symbol=symbol)
            if not db_docs.exists():
                return {
                    'answer': None,
                    'sources': [],
                    'error': f'No documents found for {symbol}. Please upload documents first.'
                }

            # Filter by document type if specified
            active_docs = db_docs
            if doc_type:
                active_docs = active_docs.filter(document_type=doc_type)

            chunks = DocumentChunk.objects.filter(document__in=active_docs).select_related('document')
            
            # 2. Auto-reindex if no chunks found but documents exist
            if not chunks.exists():
                logger.info(f"[RAG] No chunks in DB for {symbol}, auto-reindexing...")
                reindex_result = self.reindex_symbol(symbol)
                if reindex_result['indexed'] == 0:
                    return {
                        'answer': None,
                        'sources': [],
                        'error': f'Documents exist but could not be indexed. Please re-upload. Errors: {"; ".join(reindex_result["errors"][:2])}'
                    }
                # Re-fetch chunks after reindexing
                chunks = DocumentChunk.objects.filter(document__in=active_docs).select_related('document')

            chunk_list = list(chunks)
            if not chunk_list:
                return {
                    'answer': 'No document chunks found matching the filters.',
                    'sources': [],
                    'error': None
                }

            # 3. Compute similarities in Python
            query_emb = np.array(get_embeddings([question])[0])
            doc_embs = np.array([chunk.embedding for chunk in chunk_list])

            similarities = cosine_similarity(query_emb, doc_embs)

            # 4. Get Top-K matches
            n_results = min(TOP_K, len(chunk_list))
            top_k_indices = np.argsort(similarities)[::-1][:n_results]
            matched_chunks = [chunk_list[idx] for idx in top_k_indices]

            # Build context block
            context = '\n\n---\n\n'.join(
                f"[{chunk.document.title} – {chunk.document.get_document_type_display()}]\n{chunk.content}"
                for chunk in matched_chunks
            )

            # 5. Call LLM
            answer = self._answer_with_llm(symbol, question, context)
            
            # Format sources
            sources = [
                {'title': chunk.document.title, 'type': chunk.document.document_type}
                for chunk in matched_chunks
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
            logger.error(f"[RAG] Query error for {symbol}: {e}", exc_info=True)
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
        """Returns list of all documents for a symbol from the DB."""
        try:
            # Show ALL documents (not just is_indexed=True) so users see pending ones too
            docs = StockDocument.objects.filter(
                stock__symbol=symbol
            ).values('id', 'title', 'document_type', 'uploaded_at', 'chunk_count', 'is_indexed')
            return list(docs)
        except Exception:
            return []

    def get_collection_stats(self, symbol: str) -> dict:
        """Returns collection stats for a symbol."""
        try:
            count = DocumentChunk.objects.filter(document__stock__symbol=symbol).count()
            return {'count': count, 'name': f"pgvector_{symbol}"}
        except Exception:
            return {'count': 0, 'name': None}


# Module-level singleton
pgvector_rag_service = PGVectorRAGService()
