"""
Прогон OCR по MWS-Vision-Bench (русский конфиг) и сверка с эталоном.

Датасет — бенчмарк вопросов к документу, а не список полей справки.
Поэтому сверяем то, что наш OCR вообще умеет:

    full-page OCR, document parsing
        доля слов эталона, которые нашлись в распознанном тексте
    key information extraction, reasoning VQA
        доля эталонных значений, которые нашлись в тексте
    text grounding
        нашлась ли цитата из вопроса и попал ли центр эталонной рамки
        в нашу рамку строки

Картинка распознаётся один раз: в датасете 400 уникальных фото на 1302 вопроса.
Повторный запуск берёт результат из data/mws/cache.

Запуск из корня проекта:
    .venv\\Scripts\\python tools/eval_mws.py
"""
import ast
import hashlib
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pyarrow.parquet as pq

from backend.ocr import OcrError, run_ocr
from backend.ocr.engine import SETTINGS

ROOT = Path(__file__).resolve().parents[1]
PARQUET = ROOT / "data" / "mws" / "train.parquet"
CACHE = ROOT / "data" / "mws" / "cache"
REPORT = ROOT / "data" / "mws" / "report.json"

QUOTED = re.compile(r"«([^»]+)»|\"([^\"]+)\"|“([^”]+)”")


