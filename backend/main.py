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
    POST /documents              принять фото или PDF + тип документа + вопрос + session_id, поставить в очередь
                                 (файл до MAX_UPLOAD_MB, настоящая картинка или PDF, не больше MAX_ACTIVE_JOBS задач в работе;
                                 PDF сразу превращается в картинку, см. pdf.py)
    GET  /jobs/{job_id}?session_id=...  статус одной задачи этого посетителя
    GET  /jobs?session_id=...    список задач этого посетителя (страница опрашивает его каждые 2 с)
    DELETE /jobs?session_id=...  удалить завершённые задачи посетителя и их фото

Старые задачи и фото удаляются сами (через час), см. cleanup.py.
Все запросы, отказы (4xx) и ошибки пишутся в лог data/logs/app.log, см. log.py.

Приватность без регистрации: страница придумывает посетителю случайный код session_id
и хранит его в адресе (?s=...). Задачи в базе помечены этим кодом (столбец owner),
список и очистка работают только с задачами своего кода.
"""
import asyncio
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from backend.db import UPLOAD_DIR, init_db, get_job, list_jobs, delete_finished_jobs, count_active_jobs
from backend.jobs import create_job, restore_queue
from backend.cleanup import cleanup_once, cleanup_loop
from backend.pdf import pdf_to_png, PdfError
from backend.log import log

from fastapi import FastAPI, File, Form, Query, Request, UploadFile, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from PIL import Image, UnidentifiedImageError
from starlette.exceptions import HTTPException as StarletteHTTPException

init_db()
cleanup_once()   # сначала стираем устаревшее, чтобы не возвращать в очередь задачи старше часа
restore_queue()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Пока сервер работает, в фоне крутится автоудаление старых задач и фото."""
    task = asyncio.create_task(cleanup_loop())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)

# Частые опросы страницы (раз в 2 с на каждого посетителя): при успехе пишем их только на уровне DEBUG,
# иначе они забьют лог. Всё остальное и любые ошибки пишутся на уровне INFO и выше.
QUIET_PATHS = ("/jobs", "/health")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Пишет в лог каждый входящий запрос: метод, путь, статус и время ответа.
    Строку запроса (?session_id=...) не пишем: это код посетителя."""
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("%s %s -> необработанная ошибка", request.method, request.url.path)
        raise
    ms = (time.perf_counter() - start) * 1000
    quiet = request.method == "GET" and request.url.path.startswith(QUIET_PATHS) and response.status_code < 400
    log.log(10 if quiet else 20, "%s %s -> %d (%.0f мс)", request.method, request.url.path, response.status_code, ms)
    return response


@app.exception_handler(StarletteHTTPException)
async def log_http_error(request: Request, exc: StarletteHTTPException):
    """Отказы (400, 404, 413, 429...) пишем в лог вместе с причиной, а ответ отдаём как обычно."""
    log.warning("%s %s -> %d: %s", request.method, request.url.path, exc.status_code, exc.detail)
    return await http_exception_handler(request, exc)


@app.exception_handler(RequestValidationError)
async def log_validation_error(request: Request, exc: RequestValidationError):
    """Запрос без нужных полей (422): пишем в лог, какие поля не так, без их значений."""
    problems = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
    log.warning("%s %s -> 422: %s", request.method, request.url.path, problems)
    return await request_validation_exception_handler(request, exc)

# Что разрешаем: картинки и PDF, остальные файлы сервер отклонит.
# content-type присылает сам клиент, поэтому это лишь первый фильтр;
# настоящая проверка - check_image() для картинок и pdf_to_png() для PDF
PDF_TYPE = "application/pdf"
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", PDF_TYPE}

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
DOC_TYPES = {"study_certificate", "academic_leave_application", "internship_certificate"}

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
    """Принимает одно фото или PDF с типом документа и вопросом, сохраняет его как картинку и ставит задачу в очередь."""
    check_session(session_id)

    # 1. Проверяем, что это картинка или PDF
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Можно загружать только JPG, PNG или PDF")

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

    # 5. Проверяем содержимое: это действительно картинка или PDF (а не, например, переименованный .exe).
    #    PDF превращаем в PNG сразу здесь: pipeline.py (OCR) работает только с картинками
    if file.content_type == PDF_TYPE:
        if not content.startswith(b"%PDF-"):
            raise HTTPException(status_code=400, detail="Файл не является PDF, либо повреждён")
        try:
            content = await run_in_threadpool(pdf_to_png, content)  # отрисовка занимает время, не блокируем сервер
        except PdfError as e:
            raise HTTPException(status_code=400, detail=str(e))
        suffix, source = ".png", "pdf"
    else:
        suffix = check_image(content)  # расширение берём по настоящему формату, а не по имени файла
        source = suffix.lstrip(".")

    # 6. Сохраняем файл под уникальным именем, чтобы два photo.jpg не затёрли друг друга
    job_id = uuid.uuid4().hex
    filename = file.filename or "photo" + suffix
    path = UPLOAD_DIR / f"{job_id}{suffix}"
    path.write_bytes(content)

    # 7. Ставим задачу в очередь (дальше работает jobs.py -> pipeline.py)
    create_job(job_id, session_id, str(path), filename, doc_type, question)
    log.info("Задача %s принята: %s, %s, %d КБ", job_id, doc_type, source, len(content) // 1024)
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
    paths = delete_finished_jobs(check_session(session_id))
    for path in paths:
        Path(path).unlink(missing_ok=True)  # удалить файл с диска, если он ещё есть
    log.info("Очистка истории посетителем: удалено задач %d", len(paths))
    return {"status": "ok"}
