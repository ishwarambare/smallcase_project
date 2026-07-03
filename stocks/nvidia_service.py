"""
stocks/nvidia_service.py

NVIDIA NIM Service — OpenAI-compatible LLM wrapper.

NVIDIA NIM provides free-tier access to powerful LLMs via an OpenAI-compatible API.
Endpoint: https://integrate.api.nvidia.com/v1

Supported free models:
  - meta/llama-3.1-70b-instruct    (default — best reasoning)
  - meta/llama-3.1-8b-instruct     (faster, smaller)
  - nvidia/llama-3.1-nemotron-70b-instruct (NVIDIA fine-tuned)
  - mistralai/mixtral-8x7b-instruct-v0.1

Usage:
    from stocks.nvidia_service import nvidia_llm, call_nvidia
    response = call_nvidia("What is ROCE?")
    lc_llm = nvidia_llm()  # LangChain ChatOpenAI instance pointing to NVIDIA NIM
"""

import os
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

NVIDIA_BASE_URL    = getattr(settings, 'NVIDIA_BASE_URL', 'https://integrate.api.nvidia.com/v1')
NVIDIA_API_KEY     = getattr(settings, 'NVIDIA_API_KEY', os.environ.get('NVIDIA_API_KEY', ''))
NVIDIA_DEFAULT_MODEL = getattr(settings, 'NVIDIA_DEFAULT_MODEL', 'meta/llama-3.1-70b-instruct')


def nvidia_llm(model: str = None, temperature: float = 0.1, max_tokens: int = 2048):
    """
    Returns a LangChain ChatOpenAI instance configured for NVIDIA NIM.

    NVIDIA NIM is OpenAI API-compatible, so we simply swap:
        base_url  → https://integrate.api.nvidia.com/v1
        api_key   → your NVIDIA API key

    Args:
        model: Model name (default: meta/llama-3.1-70b-instruct)
        temperature: Sampling temperature (0 = deterministic)
        max_tokens: Maximum response tokens

    Returns:
        langchain_openai.ChatOpenAI instance
    """
    try:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            base_url=NVIDIA_BASE_URL,
            api_key=NVIDIA_API_KEY,
            model=model or NVIDIA_DEFAULT_MODEL,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except ImportError:
        raise ImportError(
            "langchain-openai is not installed. Run: pip install langchain-openai"
        )


def call_nvidia(
    prompt: str,
    model: str = None,
    temperature: float = 0.1,
    max_tokens: int = 2048,
    system_prompt: str = "You are a helpful financial analysis assistant.",
) -> str:
    """
    Simple synchronous call to NVIDIA NIM API.
    Returns the text content of the first response message.

    Args:
        prompt: User prompt / question
        model: Override default model
        temperature: Sampling temperature
        max_tokens: Max output tokens
        system_prompt: System message

    Returns:
        str — LLM response text
    """
    try:
        from openai import OpenAI

        client = OpenAI(
            base_url=NVIDIA_BASE_URL,
            api_key=NVIDIA_API_KEY,
        )
        completion = client.chat.completions.create(
            model=model or NVIDIA_DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return completion.choices[0].message.content

    except Exception as e:
        logger.error(f"[NVIDIA] API call failed: {e}", exc_info=True)
        raise


def nvidia_embeddings():
    """
    Returns a LangChain NVIDIAEmbeddings instance for semantic search.
    Falls back to sentence-transformers if nvidia endpoints not available.

    NVIDIA embedding model: NV-Embed-QA (free tier)
    """
    try:
        from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
        return NVIDIAEmbeddings(
            model="nvidia/nv-embedqa-e5-v5",
            api_key=NVIDIA_API_KEY,
        )
    except Exception as e:
        logger.warning(f"[NVIDIA] Embeddings unavailable, falling back to local: {e}")
        # Fallback: use default ChromaDB embeddings (sentence-transformers)
        return None


def test_nvidia_connection() -> dict:
    """
    Quick health-check — calls NVIDIA NIM with a simple prompt.
    Returns {'ok': bool, 'model': str, 'response': str, 'error': str}
    """
    try:
        response = call_nvidia(
            prompt="Reply with exactly: NVIDIA NIM is working.",
            max_tokens=20,
            temperature=0,
        )
        return {
            'ok': True,
            'model': NVIDIA_DEFAULT_MODEL,
            'response': response.strip(),
            'error': None,
        }
    except Exception as e:
        return {
            'ok': False,
            'model': NVIDIA_DEFAULT_MODEL,
            'response': None,
            'error': str(e),
        }
