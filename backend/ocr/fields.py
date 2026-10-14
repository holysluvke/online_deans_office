"""
Поля документа для сайта: плоский словарь str -> str | bool.

Ключи фиксированы типом документа. Вложенных словарей, списков и None нет.
Чего нет на листе — строка «не найдено», печать и подпись — False.
Полный текст OCR сюда не кладётся: он остаётся в результате run_ocr.
"""
import re

import numpy as np

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

NAME = r"[А-ЯЁ][а-яё]+(?:[ \t]+[А-ЯЁ][а-яё]+){1,3}"
REASONS = (
    "по состоянию здоровья",
    "по семейным обстоятельствам",
    "по уходу за ребенком",
    "по уходу за ребёнком",
    "в связи с призывом",
)
GRADES = ("отлично", "хорошо", "удовлетворительно", "зачтено", "неудовлетворительно")


def pick_fields(doc_type: str, ocr: dict, images: list) -> dict:
    kind = KINDS.get(doc_type)
    if kind is None:
        raise Exception(f"Неизвестный тип документа: {doc_type}")

    rows = []
    for page in ocr.get("pages", []):
        rows.extend(line for line in page.get("text", "").split("\n") if line.strip())
    blob = "\n".join(rows)
    signed, sealed = _marks(images, ocr.get("pages", []))

    if kind == "study":
        return _study(rows, blob, signed, sealed)
    if kind == "leave":
        return _leave(rows, blob, signed)
    return _practice(rows, blob, signed, sealed)


def _study(rows: list[str], blob: str, signed: bool, sealed: bool) -> dict:
    start, end = _period(rows, ("период", "срок обучения", "обучен"))
    number, issued = _number_and_issue(rows, blob)
    return {
        "student_name": _name(rows, blob) or MISSING,
        "university": _university(blob) or MISSING,
        "program": _labeled(rows, r"направлен\w*(?:\s+подготовки)?|специальност\w*|программ\w*") or MISSING,
        "study_form": _form(blob) or MISSING,
        "study_start": start or MISSING,
        "study_end": end or MISSING,
        "document_number": number or MISSING,
        "issue_date": issued or MISSING,
        "signature_present": signed,
        "seal_present": sealed,
    }


def _leave(rows: list[str], blob: str, signed: bool) -> dict:
    start, end = _period(rows, ("отпуск", "прошу", "с "))
    return {
        "student_name": _name(rows, blob) or MISSING,
        "group": _group(blob) or MISSING,
        "course": _course(blob) or MISSING,
        "leave_reason": _reason(blob) or MISSING,
        "leave_start": start or MISSING,
        "leave_end": end or MISSING,
        "application_date": _application_date(rows, start, end) or MISSING,
        "signature_present": signed,
    }


def _practice(rows: list[str], blob: str, signed: bool, sealed: bool) -> dict:
    start, end = _period(rows, ("практик", "срок", "период"))
    number, issued = _number_and_issue(rows, blob)
    return {
        "student_name": _name(rows, blob) or MISSING,
        "organization": _labeled(rows, r"организац\w*|предприят\w*|учрежден\w*") or MISSING,
        "internship_start": start or MISSING,
        "internship_end": end or MISSING,
        "supervisor_name": _labeled(rows, r"руководител\w*(?:\s+практик\w*)?") or MISSING,
        "grade": _grade(blob) or MISSING,
        "document_number": number or MISSING,
        "issue_date": issued or MISSING,
        "signature_present": signed,
        "seal_present": sealed,
    }


def _name(rows: list[str], blob: str) -> str | None:
    labeled = _labeled(rows, r"фио|фамилия(?:\s*,\s*имя(?:\s*,\s*отчество)?)?")
    if labeled:
        found = re.search(NAME, labeled)
        if found:
            return _nominative_phrase(found.group(0))
    # Регистр в шаблоне имени важен: «студент группы» — это не ФИО.
    for pattern in (
        rf"(?:^|\n)\s*[Яя]\s*,\s*({NAME})",
        rf"(?:[Вв]ыдан[аоы]?|[Сс]тудент[уа]?)\s+({NAME})",
    ):
        found = re.search(pattern, blob)
        if found:
            return _nominative_phrase(found.group(1))
    return None


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


def _university(blob: str) -> str | None:
    stop = {"в", "во", "на", "и", "что", "он", "она", "они", "обучался", "обучалась", "обучается"}
    for row in blob.split("\n"):
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


def _form(blob: str) -> str | None:
    found = re.search(r"очно-заочн\w*|заочн\w*|очн\w*", blob, flags=re.IGNORECASE)
    if not found:
        return None
    word = found.group(0).lower()
    if word.startswith("очно-заоч"):
        return "очно-заочная"
    if word.startswith("заоч"):
        return "заочная"
    return "очная"


def _group(blob: str) -> str | None:
    found = re.search(r"\b[А-ЯЁA-Z]{1,6}-\d{2}(?:-\d{1,2})?\b", blob)
    return found.group(0) if found else None


def _course(blob: str) -> str | None:
    found = re.search(r"(\d)\s*курс|курс\s*[:№]?\s*(\d)", blob, flags=re.IGNORECASE)
    if not found:
        return None
    return found.group(1) or found.group(2)


def _reason(blob: str) -> str | None:
    low = blob.lower().replace("ё", "е")
    for phrase in REASONS:
        if phrase.replace("ё", "е") in low:
            return phrase.replace("ё", "е")
    labeled = re.search(r"причин\w*\s*[:\-–]?\s*(.+)", blob, flags=re.IGNORECASE)
    if labeled:
        return labeled.group(1).split("\n")[0].strip(" .")
    return None


