"""
Автоудаление старых задач и фото - главная защита персональных данных:
документы студентов не копятся на сервере, всё старше JOB_TTL_MINUTES стирается.

Как работает:
    - cleanup_once() вызывается при старте сервера (main.py), до восстановления очереди;
    - cleanup_loop() крутится в фоне и повторяет её каждые CLEANUP_EVERY_MINUTES минут.

Что удаляется за один проход:
    1. задачи старше JOB_TTL_MINUTES (по created_at) вместе с их фото,
       кроме тех, что прямо сейчас обрабатываются: они удалятся при следующем проходе;
    2. фото в data/uploads, к которым нет задачи в базе и которые старше того же срока
       (например, остались после удаления data/app.db или после сбоя).

Настройки (переменные окружения, в минутах):
    JOB_TTL_MINUTES        сколько живут задачи и фото, по умолчанию 60
    CLEANUP_EVERY_MINUTES  как часто проверять, по умолчанию 5
"""
import asyncio
import logging
import os
import time
from pathlib import Path

from backend.db import UPLOAD_DIR, delete_old_jobs, list_paths

JOB_TTL_MINUTES = int(os.getenv("JOB_TTL_MINUTES", "60"))
CLEANUP_EVERY_MINUTES = int(os.getenv("CLEANUP_EVERY_MINUTES", "5"))

log = logging.getLogger("uvicorn.error")  # пишем в тот же вывод, что и uvicorn


def cleanup_once() -> None:
    """Один проход: удаляет старые задачи с их фото и фото без задач."""
    # 1. Старые задачи из базы и их фото
    old_paths = delete_old_jobs(JOB_TTL_MINUTES)
    for path in old_paths:
        Path(path).unlink(missing_ok=True)

    # 2. Фото без задачи в базе. Свежие не трогаем: файл сохраняется чуть раньше,
    #    чем задача попадает в базу, и его нельзя удалить в этот момент.
    known = {Path(p).name for p in list_paths()}
    deadline = time.time() - JOB_TTL_MINUTES * 60
    orphans = 0
    for file in UPLOAD_DIR.iterdir():
        if file.is_file() and file.name not in known and file.stat().st_mtime < deadline:
            file.unlink(missing_ok=True)
            orphans += 1

    if old_paths or orphans:
        log.info("Автоудаление: задач %d, фото без задачи %d", len(old_paths), orphans)


async def cleanup_loop() -> None:
    """Фоновый цикл: раз в CLEANUP_EVERY_MINUTES минут вызывает cleanup_once()."""
    while True:
        await asyncio.sleep(CLEANUP_EVERY_MINUTES * 60)
        try:
            await asyncio.to_thread(cleanup_once)  # в отдельном потоке, чтобы не тормозить запросы
        except Exception:
            # Сбой одного прохода не должен останавливать цикл: попробуем в следующий раз
            log.exception("Автоудаление: ошибка, повторим через %d мин", CLEANUP_EVERY_MINUTES)
