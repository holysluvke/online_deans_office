"""
Бэкенд «Онлайн-деканата» (FastAPI). Это «приёмная»: принимает фото от страницы,
ставит его в очередь и отдаёт статус/результат.

Файлы бэкенда:
    main.py      - ЭТОТ файл: адреса (эндпоинты) для страницы
    jobs.py      - очередь задач и их статусы
    pipeline.py  - распознавание (OCR) и ответ по Положению (RAG) - СЮДА подключается ML

Запуск (из корня проекта, с включённым .venv):
    uvicorn backend.main:app --reload
Документация со всеми адресами и кнопкой «Try it out»: http://127.0.0.1:8000/docs

Адреса:
    GET  /health         проверка, что сервер жив
    POST /documents      принять фото + тип документа + вопрос, поставить в очередь
    GET  /jobs/{job_id}  статус и результат одной задачи (страница опрашивает его каждые 2 с)
    GET  /jobs           список всех задач
"""
import uuid
from pathlib import Path
from backend.jobs import create_job
from backend.db import init_db, get_job, list_jobs

from fastapi import FastAPI, File, Form, UploadFile, HTTPException

app = FastAPI()

init_db()
# Куда сохраняем загруженные фото (папка data/ есть в .gitignore, в git не попадает)
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Что разрешаем: только картинки, остальные файлы сервер отклонит
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}

# Допустимые типы документов. Эти же значения использует ui/app.py (словарь DOC_TYPES)
# и pipeline.py (параметр doc_type). Добавляешь новый тип - добавь во всех трёх местах.
DOC_TYPES = {"study_certificate", "academic_leave", "practice_certificate"}


@app.get("/health")
def health():
    """Проверка, что сервер запущен."""
    return {"status": "ok"}


@app.post("/documents")
async def upload_document(
    file: UploadFile = File(...),   # само фото
    doc_type: str = Form(...),      # тип документа, одно из DOC_TYPES
    question: str = Form(...),      # вопрос студента
):
    """Принимает одно фото с типом документа и вопросом, сохраняет его и ставит задачу в очередь."""
    # 1. Проверяем, что это картинка
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Можно загружать только фото (jpg, png, webp)")

    # 2. Проверяем тип документа
    if doc_type not in DOC_TYPES:
        raise HTTPException(status_code=400, detail="Неизвестный тип документа")

    # 3. Сохраняем файл под уникальным именем, чтобы два photo.jpg не затёрли друг друга
    job_id = uuid.uuid4().hex
    suffix = Path(file.filename).suffix or ".jpg"
    path = UPLOAD_DIR / f"{job_id}{suffix}"
    path.write_bytes(await file.read())

    # 4. Ставим задачу в очередь (дальше работает jobs.py -> pipeline.py)
    create_job(job_id, str(path), file.filename, doc_type, question)
    return {"job_id": job_id, "status": "queued"}


def _public(job: dict) -> dict:
    """Копия задачи без пути к файлу, чтобы не отдавать его наружу."""
    return {key: val for key, val in job.items() if key != "path"}


@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    """Возвращает статус и результат одной задачи (404, если такой нет)."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, "Задача не найдена")
    return _public(job)


@app.get("/jobs")
def all_jobs():
    """Возвращает список всех задач."""
    return [_public(j) for j in list_jobs()]
