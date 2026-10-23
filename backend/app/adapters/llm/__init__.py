"""Concrete LLM adapters. Everything Pi-specific stays inside this package (F3 S1-S2)."""

from app.adapters.llm.pi import PiCliAdapter

__all__ = ["PiCliAdapter"]
