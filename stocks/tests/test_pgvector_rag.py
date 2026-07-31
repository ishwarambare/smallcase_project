"""
Tests for pgvector_rag_service.py — Gemini embedding, chunking, PDF extraction, and the full PGVectorRAGService pipeline.
"""

import os
import sys
import io
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock, mock_open
import numpy as np

os.environ["HOME"] = os.environ.get("USERPROFILE", "")
os.environ["DJANGO_SETTINGS_MODULE"] = "smallcase_project.settings"

# Ensure chromadb can be imported (Path.home() needs HOME env on some systems)
import pathlib
pathlib.Path.home()  # warm up the home directory resolution

import django
django.setup()

from stocks.pgvector_rag_service import (
    _chunk_text,
    _extract_pdf_text,
    get_embeddings,
    cosine_similarity,
    PGVectorRAGService,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    TOP_K,
)


MOCK_TEXT = """Apple Inc. (AAPL) is an American multinational technology company headquartered in Cupertino, California.
In fiscal year 2024, Apple reported total revenue of $391 billion, with net income of $97 billion.
The company's Services segment reached an all-time high of $85 billion.
iPhone revenue accounted for approximately 52% of total revenue.
Apple's installed base of active devices grew to over 2.2 billion worldwide.
The company returned over $29 billion to shareholders through dividends and share repurchases."""


class TestChunkText(unittest.TestCase):
    def test_chunk_short_text(self):
        chunks = _chunk_text("Short text")
        self.assertEqual(len(chunks), 0)

    def test_chunk_long_text(self):
        text = "A" * 1500
        chunks = _chunk_text(text)
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertGreater(len(c), 50)
            self.assertLessEqual(len(c), CHUNK_SIZE)

    def test_chunk_overlap(self):
        text = "X" * (CHUNK_SIZE + CHUNK_OVERLAP + 10)
        chunks = _chunk_text(text)
        if len(chunks) >= 2:
            self.assertIn("X" * min(CHUNK_OVERLAP, len(chunks[-1])), chunks[-1])


class TestExtractPdfText(unittest.TestCase):
    @patch("pypdf.PdfReader")
    def test_extract_success(self, MockPdfReader):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page 1 content"
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        MockPdfReader.return_value = mock_reader

        result = _extract_pdf_text("dummy.pdf")
        self.assertEqual(result, "Page 1 content")
        MockPdfReader.assert_called_once_with("dummy.pdf")

    @patch("builtins.__import__", side_effect=ImportError("no module named pypdf"))
    def test_extract_no_pypdf(self, mock_import):
        with self.assertRaises(ImportError):
            _extract_pdf_text("dummy.pdf")


class TestGetEmbeddings(unittest.TestCase):
    @patch.dict(os.environ, {"GEMINI_API_KEY": "AIzaSyBP_7V7I23ckkXPyAyul2_Kt8PQecjDDEw", "HOME": os.environ.get("USERPROFILE", "")})
    def test_gemini_embedding_success(self):
        import google.generativeai as real_genai
        mock_genai = MagicMock()
        with patch.object(real_genai, "configure"), \
             patch.object(real_genai, "embed_content", return_value={
                 "embedding": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
             }):
            result = get_embeddings(["text one", "text two"])
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0], [0.1, 0.2, 0.3])

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "HOME": os.environ.get("USERPROFILE", "")})
    def test_gemini_embedding_empty_response(self):
        import google.generativeai as real_genai
        import chromadb.utils.embedding_functions as chroma_ef
        mock_fn = MagicMock()
        mock_fn.return_value = [[0.5, 0.6]]

        with patch.object(real_genai, "configure"), \
             patch.object(real_genai, "embed_content", return_value={"embedding": []}), \
             patch.object(chroma_ef, "ONNXMiniLM_L6_V2", return_value=mock_fn):
            result = get_embeddings(["test"])
            self.assertEqual(len(result), 1)
            mock_fn.assert_called_once_with(["test"])

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "HOME": os.environ.get("USERPROFILE", "")})
    def test_gemini_embedding_fallback_on_exception(self):
        import google.generativeai as real_genai
        import chromadb.utils.embedding_functions as chroma_ef
        mock_fn = MagicMock()
        mock_fn.return_value = [[0.7, 0.8]]

        with patch.object(real_genai, "configure"), \
             patch.object(real_genai, "embed_content", side_effect=Exception("API Error")), \
             patch.object(chroma_ef, "ONNXMiniLM_L6_V2", return_value=mock_fn):
            result = get_embeddings(["test"])
            self.assertEqual(len(result), 1)
            mock_fn.assert_called_once_with(["test"])

    @patch.dict(os.environ, {"HOME": os.environ.get("USERPROFILE", "")})
    def test_onnx_fallback_no_gemini_key(self):
        # Temporarily remove GEMINI_API_KEY from environment to force fallback
        with patch.dict(os.environ, {}):
            if "GEMINI_API_KEY" in os.environ:
                del os.environ["GEMINI_API_KEY"]
            import chromadb.utils.embedding_functions as chroma_ef
            mock_fn = MagicMock()
            mock_fn.return_value = [[0.5, 0.6], [0.7, 0.8]]

            with patch.object(chroma_ef, "ONNXMiniLM_L6_V2", return_value=mock_fn):
                result = get_embeddings(["Hello world", "Test embedding"])
                self.assertEqual(len(result), 2)
                self.assertEqual(result, [[0.5, 0.6], [0.7, 0.8]])
                mock_fn.assert_called_once_with(["Hello world", "Test embedding"])


