"""
Прогрев моделей. Первый запрос к Paddle (и TrOCR) загружает модели около минуты, и без прогрева
эту минуту ждал бы тот, кто первым загрузит документ. Поэтому при старте сервера (lifespan в main.py)
модели грузятся в фоне, а очередь (jobs.py) не берёт задачи, пока прогрев не закончится.

Что именно грузить, решает функция warmup() в pipeline.py. Здесь только запуск и состояние.

Состояние отдаёт GET /health (поле ready), по нему страница пишет «модель загружается».

Загрузить модели заранее, вручную, и узнать, сколько это занимает (см. README, «Работа без сети»):
    python -m backend.warmup
"""
import os
import threading
import time

from backend.log import log

# Сколько очередь ждёт прогрев, секунд. Если за это время модели не загрузились, задачи всё равно пойдут
# (модель тогда загрузится при первом документе), чтобы очередь не зависла навсегда.
WAIT_SECONDS = int(os.getenv("WARMUP_WAIT_SECONDS", "600"))

_state = {"state": "loading", "seconds": None}   # state: loading (грузится) / ready (готово) / failed (не вышло)
_done = threading.Event()
_started = False
_lock = threading.Lock()


def _run() -> None:
    """Грузит модели через pipeline.warmup() и записывает итог. Исключение не пробрасывается: сервер работает и без прогрева."""
    from backend import pipeline  # импорт здесь: сам он может быть тяжёлым и не должен задерживать старт сервера

    start = time.perf_counter()
    try:
        log.info("Прогрев моделей: начало")
        pipeline.warmup()
        _state["state"] = "ready"
    except Exception:
        log.exception("Прогрев моделей не удался, модели загрузятся при первом документе")
        _state["state"] = "failed"
    _state["seconds"] = round(time.perf_counter() - start, 1)
    log.info("Прогрев моделей: %s за %.1f с", _state["state"], _state["seconds"])
    _done.set()


def start() -> None:
    """Запускает прогрев в фоне (один раз, повторные вызовы ничего не делают)."""
    global _started
    with _lock:
        if _started:
            return
        _started = True
    threading.Thread(target=_run, name="warmup", daemon=True).start()


def wait() -> None:
    """Ждёт конца прогрева (но не дольше WAIT_SECONDS). Вызывается очередью перед каждой задачей."""
    _done.wait(WAIT_SECONDS)


def status() -> dict:
    """Состояние для /health: ready (bool), state (loading / ready / failed) и seconds (сколько грузились)."""
    return {"ready": _state["state"] == "ready", **_state}


if __name__ == "__main__":
    # Ручной запуск: загрузить (и при первом запуске скачать) модели и показать время
    t0 = time.perf_counter()
    from backend import pipeline

    pipeline.warmup()
    print(f"Модели загружены за {time.perf_counter() - t0:.1f} с")
