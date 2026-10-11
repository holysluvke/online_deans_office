"""
Очередь задач. Здесь нет ни распознавания, ни правил, только порядок и статусы.
ML-щикам этот файл менять не нужно: они работают в pipeline.py.

Жизнь задачи:
    queued (в очереди) -> processing (идёт обработка) -> done (готово) или error (сбой)

Что происходит внутри _run для каждой задачи:
    1. extract_fields(...)   - OCR: фото -> словарь полей      (progress 10 -> 60)
    2. answer_question(...)  - RAG: поля + вопрос -> ответ      (progress 60 -> 100)
"""
from concurrent.futures import ThreadPoolExecutor

from backend.pipeline import extract_fields, answer_question

# Один рабочий => задачи идут строго по очереди
# (нужно больше параллели - увеличить max_workers, но тяжёлые модели на CPU лучше по одной)
executor = ThreadPoolExecutor(max_workers=1)

# Хранилище задач: ключ - job_id, значение - словарь с данными
JOBS: dict[str, dict] = {} # при перезапуске сервера пустеет.


def create_job(job_id: str, path: str, filename: str, doc_type: str, question: str) -> None:
    """Создаёт запись о задаче в JOBS и ставит её в очередь на обработку."""
    JOBS[job_id] = {
        "job_id": job_id,
        "filename": filename, # Исходное имя файла, которое загрузил студент
        "doc_type": doc_type, # Тип документа, из списка DOC_TYPES в main.py.
        "question": question, # Вопрос студента
        "path": path, # Путь к сохранённому фото на диске. По нему extract_fields открывает файл.
        "status": "queued", # "processing" → "done" или "error"
        "progress": 0, # проценты для прогресс-бара
        "fields": None, # словарь с полями, распознанными на документе (ФИО, даты, номер и так далее). Заполняет extract_fields
        "result": None, # итоговый ответ на вопрос с цитатой из правил. Заполняет answer_question
        "error": None, # текст ошибки
    }
    executor.submit(_run, job_id)  # поставить в очередь


def _run(job_id: str) -> None:
    """Обрабатывает одну задачу в фоне: сначала OCR (extract_fields), потом ответ по Положению (answer_question)."""
    job = JOBS[job_id]
    try:
        job["status"] = "processing"
        job["progress"] = 10

        # Шаг 1: OCR (функция из pipeline.py)
        job["fields"] = extract_fields(job["path"], job["doc_type"])
        job["progress"] = 60

        # Шаг 2: ответ по Положению (функция из pipeline.py)
        job["result"] = answer_question(job["fields"], job["doc_type"], job["question"])
        job["progress"] = 100
        job["status"] = "done"
    except Exception as e:
        # Любая ошибка внутри pipeline.py не ломает очередь: задача получает статус error,
        # а страница покажет текст ошибки. Остальные задачи идут дальше.
        job["status"] = "error"
        job["error"] = str(e)