class TestCosineSimilarity(unittest.TestCase):
    def test_similar_vectors(self):
        query = np.array([1.0, 0.0])
        docs = np.array([[1.0, 0.0], [0.0, 1.0]])
        sims = cosine_similarity(query, docs)
        self.assertAlmostEqual(sims[0], 1.0)
        self.assertAlmostEqual(sims[1], 0.0)

    def test_zero_vector(self):
        query = np.array([0.0, 0.0])
        docs = np.array([[1.0, 0.0]])
        sims = cosine_similarity(query, docs)
        self.assertAlmostEqual(sims[0], 0.0)


class TestPGVectorRAGService(unittest.TestCase):
    def setUp(self):
        self.service = PGVectorRAGService()
        self.temp_pdf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        self.temp_pdf.write(b"%PDF-1.4 dummy pdf content for testing purposes")
        self.temp_pdf.close()

    def tearDown(self):
        os.unlink(self.temp_pdf.name)

    @patch("stocks.pgvector_rag_service._extract_pdf_text", return_value=MOCK_TEXT)
    @patch("stocks.pgvector_rag_service.get_embeddings", return_value=[[0.1, 0.2]] * 3)
    @patch("stocks.pgvector_rag_service.transaction.atomic")
    @patch("stocks.pgvector_rag_service.DocumentChunk")
    @patch("stocks.pgvector_rag_service.DocumentChunk.objects.bulk_create")
    @patch("stocks.pgvector_rag_service.DocumentChunk.objects.filter")
    @patch("stocks.pgvector_rag_service.StockDocument.objects.get")
    def test_ingest_document_success(
        self, mock_doc_get, mock_chunk_filter, mock_bulk_create,
        mock_document_chunk, mock_atomic, mock_get_emb, mock_extract
    ):
        mock_doc = MagicMock()
        mock_doc.file = None
        mock_doc.id = 1
        mock_doc.notes = ""
        mock_doc.is_indexed = False
        mock_doc.chunk_count = 0
        mock_doc_get.return_value = mock_doc

        mock_chunk_qs = MagicMock()
        mock_chunk_filter.return_value = mock_chunk_qs

        result = self.service.ingest_document(
            symbol="AAPL",
            document_id=1,
            file_path=self.temp_pdf.name,
            doc_title="Apple Test Report",
            doc_type="annual_report",
        )
        self.assertTrue(result["success"])
        self.assertGreater(result["chunk_count"], 0)

    @patch("stocks.pgvector_rag_service.StockDocument.objects.get")
    def test_ingest_document_file_not_found(self, mock_doc_get):
        mock_doc_get.return_value = None
        result = self.service.ingest_document(
            symbol="AAPL",
            document_id=1,
            file_path="nonexistent.pdf",
            doc_title="Test",
            doc_type="other",
        )
        self.assertFalse(result["success"])
        self.assertIn("File not found", result["error"])

    def test_query_no_documents(self):
        with patch("stocks.pgvector_rag_service.StockDocument.objects.filter") as mock_filter:
            mock_qs = MagicMock()
            mock_qs.exists.return_value = False
            mock_filter.return_value = mock_qs

            result = self.service.query("AAPL", "What is revenue?")
            self.assertIsNone(result["answer"])
            self.assertIn("No documents found", result["error"])

    def test_list_documents_empty(self):
        with patch("stocks.pgvector_rag_service.StockDocument.objects.filter") as mock_filter:
            mock_qs = MagicMock()
            mock_qs.values.return_value = []
            mock_filter.return_value = mock_qs

            result = self.service.list_documents("AAPL")
            self.assertEqual(result, [])

    def test_get_collection_stats_empty(self):
        with patch("stocks.pgvector_rag_service.DocumentChunk.objects.filter") as mock_filter:
            mock_qs = MagicMock()
            mock_qs.count.return_value = 0
            mock_filter.return_value = mock_qs

            result = self.service.get_collection_stats("AAPL")
            self.assertEqual(result["count"], 0)
            self.assertEqual(result["name"], "pgvector_AAPL")


if __name__ == "__main__":
    unittest.main(verbosity=2)
