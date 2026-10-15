"""
Поля документа для сайта: плоский словарь str -> str | bool.

Ключи фиксированы типом документа. Вложенных словарей, списков и None нет.
Чего нет на листе — строка «не найдено», печать и подпись — False.
Полный текст OCR сюда не кладётся: он остаётся в результате run_ocr.

Значение берём только из строки своей метки. Пустая метка не забирает
следующую строку, если та сама начинается с другой метки. Дату не угадываем
по порядку дат в документе: либо подпись «Дата начала…» / «Дата окончания…»,
либо пара дат на одной строке периода.
"""
import datetime
import re

from backend.ocr.marks import detect_marks
from backend.ocr.marks import find_seals as find_seals

MISSING = "не найдено"

# Имена с сайта и имена из ТЗ лида — один и тот же набор полей.
KINDS = {
    "study_certificate": "study",
    "academic_leave": "leave",
    "academic_leave_application": "leave",
    "practice_certificate": "practice",
    "internship_certificate": "practice",
}

MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

# Длинные метки раньше коротких: «дата начала практики» не равна «дата начала».
_LABELS = tuple(sorted({
    "фио руководителя практики",
    "фио студента",
    "название организации",
    "название вуза",
    "направление подготовки",
    "начало периода обучения",
    "окончание периода обучения",
    "дата начала практики",
    "дата окончания практики",
    "дата начала отпуска",
    "дата окончания отпуска",
    "дата начала обучения",
    "дата окончания обучения",
    "начало практики",
    "окончание практики",
    "начало отпуска",
    "окончание отпуска",
    "дата начала",
    "дата окончания",
    "номер справки",
    "номер документа",
    "руководитель практики",
    "причина отпуска",
    "форма обучения",
    "учебная группа",
    "дата выдачи",
    "дата заявления",
    "специальность",
    "организация",
    "направление",
    "фамилия",
    "оценка",
    "группа",
    "номер",
    "курс",
    "фио",
    "вуз",
}, key=len, reverse=True))

NAME = r"[А-ЯЁ][а-яё]+(?:[ \t]+[А-ЯЁ][а-яё]+){1,3}"
GROUP = re.compile(r"(?<![А-Яа-яЁёA-Za-z0-9])([А-ЯЁ]{1,8}-\d{2}-\d)(?!\d)")
NUMBER = re.compile(r"(ОБ|ПР|OB|PR|NP)\s*[-–—]\s*(\d+)", flags=re.IGNORECASE)
REASONS = (
    "по состоянию здоровья",
    "по семейным обстоятельствам",
    "по уходу за ребенком",
    "по уходу за ребёнком",
    "в связи с призывом",
)
GRADES = ("отлично", "хорошо", "удовлетворительно", "зачтено", "неудовлетворительно")
FORMS = (
    ("очно-заоч", "очно-заочная"),
    ("заоч", "заочная"),
    ("очн", "очная"),
)


def pick_fields(doc_type: str, ocr: dict, images: list) -> dict:
    kind = KINDS.get(doc_type)
    if kind is None:
        raise Exception(f"Неизвестный тип документа: {doc_type}")

    rows = []
    for page in ocr.get("pages", []):
        rows.extend(line for line in page.get("text", "").split("\n") if line.strip())
    blob = "\n".join(rows)
    signed, sealed = detect_marks(images, ocr.get("pages", []), doc_type)

    if kind == "study":
        return _study(rows, blob, signed, sealed)
    if kind == "leave":
        return _leave(rows, blob, signed)
    return _practice(rows, blob, signed, sealed)


def _study(rows: list[str], blob: str, signed: bool, sealed: bool) -> dict:
    start, end = _span(
        rows,
        ("начало периода обучения", "дата начала обучения", "дата начала"),
        ("окончание периода обучения", "дата окончания обучения", "дата окончания"),
        ("период обучения", "срок обучения"),
    )
    return {
        "student_name": _name(rows, blob) or MISSING,
        "university": _university(rows, blob) or MISSING,
        "program": _labeled(rows, ("направление подготовки", "направление", "специальность")) or MISSING,
        "study_form": _form(rows, blob) or MISSING,
        "study_start": start or MISSING,
        "study_end": end or MISSING,
        "document_number": _document_number(rows) or MISSING,
        "issue_date": _issue_date(rows) or MISSING,
        "signature_present": signed,
        "seal_present": sealed,
    }


