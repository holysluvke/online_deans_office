"""
Превращает загруженный PDF в картинку, чтобы дальше всё работало как с обычным фото.

Зачем: pipeline.py (OCR) принимает только картинки, а организаторы разрешают «JPG, PNG или PDF».
Поэтому PDF конвертируется сразу при загрузке (backend/main.py), и в очередь попадает уже PNG.
Исходный PDF нигде не сохраняется.

Как: страницы PDF рисуются в картинки библиотекой pypdfium2 (ставится через pip, ничего
дополнительно устанавливать не нужно) и склеиваются друг под другом в одну длинную картинку.
Так одна задача остаётся одним файлом, и ML-части ничего менять не надо.

Настройки (переменной окружения): MAX_PDF_PAGES - сколько страниц разрешаем (по умолчанию 3).
"""
import os
from io import BytesIO

import pypdfium2 as pdfium
from PIL import Image

# Качество отрисовки: 300 точек на дюйм - стандарт для распознавания текста (A4 выходит ~2480x3508)
RENDER_DPI = 300
# Длинная сторона страницы не больше стольких пикселей: защита от PDF с гигантским листом
MAX_SIDE_PX = 4000
# Сколько страниц принимаем. У справок и заявлений обычно одна, больше - скорее всего не тот файл.
MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "3"))


class PdfError(ValueError):
    """PDF нельзя принять; текст ошибки можно показывать посетителю."""


def pdf_to_png(content: bytes) -> bytes:
    """Рисует страницы PDF в картинки, склеивает их друг под другом и возвращает как PNG."""
    try:
        pdf = pdfium.PdfDocument(content)
    except pdfium.PdfiumError:
        raise PdfError("Не удалось открыть PDF: файл повреждён или защищён паролем")
    try:
        count = len(pdf)
        if count == 0:
            raise PdfError("В PDF нет страниц")
        if count > MAX_PDF_PAGES:
            raise PdfError(f"В PDF {count} стр., можно не больше {MAX_PDF_PAGES}")
        pages = []
        for page in pdf:
            width, height = page.get_size()  # размер листа в пунктах (1/72 дюйма)
            scale = min(RENDER_DPI / 72, MAX_SIDE_PX / max(width, height))
            pages.append(page.render(scale=scale).to_pil().convert("RGB"))
    except pdfium.PdfiumError:
        raise PdfError("Не удалось прочитать страницы PDF: файл повреждён")
    finally:
        pdf.close()

    # Склеиваем страницы в одну картинку: ширина по самой широкой, фон белый
    sheet = Image.new("RGB", (max(p.width for p in pages), sum(p.height for p in pages)), "white")
    top = 0
    for p in pages:
        sheet.paste(p, (0, top))
        top += p.height
    out = BytesIO()
    sheet.save(out, "PNG")
    return out.getvalue()
