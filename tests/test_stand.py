"""
Тесты eval-стенда (tools/*). Работают без PaddleOCR: run_ocr подменяется поддельным,
всё остальное (extract_fields, pick_fields, answer_question, evaluate) настоящее.
"""
import copy
import json
import shutil
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

import backend.ocr as ocr_pkg
from backend.ocr.intake import OcrError
from tools import degrade, field_report, pdf_text_probe, run_batch

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = next((p for p in (ROOT / "data/open/reference_results.json", ROOT / "reference_results.json") if p.is_file()), None)
QUESTIONS = next((p for p in (ROOT / "data/open/questions.json", ROOT / "questions.json") if p.is_file()), None)

pytestmark = pytest.mark.skipif(REFERENCE is None or QUESTIONS is None, reason="нет эталона")

STUDY_ROWS = [
    "СПРАВКА ОБ ОБУЧЕНИИ",
    "Выдана Иванову Ивану Петровичу",
    "в том, что он обучался в Южном университете",
    "Направление подготовки: 38.03.01 Прикладная информатика",
    "Форма обучения: очная",
    "Период обучения: 01.09.2023 - 30.06.2025",
    "Номер справки: 1542 от 12.07.2025",
]
LEAVE_ROWS = [
    "Заявление",
    "Я, Соколов Олег Николаевич, студент группы ЖР-25-1, 3 курс",
    "Прошу академический отпуск по состоянию здоровья",
    "с 01.11.2026 по 31.08.2027",
    "Дата заявления: 07.10.2026",
]
ROWS_BY_DOC = {"open-001": STUDY_ROWS, "open-011": LEAVE_ROWS}


class FakeOcr:
    """Считает вызовы: по ним проверяем, что кэш работает."""

    def __init__(self, fail=False):
        self.calls = 0
        self.fail = fail

    def __call__(self, path):
        self.calls += 1
        if self.fail:
            raise OcrError("Не удалось прочитать текст")
        rows = ROWS_BY_DOC[Path(path).stem]
        return {"text": "\n".join(rows), "pages": [{"text": "\n".join(rows), "lines": []}],
                "timings": {"ocr": 0.01}}


