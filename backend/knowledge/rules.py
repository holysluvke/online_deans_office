"""
Требования Положения к каждому типу документа.

Каждое текстовое поле привязано к пункту, который его требует.
Флаги подписи и печати вынесены отдельно: у них тип bool, а не str.

ALL_CLAUSES — все пункты типа. Нужны, когда документ полный:
в sources должны попасть все три (3.1, 3.2, 3.3), а не только проверенные.
"""

# Строка, которой помечается ненайденное поле. Совпадает с полем MISSING в OCR.
MISSING = "не найдено"


TEXT_FIELDS: dict[str, dict[str, str]] = {
    "study_certificate": {
        "student_name":    "3.1",
        "university":      "3.1",
        "program":         "3.1",
        "study_form":      "3.1",
        "study_start":     "3.1",
        "study_end":       "3.1",
        "document_number": "3.1",
        "issue_date":      "3.1",
    },
    "academic_leave_application": {
        "student_name":     "4.1",
        "group":            "4.1",
        "course":           "4.1",
        "leave_reason":     "4.1",
        "leave_start":      "4.1",
        "leave_end":        "4.1",
        "application_date": "4.1",
    },
    "internship_certificate": {
        "student_name":     "5.1",
        "organization":     "5.1",
        "internship_start": "5.1",
        "internship_end":   "5.1",
        "supervisor_name":  "5.1",
        "grade":            "5.1",
        "document_number":  "5.1",
        "issue_date":       "5.1",
    },
}

SIGN_FIELDS: dict[str, dict[str, str]] = {
    "study_certificate":          {"signature_present": "3.2", "seal_present": "3.3"},
    "academic_leave_application": {"signature_present": "4.2"},
    "internship_certificate":     {"signature_present": "5.2", "seal_present": "5.3"},
}

ALL_CLAUSES: dict[str, list[str]] = {
    "study_certificate":          ["3.1", "3.2", "3.3"],
    "academic_leave_application": ["4.1", "4.2"],
    "internship_certificate":     ["5.1", "5.2", "5.3"],
}

# Пункт, где сказано, кто принимает окончательное решение.
DECISION_CLAUSE = "1.3"


def rule_number(clause: str) -> tuple[int, ...]:
    """'3.1' → (3, 1). Для сортировки пунктов по возрастанию."""
    return tuple(int(part) for part in clause.split("."))


def sort_rules(clauses) -> list[str]:
    """Убирает дубли и сортирует: ['3.2', '3.1'] → ['3.1', '3.2']."""
    return sorted(set(clauses), key=rule_number)


def as_source(clauses) -> list[str]:
    """Готовит sources в формате evaluate.py: ['3.1'] → ['rule:3.1']."""
    return [f"rule:{c}" for c in sort_rules(clauses)]