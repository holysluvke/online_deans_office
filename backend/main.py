import uuid
from pathlib import Path
from backend.jobs import create_job, JOBS

from fastapi import FastAPI, File, Form, UploadFile, HTTPException

app = FastAPI()

# Куда сохраняем загруженные фото
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Что разрешаем
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
DOC_TYPES = {"study_certificate", "academic_leave", "practice_certificate"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form(...),
    question: str = Form(...),
):
    # 1. Проверяем, что это картинка
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Можно загружать только фото (jpg, png, webp)")

    # 2. Проверяем тип документа
    if doc_type not in DOC_TYPES:
        raise HTTPException(status_code=400, detail="Неизвестный тип документа")

    # 3. Сохраняем файл под уникальным именем
    job_id = uuid.uuid4().hex
    suffix = Path(file.filename).suffix or ".jpg"
    path = UPLOAD_DIR / f"{job_id}{suffix}"
    path.write_bytes(await file.read())

    create_job(job_id, str(path), file.filename, doc_type, question)
    return {"job_id": job_id, "status": "queued"}


def _public(job: dict) -> dict:
    """Копия задачи без внутреннего пути к файлу."""
    return {key: val for key, val in job.items() if key != "path"}


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return _public(job)


@app.get("/jobs")
def list_jobs():
    return [_public(j) for j in JOBS.values()]