def _grade(blob: str) -> str | None:
    low = blob.lower()
    for grade in GRADES:
        if grade in low:
            return grade
    return None


def _labeled(rows: list[str], label: str) -> str | None:
    pattern = re.compile(rf"(?:{label})\s*[:\-–]?\s*(.*)$", flags=re.IGNORECASE)
    for index, row in enumerate(rows):
        found = pattern.search(row)
        if not found:
            continue
        tail = found.group(1).strip(" .:-–")
        if tail:
            return tail
        if index + 1 < len(rows):
            return rows[index + 1].strip()
    return None


def _period(rows: list[str], hints: tuple[str, ...]) -> tuple[str | None, str | None]:
    for row in rows:
        low = row.lower()
        if any(hint in low for hint in hints):
            dates = _iso_dates(row)
            if len(dates) >= 2:
                return dates[0], dates[1]
    dates = _iso_dates("\n".join(rows))
    if len(dates) >= 2:
        return dates[0], dates[1]
    return None, None


def _number_and_issue(rows: list[str], blob: str) -> tuple[str | None, str | None]:
    number = None
    issued = None
    for row in rows:
        found = re.search(
            r"(?:номер\w*|№)\s*(?:справки|документа|практики)?\s*[:№]?\s*([0-9A-Za-zА-Яа-яЁё][\w\-/]{0,24})",
            row,
            flags=re.IGNORECASE,
        )
        if found and number is None:
            number = found.group(1)
        after_ot = re.search(r"\bот\s+(\d{1,2}[./]\d{1,2}[./]\d{4}|\d{1,2}\s+[А-Яа-яЁё]+\s+\d{4})", row, flags=re.IGNORECASE)
        if after_ot and issued is None:
            parsed = _iso_dates(after_ot.group(1))
            if parsed:
                issued = parsed[0]
        labeled = re.search(r"дата\s+(?:выдачи|справки)\s*[:\-–]?\s*(.+)", row, flags=re.IGNORECASE)
        if labeled and issued is None:
            parsed = _iso_dates(labeled.group(1))
            if parsed:
                issued = parsed[0]
    if issued is None:
        labeled = re.search(r"дата\s+(?:выдачи|справки)\s*[:\-–]?\s*(.+)", blob, flags=re.IGNORECASE)
        if labeled:
            parsed = _iso_dates(labeled.group(1))
            if parsed:
                issued = parsed[0]
    return number, issued


def _application_date(rows: list[str], start: str | None, end: str | None) -> str | None:
    for row in rows:
        if re.search(r"дата\s+заявлен", row, flags=re.IGNORECASE):
            parsed = _iso_dates(row)
            if parsed:
                return parsed[0]
    for row in rows:
        parsed = _iso_dates(row)
        if len(parsed) == 1 and parsed[0] not in {start, end}:
            if not re.search(r"отпуск|период|практик|обучен", row, flags=re.IGNORECASE):
                return parsed[0]
    return None


def _iso_dates(text: str) -> list[str]:
    found = []
    numeric = re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b")
    iso = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
    words = re.compile(
        r"\b(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+(\d{4})",
        flags=re.IGNORECASE,
    )
    for match in numeric.finditer(text):
        day, month, year = (int(part) for part in match.groups())
        if 1 <= day <= 31 and 1 <= month <= 12:
            found.append((match.start(), f"{year:04d}-{month:02d}-{day:02d}"))
    for match in iso.finditer(text):
        year, month, day = (int(part) for part in match.groups())
        if 1 <= day <= 31 and 1 <= month <= 12:
            found.append((match.start(), f"{year:04d}-{month:02d}-{day:02d}"))
    for match in words.finditer(text):
        day = int(match.group(1))
        month = MONTHS[match.group(2).lower()]
        year = int(match.group(3))
        if 1 <= day <= 31:
            found.append((match.start(), f"{year:04d}-{month:02d}-{day:02d}"))
    found.sort(key=lambda item: item[0])
    ordered = []
    for _, value in found:
        if value not in ordered:
            ordered.append(value)
    return ordered


def _marks(images: list, pages: list[dict]) -> tuple[bool, bool]:
    signed = False
    sealed = False
    for image, page in zip(images, pages):
        page_signed, page_sealed = _page_marks(image, page.get("lines", []))
        signed = signed or page_signed
        sealed = sealed or page_sealed
    return signed, sealed


def _page_marks(image, lines: list[dict]) -> tuple[bool, bool]:
    rgb = np.asarray(image.convert("RGB"))
    height, width = rgb.shape[:2]
    red = rgb[:, :, 0].astype(np.int16)
    green = rgb[:, :, 1].astype(np.int16)
    blue = rgb[:, :, 2].astype(np.int16)
    stamp = ((red > 140) & (red > green + 35) & (red > blue + 35)) | (
        (blue > 140) & (blue > red + 30) & (blue > green + 15)
    )
    covered = np.zeros((height, width), dtype=bool)
    for line in lines:
        x, y, box_w, box_h = (int(v) for v in line["bbox"])
        x1 = max(0, x - 4)
        y1 = max(0, y - 4)
        x2 = min(width, x + box_w + 4)
        y2 = min(height, y + box_h + 4)
        covered[y1:y2, x1:x2] = True
    dark = rgb.mean(axis=2) < 60
    bottom = np.zeros((height, width), dtype=bool)
    bottom[int(height * 0.55):, :] = True
    signature = int((dark & bottom & ~covered).sum()) > 120
    return signature, int(stamp.sum()) > 250
