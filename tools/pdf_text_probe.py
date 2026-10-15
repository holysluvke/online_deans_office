#!/usr/bin/env python3
"""
Спайк #4: есть ли в PDF организаторов текстовый слой и даёт ли он выигрыш над OCR.

    python tools/pdf_text_probe.py                       # data/open
    python tools/pdf_text_probe.py --show 3              # напечатать текст первых 3 PDF
    python tools/pdf_text_probe.py --ocr-results results.json
        # сравнить с OCR: results.json получен командой run_batch --mode ocr --source png

Что проверяет:
    1. Для каждого PDF: страниц, символов в текстовом слое, есть ли встроенные картинки
       (скан внутри PDF) и есть ли векторные штрихи.
    2. Если есть эталон: прогоняет pick_fields по тексту слоя (без OCR) и считает точность
       ТЕКСТОВЫХ полей. Подпись и печать не считаются: они определяются по картинке
       (issue #7), а здесь картинки в разборе нет.
    3. С --ocr-results: считает ту же точность для OCR и печатает вывод по порогу.

Как читать вывод. Если у всех PDF символов 0 или мало, документ внутри это картинка,
и ветка «текстовый слой» бесполезна: честно пишем в README, что для PDF работает OCR.
Если слой есть и точность текстовых полей заметно выше OCR, делаем ветку
«слой, иначе OCR» и честно говорим жюри, что для PDF мы читаем слой, а не распознаём.
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import field_report  # noqa: E402
from tools.run_batch import load_documents, load_json  # noqa: E402

MIN_CHARS = 50  # меньше: слоя фактически нет (колонтитул, водяной знак)
GAIN_THRESHOLD = 0.03  # +3 п.п. над OCR и выше считаем «выигрыш большой»


def inspect_pdf(path):
    """Возвращает {pages, chars, text, image_objects, text_objects}. Текст страниц через пустую строку."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    texts, images, text_objs = [], 0, 0
    try:
        for i in range(len(pdf)):
            page = pdf[i]
            textpage = page.get_textpage()
            texts.append(textpage.get_text_range().replace("\r\n", "\n").replace("\r", "\n"))
            try:
                for obj in page.get_objects():
                    if obj.type == pdfium.raw.FPDF_PAGEOBJ_IMAGE:
                        images += 1
                    elif obj.type == pdfium.raw.FPDF_PAGEOBJ_TEXT:
                        text_objs += 1
            except Exception:
                pass  # старые версии pypdfium2: счётчики объектов необязательны
        count = len(pdf)
    finally:
        pdf.close()
    text = "\n\n".join(texts)
    return {"pages": count, "chars": len("".join(text.split())), "text": text,
            "image_objects": images, "text_objects": text_objs}


def fields_from_text(doc_type, text):
    from backend.ocr.fields import pick_fields

    rows = [r for r in text.split("\n") if r.strip()]
    ocr = {"text": text, "pages": [{"text": "\n".join(rows), "lines": []}]}
    return pick_fields(doc_type, ocr, [])  # картинок нет: подпись и печать False, их не оцениваем


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", default="data/open")
    p.add_argument("--reference")
    p.add_argument("--ocr-results")
    p.add_argument("--show", type=int, default=1, help="сколько PDF напечатать целиком")
    p.add_argument("--dump", metavar="FILE", help="записать текстовый слой всех PDF в один UTF-8 файл")
    args = p.parse_args(argv)

    data_dir = Path(args.data)
    if not data_dir.is_absolute():
        data_dir = ROOT / data_dir
    ref_path = next((Path(c) for c in (args.reference, data_dir / "reference_results.json",
                                       ROOT / "reference_results.json") if c and Path(c).is_file()), None)
    ref = load_json(ref_path) if ref_path else None
    docs = load_documents(data_dir, "pdf", ref)

    infos = {}
    print(f"{'документ':<10} {'стр':>3} {'символов':>9} {'картинок':>9} {'текст.объектов':>15}")
    for d in docs:
        info = inspect_pdf(d["path"])
        infos[d["document_id"]] = info
        print(f"{d['document_id']:<10} {info['pages']:>3} {info['chars']:>9} {info['image_objects']:>9} {info['text_objects']:>15}")

    if args.dump:
        types = {d["document_id"]: d["document_type"] for d in docs}
        Path(args.dump).write_text(
            "".join(f"=== {i} ({types[i]}) ===\n{v['text'].strip()}\n\n" for i, v in infos.items()),
            encoding="utf-8")
        print(f"\nтекстовый слой всех PDF записан: {args.dump}")

    with_layer = [i for i, v in infos.items() if v["chars"] >= MIN_CHARS]
    print(f"\nс текстовым слоем (>= {MIN_CHARS} символов): {len(with_layer)} из {len(infos)}")
    if not with_layer:
        print("ВЫВОД: слоя нет, PDF = картинка. Ветка «текстовый слой» не нужна. Для PDF работает OCR.")
        return 0

    for doc_id in with_layer[: args.show]:
        print(f"\n--- текстовый слой {doc_id} ---\n{infos[doc_id]['text'][:1500]}\n--- конец ---")

    if ref is None:
        print("\nЭталона нет: точность не считается.")
        return 0

    ref_docs = {d["document_id"]: d for d in ref["documents"]}
    stats = defaultdict(lambda: [0, 0])
    code_count = defaultdict(int)
    for doc in docs:
        doc_id = doc["document_id"]
        if doc_id not in with_layer or doc_id not in ref_docs:
            continue
        got = fields_from_text(doc["document_type"], infos[doc_id]["text"])
        for key, expected in ref_docs[doc_id]["fields"].items():
            if key in field_report.FLAGS:
                continue
            code = field_report.classify_error(expected, got.get(key))
            stats[key][0] += 1
            stats[key][1] += int(not code)
            if code:
                code_count[code] += 1
    total_n = sum(v[0] for v in stats.values())
    total_ok = sum(v[1] for v in stats.values())
    layer_acc = total_ok / total_n if total_n else None
    print("\nТочность текстовых полей по слою PDF (без подписи и печати):")
    for key, (n, ok) in sorted(stats.items()):
        print(f"  {key:<18} {ok}/{n}")
    print(f"ИТОГО по слою: {total_ok}/{total_n} = {layer_acc * 100:.1f}%  "
          f"(ложно найдено F={code_count['F']}, не найдено M={code_count['M']}, неверно W={code_count['W']})")

    if args.ocr_results:
        results = load_json(args.ocr_results)
        ids = set(with_layer)
        ref_part = {**ref, "documents": [d for d in ref["documents"] if d["document_id"] in ids]}
        res_part = {**results, "documents": [d for d in results["documents"] if d["document_id"] in ids]}
        ocr_acc = field_report.text_field_accuracy(field_report.build_report(ref_part, res_part))
        print(f"ИТОГО по OCR на тех же документах: {ocr_acc * 100:.1f}%")
        gain = layer_acc - ocr_acc
        verdict = ("ВЫИГРЫШ БОЛЬШОЙ: делаем ветку «слой, иначе OCR» и честно пишем об этом жюри"
                   if gain >= GAIN_THRESHOLD else "выигрыша нет: оставляем OCR, ветку не делаем")
        print(f"разница {gain * 100:+.1f} п.п. -> {verdict}")
    else:
        print("\nЧтобы принять решение, добавьте --ocr-results results.json (прогон OCR по PNG).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