def make_data(tmp_path, style="list"):
    """Мини-набор данных: два документа с PNG и documents.json в одном из форматов."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    docs = tmp_path / "documents"
    docs.mkdir(exist_ok=True)
    for number, doc_id in enumerate(ROWS_BY_DOC):
        img = Image.new("RGB", (200, 300), "white")
        img.putpixel((number, number), (0, 0, 0))  # разные байты: кэш ключуется по хешу файла
        img.save(docs / f"{doc_id}.png")
    entries = [
        {"document_id": "open-001", "document_type": "study_certificate", "file": "open-001.png"},
        {"document_id": "open-011", "document_type": "academic_leave_application", "file": "documents/open-011.png"},
    ]
    if style == "list":
        (tmp_path / "documents.json").write_text(json.dumps(entries), encoding="utf-8")
    elif style == "wrapped":
        wrapped = {"documents": [{"id": e["document_id"], "type": e["document_type"],
                                  "files": {"png": e["file"].split("/")[-1]}} for e in entries]}
        (tmp_path / "documents.json").write_text(json.dumps(wrapped), encoding="utf-8")
    # style == "none": только папка documents, тип берётся из эталона
    return tmp_path


@pytest.fixture
def fake_ocr(monkeypatch):
    fake = FakeOcr()
    monkeypatch.setattr(ocr_pkg, "run_ocr", fake)
    return fake


@pytest.mark.parametrize("style", ["list", "wrapped", "none"])
def test_ocr_chain_formats_and_cache(tmp_path, fake_ocr, style):
    data = make_data(tmp_path / "data", style)
    cache = tmp_path / "cache"
    kwargs = dict(reference=str(REFERENCE), questions=str(QUESTIONS), cache_dir=cache, quiet=True)

    results, meta, ref = run_batch.run("ocr", "png", data, **kwargs)
    assert fake_ocr.calls == 2
    assert [d["document_id"] for d in results["documents"]] == ["open-001", "open-011"]
    assert run_batch.check_format(results) == []
    assert all(m["cache_hit"] is False for m in meta["documents"].values())

    # evaluate.py на частичном наборе: эталон режем до тех же документов
    ref_part = {**ref, "documents": [d for d in ref["documents"] if d["document_id"] in ROWS_BY_DOC]}
    report = run_batch.load_evaluate().evaluate(ref_part, results)
    assert report["format_valid"] is True and report["documents"] == 2

    # повторный прогон целиком из кэша, настоящий OCR не вызывается
    results2, meta2, _ = run_batch.run("ocr", "png", data, **kwargs)
    assert fake_ocr.calls == 2
    assert all(m["cache_hit"] is True for m in meta2["documents"].values())
    assert results2 == results

    # --no-cache перечитывает
    run_batch.run("ocr", "png", data, use_cache=False, **{k: v for k, v in kwargs.items()})
    assert fake_ocr.calls == 4


def test_ocr_cache_does_not_leak_into_production(tmp_path, monkeypatch):
    fake = FakeOcr()
    monkeypatch.setattr(ocr_pkg, "run_ocr", fake)
    data = make_data(tmp_path / "d")
    run_batch.run("ocr", "png", data, reference=str(REFERENCE), cache_dir=tmp_path / "c", quiet=True)
    assert ocr_pkg.run_ocr is fake  # обёртка с кэшем снята после прогона


def test_ocr_error_falls_back_to_valid_empty_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr_pkg, "run_ocr", FakeOcr(fail=True))
    data = make_data(tmp_path / "d")
    results, meta, _ = run_batch.run("ocr", "png", data, reference=str(REFERENCE),
                                     cache_dir=tmp_path / "c", quiet=True)
    assert run_batch.check_format(results) == []
    assert all("OcrError" in m["error"] for m in meta["documents"].values())
    doc = results["documents"][0]
    assert doc["validation"]["status"] == "missing_fields"
    assert doc["fields"]["student_name"] == "не найдено" and doc["fields"]["seal_present"] is False


def test_missing_file_is_reported(tmp_path, fake_ocr):
    data = tmp_path / "d"
    (data / "documents").mkdir(parents=True)
    (data / "documents.json").write_text(json.dumps(
        [{"document_id": "open-001", "document_type": "study_certificate", "file": "open-001.png"}]), encoding="utf-8")
    with pytest.raises(SystemExit, match="нет файла"):
        run_batch.run("ocr", "png", data, reference=str(REFERENCE), quiet=True)


def test_pdf_source_converted_like_web(tmp_path, fake_ocr):
    """PDF по умолчанию идёт через backend/pdf.py, как на сайте: в OCR приходит PNG."""
    data = tmp_path / "d"
    (data / "documents").mkdir(parents=True)
    Image.new("RGB", (595, 842), "white").save(data / "documents" / "open-001.pdf", "PDF", resolution=72)
    (data / "documents.json").write_text(json.dumps(
        [{"document_id": "open-001", "document_type": "study_certificate", "file": "open-001.pdf"}]), encoding="utf-8")
    results, meta, _ = run_batch.run("ocr", "pdf", data, reference=str(REFERENCE), questions=str(QUESTIONS),
                                     cache_dir=tmp_path / "c", quiet=True)
    assert fake_ocr.calls == 1 and meta["documents"]["open-001"]["error"] is None
    assert run_batch.check_format(results) == []


def test_check_format_catches_problems():
    results, _, _ = run_batch.run("gold", reference=str(REFERENCE), quiet=True)
    bad = copy.deepcopy(results)
    bad["documents"][0]["fields"]["student_name"] = None
    bad["documents"][1]["answers"][0]["sources"] = ["3.1"]
    bad["documents"][2]["validation"]["status"] = "ok"
    problems = run_batch.check_format(bad)
    assert len(problems) == 3


# ---------------------------------------------------------------- field_report

def _gold():
    results, _, ref = run_batch.run("gold", reference=str(REFERENCE), quiet=True)
    return ref, results


def test_field_report_classifies_errors_and_flags():
    ref, results = _gold()
    res = copy.deepcopy(results)
    docs = {d["document_id"]: d for d in res["documents"]}
    docs["open-001"]["fields"]["student_name"] = "Другое Имя Иванович"      # W
    docs["open-001"]["fields"]["university"] = "не найдено"                  # M
    docs["open-002"]["fields"]["issue_date"] = "2026-09-01"                  # F (в эталоне «не найдено»)
    docs["open-003"]["fields"]["signature_present"] = True                   # ложное «есть» (эталон False)
    docs["open-001"]["fields"]["seal_present"] = False                       # пропущенная печать

    report = field_report.build_report(ref, res)
    totals = {k: sum(r[k] for r in report["fields"].values()) for k in ("F", "M", "W")}
    # W=3: неверное имя и две ошибки флагов (для bool «ложное найдено» не бывает)
    assert totals == {"F": 1, "M": 1, "W": 3}
    assert report["fields"][("study_certificate", "student_name")]["W"] == 1
    assert report["fields"][("study_certificate", "university")]["M"] == 1
    assert report["fields"][("study_certificate", "issue_date")]["F"] == 1

    sig = report["confusion"]["signature_present"]
    assert sig["fp"] == 1 and sig["fn"] == 0
    seal = report["confusion"]["seal_present"]
    assert seal["fn"] == 1
    assert "open-003" in sig["bad"] and "open-001" in seal["bad"]

    text = field_report.render(report)
    assert "Матрица документ x поле" in text and "open-002" in text
    assert "Q2 поле (пропущено)" in text and "Q4 нет в документе" in text


def test_field_report_is_clean_on_gold():
    ref, results = _gold()
    report = field_report.build_report(ref, results)
    assert report["errors"] == [] and report["valid_bad"] == []
    assert field_report.text_field_accuracy(report) == 1.0
    assert all(v[0] == v[1] for v in report["kinds"].values())
    assert report["kinds"]["Q2 поле (пропущено)"][0] == 17  # как в ISSUES.md: 17 из 30


# ---------------------------------------------------------------- degrade

def test_degrade_levels_are_deterministic_and_progressive():
    rng = np.random.default_rng(0)
    img = Image.fromarray(rng.integers(0, 255, (300, 200, 3), dtype=np.uint8))
    assert np.array_equal(np.asarray(degrade.degrade(img, 0, "k")), np.asarray(img))
    a = degrade.degrade(img, 3, "k")
    b = degrade.degrade(img, 3, "k")
    assert np.array_equal(np.asarray(a), np.asarray(b))
    other = degrade.degrade(img, 3, "other")
    assert other.size != a.size or not np.array_equal(np.asarray(other), np.asarray(a))  # другой ключ, другая порча
    assert a.mode == "RGB"
    # чем выше уровень, тем меньше разрешение: 0.35 против 0.8 (поворот добавляет поля, поэтому берём площадь листа до поворота)
    assert degrade.LEVELS[4][3] < degrade.LEVELS[1][3]


def test_degrade_builds_runnable_data_dir(tmp_path, fake_ocr):
    src = make_data(tmp_path / "src")
    for name in ("questions.json", "reference_results.json"):
        shutil.copy(ROOT / (name if (ROOT / name).is_file() else f"data/open/{name}"), src / name)
    n = degrade.build_level(src, tmp_path / "out" / "level_2", 2, seed=7)
    assert n == 2
    out = tmp_path / "out" / "level_2"
    assert (out / "documents.json").is_file() and (out / "reference_results.json").is_file()
    results, meta, ref = run_batch.run("ocr", "png", out, cache_dir=tmp_path / "c", quiet=True)
    assert len(results["documents"]) == 2 and run_batch.check_format(results) == []


# ---------------------------------------------------------------- PDF-проба

def make_text_pdf(text):
    stream = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for i, obj in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{obj}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return out


def test_pdf_probe_sees_text_layer_and_image_only(tmp_path):
    with_text = tmp_path / "text.pdf"
    with_text.write_bytes(make_text_pdf("Hello certificate number 12345 issued to student Ivanov at the university of Test"))
    info = pdf_text_probe.inspect_pdf(with_text)
    assert info["pages"] == 1 and info["chars"] >= pdf_text_probe.MIN_CHARS
    assert "12345" in info["text"]

    scan = tmp_path / "scan.pdf"
    Image.new("RGB", (300, 200), "white").save(scan, "PDF", resolution=72)
    info = pdf_text_probe.inspect_pdf(scan)
    assert info["chars"] == 0 and info["image_objects"] >= 1


def test_dump_text_writes_utf8_per_document(tmp_path, fake_ocr):
    data = make_data(tmp_path / "d")
    dump = tmp_path / "txt"
    kwargs = dict(reference=str(REFERENCE), questions=str(QUESTIONS), cache_dir=tmp_path / "c", quiet=True, dump_dir=dump)
    run_batch.run("ocr", "png", data, **kwargs)
    assert (dump / "open-001.txt").read_text(encoding="utf-8").startswith("СПРАВКА ОБ ОБУЧЕНИИ")
    for f in dump.iterdir():
        f.unlink()
    run_batch.run("ocr", "png", data, **kwargs)  # из кэша тоже пишет
    assert fake_ocr.calls == 2 and (dump / "open-011.txt").is_file()


def test_pdf_probe_dump_file(tmp_path):
    data = tmp_path / "open"
    (data / "documents").mkdir(parents=True)
    (data / "documents" / "open-001.pdf").write_bytes(make_text_pdf("Hello certificate number 12345 for student at the university of Test"))
    out = tmp_path / "layer.txt"
    pdf_text_probe.main(["--data", str(data), "--reference", str(REFERENCE), "--dump", str(out)])
    assert out.read_text(encoding="utf-8").startswith("=== open-001 (study_certificate) ===")
