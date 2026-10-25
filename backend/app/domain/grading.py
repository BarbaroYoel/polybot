"""Deterministic comparison of one lesson answer (F5 S8).

The lesson practice is producing text in the practised language, so the comparison decides what
counts as the same answer. Case, spacing and punctuation are ignored because they are typing, not
knowledge: «Bonjour, comment allez-vous ?» and «bonjour comment allez-vous» are the same answer.
Accents are **not** ignored: «élève» and «eleve» are different words in French, and a tutor that
accepts both would teach the mistake.

`domain/` imports no infrastructure (docs/architecture.md §3): the stdlib is enough here.
"""

import re
import unicodedata
from collections.abc import Sequence

# Anything that is not a letter, a digit or a space is punctuation for this comparison. Apostrophes
# and hyphens are included on purpose: «Je m'appelle» and «Je m appelle» must both be accepted.
_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)
_SPACES = re.compile(r"\s+", re.UNICODE)


def normalize_answer(text: str) -> str:
    """Case, punctuation and spacing folded; accents kept. Empty text stays empty."""
    folded = unicodedata.normalize("NFKC", text).casefold()
    spaced = _PUNCTUATION.sub(" ", folded)
    return _SPACES.sub(" ", spaced).strip()


def is_correct(answer: str, accepted: Sequence[str]) -> bool:
    """True when the answer matches one of the accepted ones after normalization."""
    normalized = normalize_answer(answer)
    return bool(normalized) and normalized in {
        candidate for candidate in map(normalize_answer, accepted) if candidate
    }
