"""Подпись и печать.

Слова «Подпись» и «М.П.» сами по себе отметкой не считаются.
Подпись есть, только если на листе написано «подпись» и рядом есть линия,
а в зоне этой линии начерчен росчерк. Пустая линия — не подпись.
Печать — круглое или прямоугольное пятно цветных чернил.
У заявления на отпуск печати нет: для этого типа её не ищем.
"""
import re

import numpy as np

LEAVE_TYPES = {"academic_leave", "academic_leave_application"}
_SIGNATURE_WORD = re.compile(r"подпись", flags=re.IGNORECASE)
_PLACE_WORD = re.compile(r"м\s*\.?\s*п", flags=re.IGNORECASE)


def detect_marks(images, ocr_pages, doc_type: str) -> tuple[bool, bool]:
    """(подпись, печать). Для заявления печать всегда False."""
    want_seal = doc_type not in LEAVE_TYPES
    signed = False
    sealed = False
    for image, page in zip(images or [], ocr_pages or []):
        lines = page.get("lines", [])
        seals = find_seals(image)
        signed = signed or _signature_near_label(image, lines, seals)
        if want_seal:
            sealed = sealed or bool(seals)
    return signed, sealed


def find_seals(image) -> list[list[int]]:
    """Рамки печатей: [x, y, ширина, высота].

    Круглая и прямоугольная цветная печать (синяя, красная, фиолетовая).
    Чёрный текст, серая тень и длинный росчерк ручки сюда не попадают.
    """
    import cv2

    rgb = np.asarray(image.convert("RGB"))
    height, width = rgb.shape[:2]
    if height < 16 or width < 16:
        return []
    scale = min(1.0, 1200 / max(height, width))
    if scale < 1:
        small = cv2.resize(
            rgb,
            (max(1, int(width * scale)), max(1, int(height * scale))),
            interpolation=cv2.INTER_AREA,
        )
    else:
        small = rgb
    red = small[:, :, 0].astype(np.int16)
    green = small[:, :, 1].astype(np.int16)
    blue = small[:, :, 2].astype(np.int16)
    lead = np.maximum(np.maximum(red, green), blue) - np.minimum(np.minimum(red, green), blue)
    brightest = np.maximum(np.maximum(red, green), blue)
    ink = (lead > 18) & (brightest > 55) & (brightest < 248)
    mask = ink.astype(np.uint8) * 255
    short = min(mask.shape[:2])
    kernel = max(5, int(short * 0.018) | 1)
    ellipse = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel, kernel))
    closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, ellipse)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
    page_area = mask.shape[0] * mask.shape[1]
    boxes = []
    for index in range(1, count):
        x, y, box_w, box_h, area = (int(v) for v in stats[index])
        if box_w < 12 or box_h < 12:
            continue
        ratio = box_w / box_h
        aspect = max(ratio, 1 / ratio)
        # Длинный росчерк ручки, не корпус печати.
        if aspect > 2.6:
            continue
        box_area = box_w * box_h
        if not 0.004 * page_area <= box_area <= 0.22 * page_area:
            continue
        extent = area / box_area
        if not 0.06 <= extent <= 0.96:
            continue
        component = np.uint8(labels == index) * 255
        contours, _ = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        contour = max(contours, key=cv2.contourArea)
        perimeter = cv2.arcLength(contour, True)
        contour_area = cv2.contourArea(contour)
        if perimeter <= 0 or contour_area <= 0:
            continue
        circularity = 4 * np.pi * contour_area / (perimeter * perimeter)
        short_side = min(box_w, box_h)
        is_round = 0.7 <= ratio <= 1.45 and circularity >= 0.55
        is_rect = circularity >= 0.4 and short_side >= 0.05 * short
        if not (is_round or is_rect):
            continue
        if is_round and not is_rect and len(contour) >= 5:
            (_, _), (axis_a, axis_b), _ = cv2.fitEllipse(contour)
            if min(axis_a, axis_b) / max(axis_a, axis_b) < 0.7:
                continue
        boxes.append([
            int(round(x / scale)),
            int(round(y / scale)),
            max(1, int(round(box_w / scale))),
            max(1, int(round(box_h / scale))),
        ])
    return _merge_seals(boxes)


def _merge_seals(boxes: list[list[int]]) -> list[list[int]]:
    """Двойное кольцо или рамка внутри рамки — одна печать."""
    ordered = sorted(boxes, key=lambda box: box[2] * box[3], reverse=True)
    kept = []
    for box in ordered:
        center_x = box[0] + box[2] / 2
        center_y = box[1] + box[3] / 2
        inside = False
        for other in kept:
            if other[0] <= center_x <= other[0] + other[2] and other[1] <= center_y <= other[1] + other[3]:
                inside = True
                break
        if not inside:
            kept.append(box)
    return kept


