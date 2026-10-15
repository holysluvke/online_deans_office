"""
Единый формат ответа answer_question и два простых конструктора.

Answer собирается в completeness.py, lookup.py и здесь.
На границе стыка с jobs.py вызывается to_dict() — jobs.py сериализует ответ в JSON.
"""
from dataclasses import dataclass, field

from .rules import DECISION_CLAUSE


@dataclass
class Answer:
    """Ответ на вопрос студента.

    status     — для UI: "ok" | "missing" | "no_answer" (цвет карточки).
    message    — текст для пользователя.
    sources    — ссылки на источники: ["rule:3.1"] или ["field:student_name"].
    answerable — для автопроверки: был ли у системы ответ.
    value      — машинное значение для автопроверки: "document_ok" / "missing_fields" /
                 значение поля / None.
    missing_fields — только для Q1: ключи недостающих полей.
    """
    status: str
    message: str
    sources: list[str] = field(default_factory=list)
    answerable: bool = False
    value: str | None = None
    missing_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Словарь для answer_question — 6 полей, включая missing_fields."""
        return {
            "status":         self.status,
            "message":        self.message,
            "sources":        self.sources,
            "answerable":     self.answerable,
            "value":          self.value,
            "missing_fields": self.missing_fields,
        }


def who_decides() -> Answer:
    """Ответ на вопрос «Кто принимает окончательное решение?» (п. 1.3)."""
    return Answer(
        status="ok",
        message=f"Окончательное решение принимает сотрудник деканата, пункт {DECISION_CLAUSE} Положения.",
        sources=[f"rule:{DECISION_CLAUSE}"],
        answerable=True,
        value="сотрудник деканата",
    )


def no_answer() -> Answer:
    """Fallback: в документе и Положении нет ответа (п. 2.4 и 6.3)."""
    return Answer(
        status="no_answer",
        message=(
            "В документе и в Положении нет информации для ответа на этот вопрос. "
            "Обратитесь в деканат."
        ),
    )