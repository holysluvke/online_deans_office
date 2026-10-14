"""
=====================  ЭТО МЕСТО ДЛЯ ML-ЧАСТИ  =====================

Сейчас здесь две ЗАГЛУШКИ: они возвращают фейковые данные, чтобы сайт можно было
разрабатывать и проверять, не дожидаясь настоящего распознавания.

Что нужно сделать:
    - заменить ТЕЛО функций extract_fields и answer_question на настоящий код
      (OCR и поиск по Положению);
    - НЕ менять названия функций, их аргументы и ФОРМАТ того, что они возвращают.
      Тогда очередь (jobs.py), бэкенд (main.py) и страница (ui/app.py) продолжат
      работать без правок.

Как это вызывается (backend/jobs.py), по порядку:
    fields = extract_fields(путь_к_фото, doc_type)
    result = answer_question(fields, doc_type, вопрос_студента)

Если внутри функции что-то пошло не так, достаточно сделать raise Exception("понятный текст").
Задача получит статус «Ошибка», а текст покажется на странице; остальные задачи не пострадают.

doc_type - одно из:
    "study_certificate"           справка об обучении
    "academic_leave_application"  заявление на академический отпуск
    "internship_certificate"      справка о практике

Что возвращают функции:
    extract_fields  -> словарь {имя_поля: значение}; не найденное поле = "не найдено", печать/подпись = True/False
    answer_question -> {"status": "ok" | "missing" | "no_answer", "message": "текст ответа", "sources": ["п. 3.4"]}
                       ok = документ в порядке, missing = чего-то не хватает, no_answer = ответа нет (не выдумывать)
"""
import time

from backend.knowledge import (
    check_completeness,
    field_lookup,
    no_answer,
    who_decides,
)

# Триггеры для классификации типа вопроса. Порядок проверок в _classify — по этому кортежу.
# Узкие фразы идут первыми, чтобы Q3 не перехватывал Q1 или Q2.
_WHO_DECIDES_TRIGGERS = ("кто принимает окончательное решение",)
_COMPLETENESS_TRIGGERS = ("содержит ли документ все обязательные", "все обязательные сведения")
_FIELD_LOOKUP_TRIGGERS = ("укажи значение поля", "значение поля")

def extract_fields(image_path: str, doc_type: str) -> dict:
    """ЗАГЛУШКА OCR: по фото вернуть поля документа."""
    #тестовая заглушка
    time.sleep(1)  # притворяемся, что думаем
    return {
        "fio": "Иванов Иван Иванович",
        "university": "Южный федеральный университет",
        "issue_date": "не найдено",
        "stamp": False,
    }

def _classify(question: str) -> str:
    """Определяет тип вопроса: 'who_decides' | 'completeness' | 'field_lookup' | 'unknown'."""
    q = question.lower().strip()
    if any(t in q for t in _WHO_DECIDES_TRIGGERS):
        return "who_decides"
    if any(t in q for t in _COMPLETENESS_TRIGGERS):
        return "completeness"
    if any(t in q for t in _FIELD_LOOKUP_TRIGGERS):
        return "field_lookup"
    return "unknown"


def answer_question(fields: dict, doc_type: str, question: str) -> dict:
    """RAG: по полям документа и вопросу вернуть ответ со ссылкой на пункт Положения."""
    kind = _classify(question)

    if kind == "who_decides":
        answer = who_decides()
    elif kind == "completeness":
        answer = check_completeness(fields, doc_type)
    elif kind == "field_lookup":
        answer = field_lookup(fields, doc_type, question) or no_answer()
    else:
        answer = no_answer()

    return answer.to_dict()
