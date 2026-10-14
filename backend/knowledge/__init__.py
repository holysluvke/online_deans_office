"""
База знаний «Онлайн-деканата»: требования Положения и ответы на вопросы.

Публичный API:
    Answer             — единый формат ответа
    check_completeness — проверка комплектности (Q1)
    field_lookup       — ответ по конкретному полю (Q2)
    who_decides        — ответ на вопрос «кто решает» (Q3)
    no_answer          — fallback для off-topic и нераспознанных вопросов
"""
from .answers import Answer, no_answer, who_decides
from .completeness import check_completeness
from .lookup import field_lookup

__all__ = [
    "Answer",
    "check_completeness",
    "field_lookup",
    "no_answer",
    "who_decides",
]