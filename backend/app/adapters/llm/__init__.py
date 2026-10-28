"""Concrete LLM adapters. Every harness-specific detail stays inside this package (ADR-004)."""

from app.adapters.llm.opencode import OpenCodeCliAdapter
from app.adapters.llm.pi import PiCliAdapter

__all__ = ["OpenCodeCliAdapter", "PiCliAdapter"]
