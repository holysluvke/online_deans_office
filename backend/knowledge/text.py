"""Нормализация текста вопроса: регистр, ё→е, кавычки и пунктуация → пробел, пробелы."""
from __future__ import annotations

import re

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_SPACES = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Регистр, ё→е, пунктуация (включая кавычки) → пробел, схлопывание пробелов."""
    text = text.lower().replace("ё", "е")
    text = _PUNCT.sub(" ", text)
    return _SPACES.sub(" ", text).strip()