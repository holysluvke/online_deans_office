"""
Тесты OCR. Запуск из корня проекта: python -m pytest tests -q

Быстрые тесты (приём файлов, подготовка, текст, повороты) работают без PaddleOCR.
Медленные (класс TestPaddle) запускают настоящую модель и пропускаются, если её нет.
"""
import json
import math
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from backend.ocr import save_result
from backend.ocr.engine import _unrotate
from backend.ocr.intake import OcrError, detect_format, load_document
from backend.ocr.preprocess import prepare
from backend.ocr.text import clean_line, fix_homoglyphs, page_text, reading_order

FONT_PATH = Path(r"C:\Windows\Fonts\arial.ttf")

CERTIFICATE_LINES = [
    "СПРАВКА ОБ ОБУЧЕНИИ",
    "Выдана Иванову Ивану Петровичу",
    "в том, что он обучался в Южном университете",
    "Направление подготовки: Прикладная информатика",
    "Форма обучения: очная",
    "Период обучения: 01.09.2023 - 30.06.2025",
    "Номер справки: 1542 от 12.07.2025",
]


def draw_certificate(width=1240, height=1000, font_size=34) -> tuple[Image.Image, dict]:
    """Белый лист с текстом справки. Возвращает картинку и рамку каждой строки."""
    if not FONT_PATH.exists():
        pytest.skip("Нет шрифта Arial с кириллицей")
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(str(FONT_PATH), font_size)
    boxes = {}
    y = 80
    for line in CERTIFICATE_LINES:
        draw.text((80, y), line, fill="black", font=font)
        boxes[line] = draw.textbbox((80, y), line, font=font)
        y += font_size * 2
    return img, boxes


# ---------- приём файлов ----------

class TestIntake:
    def test_formats_by_magic_bytes(self):
        assert detect_format(b"%PDF-1.7") == "pdf"
        assert detect_format(b"\xff\xd8\xff\xe0") == "jpeg"
        assert detect_format(b"\x89PNG\r\n\x1a\n....") == "png"
        assert detect_format(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "webp"
        assert detect_format(b"PK\x03\x04") is None

    def test_png_named_jpg_is_read_by_content(self, tmp_path):
        p = tmp_path / "photo.jpg"
        Image.new("RGB", (50, 40), "white").save(p, "PNG")
        fmt, pages = load_document(p)
        assert fmt == "png"
        assert pages[0].image.size == (50, 40)

    def test_transparent_png_becomes_white(self, tmp_path):
        p = tmp_path / "scan.png"
        Image.new("RGBA", (10, 10), (0, 0, 0, 0)).save(p)
        _, pages = load_document(p)
        assert pages[0].image.mode == "RGB"
        assert pages[0].image.getpixel((5, 5)) == (255, 255, 255)

    def test_webp(self, tmp_path):
        p = tmp_path / "doc.webp"
        Image.new("RGB", (30, 20), "white").save(p, "WEBP")
        fmt, pages = load_document(p)
        assert fmt == "webp" and len(pages) == 1

    def test_phone_photo_rotated_by_exif(self, tmp_path):
        p = tmp_path / "phone.jpg"
        exif = Image.Exif()
        exif[0x0112] = 6  # «повернуть на 90° по часовой»
        Image.new("RGB", (300, 100), "white").save(p, "JPEG", exif=exif)
        _, pages = load_document(p)
        assert pages[0].image.size == (100, 300)

    def test_pdf_pages_rendered(self, tmp_path):
        p = tmp_path / "doc.pdf"
        first = Image.new("RGB", (595, 842), "white")
        second = Image.new("RGB", (595, 842), "white")
        first.save(p, "PDF", resolution=72, save_all=True, append_images=[second])
        fmt, pages = load_document(p)
        assert fmt == "pdf"
        assert [page.index for page in pages] == [0, 1]
        # 200 dpi: лист A4 в 72 dpi (595 точек) -> около 1653 пикселей
        assert abs(pages[0].image.width - 595 * 200 / 72) < 3

    def test_pdf_too_many_pages(self, tmp_path, monkeypatch):
        import backend.ocr.intake as intake

        monkeypatch.setattr(intake, "MAX_PDF_PAGES", 1)
        p = tmp_path / "doc.pdf"
        pages = [Image.new("RGB", (100, 100), "white") for _ in range(2)]
        pages[0].save(p, "PDF", save_all=True, append_images=pages[1:])
        with pytest.raises(OcrError, match="слишком много страниц"):
            load_document(p)

    def test_rejects_other_files(self, tmp_path):
        p = tmp_path / "doc.docx"
        p.write_bytes(b"PK\x03\x04 not an image")
        with pytest.raises(OcrError, match="JPG, PNG, WEBP, PDF"):
            load_document(p)

    def test_rejects_empty_and_broken(self, tmp_path):
        empty = tmp_path / "empty.jpg"
        empty.write_bytes(b"")
        with pytest.raises(OcrError, match="пустой"):
            load_document(empty)

        broken = tmp_path / "broken.jpg"
        broken.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)
        with pytest.raises(OcrError, match="повреждён"):
            load_document(broken)

    def test_rejects_too_large(self, tmp_path, monkeypatch):
        import backend.ocr.intake as intake

        monkeypatch.setattr(intake, "MAX_FILE_MB", 0.001)
        p = tmp_path / "big.png"
        Image.new("RGB", (400, 400), "white").save(p, "PNG", compress_level=0)
        with pytest.raises(OcrError, match="слишком большой"):
            load_document(p)


