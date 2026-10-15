"""Наброски: нормализация, выключенный TrOCR, порча снимка."""
import os

from PIL import Image, ImageDraw

from backend.ocr.fields import MISSING, pick_fields
from backend.ocr.handwriting import enabled, reread
from backend.ocr.normalize import fix_digits, parse_dates
from backend.ocr.spoil import field_recall, spoil
from tests.test_fields import ocr


def test_dates_words_quotes_and_short_year():
    assert parse_dates("1 сентября 2026 года") == ["2026-09-01"]
    assert parse_dates("01.09.2026") == ["2026-09-01"]
    assert parse_dates("«15» сентября 2026") == ["2026-09-15"]
    assert parse_dates("01.09.26") == ["2026-09-01"]
    assert parse_dates("31.02.2026") == []
    assert parse_dates("2026 сентября") == []


def test_digit_lookalikes_stay_out_of_words():
    assert fix_digits("O1.O9.2O26") == "01.09.2026"
    assert fix_digits("О8.12.2022") == "08.12.2022"
    assert fix_digits("5о0") == "500"
    assert fix_digits("1оо0") == "1000"
    assert fix_digits("б0%") == "60%"
    assert fix_digits("1.l.") == "1.1."
    assert fix_digits("125Омм") == "1250мм"
    assert fix_digits("Del1") == "Del1"
    assert fix_digits("ОБ-1001") == "ОБ-1001"
    assert fix_digits("Ряз004633") == "Ряз004633"
    assert fix_digits("И.О.:") == "И.О.:"
    assert fix_digits("г.о.") == "г.о."
    assert fix_digits("M1I") == "M1I"
    assert fix_digits("90о") == "900"
    assert fix_digits("О0О") == "О0О"
    assert fix_digits("ПриказУ0от") == "ПриказУ0от"
    assert fix_digits("Иванов") == "Иванов"
    assert fix_digits("по состоянию здоровья") == "по состоянию здоровья"
    assert parse_dates("O1.O9.2O26") == ["2026-09-01"]


def test_closed_set_keeps_raw_text_and_fuzzy_label():
    form = pick_fields("study_certificate", ocr(["Форма обучения: очнвя"]), [])
    assert form["study_form"] == "очная"
    odd = pick_fields("study_certificate", ocr(["Форма обучения: вечерняя"]), [])
    assert odd["study_form"] == "вечерняя"
    grade = pick_fields("internship_certificate", ocr(["Оценка: хор"]), [])
    assert grade["grade"] == "хор"
    reason = pick_fields("academic_leave_application", ocr(["Причина отпуска: уехал к бабушке"]), [])
    assert reason["leave_reason"] == "уехал к бабушке"
    known = pick_fields("academic_leave_application", ocr(["Причина: по состоянию здоровья"]), [])
    assert known["leave_reason"] == "по состоянию здоровья"
    issued = pick_fields("study_certificate", ocr(["Дата вьцачи: 01.09.2026"]), [])
    assert issued["issue_date"] == "2026-09-01"
    assert issued["student_name"] == MISSING


def test_number_prefix_follows_document_type():
    study = pick_fields("study_certificate", ocr(["Номер справки: OB-1OO1"]), [])
    assert study["document_number"] == "ОБ-1001"
    practice = pick_fields("internship_certificate", ocr(["Номер справки: NP-2021"]), [])
    assert practice["document_number"] == "ПР-2021"
    wrong = pick_fields("study_certificate", ocr(["Номер справки: ПР-2021"]), [])
    assert wrong["document_number"] == MISSING


def test_inverted_period_drops_the_end():
    fields = pick_fields(
        "academic_leave_application",
        ocr([
            "Дата начала отпуска: 31.08.2027",
            "Дата окончания отпуска: 01.11.2026",
        ]),
        [],
    )
    assert fields["leave_start"] == "2027-08-31"
    assert fields["leave_end"] == MISSING


def test_handwriting_is_off_until_asked(monkeypatch):
    monkeypatch.delenv("USE_HANDWRITING", raising=False)
    assert enabled() is False
    monkeypatch.setenv("USE_HANDWRITING", "1")
    assert enabled() is True
    os.environ.pop("USE_HANDWRITING", None)


def test_handwriting_rejects_latin_and_stops_after_the_limit():
    image = Image.new("RGB", (200, 80), "white")
    box = [[10, 10], [80, 10], [80, 30], [10, 30]]
    kept = reread(
        image,
        [{"text": "01.09.2026", "confidence": 0.2, "polygon": box}],
        reader=lambda crop: "asdfgh",
    )
    assert kept[0]["text"] == "01.09.2026" and kept[0]["source"] == "paddle"

    calls = {"n": 0}

    def reader(crop):
        calls["n"] += 1
        return "по семейным обстоятельствам"

    lines = [
        {"text": f"qwe{index}", "confidence": 0.1, "polygon": box}
        for index in range(10)
    ]
    out = reread(image, lines, reader=reader)
    assert calls["n"] == 8
    assert all(line["source"] == "trocr" for line in out[:8])
    assert out[8]["source"] == "paddle" and out[9]["source"] == "paddle"

    calls["n"] = 0
    ordered = [{"text": "qhigh", "confidence": 0.45, "polygon": box}]
    ordered += [{"text": f"q{index}", "confidence": 0.05, "polygon": box} for index in range(8)]
    ranked = reread(image, ordered, reader=reader)
    assert ranked[0]["source"] == "paddle"
    assert all(line["source"] == "trocr" for line in ranked[1:])

    def refuse(crop):
        calls["n"] += 1
        return "ерунда"

    russian = [{"text": "отпуск по семейным", "confidence": 0.1, "polygon": box}]
    skipped = reread(image, russian, reader=refuse)
    assert calls["n"] == 8
    assert skipped[0]["source"] == "paddle" and skipped[0]["text"] == "отпуск по семейным"


def test_spoil_changes_the_photo_and_recall_counts_matches():
    image = Image.new("RGB", (80, 120), "white")
    ImageDraw.Draw(image).rectangle((10, 10, 40, 70), fill="black")
    damaged = spoil(image, turn=18, blur=1.4, scale=0.5, shadow=0.4)
    assert damaged.mode == "RGB"
    assert damaged.size != image.size
    assert field_recall({"a": "1", "b": "2"}, {"a": "1", "b": "нет"}) == 0.5
