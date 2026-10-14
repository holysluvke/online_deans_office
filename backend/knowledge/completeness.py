"""
Проверка комплектности документа (Q1).

Идёт по всем обязательным полям типа: текстовым и флагам подписи/печати.
Если что-то не найдено — собирает список ключей и множество пунктов.

Полный документ → sources содержат все пункты типа (3.1, 3.2, 3.3).
Неполный         → sources содержат только пункты недостающих элементов.
Так требует reference_results.json.
"""
from .answers import Answer, no_answer
from .labels import label_for
from .rules import ALL_CLAUSES, MISSING, SIGN_FIELDS, TEXT_FIELDS, as_source, sort_rules


def check_completeness(fields: dict, doc_type: str) -> Answer:
    """Проверяет обязательные поля и флаги для типа документа."""
    if doc_type not in TEXT_FIELDS:
        return no_answer()

    missing_keys: list[str] = []
    missing_clauses: set[str] = set()

    for key, clause in TEXT_FIELDS[doc_type].items():
        if fields.get(key) in (None, "", MISSING):
            missing_keys.append(key)
            missing_clauses.add(clause)

    for key, clause in SIGN_FIELDS[doc_type].items():
        if not fields.get(key):
            missing_keys.append(key)
            missing_clauses.add(clause)

    if not missing_keys:
        return _full_document(doc_type)
    return _incomplete_document(doc_type, missing_keys, missing_clauses)


def _full_document(doc_type: str) -> Answer:
    clauses = ALL_CLAUSES[doc_type]
    return Answer(
        status="ok",
        message=(
            f"Документ содержит все обязательные сведения по пунктам "
            f"{', '.join(clauses)} Положения. "
            f"Окончательное решение примет сотрудник деканата."
        ),
        sources=as_source(clauses),
        answerable=True,
        value="document_ok",
    )


def _incomplete_document(doc_type: str, missing_keys: list[str], missing_clauses: set[str]) -> Answer:
    missing_labels = ", ".join(label_for(k, doc_type).lower() for k in missing_keys)
    missing_sorted = sort_rules(missing_clauses)
    return Answer(
        status="missing",
        message=(
            f"Не хватает следующих сведений: {missing_labels}. "
            f"Основание: пункты {', '.join(missing_sorted)} Положения."
        ),
        sources=as_source(missing_sorted),
        answerable=True,
        value="missing_fields",
        missing_fields=missing_keys,
    )