# ---------- подготовка ----------

class TestPrepare:
    def test_small_photo_upscaled(self):
        prepared = prepare(Image.new("RGB", (400, 300), "white"))
        assert prepared.scale == pytest.approx(2.5)
        assert prepared.image.size == (1000, 750)

    def test_huge_photo_downscaled(self):
        prepared = prepare(Image.new("RGB", (5200, 3900), "white"))
        assert prepared.scale == pytest.approx(0.5)
        assert max(prepared.image.size) == 2600

    def test_even_light_untouched(self):
        img, _ = draw_certificate()
        prepared = prepare(img)
        assert prepared.shadow_fixed is False

    def test_shadow_flattened(self):
        img, _ = draw_certificate()
        shaded = add_shadow(img)
        prepared = prepare(shaded)
        assert prepared.shadow_fixed is True
        gray = np.asarray(prepared.image.convert("L"), dtype=np.float32)
        # Чистый фон слева (в тени) и справа (на свету) после выравнивания почти одинаковый
        left = np.percentile(gray[:, : gray.shape[1] // 10], 90)
        right = np.percentile(gray[:, -gray.shape[1] // 10 :], 90)
        assert abs(left - right) < 25


def add_shadow(img: Image.Image) -> Image.Image:
    arr = np.asarray(img, dtype=np.float32)
    ramp = np.linspace(0.35, 1.0, arr.shape[1], dtype=np.float32)[None, :, None]
    return Image.fromarray((arr * ramp).astype(np.uint8))


# ---------- текст ----------

class TestText:
    def test_homoglyphs_fixed_only_in_russian_words(self):
        assert fix_homoglyphs("Cправка") == "Справка"
        assert fix_homoglyphs("OOO") == "OOO"
        assert fix_homoglyphs("ivan@mail.ru") == "ivan@mail.ru"

    def test_clean_line(self):
        assert clean_line("  ФИО :   Иванов  ( студент ) ") == "ФИО: Иванов (студент)"

    def test_label_and_value_joined_in_one_row(self):
        lines = [
            {"text": "Иванов И. И.", "bbox": [300, 102, 200, 30], "low_confidence": False},
            {"text": "ФИО:", "bbox": [50, 100, 80, 32], "low_confidence": False},
            {"text": "Группа: ПИ-21", "bbox": [50, 160, 220, 30], "low_confidence": False},
        ]
        rows = reading_order(lines)
        assert [[l["text"] for l in row] for row in rows] == [["ФИО:", "Иванов И. И."], ["Группа: ПИ-21"]]
        assert page_text(lines) == "ФИО: Иванов И. И.\nГруппа: ПИ-21"

    def test_tilted_rows_not_merged(self):
        # Лист наклонён на 12°: прямые рамки соседних строк перекрываются по высоте
        angle = math.radians(12)
        lines = []
        for i, text in enumerate(["Первая строка", "Вторая строка", "Третья строка"]):
            x0, y0, w, h = 100, 100 + i * 70, 500, 34
            corners = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]
            poly = [
                [x * math.cos(angle) - y * math.sin(angle), x * math.sin(angle) + y * math.cos(angle)]
                for x, y in corners
            ]
            xs, ys = [p[0] for p in poly], [p[1] for p in poly]
            bbox = [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)]
            lines.append({"text": text, "bbox": bbox, "polygon": poly, "low_confidence": False})
        assert page_text(lines[::-1]) == "Первая строка\nВторая строка\nТретья строка"

    def test_punctuation_only_dropped(self):
        lines = [
            {"text": "Справка", "bbox": [0, 0, 100, 30], "low_confidence": False},
            {"text": "---", "bbox": [0, 40, 80, 20], "low_confidence": False},
        ]
        assert page_text(lines) == "Справка"

    def test_low_confidence_not_in_text(self):
        lines = [
            {"text": "Справка", "bbox": [0, 0, 100, 30], "low_confidence": False},
            {"text": "##%", "bbox": [0, 60, 100, 30], "low_confidence": True},
        ]
        assert page_text(lines) == "Справка"


# ---------- обратный поворот рамок ----------

@pytest.mark.parametrize("turns", [0, 1, 2, 3])
def test_unrotate_matches_numpy_rot90(turns):
    img = np.zeros((40, 70), dtype=np.uint8)
    x, y = 12, 30
    img[y, x] = 255
    rotated = np.rot90(img, turns)
    ry, rx = np.argwhere(rotated == 255)[0]
    assert _unrotate(float(rx), float(ry), img.shape, turns) == [x, y]


def test_save_result_writes_txt_and_json(tmp_path):
    result = {"source": {"file": "справка.jpg"}, "text": "СПРАВКА", "pages": []}
    txt, js = save_result(result, tmp_path)
    assert txt.read_text(encoding="utf-8") == "СПРАВКА\n"
    assert json.loads(js.read_text(encoding="utf-8"))["text"] == "СПРАВКА"


# ---------- настоящий PaddleOCR ----------

try:
    import paddleocr  # noqa: F401

    HAS_PADDLE = True
except ImportError:
    HAS_PADDLE = False


def words(text: str) -> set[str]:
    return set(text.lower().replace(":", " ").replace(".", " ").split())


def bbox_center_inside(bbox, box, tolerance=25):
    x, y, w, h = bbox
    cx, cy = x + w / 2, y + h / 2
    left, top, right, bottom = box
    return left - tolerance <= cx <= right + tolerance and top - tolerance <= cy <= bottom + tolerance


@pytest.mark.skipif(not HAS_PADDLE, reason="PaddleOCR не установлен")
class TestPaddle:
    KEY_WORDS = {"справка", "обучении", "иванову", "очная", "1542", "информатика"}

    def run(self, img: Image.Image, tmp_path: Path, name="doc.png") -> dict:
        from backend.ocr import run_ocr

        p = tmp_path / name
        img.save(p)
        return run_ocr(p)

    def find_line(self, result, needle):
        for line in result["pages"][0]["lines"]:
            if needle.lower() in line["text"].lower():
                return line
        raise AssertionError(f"Строка «{needle}» не найдена: {result['text']!r}")

    def test_clean_scan(self, tmp_path):
        img, boxes = draw_certificate()
        result = self.run(img, tmp_path)
        assert self.KEY_WORDS <= words(result["text"]), result["text"]
        assert result["pages"][0]["rotation"] == 0
        line = self.find_line(result, "Форма обучения")
        assert bbox_center_inside(line["bbox"], boxes["Форма обучения: очная"])

    def test_sideways_photo_boxes_on_original(self, tmp_path):
        img, boxes = draw_certificate()
        sideways = img.rotate(90, expand=True)
        result = self.run(sideways, tmp_path)
        assert self.KEY_WORDS <= words(result["text"]), result["text"]
        assert result["pages"][0]["rotation"] in (90, 270)

        # Рамка строки должна лежать там, где строка нарисована на повёрнутом файле
        w, _ = img.size
        left, top, right, bottom = boxes["Форма обучения: очная"]
        # rotate(90) против часовой: точка (x, y) -> (y, w - 1 - x)
        rotated_box = (top, w - 1 - right, bottom, w - 1 - left)
        line = self.find_line(result, "Форма обучения")
        assert bbox_center_inside(line["bbox"], rotated_box)

    def test_tilted_shadowed_low_res_photo(self, tmp_path):
        img, _ = draw_certificate()
        bad = add_shadow(img).rotate(15, expand=True, fillcolor="white", resample=Image.BICUBIC)
        bad = bad.resize((bad.width // 2, bad.height // 2), Image.BILINEAR).filter(ImageFilter.GaussianBlur(0.8))
        result = self.run(bad, tmp_path, name="bad.jpg")
        found = self.KEY_WORDS & words(result["text"])
        assert len(found) >= 5, result["text"]
        # Строки не склеены и идут сверху вниз, как на бланке
        rows = result["text"].lower().split("\n")
        assert len(rows) == len(CERTIFICATE_LINES), result["text"]
        order = [next(i for i, r in enumerate(rows) if key in r) for key in ("справка", "иванову", "очная", "1542")]
        assert order == sorted(order), result["text"]

    def test_pdf(self, tmp_path):
        from backend.ocr import run_ocr

        img, _ = draw_certificate()
        p = tmp_path / "doc.pdf"
        img.save(p, "PDF", resolution=150)
        result = run_ocr(p)
        assert result["source"]["format"] == "pdf"
        assert "справка" in result["text"].lower()

    def test_blank_page_is_honest_error(self, tmp_path):
        with pytest.raises(OcrError, match="Не удалось прочитать текст"):
            self.run(Image.new("RGB", (1200, 900), "white"), tmp_path)
