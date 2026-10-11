from concurrent.futures import ThreadPoolExecutor

from backend.pipeline import extract_fields, answer_question

# Один рабочий => задачи идут строго по очереди
executor = ThreadPoolExecutor(max_workers=1)

# Хранилище задач: ключ - job_id, значение - словарь с данными
JOBS: dict[str, dict] = {} # при перезапуске сервера пустеет.


def create_job(job_id: str, path: str, filename: str, doc_type: str, question: str) -> None:
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
    job = JOBS[job_id]
    try:
        job["status"] = "processing"
        job["progress"] = 10

        job["fields"] = extract_fields(job["path"], job["doc_type"])
        job["progress"] = 60

        job["result"] = answer_question(job["fields"], job["doc_type"], job["question"])
        job["progress"] = 100
        job["status"] = "done"
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)