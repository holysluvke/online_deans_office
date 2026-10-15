"""
Форматирование ISO-дат для текста ответа.

В message — «1 сентября 2026», в value — «2026-09-01» (ISO, для автопроверки).
"""
from __future__ import annotations

import re

_MONTHS_GENITIVE: dict[int, str] = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}

_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def humanize_date(value: str) -> str:
    """«2026-09-01» → «1 сентября 2026». Не-ISO строку возвращает как есть.

    Используется только для message: value в ответе остаётся в ISO.
    """
    if not isinstance(value, str):
        return value
    match = _ISO.match(value)
    if not match:
        return value
    year, month, day = (int(part) for part in match.groups())
    if month not in _MONTHS_GENITIVE:
        return value
    return f"{day} {_MONTHS_GENITIVE[month]} {year}"