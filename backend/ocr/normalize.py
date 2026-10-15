"""
Набросок нормализации полей. Словарь ФИО, вузов, организаций и направлений сюда не входит:
в закрытом наборе будут новые значения, их оставляем как прочитали.

Похожесть — rapidfuzz, если пакет стоит, иначе стандартное сравнение. Порог один.
Не дотянули до порога: возвращаем прочитанный текст, не «не найдено» и не чужое значение.
"""
import re

MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

FORMS = ("очно-заочная", "заочная", "очная")
GRADES = ("неудовлетворительно", "удовлетворительно", "отлично", "хорошо", "зачтено")
# Три причины из положения. Всё остальное после метки «Причина» остаётся текстом строки.
REASONS = (
    "по состоянию здоровья",
    "по семейным обстоятельствам",
    "в связи с призывом",
)

_LOOKALIKES = {
    "O": "0", "o": "0", "О": "0", "о": "0",
    "З": "3", "з": "3",
    "б": "6", "Б": "6",
    "l": "1", "I": "1", "І": "1", "і": "1",
}
_O_LIKE = set("OoОо")
_PUNCT = set(".,/-–—")
_PREFIX = {"OB": "ОБ", "PR": "ПР", "NP": "ПР", "ОБ": "ОБ", "ПР": "ПР"}
_KIND_PREFIX = {"study": "ОБ", "practice": "ПР"}


def ratio(left: str, right: str) -> int:
    try:
        from rapidfuzz import fuzz
        return int(fuzz.ratio(left, right))
    except ImportError:
        from difflib import SequenceMatcher
        return int(SequenceMatcher(None, left, right).ratio() * 100)


def _real_letter(char: str) -> bool:
    return bool(char) and char.isalpha() and char not in _LOOKALIKES


_UNITS = {"мм", "см", "км", "кг", "мл", "шт", "гр", "м", "г"}


def _stuck_to_unit(chars: list[str], pos: int) -> bool:
    """«125Омм»: ноль прилип к единице измерения, это не буква внутри слова."""
    if chars[pos] not in _O_LIKE or pos == 0 or not chars[pos - 1].isdigit():
        return False
    tail = []
    cursor = pos + 1
    while cursor < len(chars) and _real_letter(chars[cursor]):
        tail.append(chars[cursor])
        cursor += 1
        if len(tail) > 3:
            return False
    return "".join(tail).lower() in _UNITS


def fix_digits(text: str) -> str:
    """O→0, З→3, б→6, l/I→1 внутри числа. Букву рядом со словом не трогаем."""
    original = text
    chars = list(text)
    length = len(chars)

    def numeric(char: str) -> bool:
        return char.isdigit() or char in _LOOKALIKES or char in _PUNCT

    start = 0
    while start < length:
        if not numeric(original[start]):
            start += 1
            continue
        end = start
        while end < length and numeric(original[end]):
            end += 1
        run_has_digit = any(original[index].isdigit() for index in range(start, end))
        cursor = start
        while cursor < end:
            if original[cursor] in _PUNCT:
                cursor += 1
                continue
            stop = cursor
            while stop < end and original[stop] not in _PUNCT:
                stop += 1
            piece = original[cursor:stop]
            has_digit = any(char.isdigit() for char in piece)
            between_dots = (
                run_has_digit
                and len(piece) == 1
                and piece[0] in _LOOKALIKES
                and cursor > start
                and original[cursor - 1] in _PUNCT
                and stop < end
                and original[stop] in _PUNCT
            )
            left_edge = original[cursor - 1] if cursor else ""
            right_edge = original[stop] if stop < length else ""
            glued = _real_letter(left_edge) or _real_letter(right_edge)
            lookalikes = sum(char in _LOOKALIKES for char in piece)
            digits = sum(char.isdigit() for char in piece)
            if not glued and not between_dots and lookalikes > digits and len(piece) <= 4:
                cursor = stop
                continue
            if has_digit or between_dots:
                for pos in range(cursor, stop):
                    char = original[pos]
                    if char not in _LOOKALIKES:
                        continue
                    if glued and not between_dots:
                        left = original[pos - 1] if pos else ""
                        right = original[pos + 1] if pos + 1 < length else ""
                        if not (left.isdigit() and right.isdigit()) and not _stuck_to_unit(list(original), pos):
                            continue
                    chars[pos] = _LOOKALIKES[char]
            cursor = stop
        start = end
    return "".join(chars)


