"""Поля документа: плоский словарь, без моделей."""
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from backend.ocr.fields import MISSING, pick_fields
from backend.pipeline import answer_question, extract_fields

STUDY_ROWS = [
    "СПРАВКА ОБ ОБУЧЕНИИ",
    "Выдана Иванову Ивану Петровичу",
    "в том, что он обучался в Южном университете",
    "Направление подготовки: 38.03.01 Прикладная информатика",
    "Форма обучения: очная",
    "Период обучения: 01.09.2023 - 30.06.2025",
    "Номер справки: ОБ-1542 от 12.07.2025",
]

LEAVE_ROWS = [
    "Заявление",
    "Я, Соколов Олег Николаевич, студент группы ЖР-25-1, 3 курс",
    "Прошу академический отпуск по состоянию здоровья",
    "с 01.11.2026 по 31.08.2027",
    "Дата заявления: 07.10.2026",
]

PRACTICE_ROWS = [
    "Справка о прохождении практики",
    "Студент Данилов Олег Алексеевич",
    "Организация: Учебная организация «Спектр»",
    "Срок практики: 01.06.2026 - 15.07.2026",
    "Руководитель практики: Ильина Елена Андреевна",
    "Оценка: удовлетворительно",
    "Номер: ПР-2021 от 18.07.2026",
]


def ocr(rows: list[str]) -> dict:
    return {"text": "\n".join(rows), "pages": [{"text": "\n".join(rows), "lines": []}]}


def assert_flat(fields: dict) -> None:
    assert fields
    for key, value in fields.items():
        assert type(key) is str
        assert type(value) in (str, bool)
        assert value is not None


def test_study_certificate_matches_contract():
    fields = pick_fields("study_certificate", ocr(STUDY_ROWS), [])
    assert_flat(fields)
    assert fields == {
        "student_name": "Иванов Иван Петрович",
        "university": "Южном университете",
        "program": "38.03.01 Прикладная информатика",
        "study_form": "очная",
        "study_start": "2023-09-01",
        "study_end": "2025-06-30",
        "document_number": "ОБ-1542",
        "issue_date": "2025-07-12",
        "signature_present": False,
        "seal_present": False,
    }


def test_academic_leave_course_is_string():
    fields = pick_fields("academic_leave", ocr(LEAVE_ROWS), [])
    assert_flat(fields)
    assert fields["student_name"] == "Соколов Олег Николаевич"
    assert fields["group"] == "ЖР-25-1"
    assert fields["course"] == "3" and isinstance(fields["course"], str)
    assert fields["leave_reason"] == "по состоянию здоровья"
    assert fields["leave_start"] == "2026-11-01"
    assert fields["leave_end"] == "2027-08-31"
    assert fields["application_date"] == "2026-10-07"
    assert fields["signature_present"] is False
    assert "seal_present" not in fields


def test_practice_certificate_and_alias():
    expected = {
        "student_name": "Данилов Олег Алексеевич",
        "organization": "Учебная организация «Спектр»",
        "internship_start": "2026-06-01",
        "internship_end": "2026-07-15",
        "supervisor_name": "Ильина Елена Андреевна",
        "grade": "удовлетворительно",
        "document_number": "ПР-2021",
        "issue_date": "2026-07-18",
        "signature_present": False,
        "seal_present": False,
    }
    assert pick_fields("practice_certificate", ocr(PRACTICE_ROWS), []) == expected
    assert pick_fields("internship_certificate", ocr(PRACTICE_ROWS), []) == expected


def test_missing_fields_are_text_not_none():
    fields = pick_fields("academic_leave_application", ocr(["Заявление"]), [])
    assert_flat(fields)
    assert fields["student_name"] == MISSING
    assert fields["course"] == MISSING
    assert fields["leave_start"] == MISSING


def test_unknown_type_raises():
    with pytest.raises(Exception, match="Неизвестный тип"):
        pick_fields("passport", ocr(["текст"]), [])


