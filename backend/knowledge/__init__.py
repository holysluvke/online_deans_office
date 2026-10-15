"""
База знаний «Онлайн-деканата»: требования Положения и ответы на вопросы.

Публичный API:
    Answer             — единый формат ответа (6 полей, включая missing_fields)
    check_completeness — проверка комплектности (Q1)
    field_lookup       — ответ по конкретному полю (Q2)
    who_decides        — ответ на вопрос «кто решает» (Q3)
    no_answer          — fallback для off-topic и нераспознанных вопросов
    ROUTER             — роутер вопросов (fuzzy-матчинг)
"""
from .answers import Answer, no_answer, who_decides
from .completeness import check_completeness
from .lookup import field_lookup
from .router import ROUTER
from .transfer import is_transfer_question, transfer_answer

__all__ = [
    "Answer",
    "ROUTER",
    "check_completeness",
    "field_lookup",
    "is_transfer_question",
    "no_answer",
    "transfer_answer",
    "who_decides",
]