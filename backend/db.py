import sqlite3
from pathlib import Path
import json

DB_PATH = Path("data/app.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def get_conn() -> sqlite3.Connection:
    """Открывает соединение с базой."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # строки можно читать по названию столбца: row["status"]
    return conn



def init_db() -> None:
    """Создаёт таблицу jobs, если её ещё нет."""
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id     TEXT PRIMARY KEY,
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

def _row_to_dict(row: sqlite3.Row) -> dict:
    """Превращает строку из базы в обычный словарь (как раньше лежал в JOBS)."""
    job = dict(row)
    for key in ("fields", "result"):  # эти два столбца хранятся текстом JSON
        if job[key] is not None:
            job[key] = json.loads(job[key])
    return job


def insert_job(job_id: str, path: str, filename: str, doc_type: str, question: str) -> None:
    """Добавляет в базу новую задачу (статус и прогресс ставятся сами: queued, 0)."""
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO jobs (job_id, filename, doc_type, question, path) VALUES (?, ?, ?, ?, ?)",
            (job_id, filename, doc_type, question, path),
        )


def get_job(job_id: str) -> dict | None:
    """Возвращает задачу по номеру или None, если такой нет."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    return _row_to_dict(row) if row else None


def list_jobs() -> list[dict]:
    """Возвращает все задачи, старые первыми."""
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM jobs ORDER BY rowid").fetchall()
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