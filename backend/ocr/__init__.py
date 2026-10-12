"""
OCR для «Онлайн-деканата»: фото или PDF -> чистый текст + JSON по шаблону.

Главное:
    run_ocr(путь)                  -> словарь по шаблону ниже
    save_result(результат, папка)  -> пишет <имя>.txt и <имя>.json
Из консоли:
    python -m backend.ocr data/samples/справка.jpg --out data/ocr

Шаблон JSON (schema_version 1, поправим, когда лид утвердит контракт):
{
  "schema_version": 1,
  "source": {"file": "справка.jpg", "format": "jpeg", "pages": 1},
  "engine": {"name": "PaddleOCR", "version": "3.x", "lang": "ru", ...},
  "text": "весь чистый текст, страницы через пустую строку",
  "pages": [
    {
      "index": 0,
      "width": 1240, "height": 1754,          # размер исходной страницы в пикселях
      "rotation": 0,                          # на сколько градусов PaddleOCR повернул лист
      "shadow_fixed": false,                  # выравнивали ли тень
      "text": "чистый текст страницы",
      "lines": [
        {
          "text": "СПРАВКА ОБ ОБУЧЕНИИ",
          "confidence": 0.98,
          "low_confidence": false,            # true -> строки нет в "text"
          "bbox": [x, y, ширина, высота],     # на исходной странице, для подсветки
          "polygon": [[x, y], [x, y], [x, y], [x, y]]
        }
      ]
    }
  ],
  "warnings": ["Текст не найден на странице 2"],
  "timings": {"load": 0.1, "ocr": 3.2}
}
"""
import json
import time
from pathlib import Path

from backend.ocr.intake import OcrError, load_document
from backend.ocr.preprocess import prepare
from backend.ocr.text import clean_line, page_text

SCHEMA_VERSION = 1

__all__ = ["OcrError", "run_ocr", "save_result"]


def run_ocr(path: str | Path) -> dict:
    from backend.ocr import engine

    path = Path(path)
    started = time.perf_counter()
    fmt, pages = load_document(path)
    loaded = time.perf_counter()

    out_pages = []
    warnings = []
    for page in pages:
        prepared = prepare(page.image)
        raw_lines, turns = engine.recognize(prepared.image)
        lines = [_to_page_coords(l, prepared.scale, page.image.size) for l in raw_lines]
        text = page_text(lines)
        if not text:
            warnings.append(f"Текст не найден на странице {page.index + 1}")
        out_pages.append({
            "index": page.index,
            "width": page.image.width,
            "height": page.image.height,
            "rotation": turns * 90,
            "shadow_fixed": prepared.shadow_fixed,
            "text": text,
            "lines": lines,
        })

    full_text = "\n\n".join(p["text"] for p in out_pages if p["text"])
    if not full_text:
        raise OcrError("Не удалось прочитать текст. Переснимите документ при хорошем свете")

    return {
        "schema_version": SCHEMA_VERSION,
        "source": {"file": path.name, "format": fmt, "pages": len(pages)},
        "engine": engine.engine_info(),
        "text": full_text,
        "pages": out_pages,
        "warnings": warnings,
        "timings": {
            "load": round(loaded - started, 3),
            "ocr": round(time.perf_counter() - loaded, 3),
        },
    }


def _to_page_coords(line: dict, scale: float, size: tuple[int, int]) -> dict:
    from backend.ocr.engine import MIN_CONFIDENCE

    width, height = size
    polygon = [
        [round(min(max(x / scale, 0), width - 1), 1), round(min(max(y / scale, 0), height - 1), 1)]
        for x, y in line["polygon"]
    ]
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    left, top = int(min(xs)), int(min(ys))
    confidence = round(line["confidence"], 4)
    return {
        "text": clean_line(line["text"]),
        "confidence": confidence,
        "low_confidence": confidence < MIN_CONFIDENCE,
        "bbox": [left, top, int(max(xs)) - left + 1, int(max(ys)) - top + 1],
        "polygon": polygon,
    }


def save_result(result: dict, out_dir: str | Path) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(result["source"]["file"]).stem
    txt_path = out_dir / f"{stem}.txt"
    json_path = out_dir / f"{stem}.json"
    txt_path.write_text(result["text"] + "\n", encoding="utf-8")
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return txt_path, json_path