def test_stamp_and_signature_are_bools():
    image = Image.new("RGB", (400, 500), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 40, 300, 80), fill="black")
    draw.ellipse((250, 80, 340, 170), fill=(180, 20, 20))
    draw.line((140, 400, 210, 445), fill="black", width=3)
    draw.line((210, 445, 155, 478), fill="black", width=3)
    pages = [{
        "text": "Справка",
        "lines": [
            {"text": "Справка", "bbox": [40, 40, 260, 40]},
            {"text": "Подпись", "bbox": [30, 400, 80, 22]},
        ],
    }]
    fields = pick_fields("study_certificate", {"pages": pages}, [image])
    assert fields["signature_present"] is True
    assert fields["seal_present"] is True


def test_round_ink_stamp_is_caught_and_pen_lines_are_not():
    from backend.ocr.fields import find_seals

    ring = Image.new("RGB", (900, 700), "white")
    draw = ImageDraw.Draw(ring)
    draw.rectangle((40, 40, 500, 80), fill="black")
    draw.ellipse((560, 420, 760, 620), outline=(25, 70, 170), width=7)
    draw.ellipse((600, 460, 720, 580), outline=(25, 70, 170), width=4)
    assert len(find_seals(ring)) == 1

    pen = Image.new("RGB", (900, 700), "white")
    draw = ImageDraw.Draw(pen)
    for y in range(80, 500, 36):
        draw.line((40, y, 820, y + 8), fill=(20, 60, 160), width=3)
    assert find_seals(pen) == []

    faded = Image.new("RGB", (900, 700), (245, 245, 245))
    draw = ImageDraw.Draw(faded)
    draw.ellipse((500, 360, 700, 560), outline=(90, 120, 170), width=8)
    assert find_seals(faded)

    pages = [{"text": "Справка", "lines": []}]
    assert pick_fields("study_certificate", {"pages": pages}, [ring])["seal_present"] is True
    assert pick_fields("study_certificate", {"pages": pages}, [pen])["seal_present"] is False


def test_stamp_on_tilted_photo_is_one_seal():
    path = Path("data/samples/spravka_bad.jpg")
    if not path.is_file():
        pytest.skip("нет примера справки")
    from backend.ocr.fields import find_seals

    photo = Image.open(path).convert("RGB")
    assert find_seals(photo) == []
    stamped = photo.copy()
    draw = ImageDraw.Draw(stamped)
    draw.ellipse((700, 360, 880, 540), outline=(30, 75, 180), width=8)
    draw.ellipse((745, 405, 835, 495), outline=(30, 75, 180), width=5)
    assert len(find_seals(stamped)) == 1
    pages = [{"text": "Справка", "lines": []}]
    assert pick_fields("study_certificate", {"pages": pages}, [stamped])["seal_present"] is True


def test_extract_fields_returns_flat_dict(monkeypatch, tmp_path):
    photo = tmp_path / "doc.jpg"
    Image.new("RGB", (20, 20), "white").save(photo)

    def fake_ocr(path):
        assert str(path) == str(photo)
        return ocr(STUDY_ROWS)

    class Page:
        image = Image.new("RGB", (20, 20), "white")

    monkeypatch.setattr("backend.ocr.run_ocr", fake_ocr)
    monkeypatch.setattr("backend.ocr.intake.load_document", lambda path: ("jpeg", [Page()]))
    fields = extract_fields(str(photo), "study_certificate")
    assert_flat(fields)
    assert fields["student_name"] == "Иванов Иван Петрович"
    assert fields["study_start"] == "2023-09-01"


def test_answer_question_keeps_the_handoff_shape():
    fields = {"student_name": "Иванов", "issue_date": "не найдено", "seal_present": False}
    result = answer_question(fields, "study_certificate", "Содержит ли документ все обязательные сведения?")
    assert set(result) == {"status", "message", "sources", "answerable", "value", "missing_fields"}
    assert result["status"] in {"ok", "missing", "no_answer"}
    assert isinstance(result["message"], str) and result["message"]
    assert isinstance(result["sources"], list) and all(isinstance(item, str) for item in result["sources"])
    assert isinstance(result["answerable"], bool)
    assert isinstance(result["value"], str)
    assert isinstance(result["missing_fields"], list)
    assert all(isinstance(s, str) for s in result["missing_fields"])


