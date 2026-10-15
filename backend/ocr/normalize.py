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
_PREFIX = {"OB": "ОБ", "PR": "ПР", "NP": "ПР", "ОБ": "ОБ", "ПР": "ПР"}
_KIND_PREFIX = {"study": "ОБ", "practice": "ПР"}


def ratio(left: str, right: str) -> int:
    try:
        from rapidfuzz import fuzz
        return int(fuzz.ratio(left, right))
    except ImportError:
        from difflib import SequenceMatcher
        return int(SequenceMatcher(None, left, right).ratio() * 100)


def fix_digits(text: str) -> str:
    """O→0, З→3, б→6, l/I→1 только рядом с цифрами. Слова не трогаем."""
    chars = list(text)
    for index, char in enumerate(chars):
        if char not in _LOOKALIKES:
            continue
        neighbors = []
        if index > 0:
            neighbors.append(chars[index - 1])
        if index + 1 < len(chars):
            neighbors.append(chars[index + 1])
        # Только если буква стоит прямо у цифры: «2O26», но не «ОБ» и не «здоровья».
        if not any(item.isdigit() for item in neighbors):
            continue
        chars[index] = _LOOKALIKES[char]
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
        rf"[«\"„]?(\d{{1,2}})[»\"“]?\s+(?:{months})\s+(\d{{2,4}})",
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
