#!/usr/bin/env python3
"""
Бонус #15, вторая половина: прогоняет OCR по всем уровням порчи и строит кривую.

    python tools/degrade.py                 # сначала создать data/degraded/level_N
    python tools/degrade_curve.py           # потом прогнать и построить кривую

Пишет data/degraded/curve.csv и (если установлен matplotlib) data/degraded/curve.png
для слайда. matplotlib необязателен: pip install matplotlib.
По каждому уровню считает: точность текстовых полей, точность подписи/печати,
validation_exact_match и question_exact_match, ложные «найдено» (F).
"""
import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import field_report  # noqa: E402
from tools.run_batch import load_evaluate, run  # noqa: E402


def measure(data_dir, source="png", use_cache=True):
    results, meta, ref = run("ocr", source, data_dir, use_cache=use_cache, quiet=True)
    if ref is None:
        raise SystemExit(f"В {data_dir} нет reference_results.json: degrade.py копирует его из исходной папки")
    report = field_report.build_report(ref, results, meta)
    evaluate = load_evaluate().evaluate(ref, results)
    flags_ok = flags_n = 0
    for (dtype, key), r in report["fields"].items():
        if key in field_report.FLAGS:
            flags_ok += r["ok"]
            flags_n += r["n"]
    return {
        "text_fields": field_report.text_field_accuracy(report),
        "marks": flags_ok / flags_n if flags_n else None,
        "validation": evaluate["validation_exact_match"],
        "questions": evaluate["question_exact_match"],
        "false_found": sum(r["F"] for r in report["fields"].values()),
        "errors": sum(1 for i in meta["documents"].values() if i["error"]),
    }


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", default="data/degraded")
    p.add_argument("--levels", default="0,1,2,3,4")
    p.add_argument("--no-cache", action="store_true")
    args = p.parse_args(argv)

    base = Path(args.base) if Path(args.base).is_absolute() else ROOT / args.base
    rows = []
    for level in (int(x) for x in args.levels.split(",")):
        folder = base / f"level_{level}"
        if not folder.is_dir():
            raise SystemExit(f"Нет {folder}: сначала python tools/degrade.py")
        print(f"уровень {level}...", flush=True)
        rows.append({"level": level, **measure(folder, use_cache=not args.no_cache)})

    csv_path = base / "curve.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n{'уровень':>7} {'поля %':>8} {'подп/печ %':>11} {'validation %':>13} {'вопросы %':>10} {'F':>3} {'ошибок OCR':>11}")
    for r in rows:
        print(f"{r['level']:>7} {r['text_fields'] * 100:>8.1f} {r['marks'] * 100:>11.1f} "
              f"{r['validation'] * 100:>13.1f} {r['questions'] * 100:>10.1f} {r['false_found']:>3} {r['errors']:>11}")
    print(f"\nCSV: {csv_path}")

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib не установлен: график не построен (pip install matplotlib), CSV готов")
        return 0
    xs = [r["level"] for r in rows]
    plt.figure(figsize=(7, 4))
    for key, label in (("text_fields", "текстовые поля"), ("marks", "подпись и печать"),
                       ("validation", "проверка комплектности"), ("questions", "ответы на вопросы")):
        plt.plot(xs, [r[key] * 100 for r in rows], marker="o", label=label)
    plt.xlabel("уровень порчи снимка (0 = оригинал, 4 = поворот 30°, тень, блюр, 0.35 разрешения)")
    plt.ylabel("точность, %")
    plt.ylim(0, 105)
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    png = base / "curve.png"
    plt.savefig(png, dpi=150)
    print(f"график: {png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