STUDY_TEMPLATE = [
    "СПРАВКА ОБ ОБУЧЕНИИ",
    "ФИО студента: Александров Артём Игоревич",
    "Название вуза: Учебный университет «Меридиан»",
    "Направление подготовки: 38.03.01 Экономика",
    "Форма обучения: очная",
    "Начало периода обучения: 01.09.2023",
    "Окончание периода обучения: 31.08.2026",
    "Номер справки: ОБ-1001",
    "Дата выдачи: 01.09.2026",
]
STUDY_EXPECTED = {
    "student_name": "Александров Артём Игоревич",
    "university": "Учебный университет «Меридиан»",
    "program": "38.03.01 Экономика",
    "study_form": "очная",
    "study_start": "2023-09-01",
    "study_end": "2026-08-31",
    "document_number": "ОБ-1001",
    "issue_date": "2026-09-01",
    "signature_present": False,
    "seal_present": False,
}
LEAVE_TEMPLATE = [
    "Заявление на академический отпуск",
    "ФИО студента: Соколов Олег Николаевич",
    "Учебная группа: ЖР-25-1",
    "Курс: 3",
    "Причина отпуска: по состоянию здоровья",
    "Дата начала отпуска: 01.11.2026",
    "Дата окончания отпуска: 31.08.2027",
    "Дата заявления: 07.10.2026",
]
LEAVE_EXPECTED = {
    "student_name": "Соколов Олег Николаевич",
    "group": "ЖР-25-1",
    "course": "3",
    "leave_reason": "по состоянию здоровья",
    "leave_start": "2026-11-01",
    "leave_end": "2027-08-31",
    "application_date": "2026-10-07",
    "signature_present": False,
}
PRACTICE_TEMPLATE = [
    "Справка о прохождении практики",
    "ФИО студента: Данилов Олег Алексеевич",
    "Название организации: Учебная организация «Спектр»",
    "Дата начала практики: 01.06.2026",
    "Дата окончания практики: 15.07.2026",
    "ФИО руководителя практики: Ильина Елена Андреевна",
    "Оценка: удовлетворительно",
    "Номер справки: ПР-2021",
    "Дата выдачи: 18.07.2026",
]
PRACTICE_EXPECTED = {
    "student_name": "Данилов Олег Алексеевич",
    "organization": "Учебная организация «Спектр»",
    "internship_start": "2026-06-01",
    "internship_end": "2026-07-15",
    "supervisor_name": "Ильина Елена Андреевна",
    "grade": "удовлетворительно",
    "document_number": "ПР-2021",
    "issue_date": "2026-07-18",
    "signature_present": False,
    "seal_present": False,
}


def _blank(rows: list[str], prefix: str) -> list[str]:
    return [prefix if row.startswith(prefix) else row for row in rows]


def test_official_templates_and_erasure():
    cases = (
        ("study_certificate", STUDY_TEMPLATE, STUDY_EXPECTED, {
            "student_name": "ФИО студента:",
            "university": "Название вуза:",
            "program": "Направление подготовки:",
            "study_form": "Форма обучения:",
            "study_start": "Начало периода обучения:",
            "study_end": "Окончание периода обучения:",
            "document_number": "Номер справки:",
            "issue_date": "Дата выдачи:",
        }),
        ("academic_leave_application", LEAVE_TEMPLATE, LEAVE_EXPECTED, {
            "student_name": "ФИО студента:",
            "group": "Учебная группа:",
            "course": "Курс:",
            "leave_reason": "Причина отпуска:",
            "leave_start": "Дата начала отпуска:",
            "leave_end": "Дата окончания отпуска:",
            "application_date": "Дата заявления:",
        }),
        ("internship_certificate", PRACTICE_TEMPLATE, PRACTICE_EXPECTED, {
            "student_name": "ФИО студента:",
            "organization": "Название организации:",
            "internship_start": "Дата начала практики:",
            "internship_end": "Дата окончания практики:",
            "supervisor_name": "ФИО руководителя практики:",
            "grade": "Оценка:",
            "document_number": "Номер справки:",
            "issue_date": "Дата выдачи:",
        }),
    )
    for doc_type, rows, expected, blanks in cases:
        full = pick_fields(doc_type, ocr(rows), [])
        assert_flat(full)
        assert full == expected
        for key, prefix in blanks.items():
            erased = pick_fields(doc_type, ocr(_blank(rows, prefix)), [])
            assert erased[key] == MISSING, key
            for other, value in expected.items():
                if other != key:
                    assert erased[other] == value, (key, other)