def _leave(rows: list[str], blob: str, signed: bool) -> dict:
    start, end = _span(
        rows,
        ("дата начала отпуска", "начало отпуска", "дата начала"),
        ("дата окончания отпуска", "окончание отпуска", "дата окончания"),
        ("срок отпуска", "период отпуска"),
    )
    return {
        "student_name": _name(rows, blob) or MISSING,
        "group": _group(rows, blob) or MISSING,
        "course": _course(rows, blob) or MISSING,
        "leave_reason": _reason(rows, blob) or MISSING,
        "leave_start": start or MISSING,
        "leave_end": end or MISSING,
        "application_date": _date_by_label(rows, ("дата заявления",)) or MISSING,
        "signature_present": signed,
    }


def _practice(rows: list[str], blob: str, signed: bool, sealed: bool) -> dict:
    start, end = _span(
        rows,
        ("дата начала практики", "начало практики", "дата начала"),
        ("дата окончания практики", "окончание практики", "дата окончания"),
        ("срок практики", "период практики"),
    )
    return {
        "student_name": _name(rows, blob) or MISSING,
        "organization": _labeled(rows, ("название организации", "организация")) or MISSING,
        "internship_start": start or MISSING,
        "internship_end": end or MISSING,
        "supervisor_name": _person(rows, ("фио руководителя практики", "руководитель практики", "руководитель")) or MISSING,
        "grade": _grade(rows) or MISSING,
        "document_number": _document_number(rows) or MISSING,
        "issue_date": _issue_date(rows) or MISSING,
        "signature_present": signed,
        "seal_present": sealed,
    }


def _split_label(row: str) -> tuple[str, str] | None:
    low = row.lower().strip()
    for label in _LABELS:
        if not low.startswith(label):
            continue
        rest = row.strip()[len(label):]
        if rest[:1] not in ("", " ", ":", "-", "–", "—", "."):
            continue
        return label, rest.lstrip(" \t:.-–—").strip()
    return None


def _labeled(rows: list[str], labels: tuple[str, ...], accept=None) -> str | None:
    """Хвост своей метки. Следующую строку берём, только если это не другая метка."""
    if accept is None:
        accept = _plain
    wanted = set(labels)
    for index, row in enumerate(rows):
        split = _split_label(row)
        if split is None or split[0] not in wanted:
            continue
        tail = split[1]
        if not tail and index + 1 < len(rows) and _split_label(rows[index + 1]) is None:
            tail = rows[index + 1].strip()
        if not tail or _split_label(tail) is not None:
            continue
        cleaned = accept(tail)
        if cleaned:
            return cleaned
    return None


def _plain(tail: str) -> str | None:
    text = tail.strip(" .")
    if not text or _split_label(text) is not None:
        return None
    return text


def _name(rows: list[str], blob: str) -> str | None:
    # Подпись «ФИО» уже в именительном. Склоняем только «Выдана Иванову…».
    labeled = _person(rows, ("фио студента", "фамилия"))
    if labeled:
        return labeled
    for index, row in enumerate(rows):
        split = _split_label(row)
        if split is None or split[0] != "фио":
            continue
        tail = split[1]
        if not tail and index + 1 < len(rows) and _split_label(rows[index + 1]) is None:
            tail = rows[index + 1].strip()
        person = _person_in(tail or "")
        if person:
            return person
    for pattern in (
        rf"(?:^|\n)\s*[Яя]\s*,\s*({NAME})",
        rf"(?:[Вв]ыдан[аоы]?|[Сс]тудент[уа]?)\s+({NAME})",
    ):
        found = re.search(pattern, blob)
        if found:
            return _nominative_phrase(found.group(1))
    return None


