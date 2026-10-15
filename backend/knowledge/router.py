"""
Роутер вопросов: определяет намерение по нормализованной строке.

Устойчив к опечаткам: rapidfuzz.fuzz.ratio сравнивает вопрос с каноническими
формулировками. Ниже порога или без якоря — "other", и вопрос уходит
в field_lookup (он сам решает: Q2 или off-topic).

Намерения:
    completeness — Q1: «содержит ли документ все обязательные сведения»,
                       «чего не хватает», «проверь документ»
    who_decides  — Q3: «кто принимает окончательное решение»,
                       «кто решает принят ли документ»

Защита от ложных срабатываний:
    якоря «обязатель»/«сведен»/«положен» для completeness,
    «реша»/«решен»/«реши» для who_decides.
    Если score в «серой зоне» (88..93), якорь обязателен.
    Если score >= 93 — уверены и без якоря.

fuzz.token_set_ratio не используем: короткое подмножество слов может ложно
совпасть с канонической формулировкой.
"""
from __future__ import annotations

from dataclasses import dataclass
from rapidfuzz import fuzz

from .text import normalize

# Канонические фразы

_INTENTS: dict[str, tuple[str, ...]] = {
    "completeness": (
        "содержит ли документ все обязательные сведения по положению",
        "содержит ли документ все обязательные сведения",
        "все ли обязательные сведения",
        "все ли обязательные сведения есть в документе", 
        "все обязательные сведения",
        "все ли обязательные поля",
        "все ли поля заполнены",
        "чего не хватает",
        "чего не хватает в документе",
        "хватает ли сведений",
        "документ в порядке",
        "проверь документ",
        "проверь документ на комплектность",
        "проверь справку",
        "проверь заявление",
    ),
    "who_decides": (
        "кто принимает окончательное решение о принятии документа",
        "кто принимает окончательное решение",
        "кто принимает решение",
        "кто принимает решение о принятии документа",
        "кто решает принят ли документ",
        "кто решает",
    ),
}

# Якоря — обязательные подстроки в вопросе для «серой зоны».
_ANCHORS: dict[str, tuple[str, ...]] = {
    "completeness": ("обязатель", "сведен", "свед", "комплектн", "положен"),
    "who_decides": ("реша", "решен", "реши"),
}

# Стандартный вопрос кнопки «самостоятельная проверка» (п. 6.5).
SELF_CHECK_QUESTION = "Содержит ли документ все обязательные сведения по Положению?"


# Результат

@dataclass(frozen=True)
class RouteResult:
    intent: str            # "completeness" | "who_decides" | "other"
    score: float           # лучший score (0..100)
    runner_up_score: float # второй по величине

    @property
    def margin(self) -> float:
        return self.score - self.runner_up_score


# Роутер

class QuestionRouter:
    """Определяет намерение вопроса через fuzzy-сравнение с каноническими фразами."""

    WEAK_THRESHOLD = 88.0     # выше — нужен якорь
    STRONG_THRESHOLD = 93.0   # выше — уверены и без якоря

    def __init__(self, intents: dict[str, tuple[str, ...]] | None = None) -> None:
        raw = intents or _INTENTS
        # Нормализуем каноны один раз — при каждом запросе не делать этого.
        self._intents = {
            name: tuple(normalize(p) for p in phrases)
            for name, phrases in raw.items()
        }

    def route(self, question: str) -> RouteResult:
        normalized = normalize(question)
        if not normalized:
            return RouteResult("other", 0.0, 0.0)

        scored = sorted(
            (
                (self._best_score(normalized, phrases), name)
                for name, phrases in self._intents.items()
            ),
            key=lambda pair: pair[0],
            reverse=True,
        )
        best_score, best_intent = scored[0]
        runner_up = scored[1][0] if len(scored) > 1 else 0.0

        if best_score >= self.STRONG_THRESHOLD:
            return RouteResult(best_intent, best_score, runner_up)
        if best_score >= self.WEAK_THRESHOLD and self._has_anchor(normalized, best_intent):
            return RouteResult(best_intent, best_score, runner_up)
        return RouteResult("other", best_score, runner_up)

    @staticmethod
    def _best_score(normalized: str, phrases: tuple[str, ...]) -> float:
        return max((fuzz.ratio(normalized, p) for p in phrases), default=0.0)

    @staticmethod
    def _has_anchor(normalized: str, intent: str) -> bool:
        return any(a in normalized for a in _ANCHORS.get(intent, ()))


# Singleton — индекс канонических фраз строится один раз при импорте.
ROUTER = QuestionRouter()