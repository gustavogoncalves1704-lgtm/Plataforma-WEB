"""Configuração central — chaves via env/secrets."""
import os
from dotenv import load_dotenv

load_dotenv()

def _get(key: str, default: str = "") -> str:
    try:
        import streamlit as st
        val = st.secrets.get(key)
        if val:
            return val
    except Exception:
        pass
    return os.getenv(key, default)

GROQ_API_KEY = _get("GROQ_API_KEY")
TAVILY_API_KEY = _get("TAVILY_API_KEY")

# Modelos Groq confirmados ativos em 2026
GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "openai/gpt-oss-120b",
    "qwen/qwen3-32b",
    "llama-3.1-8b-instant",
]

COMPRASMG_URL = "https://compras.mg.gov.br"
PNCP_URL = "https://dadosabertos.compras.gov.br"
TIMEOUT = 30

def setup_logging():
    import logging
    logging.basicConfig(
        format="%(asctime)s | %(levelname)s | %(message)s",
        level=logging.INFO,
    )