"""
Логирование бэкенда. Все модули пишут через один логгер:
    from backend.log import log
    log.info("...") / log.warning("...") / log.exception("...")  (exception - внутри except, с трассировкой)

Куда пишется:
    - в консоль (рядом с сообщениями uvicorn);
    - в файл data/logs/app.log; при 5 МБ файл переименовывается в app.log.1 и т.д., хранятся 3 старых.

Уровень задаётся переменной окружения LOG_LEVEL (по умолчанию INFO).
С LOG_LEVEL=DEBUG видны ещё и частые опросы страницы (GET /jobs раз в 2 с), они по умолчанию скрыты.

ВАЖНО, персональные данные: в лог НЕ пишем session_id, IP, имена файлов, вопросы и распознанные поля.
Только служебное: метод, путь, статус, время, job_id, тип документа, размер.
"""
import logging
import os
from logging.handlers import RotatingFileHandler

from backend.db import DATA_DIR

LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

log = logging.getLogger("deans_office")

if not log.handlers:  # настраиваем один раз, даже если модуль импортируют повторно
    log.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    log.propagate = False  # не дублировать сообщения через корневой логгер

    formatter = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S")
    for handler in (
        logging.StreamHandler(),
        RotatingFileHandler(LOG_DIR / "app.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"),
    ):
        handler.setFormatter(formatter)
        log.addHandler(handler)