def norm(text: str) -> str:
    text = text.lower().replace("ё", "е")
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&emsp;", " ").replace("&nbsp;", " ")
    text = re.sub(r"[#|*_`]+", " ", text)
    text = re.sub(r"[^\w\s]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def words(text: str) -> list[str]:
    return [w for w in norm(text).split() if len(w) > 1]


def contained(value: str, text: str) -> bool:
    needle = norm(value).replace(" ", "")
    haystack = norm(text).replace(" ", "")
    return bool(needle) and needle in haystack


def word_recall(gold: str, predicted: str) -> float | None:
    gold_words = words(gold)
    if not gold_words:
        return None
    found = set(words(predicted))
    return sum(word in found for word in gold_words) / len(gold_words)


def quoted_phrases(question: str) -> list[str]:
    phrases = [part for match in QUOTED.finditer(question) for part in match.groups() if part]
    return [phrase for phrase in phrases if "x1" not in phrase.lower() and len(phrase.strip()) > 1]


def kie_values(answer: str) -> list[str]:
    try:
        parsed = ast.literal_eval(answer)
    except (ValueError, SyntaxError):
        return [answer]
    if isinstance(parsed, dict):
        values = []
        for value in parsed.values():
            values.extend(value if isinstance(value, list) else [value])
        return [str(value) for value in values]
    return [answer]


def union(lines: list[dict]) -> list[float]:
    x1 = min(line["bbox"][0] for line in lines)
    y1 = min(line["bbox"][1] for line in lines)
    x2 = max(line["bbox"][0] + line["bbox"][2] for line in lines)
    y2 = max(line["bbox"][1] + line["bbox"][3] for line in lines)
    return [x1, y1, x2, y2]


def phrase_box(lines: list[dict], phrase: str) -> list[float] | None:
    target = norm(phrase).replace(" ", "")
    ordered = sorted(lines, key=lambda line: (line["bbox"][1], line["bbox"][0]))
    for width in range(1, 4):
        for start in range(len(ordered) - width + 1):
            chunk = ordered[start:start + width]
            text = norm(" ".join(line["text"] for line in chunk)).replace(" ", "")
            if target and target in text:
                return union(chunk)
    return None


def center_inside(gold: list[float], box: list[float]) -> bool:
    cx, cy = (gold[0] + gold[2]) / 2, (gold[1] + gold[3]) / 2
    return box[0] <= cx <= box[2] and box[1] <= cy <= box[3]


def iou(a: list[float], b: list[float]) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    if inter == 0:
        return 0.0
    area_a = max(0, a[2] - a[0]) * max(0, a[3] - a[1])
    area_b = max(0, b[2] - b[0]) * max(0, b[3] - b[1])
    return inter / (area_a + area_b - inter)


def gold_box(answers: list[str]) -> list[float] | None:
    numbers = []
    for answer in answers:
        if re.fullmatch(r"-?\d+(?:[.,]\d+)?", answer.strip()):
            numbers.append(float(answer.replace(",", ".")))
    if len(numbers) < 4:
        return None
    return numbers[:4]


def _cache_tag() -> str:
    blob = json.dumps(SETTINGS, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()[:8]


def recognize(image_bytes: bytes, suffix: str) -> dict:
    digest = hashlib.sha256(image_bytes).hexdigest()
    path = CACHE / f"{digest}_{_cache_tag()}.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))

    image_path = CACHE / f"{digest}{suffix or '.jpg'}"
    image_path.write_bytes(image_bytes)
    started = time.perf_counter()
    try:
        result = run_ocr(image_path)
        cached = {
            "lines": [
                {"text": line["text"], "bbox": line["bbox"], "low_confidence": line["low_confidence"]}
                for page in result["pages"] for line in page["lines"]
            ],
            "seconds": round(time.perf_counter() - started, 2),
            "error": None,
        }
    except OcrError as e:
        cached = {"lines": [], "seconds": round(time.perf_counter() - started, 2), "error": str(e)}
    path.write_text(json.dumps(cached, ensure_ascii=False), encoding="utf-8")
    return cached


def mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    table = pq.read_table(PARQUET)
    rows = table.to_pylist()

    by_image: dict[str, dict] = {}
    order: list[str] = []
    for row in rows:
        raw = row["image"]["bytes"]
        digest = hashlib.sha256(raw).hexdigest()
        if digest not in by_image:
            suffix = Path(row["image"]["path"] or "").suffix.lower()
            by_image[digest] = {"bytes": raw, "suffix": suffix}
            order.append(digest)
        row["_digest"] = digest

    print(f"вопросов {len(rows)}, уникальных фото {len(order)}", flush=True)
    ocr = {}
    started = time.perf_counter()
    for index, digest in enumerate(order, start=1):
        item = by_image[digest]
        ocr[digest] = recognize(item["bytes"], item["suffix"])
        if index == 1 or index % 20 == 0 or index == len(order):
            spent = time.perf_counter() - started
            left = spent / index * (len(order) - index)
            print(f"фото {index}/{len(order)}, осталось около {left / 60:.0f} мин", flush=True)

    scores = defaultdict(list)
    misses = []
    no_phrase = 0
    for row in rows:
        predicted = ocr[row["_digest"]]
        text = "\n".join(line["text"] for line in predicted["lines"])
        kind = row["type"]
        answers = row["answers"] or []
        record = {"id": row["id"], "type": kind, "score": None, "detail": predicted["error"]}

        if kind in ("full-page OCR ru", "document parsing ru"):
            recalls = [word_recall(answer, text) for answer in answers]
            recalls = [value for value in recalls if value is not None]
            record["score"] = max(recalls) if recalls else 0.0
            scores[kind].append(record["score"])
        elif kind == "key information extraction ru":
            values = [value for answer in answers for value in kie_values(answer)]
            hits = [contained(value, text) for value in values]
            record["score"] = sum(hits) / len(hits) if hits else 0.0
            record["detail"] = f"{sum(hits)}/{len(hits)}"
            scores[kind].append(record["score"])
        elif kind == "reasoning VQA ru":
            hits = [contained(answer, text) for answer in answers]
            record["score"] = 1.0 if any(hits) else 0.0
            scores[kind].append(record["score"])
        elif kind == "text grounding ru":
            phrases = quoted_phrases(row["question"])
            box = gold_box(answers)
            if not phrases or box is None:
                record["detail"] = "в вопросе нет текстовой цели"
                no_phrase += 1
            else:
                found = phrase_box(predicted["lines"], phrases[0])
                record["score"] = 1.0 if found and center_inside(box, found) else 0.0
                record["detail"] = f"iou {iou(box, found):.2f}" if found else "цитата не найдена"
                scores[kind].append(record["score"])
        if record["score"] == 0.0 and len(misses) < 12:
            misses.append({
                "id": row["id"],
                "type": kind,
                "question": row["question"][:180],
                "answers": answers[:2],
                "detail": record["detail"],
            })

    summary = {
        "questions": len(rows),
        "images": len(order),
        "grounding_without_quote": no_phrase,
        "ocr_errors": sum(1 for item in ocr.values() if item["error"]),
        "mean_seconds": round(sum(item["seconds"] for item in ocr.values()) / len(ocr), 2),
        "by_type": {kind: {"n": len(values), "score": mean(values)} for kind, values in scores.items()},
        "misses": misses,
    }
    REPORT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary["by_type"], ensure_ascii=False, indent=2), flush=True)
    print(f"отчёт {REPORT}", flush=True)


if __name__ == "__main__":
    main()
