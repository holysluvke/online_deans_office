"""
Запуск OCR из консоли (из корня проекта, с включённым .venv):

    python -m backend.ocr файл.jpg
    python -m backend.ocr папка_с_документами --out data/ocr

Для каждого документа пишет <имя>.txt (чистый текст) и <имя>.json (шаблон из __init__.py).
"""
import argparse
import sys
from pathlib import Path

from backend.ocr import OcrError, run_ocr, save_result

SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}


def collect(paths: list[str]) -> list[Path]:
    files = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            files.extend(sorted(f for f in p.rglob("*") if f.suffix.lower() in SUFFIXES))
        else:
            files.append(p)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description="OCR документов в txt и json")
    parser.add_argument("inputs", nargs="+", help="файлы или папки")
    parser.add_argument("--out", default="data/ocr", help="куда сохранить (по умолчанию data/ocr)")
    args = parser.parse_args()

    # Консоль Windows по умолчанию не печатает кириллицу
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    files = collect(args.inputs)
    if not files:
        print("Нет файлов для распознавания")
        return 1

    failed = 0
    for f in files:
        try:
            result = run_ocr(f)
        except OcrError as e:
            failed += 1
            print(f"ОШИБКА  {f}: {e}")
            continue
        txt_path, _ = save_result(result, args.out)
        lines = sum(len(p["lines"]) for p in result["pages"])
        print(f"OK      {f} -> {txt_path} ({lines} строк, {result['timings']['ocr']} с)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
