#!/usr/bin/env python3
"""
Eval-стенд «Онлайн-деканата» (issue #1) и генератор итогового results.json (#13).

Запуск из корня проекта, с включённым окружением:

    # Уровень A: эталонные поля -> answer_question. Обязан дать 1.0 по всем метрикам.
    python tools/run_batch.py --mode gold

    # Уровень B: фото -> extract_fields -> answer_question (без веба). Это baseline OCR.
    python tools/run_batch.py --mode ocr --source png
    python tools/run_batch.py --mode ocr --source pdf

    # Закрытая проверка (эталона нет, оценка не считается, но формат проверяется):
    python tools/run_batch.py --mode ocr --source png --data data/closed --out results.json

Что делает:
    1. Находит документы в <data>/documents по documents.json (или по именам файлов).
    2. gold: берёт поля из reference_results.json. ocr: зовёт backend.pipeline.extract_fields.
    3. Считает validation через check_completeness и ответы через answer_question,
       формат ровно как ждёт evaluate.py.
    4. Пишет results.json и results.meta.json (секунды на документ, попадание в кэш, ошибки).
    5. Если есть эталон: печатает метрики evaluate.py и таблицу tools/field_report.py.

Кэш: тяжёлый шаг (run_ocr) кэшируется в data/cache/ocr по хешу файла и настроек OCR.
Правки fields.py и knowledge/* кэш НЕ сбрасывают намеренно: разбор полей каждый раз
считается заново за миллисекунды, поэтому цикл «поправил fields.py -> увидел цифры»
занимает секунды. Правки движка (engine, preprocess, text, intake, handwriting),
USE_HANDWRITING и настройки Paddle сбрасывают кэш сами.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.knowledge import check_completeness  # noqa: E402
from backend.knowledge.rules import MISSING, SIGN_FIELDS, TEXT_FIELDS  # noqa: E402
from backend.pipeline import answer_question  # noqa: E402

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
PDF_EXT = {".pdf"}
SOURCE_EXT = {"png": IMAGE_EXT, "pdf": PDF_EXT}
SOURCE_RE = re.compile(r"rule:\d+[.]\d+|field:[a-z_]+")
RULE_RE = re.compile(r"rule:\d+[.]\d+")

ID_KEYS = ("document_id", "id", "doc_id")
TYPE_KEYS = ("document_type", "doc_type", "type")


# ---------------------------------------------------------------- данные

def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _first_existing(*candidates):
    for c in candidates:
        if c is not None and Path(c).is_file():
            return Path(c)
    return None


def _entries(raw):
    """documents.json может быть списком, {"documents": [...]} или {id: {...}}."""
    if isinstance(raw, dict):
        for key in ("documents", "items", "data"):
            if isinstance(raw.get(key), list):
                return raw[key]
        out = []
        for key, value in raw.items():
            out.append({"document_id": key, **value} if isinstance(value, dict) else {"document_id": key, "file": value})
        return out
    return raw if isinstance(raw, list) else []


def _strings(value, depth=0):
    if isinstance(value, str):
        yield value
    elif depth < 2 and isinstance(value, dict):
        for v in value.values():
            yield from _strings(v, depth + 1)
    elif depth < 2 and isinstance(value, list):
        for v in value:
            yield from _strings(v, depth + 1)


def _pick(entry, keys):
    for key in keys:
        if isinstance(entry.get(key), str):
            return entry[key]
    return None


def _resolve_file(data_dir, doc_id, entry, exts):
    docs_dir = data_dir / "documents"
    for candidate in _strings(entry or {}):
        if Path(candidate).suffix.lower() not in exts:
            continue
        for path in (data_dir / candidate, docs_dir / candidate, docs_dir / Path(candidate).name):
            if path.is_file():
                return path
    if docs_dir.is_dir():
        for path in sorted(docs_dir.iterdir()):
            if path.suffix.lower() in exts and path.stem == doc_id:
                return path
        for path in sorted(docs_dir.iterdir()):
            if path.suffix.lower() in exts and path.stem.startswith(doc_id):
                return path
    return None


def load_documents(data_dir, source, reference):
    """[{document_id, document_type, path}] для режима ocr."""
    data_dir = Path(data_dir)
    exts = SOURCE_EXT[source]
    ref_types = {d["document_id"]: d["document_type"] for d in (reference or {}).get("documents", [])}
    docs_json = data_dir / "documents.json"
    docs = []
    if docs_json.is_file():
        for entry in _entries(load_json(docs_json)):
            if not isinstance(entry, dict):
                continue
            doc_id = _pick(entry, ID_KEYS)
            if not doc_id:
                continue
            doc_type = _pick(entry, TYPE_KEYS) or ref_types.get(doc_id)
            docs.append({"document_id": doc_id, "document_type": doc_type,
                         "path": _resolve_file(data_dir, doc_id, entry, exts)})
    else:
        docs_dir = data_dir / "documents"
        if not docs_dir.is_dir():
            raise SystemExit(f"Нет ни {docs_json}, ни папки {docs_dir}. Положите открытые данные в {data_dir}")
        for path in sorted(docs_dir.iterdir()):
            if path.suffix.lower() in exts:
                docs.append({"document_id": path.stem, "document_type": ref_types.get(path.stem), "path": path})
    missing_file = [d["document_id"] for d in docs if d["path"] is None]
    if missing_file:
        raise SystemExit(
            f"Для {len(missing_file)} документов нет файла формата {source} в {data_dir / 'documents'}: "
            f"{', '.join(missing_file[:5])}{'...' if len(missing_file) > 5 else ''}"
        )
    missing_type = [d["document_id"] for d in docs if d["document_type"] not in TEXT_FIELDS]
    if missing_type:
        raise SystemExit(f"Неизвестен document_type у {missing_type[:5]}: проверьте documents.json")
    return docs


def load_questions(path):
    by_doc = {}
    for q in load_json(path):
        by_doc.setdefault(q["document_id"], []).append(q)
    return by_doc


# ---------------------------------------------------------------- результат

def empty_fields(doc_type):
    """Запасной вариант, если OCR упал: формат остаётся валидным, всё «не найдено»."""
    fields = {key: MISSING for key in TEXT_FIELDS[doc_type]}
    fields.update({key: False for key in SIGN_FIELDS[doc_type]})
    return fields


def document_result(doc_id, doc_type, fields, questions):
    validation = check_completeness(fields, doc_type)
    answers = []
    for q in questions:
        r = answer_question(fields, doc_type, q["question"])
        answers.append({
            "question_id": q["question_id"],
            "answerable": r["answerable"],
            "value": r["value"],
            "answer": r["message"],
            "sources": r["sources"],
        })
    return {
        "document_id": doc_id,
        "document_type": doc_type,
        "fields": fields,
        "validation": {
            "status": validation.value,
            "missing_fields": validation.missing_fields,
            "sources": validation.sources,
        },
        "answers": answers,
    }


def check_format(results):
    """Проверка формата без эталона (те же правила, что в evaluate.py). Список проблем."""
    problems = []
    if results.get("version") != "1.0":
        problems.append("version должен быть 1.0")
    for doc in results.get("documents", []):
        did = doc.get("document_id", "?")
        if set(doc) != {"document_id", "document_type", "fields", "validation", "answers"}:
            problems.append(f"{did}: неверный набор ключей документа")
            continue
        if doc["document_type"] not in TEXT_FIELDS:
            problems.append(f"{did}: неизвестный document_type")
            continue
        expected = set(TEXT_FIELDS[doc["document_type"]]) | set(SIGN_FIELDS[doc["document_type"]])
        if set(doc["fields"]) != expected:
            problems.append(f"{did}: ключи fields не совпадают с типом документа")
        for key, value in doc["fields"].items():
            if type(value) not in (str, bool):
                problems.append(f"{did}.{key}: значение должно быть строкой или boolean")
        v = doc["validation"]
        if v.get("status") not in ("document_ok", "missing_fields"):
            problems.append(f"{did}: неверный validation.status")
        if not all(RULE_RE.fullmatch(s) for s in v.get("sources", [])):
            problems.append(f"{did}: неверный формат validation.sources")
        for a in doc["answers"]:
            qid = a.get("question_id", "?")
            if set(a) != {"question_id", "answerable", "value", "answer", "sources"}:
                problems.append(f"{qid}: неверный набор ключей ответа")
                continue
            if type(a["answerable"]) is not bool:
                problems.append(f"{qid}: answerable должен быть boolean")
            if a["value"] is not None and not isinstance(a["value"], str):
                problems.append(f"{qid}: value должен быть string или null")
            if not isinstance(a["answer"], str) or not a["answer"].strip():
                problems.append(f"{qid}: пустой answer")
            if not all(SOURCE_RE.fullmatch(s) for s in a["sources"]):
                problems.append(f"{qid}: неверный формат sources")
    return problems


# ---------------------------------------------------------------- кэш OCR

ENGINE_FILES = ("engine.py", "preprocess.py", "text.py", "intake.py", "handwriting.py", "__init__.py")


def settings_tag():
    """Короткий хеш всего, что меняет результат run_ocr (но не fields.py)."""
    from backend.ocr import engine

    h = hashlib.sha256()
    h.update(json.dumps(engine.SETTINGS, sort_keys=True, ensure_ascii=False).encode())
    h.update(str(engine.MIN_CONFIDENCE).encode())
    h.update(os.getenv("USE_HANDWRITING", "").encode())
    for name in ENGINE_FILES:
        f = ROOT / "backend" / "ocr" / name
        if f.is_file():
            h.update(f.read_bytes())
    return h.hexdigest()[:8]


def install_ocr_cache(cache_dir, use_cache, state, dump_dir=None):
    """
    Подменяет backend.ocr.run_ocr обёрткой с кэшем. extract_fields импортирует run_ocr
    внутри функции, поэтому боевой путь кода не меняется: тот же extract_fields.
    """
    import backend.ocr as ocr_pkg

    real = ocr_pkg.run_ocr
    tag = settings_tag()
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    if dump_dir:
        Path(dump_dir).mkdir(parents=True, exist_ok=True)

    def dump(path, result):
        if dump_dir:  # распознанный текст каждого документа: <id>.txt (UTF-8)
            (Path(dump_dir) / f"{Path(path).stem}.txt").write_text(result["text"] + "\n", encoding="utf-8")

    def cached(path):
        key = hashlib.sha256(Path(path).read_bytes()).hexdigest()[:20] + "_" + tag
        file = cache_dir / f"{key}.json"
        if use_cache and file.is_file():
            state["hit"] = True
            result = json.loads(file.read_text(encoding="utf-8"))
            dump(path, result)
            return result
        state["hit"] = False
        result = real(path)  # OcrError пробрасываем и не кэшируем
        file.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        dump(path, result)
        return result

    ocr_pkg.run_ocr = cached
    return lambda: setattr(ocr_pkg, "run_ocr", real)


# ---------------------------------------------------------------- прогон

def run(mode, source="png", data_dir="data/open", *, questions=None, reference=None,
        use_cache=True, cache_dir=None, ids=None, limit=None, pdf_direct=False, quiet=False, dump_dir=None):
    """Возвращает (results, meta, reference). Ничего не пишет на диск, кроме кэша OCR."""
    data_dir = Path(data_dir)
    if not data_dir.is_absolute():
        data_dir = ROOT / data_dir
    q_path = _first_existing(questions, data_dir / "questions.json", ROOT / "questions.json")
    if q_path is None:
        raise SystemExit("Не найден questions.json (ни в data/open, ни в корне проекта)")
    # Запасной эталон из корня берём только для открытого набора: у закрытого эталона быть не должно
    open_set = data_dir.resolve() == (ROOT / "data" / "open").resolve()
    ref_path = _first_existing(reference, data_dir / "reference_results.json",
                               ROOT / "reference_results.json" if open_set else None)
    ref = load_json(ref_path) if ref_path else None
    questions_by_doc = load_questions(q_path)

    if mode == "gold":
        if ref is None:
            raise SystemExit("Режим gold требует reference_results.json")
        docs = [{"document_id": d["document_id"], "document_type": d["document_type"], "gold": d["fields"]}
                for d in ref["documents"]]
    else:
        docs = load_documents(data_dir, source, ref)

    if ids:
        wanted = set(ids)
        docs = [d for d in docs if d["document_id"] in wanted]
    if limit:
        docs = docs[:limit]
    if not docs:
        raise SystemExit("Нет документов для прогона")

    state = {}
    restore = None
    extract_fields = None
    if mode == "ocr":
        from backend.pipeline import extract_fields as extract_fields  # noqa: F811

        restore = install_ocr_cache(cache_dir or ROOT / "data" / "cache" / "ocr", use_cache, state, dump_dir)

    results = {"version": "1.0", "documents": []}
    meta = {"mode": mode, "source": source, "documents": {}}
    tmp = tempfile.TemporaryDirectory()
    try:
        for index, doc in enumerate(docs, start=1):
            doc_id, doc_type = doc["document_id"], doc["document_type"]
            started = time.perf_counter()
            error = None
            state["hit"] = None
            if mode == "gold":
                fields = dict(doc["gold"])
            else:
                path = doc["path"]
                try:
                    if source == "pdf" and not pdf_direct:
                        # как на сайте: PDF -> одна PNG через backend/pdf.py (300 dpi)
                        from backend.pdf import pdf_to_png

                        path = Path(tmp.name) / f"{doc_id}.png"
                        path.write_bytes(pdf_to_png(doc["path"].read_bytes()))
                    fields = extract_fields(str(path), doc_type)
                except Exception as e:  # один плохой файл не должен ронять прогон
                    error = f"{type(e).__name__}: {e}"
                    fields = empty_fields(doc_type)
            seconds = time.perf_counter() - started
            results["documents"].append(document_result(doc_id, doc_type, fields, questions_by_doc.get(doc_id, [])))
            meta["documents"][doc_id] = {"seconds": round(seconds, 3), "cache_hit": state["hit"], "error": error}
            if not quiet:
                note = "кэш" if state["hit"] else ("ОШИБКА " + error if error else "")
                print(f"[{index:>3}/{len(docs)}] {doc_id}  {doc_type:<27} {seconds:6.2f} с  {note}", flush=True)
    finally:
        tmp.cleanup()
        if restore:
            restore()
    return results, meta, ref


def timing_summary(meta):
    """Холодные (без кэша) и тёплые замеры отдельно: первый документ включает загрузку моделей."""
    items = list(meta["documents"].values())
    cold = [i["seconds"] for i in items if i["cache_hit"] is False]
    lines = []
    if cold:
        lines.append(f"первый документ (с загрузкой моделей): {cold[0]:.1f} с")
        rest = cold[1:]
        if rest:
            lines.append(f"остальные без кэша: среднее {statistics.mean(rest):.1f} с, "
                         f"медиана {statistics.median(rest):.1f} с, максимум {max(rest):.1f} с")
    hits = sum(1 for i in items if i["cache_hit"])
    if hits:
        lines.append(f"из кэша: {hits} документов")
    errors = [k for k, i in meta["documents"].items() if i["error"]]
    if errors:
        lines.append(f"ОШИБКИ OCR на {len(errors)} документах: {', '.join(errors[:8])}")
    return lines


def load_evaluate():
    spec = importlib.util.spec_from_file_location("dean_evaluate", ROOT / "evaluate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mode", choices=["gold", "ocr"], required=True)
    p.add_argument("--source", choices=["png", "pdf"], default="png")
    p.add_argument("--data", default="data/open", help="папка с documents/, documents.json, questions.json")
    p.add_argument("--questions")
    p.add_argument("--reference")
    p.add_argument("--out", default="results.json")
    p.add_argument("--cache-dir")
    p.add_argument("--no-cache", action="store_true", help="не читать кэш (результат OCR перезапишется)")
    p.add_argument("--ids", help="через запятую: open-001,open-005")
    p.add_argument("--limit", type=int)
    p.add_argument("--pdf-direct", action="store_true", help="PDF в OCR напрямую (200 dpi), а не через pdf_to_png как на сайте")
    p.add_argument("--dump-text", metavar="DIR", help="сохранить распознанный текст каждого документа в DIR/<id>.txt")
    p.add_argument("--no-eval", action="store_true", help="не считать метрики и таблицу")
    p.add_argument("--md", help="сохранить отчёт по полям в markdown-файл")
    args = p.parse_args(argv)

    results, meta, ref = run(
        args.mode, args.source, args.data, questions=args.questions, reference=args.reference,
        use_cache=not args.no_cache, cache_dir=args.cache_dir,
        ids=args.ids.split(",") if args.ids else None, limit=args.limit, pdf_direct=args.pdf_direct,
        dump_dir=args.dump_text,
    )

    out = Path(args.out)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    meta_path = out.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nзаписано: {out} ({len(results['documents'])} документов), {meta_path}")
    for line in timing_summary(meta):
        print(" ", line)

    problems = check_format(results)
    if problems:
        print("\nФОРМАТ results.json НЕВЕРЕН:")
        for line in problems[:20]:
            print("  -", line)
        return 2
    schema = _first_existing(ROOT / "results.schema.json", ROOT / "data" / "open" / "results.schema.json")
    if schema:
        try:
            import jsonschema

            jsonschema.validate(results, load_json(schema))
            print(f"формат по {schema.name}: ок")
        except ImportError:
            print(f"(найден {schema.name}, но jsonschema не установлен: pip install jsonschema)")
        except Exception as e:
            print(f"ФОРМАТ НЕ ПО {schema.name}: {str(e).splitlines()[0]}")
            return 2

    if ref is None or args.no_eval:
        print("эталона нет: метрики не считаются, формат проверен")
        return 0

    from tools import field_report

    evaluate = load_evaluate()
    got_ids = {d["document_id"] for d in results["documents"]}
    ref_part = {**ref, "documents": [d for d in ref["documents"] if d["document_id"] in got_ids]}
    report = evaluate.evaluate(ref_part, results)
    print("\n=== evaluate.py ===")
    for key in ("documents", "questions", "field_accuracy_macro", "validation_exact_match", "question_exact_match"):
        print(f"  {key:<24} {report[key]}")
    print(f"  ошибок (полей/валидаций/вопросов): {len(report['errors'])}")

    print()
    text = field_report.render(field_report.build_report(ref_part, results, meta))
    print(text)
    if args.md:
        Path(args.md).write_text("```\n" + text + "\n```\n", encoding="utf-8")
        print(f"\nотчёт сохранён: {args.md}")

    if args.mode == "gold":
        perfect = all(report[k] == 1.0 for k in ("field_accuracy_macro", "validation_exact_match", "question_exact_match"))
        print("\nУРОВЕНЬ A:", "ОК, 1.0 по всем метрикам" if perfect else "ПРОВАЛ: слой правил ошибается на чистых полях")
        return 0 if perfect else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
