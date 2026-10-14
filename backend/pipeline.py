"""
=====================  ЭТО МЕСТО ДЛЯ ML-ЧАСТИ  =====================

extract_fields уже читает документ. answer_question пока заглушка: ответ по Положению
делает другой человек.

Что нельзя менять:
    - названия функций, их аргументы и формат ответа.
      Тогда очередь (jobs.py), бэкенд (main.py) и страница (ui/app.py) продолжат
      работать без правок.

Как это вызывается (backend/jobs.py), по порядку:
    fields = extract_fields(путь_к_фото, doc_type)
    result = answer_question(fields, doc_type, вопрос_студента)

Если внутри функции что-то пошло не так, достаточно сделать raise Exception("понятный текст").
Задача получит статус «Ошибка», а текст покажется на странице; остальные задачи не пострадают.

doc_type - одно из:
    "study_certificate"     справка об обучении
    "academic_leave"        заявление на академический отпуск
    "practice_certificate"  справка о практике

Что возвращают функции:
    extract_fields  -> плоский словарь {строка: строка | bool}.
                       Без вложенности, списков и None.
                       Нет поля на листе — "не найдено". Печать и подпись — True/False.
                       study_certificate:
                           student_name, university, program, study_form,
                           study_start, study_end, document_number, issue_date,
                           signature_present, seal_present
                       academic_leave (то же для academic_leave_application):
                           student_name, group, course, leave_reason,
                           leave_start, leave_end, application_date, signature_present
                       practice_certificate (то же для internship_certificate):
                           student_name, organization, internship_start, internship_end,
                           supervisor_name, grade, document_number, issue_date,
                           signature_present, seal_present
                       Даты — ISO (2026-09-01), курс — строка, не число.
                       Слабые строки перед разбором читает трансформер TrOCR.
                       Этот словарь уже уходит в answer_question как есть. Его не оборачивать.
    answer_question -> плоский словарь, ключи фиксированы:
                       {
                         "status": "ok" | "missing" | "no_answer",
                         "message": "Не хватает: дата выдачи. По п. 3.1.",
                         "sources": ["rule.3.1"],
                         "answerable": True,
                         "value": "missing_fields",
                       }
                       ok = документ в порядке, missing = чего-то не хватает, no_answer = ответа нет (не выдумывать).
                       Тело answer_question всё ещё заглушка: его пишет следующий человек.
"""
import time


def extract_fields(image_path: str, doc_type: str) -> dict:
    """Фото или PDF -> плоский словарь полей. Полный текст остаётся в run_ocr."""
    from backend.ocr import run_ocr
    from backend.ocr.fields import pick_fields
    from backend.ocr.intake import load_document

    recognized = run_ocr(image_path)
    images = [page.image for page in load_document(image_path)[1]]
    return pick_fields(doc_type, recognized, images)


def answer_question(fields: dict, doc_type: str, question: str) -> dict:
    """ЗАГЛУШКА. Сюда подставляется ответ по Положению.

    Вход уже готов: fields — плоский словарь extract_fields, doc_type, question.
    Ключи результата не менять, иначе страница деканата их не покажет.
    """
    time.sleep(2)
    return {
        "status": "missing",
        "message": "Не хватает: дата выдачи. По п. 3.1.",
        "sources": ["rule.3.1"],
        "answerable": True,
        "value": "missing_fields",
    }
