"""
Очередь задач. Здесь нет ни распознавания, ни правил, только порядок и статусы.
ML-щикам этот файл менять не нужно: они работают в pipeline.py.

Жизнь задачи:
    queued (в очереди) -> processing (идёт обработка) -> done (готово) или error (сбой)

Что происходит внутри _run для каждой задачи:
    1. extract_fields(...)   - OCR: фото -> словарь полей      (progress 10 -> 60)
    2. answer_question(...)  - RAG: поля + вопрос -> ответ      (progress 60 -> 100)
"""
import time
from concurrent.futures import ThreadPoolExecutor

from backend.pipeline import extract_fields, answer_question
from backend.db import insert_job, get_job, update_job, get_unfinished_jobs
from backend.log import log


# Один рабочий => задачи идут строго по очереди
# (нужно больше параллели - увеличить max_workers, но тяжёлые модели на CPU лучше по одной)
executor = ThreadPoolExecutor(max_workers=1)


def create_job(job_id: str, owner: str, path: str, filename: str, doc_type: str, question: str) -> None:
    """Записывает задачу посетителя owner в базу и ставит её в очередь на обработку."""
    insert_job(job_id, owner, path, filename, doc_type, question)
    executor.submit(_run, job_id)  # поставить в очередь


def restore_queue() -> None:
    """При старте сервера возвращает в очередь задачи, которые прервал перезапуск."""
    jobs = get_unfinished_jobs()
    for job in jobs:
        update_job(job["job_id"], status="queued", progress=0)  # processing -> queued, начинаем заново
        executor.submit(_run, job["job_id"])
    if jobs:
        log.info("Восстановлено в очереди после перезапуска: %d", len(jobs))


def _run(job_id: str) -> None:
    """Обрабатывает одну задачу в фоне: сначала OCR (extract_fields), потом ответ по Положению (answer_question)."""
    job = get_job(job_id)  # свежая запись из базы: нужны путь, тип документа и вопрос
    if job is None:
        log.info("Задача %s пропущена: удалена, пока ждала в очереди", job_id)
        return  # задачу успели удалить (автоудаление или очистка), пока она ждала в очереди
    start = time.perf_counter()
    step = "OCR (extract_fields)"
    try:
        update_job(job_id, status="processing", progress=10)
        log.info("Задача %s: начало обработки (%s)", job_id, job["doc_type"])

        # Шаг 1: OCR (функция из pipeline.py)
        fields = extract_fields(job["path"], job["doc_type"])
        update_job(job_id, fields=fields, progress=60)

        # Шаг 2: ответ по Положению (функция из pipeline.py)
        step = "ответ (answer_question)"
        result = answer_question(fields, job["doc_type"], job["question"])
        update_job(job_id, result=result, progress=100, status="done")
        log.info("Задача %s готова за %.1f с, итог: %s",
                 job_id, time.perf_counter() - start, result.get("status") if isinstance(result, dict) else "?")
    except Exception as e:
        # Любая ошибка внутри pipeline.py не ломает очередь: задача получает статус error,
        # страница покажет текст ошибки, а в лог уходит полная трассировка. Остальные задачи идут дальше.
        log.exception("Задача %s: ошибка на шаге %s (%s)", job_id, step, job["doc_type"])
        update_job(job_id, status="error", error=str(e))