def _signature_near_label(image, lines: list[dict], seals: list[list[int]] | None = None) -> bool:
    """Два флага: написано «подпись» и есть линия. Росчерк в зоне линии — подпись есть."""
    rgb = np.asarray(image.convert("RGB"))
    height, width = rgb.shape[:2]
    if height < 16 or width < 16:
        return False
    anchors = _boxes(lines, _SIGNATURE_WORD)
    has_label = bool(anchors)
    if not has_label:
        return False

    gray = rgb.mean(axis=2)
    chroma = rgb.max(axis=2).astype(np.int16) - rgb.min(axis=2).astype(np.int16)
    page_ink = (gray < 170) | ((chroma > 28) & (gray < 225))
    blocked = list(seals or []) + _round_stamp_boxes(page_ink) + _boxes(lines, _PLACE_WORD)
    signature_line = _find_signature_line(gray, anchors, blocked, width, height)
    has_line = signature_line is not None
    if not has_line:
        return False
    return _drawn_on_line(page_ink, signature_line, height)


def _find_signature_line(gray, anchors, blocked, width, height):
    """Линия справа от слова «подпись». (x1, x2, верх, низ) или None."""
    ink = gray < 210
    for x, y, box_w, box_h in blocked:
        x1, y1 = max(0, x - 6), max(0, y - 6)
        x2, y2 = min(width, x + box_w + 6), min(height, y + box_h + 6)
        ink[y1:y2, x1:x2] = False

    best = None
    min_length = max(48, int(width * 0.1))
    for x, y, box_w, box_h in anchors:
        box_h = max(box_h, 8)
        x_from = min(width - 1, x + box_w + 2)
        y_from = max(0, y - box_h)
        y_to = min(height, y + box_h + max(box_h * 4, 72))
        for row in range(y_from, y_to):
            run = _longest_run(ink[row, x_from:])
            if run is None or run[1] - run[0] + 1 < min_length:
                continue
            start, end = x_from + run[0], x_from + run[1]
            top, bottom = _line_thickness(ink, row, start, end, y_from, y_to)
            length = end - start + 1
            if best is None or length > best[0]:
                best = (length, start, end, top, bottom)
    if best is None:
        return None
    _, start, end, top, bottom = best
    return start, end, top, bottom


def _longest_run(row) -> tuple[int, int] | None:
    best = None
    start = None
    for index, on in enumerate(row):
        if on and start is None:
            start = index
        elif not on and start is not None:
            if best is None or index - start > best[1] - best[0] + 1:
                best = (start, index - 1)
            start = None
    if start is not None and (best is None or len(row) - start > best[1] - best[0] + 1):
        best = (start, len(row) - 1)
    return best


def _line_thickness(ink, row, start, end, y_from, y_to) -> tuple[int, int]:
    """Соседние ряды той же черты входят в линию, росчерк — нет."""
    need = max(24, int((end - start + 1) * 0.6))
    top = bottom = row
    while top - 1 >= y_from and _longest_run(ink[top - 1, start:end + 1]) is not None:
        run = _longest_run(ink[top - 1, start:end + 1])
        if run[1] - run[0] + 1 < need:
            break
        top -= 1
    while bottom + 1 < y_to and _longest_run(ink[bottom + 1, start:end + 1]) is not None:
        run = _longest_run(ink[bottom + 1, start:end + 1])
        if run[1] - run[0] + 1 < need:
            break
        bottom += 1
    return top, bottom


def _drawn_on_line(ink, signature_line, height) -> bool:
    """В зоне линии есть штрих помимо самой черты."""
    x1, x2, top, bottom = signature_line
    pad = 28
    y1 = max(0, top - pad)
    y2 = min(height, bottom + pad + 1)
    zone = ink[y1:y2, x1:x2 + 1].copy()
    zone[top - y1:bottom - y1 + 1, :] = False
    if int(zone.sum()) < 40:
        return False
    rows = np.flatnonzero(zone.any(axis=1))
    return bool(len(rows) and rows.max() - rows.min() + 1 >= 8)


def _round_stamp_boxes(ink: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Круглая печать на всём листе. Росчерк в эту рамку не попадает."""
    import cv2

    count, labels, stats, _ = cv2.connectedComponentsWithStats(ink.astype(np.uint8) * 255, connectivity=8)
    boxes = []
    for index in range(1, count):
        x, y, box_w, box_h, area = (int(v) for v in stats[index])
        if area < 180 or min(box_w, box_h) < 28:
            continue
        component = np.uint8(labels == index) * 255
        contours, _ = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        contour = max(contours, key=cv2.contourArea)
        perimeter = cv2.arcLength(contour, True)
        contour_area = cv2.contourArea(contour)
        if perimeter <= 0 or contour_area <= 0:
            continue
        if 4 * np.pi * contour_area / (perimeter * perimeter) < 0.7:
            continue
        boxes.append((x, y, box_w, box_h))
    return boxes


def _boxes(lines: list[dict], pattern: re.Pattern) -> list[tuple[int, int, int, int]]:
    found = []
    for line in lines:
        if not pattern.search(str(line.get("text", ""))):
            continue
        bbox = line.get("bbox")
        if not bbox or len(bbox) < 4:
            continue
        found.append(tuple(int(v) for v in bbox[:4]))
    return found
