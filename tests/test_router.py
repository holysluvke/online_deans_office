"""Тесты роутера: нормализация, эталонные формулировки, опечатки, негативные кейсы."""
import pytest

from backend.knowledge.router import ROUTER, SELF_CHECK_QUESTION
from backend.knowledge.text import normalize

# Нормализация

class TestNormalize:
    def test_lowercase(self):
        assert normalize("ПРИВЕТ") == "привет"

    def test_yo_to_e(self):
        assert normalize("Фёдор") == "федор"

    def test_quotes_removed(self):
        assert normalize("«ФИО» „студента“ \"тест\"") == "фио студента тест"

    def test_punctuation_to_space(self):
        assert normalize("Все, что нужно!") == "все что нужно"

    def test_collapse_spaces(self):
        assert normalize("много    пробелов") == "много пробелов"

    def test_full_pipeline(self):
        assert normalize("  Всё, ли «СВЕДЕНИЯ»?!  ") == "все ли сведения"


# Эталонные формулировки

REFERENCE_Q1 = [
    "Содержит ли документ все обязательные сведения по Положению?",
    SELF_CHECK_QUESTION,
]

REFERENCE_Q3 = [
    "Кто принимает окончательное решение о принятии документа?",
]

REFERENCE_Q2 = [
    "Укажи значение поля «ФИО студента».",
    "Укажи значение поля «Дата выдачи».",
    "Укажи значение поля «Направление подготовки».",
    "Укажи значение поля «Форма обучения».",
    "Укажи значение поля «Название вуза».",
    "Укажи значение поля «Окончание периода обучения».",
    "Укажи значение поля «Учебная группа».",
    "Укажи значение поля «Причина отпуска».",
    "Укажи значение поля «ФИО руководителя практики».",
    "Укажи значение поля «Оценка».",
]


@pytest.mark.parametrize("question", REFERENCE_Q1)
def test_reference_q1(question):
    assert ROUTER.route(question).intent == "completeness"


@pytest.mark.parametrize("question", REFERENCE_Q3)
def test_reference_q3(question):
    assert ROUTER.route(question).intent == "who_decides"


@pytest.mark.parametrize("question", REFERENCE_Q2)
def test_reference_q2_falls_through(question):
    """Q2 роутер не ловит — пропускает дальше в field_lookup."""
    assert ROUTER.route(question).intent == "other"


# Опечатки Q1

Q1_TYPOS = [
    "Содержит ли документ все обязательые сведения по Положению?",  # обязательые
    "Содержит ли документ все обьязательные сведения по Положению?",  # обьязательные
    "Все ли обязательные свединья есть в документе?",                 # свединья
    "Чего нехватает в документе?",                                    # нехватает слитно
    "Проверь докмуент на комплектность",                              # докмуент
]


@pytest.mark.parametrize("question", Q1_TYPOS)
def test_q1_typos_route_to_completeness(question):
    assert ROUTER.route(question).intent == "completeness"


# Опечатки Q3

Q3_TYPOS = [
    "Кто принимает окончательное решене о принятии документа?",  # решене
    "Кто решоет принят ли документ?",                              # решоет
    "Кто принмает решение о принятии документа?",                  # принмает
]


@pytest.mark.parametrize("question", Q3_TYPOS)
def test_q3_typos_route_to_who_decides(question):
    assert ROUTER.route(question).intent == "who_decides"


# Негативные кейсы

NEGATIVES = [
    # Q4 из questions.json
    "Какова стоимость обучения за следующий семестр?",
    "Какой размер стипендии положен студенту?",
    "Какой срок рассмотрения документа деканатом?",
    "По какому номеру телефона можно связаться с деканатом?",
    "В каком кабинете принимают оригиналы документов?",
    # Вымышленные
    "Как оплатить обучение?",
    "Какое расписание занятий на следующей неделе?",
    "Есть ли общежитие для иногородних студентов?",
    "Кто такой декан факультета?",
    "Где находится библиотека?",
    "Сколько длится зимняя сессия?",
    "Какой проходной балл на бюджет?",
    "Когда день открытых дверей?",
    "Как оформить студенческий билет?",
    "Как перевестись на другой факультет?",
    "Какие документы нужны для поступления?",
    "Когда начинаются каникулы?",
    "Где взять справку для военкомата?",
    "Сколько человек в группе?",
    "Как связаться с куратором?",
]


@pytest.mark.parametrize("question", NEGATIVES)
def test_negatives_do_not_route_to_q1_or_q3(question):
    intent = ROUTER.route(question).intent
    assert intent == "other", f"«{question}» → {intent}, ожидалось other"


# Ответ роутера

class TestRouteResult:
    def test_margin_non_negative(self):
        r = ROUTER.route("Содержит ли документ все обязательные сведения?")
        assert r.margin >= 0

    def test_empty_question_is_other(self):
        assert ROUTER.route("").intent == "other"

    def test_whitespace_only_is_other(self):
        assert ROUTER.route("   \n\t  ").intent == "other"