def test_empty_label_does_not_steal_the_next_line():
    rows = [
        "Направление подготовки:",
        "Форма обучения: очная",
        "Номер справки:",
        "Начало периода обучения: 01.09.2023",
        "Дата выдачи: 01.09.2026",
    ]
    fields = pick_fields("study_certificate", ocr(rows), [])
    assert fields["program"] == MISSING
    assert fields["study_form"] == "очная"
    assert fields["document_number"] == MISSING
    assert fields["study_start"] == "2023-09-01"
    assert fields["study_end"] == MISSING
    assert fields["issue_date"] == "2026-09-01"


def test_number_must_match_prefix_and_fio_label_is_not_declined():
    stolen = pick_fields("study_certificate", ocr(["Номер справки: справки"]), [])
    assert stolen["document_number"] == MISSING
    bare = pick_fields("study_certificate", ocr(["Номер справки: 1542"]), [])
    assert bare["document_number"] == MISSING
    latin = pick_fields("internship_certificate", ocr(["Номер справки: PR-2021"]), [])
    assert latin["document_number"] == "ПР-2021"
    named = pick_fields(
        "study_certificate",
        ocr(["ФИО студента: Иванову Ивану Петровичу"]),
        [],
    )
    assert named["student_name"] == "Иванову Ивану Петровичу"
    issued = pick_fields("study_certificate", ocr(["Дата выдачи: 31.02.2026"]), [])
    assert issued["issue_date"] == MISSING
    form = pick_fields("study_certificate", ocr(["Форма обучения: вечерняя"]), [])
    assert form["study_form"] == "вечерняя"
    course = pick_fields("academic_leave_application", ocr(["Курс: 5"]), [])
    assert course["course"] == MISSING
    group = pick_fields("academic_leave_application", ocr(["Учебная группа: ПИ-21"]), [])
    assert group["group"] == MISSING


def test_rectangular_stamp_is_caught_and_leave_has_no_seal():
    from backend.ocr.marks import detect_marks, find_seals

    sheet = Image.new("RGB", (900, 700), "white")
    draw = ImageDraw.Draw(sheet)
    draw.rectangle((80, 80, 460, 280), outline=(20, 55, 160), width=10)
    assert len(find_seals(sheet)) == 1

    pages = [{"text": "Справка", "lines": []}]
    assert pick_fields("study_certificate", {"pages": pages}, [sheet])["seal_present"] is True
    leave = pick_fields("academic_leave_application", {"pages": pages}, [sheet])
    assert "seal_present" not in leave
    assert detect_marks([sheet], pages, "academic_leave_application") == (False, False)
    assert detect_marks([sheet], pages, "academic_leave")[1] is False


def test_signature_word_and_underline_are_not_a_mark():
    from backend.ocr.marks import detect_marks

    image = Image.new("RGB", (400, 500), "white")
    draw = ImageDraw.Draw(image)
    draw.line((120, 410, 320, 410), fill="black", width=2)
    pages = [{"text": "Подпись", "lines": [{"text": "Подпись", "bbox": [30, 400, 80, 22]}]}]
    assert detect_marks([image], pages, "study_certificate") == (False, False)

    loose = Image.new("RGB", (400, 500), "white")
    draw = ImageDraw.Draw(loose)
    draw.line((30, 420, 90, 450), fill="black", width=3)
    draw.line((90, 450, 40, 470), fill="black", width=3)
    no_word = [{"text": "Справка", "lines": [{"text": "Справка", "bbox": [40, 40, 200, 30]}]}]
    assert detect_marks([loose], no_word, "study_certificate")[0] is False