def _person(rows: list[str], labels: tuple[str, ...]) -> str | None:
    return _labeled(rows, labels, accept=_person_in)


def _person_in(tail: str) -> str | None:
    found = re.search(NAME, tail)
    return found.group(0) if found else None


def _nominative_phrase(phrase: str) -> str:
    return " ".join(_nominative(word) for word in phrase.split())


def _nominative(word: str) -> str:
    low = word.lower().replace("ё", "е")
    pairs = (
        ("овичу", "ович"),
        ("евичу", "евич"),
        ("овне", "овна"),
        ("евне", "евна"),
        ("ову", "ов"),
        ("еву", "ев"),
        ("ину", "ин"),
        ("ыну", "ын"),
        ("ею", "ей"),
        ("ию", "ий"),
        ("аю", "ай"),
    )
    for src, dst in pairs:
        if low.endswith(src) and len(low) > len(src) + 1:
            low = low[: -len(src)] + dst
            return low[:1].upper() + low[1:]
    if len(low) > 3 and low.endswith("у") and low[-2] not in "аеиоуыэюя":
        low = low[:-1]
        return low[:1].upper() + low[1:]
    return word


def _university(rows: list[str], blob: str) -> str | None:
    labeled = _labeled(rows, ("название вуза", "вуз"))
    if labeled:
        return labeled
    stop = {"в", "во", "на", "и", "что", "он", "она", "они", "обучался", "обучалась", "обучается"}
    for row in blob.split("\n"):
        if _split_label(row) is not None:
            continue
        found = re.search(r"(?:университет|институт|академи)\w*", row, flags=re.IGNORECASE)
        if not found:
            continue
        prefix = []
        for word in reversed(row[: found.start()].split()):
            bare = word.strip(".,").lower()
            if not bare or bare in stop:
                break
            prefix.append(word.strip(".,"))
            if len(prefix) == 4:
                break
        prefix.reverse()
        tail = re.match(r"\w+(?:\s+«[^»]+»)?", row[found.start():])
        title = tail.group(0) if tail else found.group(0)
        return " ".join(prefix + [title]).strip(" .,")
    return None


def _form(rows: list[str], blob: str) -> str | None:
    labeled = _labeled(rows, ("форма обучения",), accept=_form_word)
    if labeled:
        return labeled
    return _form_word(blob)


def _form_word(text: str) -> str | None:
    low = text.lower()
    for prefix, canonical in FORMS:
        if prefix in low:
            return canonical
    return None


def _group(rows: list[str], blob: str) -> str | None:
    labeled = _labeled(rows, ("учебная группа", "группа"), accept=_group_in)
    if labeled:
        return labeled
    return _group_in(blob)


def _group_in(text: str) -> str | None:
    found = GROUP.search(text)
    return found.group(1) if found else None


def _course(rows: list[str], blob: str) -> str | None:
    labeled = _labeled(rows, ("курс",), accept=_course_in)
    if labeled:
        return labeled
    for row in blob.split("\n"):
        found = re.search(r"(?<!\d)([1-4])[ \t]*курс", row, flags=re.IGNORECASE)
        if found:
            return found.group(1)
    return None


def _course_in(text: str) -> str | None:
    found = re.fullmatch(r"([1-4])(?:[ \t]*курс)?", text.strip(), flags=re.IGNORECASE)
    return found.group(1) if found else None


def _reason(rows: list[str], blob: str) -> str | None:
    labeled = _labeled(rows, ("причина отпуска", "причина"), accept=_reason_in)
    if labeled:
        return labeled
    return _reason_in(blob)


def _reason_in(text: str) -> str | None:
    low = text.lower().replace("ё", "е")
    for phrase in REASONS:
        if phrase.replace("ё", "е") in low:
            return phrase.replace("ё", "е")
    return None


