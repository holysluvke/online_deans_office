# backend/knowledge/lookup.py

"""
Ответ по конкретному полю (Q2): «Укажи значение поля «X».».

Из вопроса вытаскивается подпись поля из «...» и переводится в ключ через LABEL_TO_FIELD.
Источник ответа — field:<ключ>, а не rule:<пункт>. Так требует reference_results.json.
"""
import re

from .answers import Answer
from .labels import LABEL_TO_FIELD, label_for
from .rules import MISSING, TEXT_FIELDS

# Захватывает содержимое «...» до первой закрывающей ёлочки.
_FIELD_IN_QUOTES = re.compile(r"«([^»]+)»")


def field_lookup(fields: dict, doc_type: str, question: str) -> Answer | None:
    """None, если вопрос не про поле или поле не относится к этому типу документа."""
    match = _FIELD_IN_QUOTES.search(question)
    if not match:
        return None

    field = LABEL_TO_FIELD.get(match.group(1).strip().lower())
    if field is None or field not in TEXT_FIELDS.get(doc_type, {}):
        return None

    value = fields.get(field)
    if value in (None, "", MISSING):
        return _missing_field(field, doc_type)
    return _found_field(field, doc_type, value)


def _missing_field(field: str, doc_type: str) -> Answer:
    label = label_for(field, doc_type)
    return Answer(
        status="missing",
        message=f"Поле «{label}» не найдено в документе. Обратитесь в деканат.",
    )


def _found_field(field: str, doc_type: str, value: str) -> Answer:
    label = label_for(field, doc_type)
    return Answer(
        status="ok",
        message=f"{label}: {value}.",
        sources=[f"field:{field}"],
        answerable=True,
        value=value,
    )