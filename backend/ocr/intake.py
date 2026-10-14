"""
Приём документа: файл с диска -> список страниц-картинок для OCR.

Что принимаем: JPG, PNG, WEBP и PDF. Формат определяем по первым байтам файла,
а не по расширению: студент может прислать photo.png, который на самом деле JPEG.

Каждая страница возвращается как PIL.Image в RGB. Её размер считается «исходным»:
рамки строк в итоговом JSON всегда в пикселях именно этой картинки.
Фото с телефона дополнительно поворачиваются по EXIF, иначе документ лежит боком.
"""
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_FILE_MB = 15
MAX_PDF_PAGES = 10
# 200 dpi хватает, чтобы мелкий шрифт справки читался, и страница не весит лишнего
PDF_DPI = 200

FORMAT_BY_MAGIC = [
    (b"%PDF", "pdf"),
    (b"\xff\xd8\xff", "jpeg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
]


class OcrError(Exception):
    """Ошибка с понятным для студента текстом. Его покажет страница сайта."""


@dataclass
class Page:
    index: int
    image: Image.Image


def detect_format(head: bytes) -> str | None:
    for magic, name in FORMAT_BY_MAGIC:
        if head.startswith(magic):
            return name
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


def load_document(path: str | Path) -> tuple[str, list[Page]]:
    """Читает файл и возвращает (формат, страницы)."""
    path = Path(path)
    if not path.is_file():
        raise OcrError("Файл не найден")

    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_FILE_MB:
        raise OcrError(f"Файл слишком большой: можно до {MAX_FILE_MB} МБ")
    if path.stat().st_size == 0:
        raise OcrError("Файл пустой")

    with path.open("rb") as f:
        fmt = detect_format(f.read(16))
    if fmt is None:
        raise OcrError("Можно загрузить фото или PDF: JPG, PNG, WEBP, PDF")

    if fmt == "pdf":
        return fmt, _load_pdf(path)
    return fmt, [Page(0, _load_image(path))]


def _load_image(path: Path) -> Image.Image:
    try:
        with Image.open(path) as img:
            img.load()
            img = ImageOps.exif_transpose(img)
            return _to_rgb(img)
    except (UnidentifiedImageError, OSError) as e:
        raise OcrError("Файл повреждён, загрузите его заново") from e


def _to_rgb(img: Image.Image) -> Image.Image:
    if img.mode == "RGB":
        return img.copy()
    # Прозрачный PNG кладём на белый лист, иначе прозрачность станет чёрной
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        white = Image.new("RGB", rgba.size, (255, 255, 255))
        white.paste(rgba, mask=rgba.getchannel("A"))
        return white
    return img.convert("RGB")


def _load_pdf(path: Path) -> list[Page]:
    import pypdfium2 as pdfium

    try:
        pdf = pdfium.PdfDocument(str(path))
    except pdfium.PdfiumError as e:
        raise OcrError("PDF повреждён или защищён паролем") from e

    try:
        count = len(pdf)
        if count == 0:
            raise OcrError("В PDF нет страниц")
        if count > MAX_PDF_PAGES:
            raise OcrError(f"В PDF слишком много страниц: можно до {MAX_PDF_PAGES}")
        pages = []
        for i in range(count):
            bitmap = pdf[i].render(scale=PDF_DPI / 72)
            pages.append(Page(i, _to_rgb(bitmap.to_pil())))
        return pages
    finally:
        pdf.close()