def expand_year(year: int) -> int:
    if year >= 100:
        return year
    return 2000 + year if year < 70 else 1900 + year


def parse_dates(text: str) -> list[str]:
    """«1 сентября 2026 года», «15» сентября и 01.09.26 → ISO. Невалидный день отбрасывается."""
    source = fix_digits(text)
    found = []
    numeric = re.compile(r"(?<!\d)(\d{1,2})[./](\d{1,2})[./](\d{4})(?!\d)")
    short = re.compile(r"(?<!\d)(\d{1,2})[./](\d{1,2})[./](\d{2})(?!\d)")
    iso = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
    months = "|".join(MONTHS)
    words = re.compile(
        rf"(?<!\d)[«\"„]?(\d{{1,2}})[»\"“]?\s+(?:{months})\s+(\d{{2,4}})",
        flags=re.IGNORECASE,
    )
    for match in numeric.finditer(source):
        day, month, year = (int(part) for part in match.groups())
        value = _calendar(year, month, day)
        if value:
            found.append((match.start(), value))
    for match in short.finditer(source):
        day, month, year = (int(part) for part in match.groups())
        value = _calendar(expand_year(year), month, day)
        if value:
            found.append((match.start(), value))
    for match in iso.finditer(source):
        year, month, day = (int(part) for part in match.groups())
        value = _calendar(year, month, day)
        if value:
            found.append((match.start(), value))
    for match in words.finditer(source):
        day = int(match.group(1))
        month_name = match.group(0).lower()
        month = next(number for name, number in MONTHS.items() if name in month_name)
        year = expand_year(int(match.group(2)))
        value = _calendar(year, month, day)
        if value:
            found.append((match.start(), value))
    found.sort(key=lambda item: item[0])
    ordered = []
    for _, value in found:
        if value not in ordered:
            ordered.append(value)
    return ordered


def ordered_span(start: str | None, end: str | None) -> tuple[str | None, str | None]:
    """start ≤ end. Перевёрнутый срок не публикуем целиком: конец снимаем."""
    if start and end and start > end:
        return start, None
    return start, end


def number_for(prefix: str, digits: str, kind: str) -> str | None:
    """Префикс номера задаёт тип: справка об обучении — ОБ, практика — ПР."""
    normal = _PREFIX.get(prefix.upper())
    expected = _KIND_PREFIX.get(kind)
    if normal is None or (expected and normal != expected):
        return None
    return f"{normal}-{digits}"


def snap(text: str, choices: tuple[str, ...], threshold: int = 80) -> str | None:
    low = text.lower().replace("ё", "е")
    for choice in sorted(choices, key=len, reverse=True):
        if choice.replace("ё", "е") in low:
            return choice
    sample = low.strip(" .")
    best = None
    score = 0
    for choice in choices:
        current = ratio(sample, choice.replace("ё", "е"))
        if current > score:
            best, score = choice, current
    if best and score >= threshold:
        return best
    return None


def closed_or_raw(text: str, choices: tuple[str, ...], threshold: int = 80) -> str:
    return snap(text, choices, threshold) or text.strip(" .")


def closest_label(head: str, labels: tuple[str, ...], threshold: int = 80) -> str | None:
    """Опечатка в метке («Дата вьцачи»). Короткие метки только точным совпадением."""
    sample = head.lower().strip()
    if len(sample) < 8:
        return None
    best = None
    score = 0
    second = 0
    for label in labels:
        if len(label) < 8:
            continue
        current = ratio(sample, label)
        if current > score:
            second = score
            best, score = label, current
        elif current > second:
            second = current
    if best and score >= threshold and score - second >= 6:
        return best
    return None


def _calendar(year: int, month: int, day: int) -> str | None:
    import datetime
    try:
        datetime.date(year, month, day)
    except ValueError:
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"
