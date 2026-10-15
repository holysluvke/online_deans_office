"""
Замер времени обработки документа: холодный и тёплый старт. Нужен, чтобы знать, сколько ждёт проверяющий.

Запуск (из корня проекта, с включённым .venv):
    python -m backend.bench путь\\к\\фото.jpg                 # сначала прогрев (как при старте сервера), потом документы
    python -m backend.bench путь\\к\\фото.jpg --no-warmup     # без прогрева: первый документ включает загрузку моделей
    python -m backend.bench фото.jpg --type internship_certificate --runs 5

Холодный старт = модели ещё не в памяти (первый документ после запуска без прогрева).
Тёплый = модели уже загружены. Для честного «холодного» замера запускайте при перезапущенном процессе.
Результат (строки внизу) можно вставить в README.
"""
import argparse
import statistics
import time

from backend import pipeline

DEFAULT_QUESTION = "Содержит ли документ все обязательные сведения по Положению?"


def run_once(path: str, doc_type: str) -> tuple[float, float]:
    """Один документ: возвращает (секунды на extract_fields, секунды на answer_question)."""
    t0 = time.perf_counter()
    fields = pipeline.extract_fields(path, doc_type)
    t1 = time.perf_counter()
    pipeline.answer_question(fields, doc_type, DEFAULT_QUESTION)
    return t1 - t0, time.perf_counter() - t1


def main() -> None:
    parser = argparse.ArgumentParser(description="Замер времени обработки документа")
    parser.add_argument("image", help="путь к фото документа")
    parser.add_argument("--type", default="study_certificate", help="тип документа (по умолчанию study_certificate)")
    parser.add_argument("--runs", type=int, default=3, help="сколько раз обработать документ (по умолчанию 3)")
    parser.add_argument("--no-warmup", action="store_true", help="не прогревать модели заранее")
    args = parser.parse_args()

    warm_s = None
    if not args.no_warmup:
        t0 = time.perf_counter()
        pipeline.warmup()
        warm_s = time.perf_counter() - t0
        print(f"Прогрев моделей: {warm_s:.1f} с")

    totals = []
    for i in range(1, args.runs + 1):
        ocr_s, rag_s = run_once(args.image, args.type)
        totals.append(ocr_s + rag_s)
        print(f"Документ {i}: {ocr_s + rag_s:.1f} с (OCR {ocr_s:.1f} с, ответ {rag_s:.1f} с)")

    print("\n--- для README ---")
    if warm_s is not None:
        print(f"Прогрев моделей при старте: {warm_s:.0f} с")
    label = "Первый документ после прогрева" if warm_s is not None else "Первый документ без прогрева (холодный старт)"
    print(f"{label}: {totals[0]:.1f} с")
    if len(totals) > 1:
        print(f"Следующие документы (тёплый старт): {statistics.mean(totals[1:]):.1f} с в среднем")


if __name__ == "__main__":
    main()
