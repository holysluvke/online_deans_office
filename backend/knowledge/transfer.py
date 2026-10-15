"""
Вопросы про перевод / перезачёт / задолженности (п. 3.5 Положения).

Условия перевода, перезачёта дисциплин и академических задолженностей
Положением не установлены. Отвечаем честно: answerable: false, value: null,
sources: [] — как у off-topic, безопасно для автопроверки.

Пользователю в message — сначала упоминание п. 3.5, затем результат
предварительной проверки комплектности (полезно: студент сразу видит,
хватает ли полей в его документе).
"""
from __future__ import annotations

from .answers import Answer
from .completeness import check_completeness

# Стеммы, чтобы ловить разные формы: «перевод», «перевестись», «для перевода».
_TRIGGERS = (
    "перевод",
    "перевес",
    "перезач",
    "задолженност",
)

_REASON = (
    "Условия перевода, перезачёта дисциплин и академических задолженностей "
    "Положением не установлены (п. 3.5)."
)


def is_transfer_question(question: str) -> bool:
    """True, если вопрос про перевод / перезачёт / задолженности."""
    q = question.lower().replace("ё", "е")
    return any(trigger in q for trigger in _TRIGGERS)


def transfer_answer(fields: dict, doc_type: str) -> Answer:
    """Ответ на вопрос про перевод: ссылка на п. 3.5 + результат проверки комплектности."""
    check = check_completeness(fields, doc_type)
    return Answer(
        status="no_answer",
        message=f"{_REASON} {check.message}",
        answerable=False,
        value=None,
        sources=[],
    )