import sqlite3
from contextlib import contextmanager
from pathlib import Path
import json

# Папка data/ в корне проекта; путь абсолютный, поэтому не зависит от того, откуда запущен сервер
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "app.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Куда сохраняем загруженные фото (папка data/ есть в .gitignore, в git не попадает)
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_conn():
    """Открывает соединение с базой: в конце блока with сохраняет изменения и закрывает его."""
    conn = sqlite3.connect(DB_PATH, timeout=10)  # если база занята, ждём до 10 с, а не падаем сразу
    conn.row_factory = sqlite3.Row  # строки можно читать по названию столбца: row["status"]
    try:
        with conn:  # commit при успехе, rollback при ошибке
            yield conn
    finally:
        conn.close()



def init_db() -> None:
    """Создаёт таблицу jobs, если её ещё нет.
    owner - код посетителя (session_id из адреса страницы): каждый видит только свои задачи.
    Схема менялась: если база создана старой версией (без owner), удалите data/app.db."""
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id     TEXT PRIMARY KEY,
                owner      TEXT NOT NULL,
                filename   TEXT NOT NULL,
                doc_type   TEXT NOT NULL,
                question   TEXT NOT NULL,
                path       TEXT NOT NULL,
                status     TEXT NOT NULL DEFAULT 'queued',
                progress   INTEGER NOT NULL DEFAULT 0,
                fields     TEXT,
                result     TEXT,
                error      TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS jobs_owner ON jobs (owner)")


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Превращает строку из базы в обычный словарь (как раньше лежал в JOBS)."""
    job = dict(row)
    for key in ("fields", "result"):  # эти два столбца хранятся текстом JSON
        if job[key] is not None:
            job[key] = json.loads(job[key])
    return job


def insert_job(job_id: str, owner: str, path: str, filename: str, doc_type: str, question: str) -> None:
    """Добавляет в базу новую задачу посетителя owner (статус и прогресс ставятся сами: queued, 0)."""
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO jobs (job_id, owner, filename, doc_type, question, path) VALUES (?, ?, ?, ?, ?, ?)",
            (job_id, owner, filename, doc_type, question, path),
        )


def get_job(job_id: str) -> dict | None:
    """Возвращает задачу по номеру или None, если такой нет."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    return _row_to_dict(row) if row else None


def list_jobs(owner: str) -> list[dict]:
    """Возвращает задачи одного посетителя, старые первыми."""
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM jobs WHERE owner = ? ORDER BY rowid", (owner,)).fetchall()
    return [_row_to_dict(r) for r in rows]


def update_job(job_id: str, **changes) -> None:
    """Меняет у задачи указанные поля, например update_job(id, status="done", progress=100)."""
    for key in ("fields", "result"):  # словари сохраняем как текст JSON
        if key in changes:
            changes[key] = json.dumps(changes[key], ensure_ascii=False)
    columns = ", ".join(f"{name} = ?" for name in changes)
    with get_conn() as conn:
        conn.execute(f"UPDATE jobs SET {columns} WHERE job_id = ?", (*changes.values(), job_id))


def get_unfinished_jobs() -> list[dict]:
    """Возвращает задачи, которые не успели завершиться (в очереди или в обработке), старые первыми."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE status IN ('queued', 'processing') ORDER BY rowid"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]

def count_active_jobs(owner: str) -> int:
    """Сколько задач посетителя ещё не завершено (в очереди или в обработке)."""
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE owner = ? AND status IN ('queued', 'processing')", (owner,)
        ).fetchone()[0]


def delete_old_jobs(max_age_minutes: int) -> list[str]:
    """Удаляет задачи старше max_age_minutes (кроме тех, что сейчас обрабатываются) и возвращает пути к их фото."""
    # created_at хранится в UTC в виде 'ГГГГ-ММ-ДД ЧЧ:ММ:СС', datetime('now', ...) даёт тот же формат
    old = "created_at < datetime('now', ?) AND status != 'processing'"
    age = f"-{max_age_minutes} minutes"
    with get_conn() as conn:
        paths = [r["path"] for r in conn.execute(f"SELECT path FROM jobs WHERE {old}", (age,))]
        conn.execute(f"DELETE FROM jobs WHERE {old}", (age,))
    return paths


def list_paths() -> list[str]:
    """Пути к фото всех задач, которые есть в базе."""
    with get_conn() as conn:
        return [r["path"] for r in conn.execute("SELECT path FROM jobs")]


def delete_finished_jobs(owner: str) -> list[str]:
    """Удаляет завершённые задачи (done/error) посетителя owner и возвращает пути к их фото."""
    finished = "owner = ? AND status IN ('done', 'error')"
    with get_conn() as conn:
        paths = [r["path"] for r in conn.execute(f"SELECT path FROM jobs WHERE {finished}", (owner,))]
        conn.execute(f"DELETE FROM jobs WHERE {finished}", (owner,))
    return paths