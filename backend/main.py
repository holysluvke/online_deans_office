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
    GET  /health                 проверка, что сервер жив
    POST /documents              принять фото + тип документа + вопрос + session_id, поставить в очередь
                                 (фото до MAX_UPLOAD_MB, настоящая картинка, не больше MAX_ACTIVE_JOBS задач в работе)
    GET  /jobs/{job_id}?session_id=...  статус одной задачи этого посетителя
    GET  /jobs?session_id=...    список задач этого посетителя (страница опрашивает его каждые 2 с)
    DELETE /jobs?session_id=...  удалить завершённые задачи посетителя и их фото

Приватность без регистрации: страница придумывает посетителю случайный код session_id
и хранит его в адресе (?s=...). Задачи в базе помечены этим кодом (столбец owner),
список и очистка работают только с задачами своего кода.
"""
import os
import re
import uuid
from io import BytesIO
from pathlib import Path
from backend.db import DATA_DIR, init_db, get_job, list_jobs, delete_finished_jobs, count_active_jobs
from backend.jobs import create_job, restore_queue

from fastapi import FastAPI, File, Form, Query, UploadFile, HTTPException
from PIL import Image, UnidentifiedImageError

app = FastAPI()

init_db()
restore_queue()

# Куда сохраняем загруженные фото (папка data/ есть в .gitignore, в git не попадает)
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Что разрешаем: только картинки, остальные файлы сервер отклонит.
# content-type присылает сам клиент, поэтому это лишь первый фильтр; настоящая проверка - check_image()
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}

# Форматы, которые Pillow должен распознать в содержимом файла, и расширение, с которым сохраняем
IMAGE_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}

# Максимум пикселей в картинке (около 89 млн, это стандартный порог Pillow).
# Защищает от «бомб»: маленький файл, который при раскодировании занимает гигабайты памяти.
MAX_PIXELS = Image.MAX_IMAGE_PIXELS

# Максимальный размер фото в МБ. По умолчанию 10, можно поменять переменной окружения:
#     set MAX_UPLOAD_MB=20   (Windows cmd)   /   $env:MAX_UPLOAD_MB=20   (PowerShell)
# Лимит на стороне страницы задаётся отдельно: server.maxUploadSize в .streamlit/config.toml
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

# Сколько задач одного посетителя может одновременно ждать в очереди или обрабатываться.
# Страница сама не даёт отправить больше MAX_FILES (ui/app.py) за раз, но запросы можно слать
# и в обход неё, поэтому настоящий лимит здесь. Меняется переменной окружения MAX_ACTIVE_JOBS.
MAX_ACTIVE_JOBS = int(os.getenv("MAX_ACTIVE_JOBS", "10"))

# Допустимые типы документов. Эти же значения использует ui/app.py (словарь DOC_TYPES)
# и pipeline.py (параметр doc_type). Добавляешь новый тип - добавь во всех трёх местах.
DOC_TYPES = {"study_certificate", "academic_leave", "practice_certificate"}

# Код посетителя: страница делает его из uuid4().hex (32 символа). Короткие коды вроде "1"
# не принимаем, чтобы чужую историю нельзя было открыть простым перебором.
SESSION_RE = re.compile(r"[A-Za-z0-9_-]{16,64}")


def check_session(session_id: str) -> str:
    """Проверяет формат кода посетителя, иначе 400."""
    if not SESSION_RE.fullmatch(session_id):
        raise HTTPException(status_code=400, detail="Некорректный session_id")
    return session_id


def check_image(content: bytes) -> str:
    """Проверяет по содержимому, что это настоящая картинка jpg/png/webp, и возвращает расширение для неё."""
    not_image = HTTPException(status_code=400, detail="Файл не является картинкой jpg, png или webp, либо повреждён")
    try:
        with Image.open(BytesIO(content)) as img:
            fmt, (width, height) = img.format, img.size
            img.verify()  # проверяет структуру файла, не раскодируя все пиксели
    except Image.DecompressionBombError:
        raise HTTPException(status_code=400, detail="Слишком большое разрешение картинки")
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise not_image
    if fmt not in IMAGE_FORMATS:
        raise not_image
    if width * height > MAX_PIXELS:
        raise HTTPException(status_code=400, detail="Слишком большое разрешение картинки")
    return IMAGE_FORMATS[fmt]


@app.get("/health")
def health():
    """Проверка, что сервер запущен."""
    return {"status": "ok"}


@app.post("/documents")
async def upload_document(
    file: UploadFile = File(...),   # само фото
    doc_type: str = Form(...),      # тип документа, одно из DOC_TYPES
    question: str = Form(...),      # вопрос студента
    session_id: str = Form(...),    # код посетителя, задача будет видна только ему
):
    """Принимает одно фото с типом документа и вопросом, сохраняет его и ставит задачу в очередь."""
    check_session(session_id)

    # 1. Проверяем, что это картинка
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Можно загружать только фото (jpg, png, webp)")

    # 2. Проверяем тип документа
    if doc_type not in DOC_TYPES:
        raise HTTPException(status_code=400, detail="Неизвестный тип документа")

    # 3. Проверяем, что у посетителя не слишком много задач в работе
    if count_active_jobs(session_id) >= MAX_ACTIVE_JOBS:
        raise HTTPException(
            status_code=429,
            detail=f"Уже {MAX_ACTIVE_JOBS} документов в очереди. Дождитесь, пока они обработаются",
        )

    # 4. Проверяем размер: читаем не больше лимита + 1 байт, чтобы не тянуть в память огромный файл
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"Файл больше {MAX_UPLOAD_MB} МБ")

    # 5. Проверяем содержимое: это действительно картинка (а не, например, переименованный .exe)
    suffix = check_image(content)  # расширение берём по настоящему формату, а не по имени файла

    # 6. Сохраняем файл под уникальным именем, чтобы два photo.jpg не затёрли друг друга
    job_id = uuid.uuid4().hex
    filename = file.filename or "photo" + suffix
    path = UPLOAD_DIR / f"{job_id}{suffix}"
    path.write_bytes(content)

    # 7. Ставим задачу в очередь (дальше работает jobs.py -> pipeline.py)
    create_job(job_id, session_id, str(path), filename, doc_type, question)
    return {"job_id": job_id, "status": "queued"}


def _public(job: dict) -> dict:
    """Копия задачи без пути к файлу и кода владельца, чтобы не отдавать их наружу."""
    return {key: val for key, val in job.items() if key not in ("path", "owner")}


@app.get("/jobs/{job_id}")
def job_status(job_id: str, session_id: str = Query(...)):
    """Возвращает статус и результат одной задачи (404, если такой нет)."""
    check_session(session_id)
    job = get_job(job_id)
    if job is None or job["owner"] != session_id:
        raise HTTPException(404, "Задача не найдена")
    return _public(job)


@app.get("/jobs")
def all_jobs(session_id: str = Query(...)):
    """Возвращает список задач одного посетителя."""
    return [_public(j) for j in list_jobs(check_session(session_id))]

@app.delete("/jobs")
def clear_jobs(session_id: str = Query(...)):
    """Удаляет завершённые задачи посетителя вместе с их фото; задачи в работе не трогает."""
    for path in delete_finished_jobs(check_session(session_id)):
        Path(path).unlink(missing_ok=True)  # удалить файл с диска, если он ещё есть
    return {"status": "ok"}
