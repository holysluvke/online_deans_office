#!/usr/bin/env python3
"""
Отчёт по ошибкам (issue #1): где именно теряются баллы.

    python tools/field_report.py --results results.json
    python tools/field_report.py --results results.json --reference data/open/reference_results.json --md report.md

Разделы:
    1. Метрики evaluate.py.
    2. Точность по каждому полю + разбор ошибок на три вида:
         F  ложное «найдено»  (в эталоне «не найдено», мы вернули значение)  - самое дорогое:
                                Q1 говорит «документ в порядке», а он не в порядке
         M  ложное «не найдено» (в эталоне значение есть, мы не нашли)
         W  неверное значение
    3. Подпись и печать: precision и recall по обоим классам (есть / нет).
    4. Матрица «документ x поле» по каждому типу документа.
    5. Точность по типам вопросов (в том же смысле, что в evaluate.py).
    6. Время на документ (если рядом лежит results.meta.json).
"""
import argparse
import json
import re
import statistics
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MISSING = "не найдено"
FLAGS = ("signature_present", "seal_present")


def _norm(value):
    """Та же нормализация, что в evaluate.py."""
    if value is None or isinstance(value, bool):
        return value
    value = unicodedata.normalize("NFC", str(value)).casefold().replace("ё", "е")
    for char in "«»“”„":
        value = value.replace(char, '"')
    return re.sub(r"\s+", " ", value).strip()


def same(a, b):
    return type(a) is type(b) and _norm(a) == _norm(b)


def classify_error(expected, actual):
    """'' если верно, иначе F / M / W."""
    if same(actual, expected):
        return ""
    if isinstance(expected, str) and expected == MISSING:
        return "F"
    if isinstance(actual, str) and actual == MISSING:
        return "M"
    return "W"


def question_kind(question_text, ref_answer):
    """Тип вопроса по тексту; если текста нет, по ответу эталона."""
    if question_text:
        q = _norm(question_text)
        if "обязательные сведения" in q:
            return "Q1 комплектность"
        if "окончательное решение" in q:
            return "Q3 кто решает"
        if "значение поля" in q:
            return "Q2 поле (есть в документе)" if ref_answer["answerable"] else "Q2 поле (пропущено)"
        return "Q4 нет в документе"
    sources = ref_answer.get("sources", [])
    if ref_answer.get("value") in ("document_ok", "missing_fields"):
        return "Q1 комплектность"
    if sources == ["rule:1.3"]:
        return "Q3 кто решает"
    if any(s.startswith("field:") for s in sources):
        return "Q2 поле (есть в документе)"
    if _norm(ref_answer.get("answer", "")).startswith('поле "'):
        return "Q2 поле (пропущено)"
    return "Q4 нет в документе"


def prf(tp, fp, fn):
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return precision, recall


def build_report(reference, results, meta=None, questions=None):
    ref_docs = {d["document_id"]: d for d in reference["documents"]}
    res_docs = {d["document_id"]: d for d in results["documents"]}
    ids = [i for i in ref_docs if i in res_docs]

    fields = defaultdict(lambda: {"n": 0, "ok": 0, "F": 0, "M": 0, "W": 0})
    cells = {}  # (doc_id, field) -> код
    errors = []
    confusion = {flag: {"tp": 0, "fp": 0, "fn": 0, "tn": 0, "bad": []} for flag in FLAGS}
    valid_bad = []
    kinds = defaultdict(lambda: [0, 0])

    for did in ids:
        ref, res = ref_docs[did], res_docs[did]
        dtype = ref["document_type"]
        for key, expected in ref["fields"].items():
            actual = res["fields"].get(key)
            code = classify_error(expected, actual)
            row = fields[(dtype, key)]
            row["n"] += 1
            row["ok" if not code else code] += 1
            cells[(did, key)] = code or "."
            if code:
                errors.append((did, key, expected, actual, code))
            if key in FLAGS:
                c = confusion[key]
                if expected is True:
                    c["tp" if actual is True else "fn"] += 1
                else:
                    c["fp" if actual is True else "tn"] += 1
                if expected is not actual:
                    c["bad"].append(did)
        rv, v = ref["validation"], res["validation"]
        if not (v["status"] == rv["status"] and set(v["missing_fields"]) == set(rv["missing_fields"])
                and set(v["sources"]) == set(rv["sources"])):
            valid_bad.append((did, rv["missing_fields"], v["missing_fields"]))
        ref_answers = {a["question_id"]: a for a in ref["answers"]}
        q_text = {q["question_id"]: q["question"] for q in (questions or [])}
        for a in res["answers"]:
            ra = ref_answers.get(a["question_id"])
            if ra is None:
                continue
            ok = (a["answerable"] == ra["answerable"] and same(a["value"], ra["value"])
                  and set(a["sources"]) == set(ra["sources"]))
            kind = question_kind(q_text.get(a["question_id"]), ra)
            kinds[kind][0] += 1
            kinds[kind][1] += int(ok)

    return {
        "documents": len(ids),
        "ref_docs": ref_docs,
        "res_docs": res_docs,
        "ids": ids,
        "fields": dict(fields),
        "cells": cells,
        "errors": errors,
        "confusion": confusion,
        "valid_bad": valid_bad,
        "kinds": dict(kinds),
        "meta": meta,
    }


def table(rows, headers):
    widths = [max(len(str(x)) for x in col) for col in zip(headers, *rows)] if rows else [len(h) for h in headers]
    line = "  ".join(str(h).ljust(w) for h, w in zip(headers, widths))
    out = [line, "  ".join("-" * w for w in widths)]
    out += ["  ".join(str(c).ljust(w) for c, w in zip(r, widths)) for r in rows]
    return "\n".join(out)


