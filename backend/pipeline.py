"""
ML-часть пайплайна «Онлайн-деканата».

Две публичные функции, которые вызывает jobs.py:
    extract_fields(путь_к_фото, doc_type)          → OCR: фото → плоский словарь полей
    answer_question(fields, doc_type, вопрос)      → RAG: поля + вопрос → ответ

Формат ответа answer_question (плоский словарь, 6 ключей):
    {
      "status":         "ok" | "missing" | "no_answer",
      "message":        "текст ответа для пользователя",
      "sources":        ["rule:3.1", "field:issue_date"],
      "answerable":     True | False,
      "value":          "document_ok" | "missing_fields" | <значение> | None,
      "missing_fields": ["issue_date", ...],   # пусто, если ничего не пропущено
    }

doc_type:
    "study_certificate"           справка об обучении
    "academic_leave_application"  заявление на академический отпуск
    "internship_certificate"      справка о практике

extract_fields возвращает плоский словарь {строка: строка | bool}:
    study_certificate:           student_name, university, program, study_form,
                                 study_start, study_end, document_number, issue_date,
                                 signature_present, seal_present
    academic_leave_application:  student_name, group, course, leave_reason,
                                 leave_start, leave_end, application_date,
                                 signature_present
    internship_certificate:      student_name, organization, internship_start,
                                 internship_end, supervisor_name, grade,
                                 document_number, issue_date,
                                 signature_present, seal_present
    Даты — ISO (2026-09-01), курс — строка, не число.
    Ненайденное поле — "не найдено". Печать и подпись — True/False.

Прогрев (backend/warmup.py): при старте сервера в фоне вызывается warmup() ниже: он заранее
загружает Paddle (и TrOCR, если включён USE_HANDWRITING=1), чтобы первый документ не ждал загрузки.
"""

from backend.knowledge import (
    check_completeness,
    field_lookup,
    who_decides,
)
from backend.knowledge.router import ROUTER
from backend.knowledge.transfer import is_transfer_question, transfer_answer


def extract_fields(image_path: str, doc_type: str) -> dict:
    """Фото или PDF -> плоский словарь полей. Полный текст остаётся в run_ocr."""
    from backend.ocr import run_ocr
    from backend.ocr.fields import pick_fields
    from backend.ocr.intake import load_document

    recognized = run_ocr(image_path)
    images = [page.image for page in load_document(image_path)[1]]
    return pick_fields(doc_type, recognized, images)


def answer_question(fields: dict, doc_type: str, question: str) -> dict:
    """RAG: по полям документа и вопросу вернуть ответ со ссылкой на пункт Положения."""
    if is_transfer_question(question):
        return transfer_answer(fields, doc_type).to_dict()

    intent = ROUTER.route(question).intent
    if intent == "completeness":
        return check_completeness(fields, doc_type).to_dict()
    if intent == "who_decides":
        return who_decides().to_dict()

    return field_lookup(fields, doc_type, question).to_dict()


def warmup() -> None:
    """Загружает модели в память заранее (при старте сервера и командой python -m backend.warmup)."""
    from backend.ocr.engine import get_engine
    from backend.ocr import handwriting

    get_engine()  # Paddle
    if handwriting.enabled():  # TrOCR только если включён USE_HANDWRITING=1
        handwriting.get_reader()
