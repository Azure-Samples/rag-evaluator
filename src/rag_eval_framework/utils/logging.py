"""Logging helpers for the RAG Evaluation Framework."""

from __future__ import annotations

import logging


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger under the framework root."""
    return logging.getLogger(f"rag_eval_framework.{name}")