def _grade(rows: list[str]) -> str | None:
    def accept(tail: str) -> str | None:
        low = tail.lower()
        for grade in GRADES:
            if grade in low:
                return grade
        return None

    return _labeled(rows, ("оценка",), accept=accept)


def _document_number(rows: list[str]) -> str | None:
    for row in rows:
        split = _split_label(row)
        on_number_line = split is not None and split[0] in {"номер справки", "номер документа", "номер"}
        if not on_number_line and not re.search(r"номер|№", row, flags=re.IGNORECASE):
            continue
        found = NUMBER.search(row)
        if not found:
            continue
        prefix = found.group(1).upper()
        prefix = {"OB": "ОБ", "PR": "ПР", "NP": "ПР"}.get(prefix, prefix)
        if prefix not in {"ОБ", "ПР"}:
            continue
        return f"{prefix}-{found.group(2)}"
    return None


def _issue_date(rows: list[str]) -> str | None:
    labeled = _date_by_label(rows, ("дата выдачи",))
    if labeled:
        return labeled
    for row in rows:
        if not re.search(r"номер|№", row, flags=re.IGNORECASE):
            continue
        after = re.search(
            r"\bот\s+(\d{1,2}[./]\d{1,2}[./]\d{4}|\d{1,2}\s+[А-Яа-яЁё]+\s+\d{4})",
            row,
            flags=re.IGNORECASE,
        )
        if not after:
            continue
        parsed = _iso_dates(after.group(1))
        if parsed:
            return parsed[0]
    return None


def _span(
    rows: list[str],
    start_labels: tuple[str, ...],
    end_labels: tuple[str, ...],
    pair_hints: tuple[str, ...],
) -> tuple[str | None, str | None]:
    start = _date_by_label(rows, start_labels)
    end = _date_by_label(rows, end_labels)
    if start and end:
        return start, end
    pair_start, pair_end = _pair(rows, pair_hints)
    return start or pair_start, end or pair_end


def _date_by_label(rows: list[str], labels: tuple[str, ...]) -> str | None:
    for label in labels:
        for index, row in enumerate(rows):
            split = _split_label(row)
            if split is None or split[0] != label:
                continue
            tail = split[1]
            if not tail and index + 1 < len(rows) and _split_label(rows[index + 1]) is None:
                tail = rows[index + 1].strip()
            if re.search(r"\d", tail or "") and not _iso_dates(tail or ""):
                return None
            parsed = _iso_dates(tail or "")
            if parsed:
                return parsed[0]
    return None


def _pair(rows: list[str], hints: tuple[str, ...]) -> tuple[str | None, str | None]:
    """Вторая ступень: две даты на одной строке периода, не по порядку листа."""
    for row in rows:
        low = row.lower()
        hinted = any(hint in low for hint in hints) or re.search(r"\bс\b.+\bпо\b", low)
        if not hinted:
            continue
        dates = _iso_dates(row)
        if len(dates) >= 2:
            return dates[0], dates[1]
    return None, None


def _iso_dates(text: str) -> list[str]:
    found = []
    numeric = re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](\d{4})(?:\s*г\.?)?")
    iso = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
    words = re.compile(
        r"\b(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+(\d{4})",
        flags=re.IGNORECASE,
    )
    for match in numeric.finditer(text):
        day, month, year = (int(part) for part in match.groups())
        value = _calendar(year, month, day)
        if value:
            found.append((match.start(), value))
    for match in iso.finditer(text):
        year, month, day = (int(part) for part in match.groups())
        value = _calendar(year, month, day)
        if value:
            found.append((match.start(), value))
    for match in words.finditer(text):
        day = int(match.group(1))
        month = MONTHS[match.group(2).lower()]
        year = int(match.group(3))
        value = _calendar(year, month, day)
        if value:
            found.append((match.start(), value))
    found.sort(key=lambda item: item[0])
    ordered = []
    for _, value in found:
        if value not in ordered:
            ordered.append(value)
    return ordered


def _calendar(year: int, month: int, day: int) -> str | None:
    try:
        datetime.date(year, month, day)
    except ValueError:
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"
