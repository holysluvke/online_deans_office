"""
Вторая модель: рукописный русский через TrOCR (трансформер).

Печатный PaddleOCR слабые строки не выкидывает в «не найдено».
Если уверенность строки ниже порога, рамку вырезаем и читаем заново
моделью kazars24/trocr-base-handwritten-ru. Её текст заменяет мусор Paddle.
Если рукописная модель тоже ничего не вернула, остаётся текст Paddle.
"""
import os
import threading
from pathlib import Path

from PIL import Image

from backend.ocr.engine import MIN_CONFIDENCE, PROJECT_ROOT

MODEL_ID = "kazars24/trocr-base-handwritten-ru"
MAX_NEW_TOKENS = 64

_bundle = None
_lock = threading.Lock()


def _cache_dir() -> None:
    """Тот же приём, что у Paddle: кэш не в домашней папке с кириллицей."""
    if os.environ.get("HF_HOME"):
        return
    if str(Path.home()).isascii():
        return
    for candidate in (PROJECT_ROOT / "data" / "hf", Path(os.environ.get("PUBLIC", r"C:\Users\Public")) / "hf"):
        if str(candidate).isascii():
            os.environ["HF_HOME"] = str(candidate)
            return


_cache_dir()


def get_reader():
    global _bundle
    with _lock:
        if _bundle is None:
            import torch
            from transformers import TrOCRProcessor, VisionEncoderDecoderModel

            processor = TrOCRProcessor.from_pretrained(MODEL_ID)
            model = VisionEncoderDecoderModel.from_pretrained(MODEL_ID)
            model.to(torch.device("cpu"))
            model.eval()
            _bundle = (processor, model)
        return _bundle


def read_crop(image: Image.Image) -> str:
    """Читает один вырезанный кусок строки. Пустая строка, если модель ничего не собрала."""
    import torch

    processor, model = get_reader()
    rgb = image.convert("RGB")
    pixels = processor(images=rgb, return_tensors="pt").pixel_values
    with _lock:
        ids = model.generate(pixels, max_new_tokens=MAX_NEW_TOKENS, num_beams=1)
    text = processor.batch_decode(ids, skip_special_tokens=True)[0]
    return " ".join(text.split())


def _crop(image: Image.Image, polygon: list, pad: int = 6) -> Image.Image | None:
    if not polygon:
        return None
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    x1 = max(0, int(min(xs)) - pad)
    y1 = max(0, int(min(ys)) - pad)
    x2 = min(image.width, int(max(xs)) + pad + 1)
    y2 = min(image.height, int(max(ys)) + pad + 1)
    if x2 - x1 < 8 or y2 - y1 < 8:
        return None
    return image.crop((x1, y1, x2, y2))


def reread(image: Image.Image, lines: list[dict], reader=read_crop) -> list[dict]:
    """
    Строки с уверенностью ниже порога читает рукописная модель.
    Уверенные печатные строки не трогает.
    """
    out = []
    for line in lines:
        copied = dict(line)
        copied["source"] = "paddle"
        if line["confidence"] >= MIN_CONFIDENCE:
            out.append(copied)
            continue
        crop = _crop(image, line["polygon"])
        handwritten = " ".join((reader(crop) if crop is not None else "").split())
        if handwritten:
            copied["text"] = handwritten
            copied["source"] = "trocr"
        out.append(copied)
    return out