def pct(x):
    return "  -  " if x is None else f"{x * 100:5.1f}"


def render(report, max_errors=60):
    out = []
    n_docs = report["documents"]

    # 2. по полям
    rows = []
    total_ok = total_n = 0
    for (dtype, key), r in sorted(report["fields"].items()):
        total_ok += r["ok"]
        total_n += r["n"]
        rows.append((dtype, key, r["n"], pct(r["ok"] / r["n"]), r["F"], r["M"], r["W"]))
    out.append(f"== Точность по полям (документов: {n_docs}, всего значений: {total_n}, верно: "
               f"{total_ok / total_n * 100:.1f}%)" if total_n else "== нет данных")
    out.append("F: ложное «найдено», M: ложное «не найдено», W: неверное значение")
    out.append(table(rows, ("тип документа", "поле", "n", "верно %", "F", "M", "W")))
    sums = {k: sum(r[k] for r in report["fields"].values()) for k in ("F", "M", "W")}
    out.append(f"\nИтого ошибок: F={sums['F']} (опасные), M={sums['M']}, W={sums['W']}")

    # 3. подпись / печать
    out.append("\n== Подпись и печать (цель из #7: precision и recall >= 95%)")
    rows = []
    for flag, c in report["confusion"].items():
        if c["tp"] + c["fp"] + c["fn"] + c["tn"] == 0:
            continue
        p_has, r_has = prf(c["tp"], c["fp"], c["fn"])
        p_no, r_no = prf(c["tn"], c["fn"], c["fp"])
        rows.append((flag, "есть", pct(p_has), pct(r_has), c["tp"] + c["fn"], c["fp"], c["fn"]))
        rows.append((flag, "нет", pct(p_no), pct(r_no), c["tn"] + c["fp"], c["fn"], c["fp"]))
    out.append(table(rows, ("флаг", "класс", "precision %", "recall %", "в эталоне", "ложно +", "ложно -")))
    for flag, c in report["confusion"].items():
        if c["bad"]:
            out.append(f"промахи {flag}: {', '.join(c['bad'])}")

    # 4. матрица
    by_type = defaultdict(list)
    for did in report["ids"]:
        by_type[report["ref_docs"][did]["document_type"]].append(did)
    out.append("\n== Матрица документ x поле  (. верно, F ложное найдено, M ложное не найдено, W неверно)")
    for dtype, dids in by_type.items():
        keys = list(report["ref_docs"][dids[0]]["fields"])
        out.append(f"\n{dtype}")
        for i, k in enumerate(keys, start=1):
            out.append(f"  {i:>2} = {k}")
        header = "  " + "id".ljust(9) + " ".join(f"{i:>2}" for i in range(1, len(keys) + 1))
        out.append(header)
        for did in dids:
            marks = " ".join(f"{report['cells'].get((did, k), '?'):>2}" for k in keys)
            out.append("  " + did.ljust(9) + marks)

    # ошибки подробно
    out.append(f"\n== Ошибки полей: ожидалось -> получено (первые {max_errors})")
    for did, key, expected, actual, code in report["errors"][:max_errors]:
        out.append(f"  [{code}] {did} {key}: {expected!r} -> {actual!r}")
    if not report["errors"]:
        out.append("  нет")
    elif len(report["errors"]) > max_errors:
        out.append(f"  ... и ещё {len(report['errors']) - max_errors}")

    # 1. документы с неверной validation
    out.append(f"\n== validation_exact_match: неверных документов {len(report['valid_bad'])} из {n_docs}")
    for did, want, got in report["valid_bad"][:20]:
        out.append(f"  {did}: ожидалось missing={want}, получено missing={got}")

    # 5. вопросы
    out.append("\n== Точность по типам вопросов")
    rows = [(k, v[0], v[1], pct(v[1] / v[0])) for k, v in sorted(report["kinds"].items())]
    out.append(table(rows, ("тип вопроса", "n", "верно", "%")))

    # 6. время
    meta = report.get("meta")
    if meta:
        secs = [i["seconds"] for i in meta["documents"].values() if i["cache_hit"] is not True]
        if secs:
            out.append(f"\n== Время: документов без кэша {len(secs)}, среднее {statistics.mean(secs):.1f} с, "
                       f"максимум {max(secs):.1f} с")
    return "\n".join(out)


def text_field_accuracy(report):
    """Доля верных текстовых полей без подписи и печати (для сравнений в spike #4)."""
    ok = n = 0
    for (dtype, key), r in report["fields"].items():
        if key in FLAGS:
            continue
        ok += r["ok"]
        n += r["n"]
    return ok / n if n else None


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--results", default="results.json")
    p.add_argument("--reference")
    p.add_argument("--questions")
    p.add_argument("--md")
    args = p.parse_args(argv)

    ref_path = next((Path(c) for c in (args.reference, ROOT / "data/open/reference_results.json",
                                       ROOT / "reference_results.json") if c and Path(c).is_file()), None)
    if ref_path is None:
        raise SystemExit("Не найден reference_results.json: положите его в data/open/")
    results_path = Path(args.results)
    meta_path = results_path.with_suffix(".meta.json")
    q_path = next((Path(c) for c in (args.questions, ROOT / "data/open/questions.json", ROOT / "questions.json")
                   if c and Path(c).is_file()), None)
    report = build_report(
        json.loads(ref_path.read_text(encoding="utf-8")),
        json.loads(results_path.read_text(encoding="utf-8")),
        json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else None,
        json.loads(q_path.read_text(encoding="utf-8")) if q_path else None,
    )
    text = render(report)
    print(text)
    if args.md:
        Path(args.md).write_text("```\n" + text + "\n```\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
