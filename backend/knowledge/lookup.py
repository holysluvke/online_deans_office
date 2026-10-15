"""
Ответ по конкретному полю (Q2).

Поддерживаются:
- кавычки любых видов (« », „ “, ", ') и вопрос без кавычек;
- синонимы полей («когда выдана», «какая оценка», «кто руководитель практики»);
- опечатки (нечёткое сравнение через difflib.SequenceMatcher).

Выбор поля:
- лучший кандидат должен оторваться от второго на MIN_MARGIN (≥ 0.05),
  иначе возвращается no_answer;
- поле из чужого типа документа → no_answer;
- поле не найдено в документе → answerable: false, value: null, sources: [];
- поле найдено → answerable: true, value = значение, sources: ["field:<ключ>"].
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from .answers import Answer, no_answer
from .dates import humanize_date
from .labels import LABEL_TO_FIELD, label_for
from .rules import MISSING, TEXT_FIELDS
from .text import normalize as _normalize

# Нормализация вопроса

# Все виды кавычек, которые могут встретиться в вопросе.
_QUOTES_OPEN  = "«„“\"'"
_QUOTES_CLOSE = "»“”\"'"
_QUOTED = re.compile(rf"[{_QUOTES_OPEN}]([^{_QUOTES_OPEN}{_QUOTES_CLOSE}]+)[{_QUOTES_CLOSE}]")

# Служебные слова, которые не помогают определить поле.
_STOPWORDS = frozenset({
    "укажи", "укажите", "значение", "поля", "поле",
    "какова", "каков", "какая", "какие", "какой", "какое",
    "как", "кто", "когда", "что", "это", "сколько",
    "и", "в", "на", "у", "с", "по",
    "мне", "нам", "пожалуйста", "скажи", "подскажи",
})


def _clean(text: str) -> str:
    """Нормализация + удаление служебных слов. Единая для запроса и синонимов."""
    words = [w for w in _normalize(text).split() if w not in _STOPWORDS]
    return " ".join(words)


def _extract_query(question: str) -> str:
    """Содержательная часть вопроса: содержимое «...» либо весь вопрос без служебных слов."""
    quoted = _QUOTED.search(question)
    raw = quoted.group(1) if quoted else question
    return _clean(raw)

# Синонимы полей

# Расширенные синонимы, включая вопросы. Точные подписи из LABELS добавляются
# автоматически через _build_synonyms() — их дублировать не нужно.
FIELD_SYNONYMS: dict[str, tuple[str, ...]] = {
    "student_name": (
        "фио студента", "фио", "фамилия имя отчество", "имя студента",
        "как зовут студента", "как зовут", "фио обучающегося",
    ),
    "university": (
        "название вуза", "вуз", "университет", "название университета",
        "учебное заведение", "название учебного заведения",
    ),
    "program": (
        "направление подготовки", "направление", "специальность",
        "программа обучения", "программа",
    ),
    "study_form": (
        "форма обучения", "форма учебы", "очная или заочная",
    ),
    "study_start": (
        "начало периода обучения", "начало обучения",
        "дата начала обучения", "с какого числа учится",
    ),
    "study_end": (
        "окончание периода обучения", "окончание обучения",
        "дата окончания обучения", "когда заканчивает учиться",
    ),
    "document_number": (
        "номер справки", "номер документа", "номер",
    ),
    "issue_date": (
        "дата выдачи", "когда выдана", "когда выдан",
        "дата выдачи справки", "какова дата выдачи", "какая дата выдачи",
    ),
    "group": (
        "учебная группа", "группа", "номер группы",
    ),
    "course": (
        "курс", "на каком курсе",
    ),
    "leave_reason": (
        "причина отпуска", "причина", "почему отпуск",
    ),
    "leave_start": (
        "дата начала отпуска", "начало отпуска", "с какого числа отпуск",
    ),
    "leave_end": (
        "дата окончания отпуска", "окончание отпуска", "по какое число отпуск",
    ),
    "application_date": (
        "дата заявления", "когда подано заявление", "когда написано заявление",
    ),
    "organization": (
        "название организации", "организация", "место практики",
        "где проходил практику",
    ),
    "internship_start": (
        "дата начала практики", "начало практики", "с какого числа практика",
    ),
    "internship_end": (
        "дата окончания практики", "окончание практики", "по какое число практика",
    ),
    "supervisor_name": (
        "фио руководителя практики", "руководитель практики",
        "фио руководителя", "кто руководитель практики", "руководитель",
    ),
    "grade": (
        "оценка", "какая оценка", "какую оценку получил", "оценка за практику",
    ),
}

def _build_synonyms() -> dict[str, tuple[str, ...]]:
    """Объединяет расширенные синонимы с точными подписями из LABELS."""
    merged: dict[str, list[str]] = {f: list(s) for f, s in FIELD_SYNONYMS.items()}
    for label, field in LABEL_TO_FIELD.items():
        bucket = merged.setdefault(field, [])
        if label not in bucket:
            bucket.append(label)
    return {f: tuple(s) for f, s in merged.items()}

# Матчер
@dataclass(frozen=True)
class MatchResult:
    """Результат сопоставления: лучший кандидат, его score и score второго."""
    field: str
    score: float
    runner_up_score: float

    @property
    def margin(self) -> float:
        return self.score - self.runner_up_score


class FieldMatcher:
    """Нечёткое сопоставление свободного запроса с полями через синонимы."""

    MIN_SCORE = 0.7
    MIN_MARGIN = 0.05

    def __init__(self, synonyms: dict[str, tuple[str, ...]]) -> None:
        # Нормализуем синонимы один раз, чтобы не делать этого при каждом запросе.
        self._index = {
            field: tuple(_clean(s) for s in phrases)
            for field, phrases in synonyms.items()
        }

    def match(self, query: str) -> MatchResult | None:
        """Находит лучший и второй по величине score среди полей."""
        if not query:
            return None

        scored = [
            (max((self._similarity(query, s) for s in phrases), default=0.0), field)
            for field, phrases in self._index.items()
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)

        best_score, best_field = scored[0]
        if best_score < self.MIN_SCORE:
            return None

        runner_up = scored[1][0] if len(scored) > 1 else 0.0
        return MatchResult(field=best_field, score=best_score, runner_up_score=runner_up)

    def is_confident(self, result: MatchResult) -> bool:
        """True, если лучший кандидат уверенно обходит второго."""
        return result.margin >= self.MIN_MARGIN

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        if a == b:
            return 1.0
        shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
        pattern = rf"(?<![а-яёa-z]){re.escape(shorter)}(?![а-яёa-z])"
        if re.search(pattern, longer):
            return 0.9
        return SequenceMatcher(None, a, b).ratio()

_MATCHER = FieldMatcher(_build_synonyms())

# Публичная функция

def field_lookup(fields: dict, doc_type: str, question: str) -> Answer:
    """Ответ на вопрос по конкретному полю. Если уверенности нет — no_answer.

    Всегда возвращает Answer (никогда None): вопрос про поле, поле из чужого типа
    и вопрос не про поле — все они корректно отображаются на Answer.
    """
    query = _extract_query(question)
    result = _MATCHER.match(query)

    if result is None or not _MATCHER.is_confident(result):
        return no_answer()

    if result.field not in TEXT_FIELDS.get(doc_type, {}):
        return no_answer()

    value = fields.get(result.field)
    if value in (None, "", MISSING):
        return _missing_field(result.field, doc_type)
    return _found_field(result.field, doc_type, value)


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
        message=f"{label}: {humanize_date(value)}.",
        sources=[f"field:{field}"],
        answerable=True,
        value=value,
    )