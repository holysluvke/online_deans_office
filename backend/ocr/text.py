"""
Из строк OCR -> чистый текст в порядке чтения.

PaddleOCR отдаёт отдельные куски строк. «ФИО:» и «Иванов И. И.» в одной строке бланка
часто приходят двумя рамками. Здесь мы:
    - собираем рамки в строки по вертикали и сортируем слева направо;
    - чиним латинские буквы-двойники внутри русских слов (C -> С, o -> о);
    - убираем лишние пробелы.
"""
import math
import re

CYRILLIC = re.compile(r"[А-Яа-яЁё]")
USEFUL = re.compile(r"[0-9A-Za-zА-Яа-яЁё№]")
SPACES = re.compile(r"\s+")
SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.;:!?)\]»])")
SPACE_AFTER_OPEN = re.compile(r"([(\[«])\s+")

# Латиница, которая на фото выглядит как кириллица
LATIN_TO_CYRILLIC = str.maketrans(
    "ABCEHKMOPTXaceopxyY",
    "АВСЕНКМОРТХасеорхуУ",
)


def fix_homoglyphs(word: str) -> str:
    """Меняет латинские двойники на кириллицу, только если в слове уже есть кириллица."""
    if not CYRILLIC.search(word):
        return word
    return word.translate(LATIN_TO_CYRILLIC)


def clean_line(text: str) -> str:
    text = SPACES.sub(" ", text).strip()
    text = " ".join(fix_homoglyphs(w) for w in text.split(" "))
    text = SPACE_BEFORE_PUNCT.sub(r"\1", text)
    return SPACE_AFTER_OPEN.sub(r"\1", text)


def _edge_angle(polygon) -> float | None:
    (x0, y0), (x1, y1) = polygon[0], polygon[1]
    if abs(x1 - x0) < 1e-6:
        return None
    return math.atan2(y1 - y0, x1 - x0)


def _page_skew(lines: list[dict]) -> float:
    """Общий наклон листа: медиана наклона верхних краёв строк."""
    angles = sorted(
        a for l in lines
        if len(l.get("polygon") or []) == 4 and (a := _edge_angle(l["polygon"])) is not None
    )
    return angles[len(angles) // 2] if angles else 0.0


def _geometry(line: dict, skew: float) -> tuple[float, float, float]:
    """(x вдоль строки, y поперёк строк, высота строки) в системе, повёрнутой на наклон листа."""
    polygon = line.get("polygon")
    if polygon and len(polygon) == 4:
        cx = sum(p[0] for p in polygon) / 4
        cy = sum(p[1] for p in polygon) / 4
        tl, tr, br, bl = polygon
        height = (math.dist(tl, bl) + math.dist(tr, br)) / 2
    else:
        x, y, w, h = line["bbox"]
        cx, cy, height = x + w / 2, y + h / 2, h
    cos, sin = math.cos(skew), math.sin(skew)
    return cx * cos + cy * sin, -cx * sin + cy * cos, height


def reading_order(lines: list[dict]) -> list[list[dict]]:
    """
    Группирует рамки в строки бланка. В каждой строке рамки слева направо.
    На наклонном фото прямые рамки соседних строк перекрываются, поэтому сравниваем
    центры строк после поворота на общий наклон листа.
    """
    skew = _page_skew(lines)
    placed = sorted(((*_geometry(l, skew), l) for l in lines), key=lambda g: (g[1], g[0]))

    rows: list[list[tuple]] = []
    for item in placed:
        _, y, h, _ = item
        if rows:
            row = rows[-1]
            row_y = sum(g[1] for g in row) / len(row)
            row_h = sum(g[2] for g in row) / len(row)
            # Та же строка, если центры почти на одной высоте
            if abs(y - row_y) < 0.5 * min(h, row_h):
                row.append(item)
                continue
        rows.append([item])
    return [[g[3] for g in sorted(row, key=lambda g: g[0])] for row in rows]


def page_text(lines: list[dict]) -> str:
    rows = reading_order([l for l in lines if not l["low_confidence"]])
    out = []
    for row in rows:
        joined = clean_line(" ".join(l["text"] for l in row))
        if joined and USEFUL.search(joined):
            out.append(joined)
    return "\n".join(out)
