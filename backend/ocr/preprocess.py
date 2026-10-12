"""
Лёгкая подготовка страницы перед OCR.

Делаем только то, что не портит нейросеть:
    - мелкое фото увеличиваем, огромное уменьшаем (рамки потом делим на scale);
    - выравниваем тень: делим кадр на размытый фон, если освещение неровное.
Чёрно-белую бинаризацию сознательно не делаем: на бликах PaddleOCR от неё читает хуже.
Поворот всего листа делает PaddleOCR (см. engine.py). Разворот отдельных строк выключен.
"""
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFilter

# Длинная сторона после подготовки. Меньше - мелкий шрифт теряется, больше - долго на CPU
MIN_LONG_SIDE = 1600
MAX_LONG_SIDE = 2600
MAX_UPSCALE = 2.5

# Насколько неровным должен быть фон (разброс яркости), чтобы включать выравнивание тени
SHADOW_MIN_SPREAD = 40


@dataclass
class Prepared:
    image: Image.Image
    scale: float
    shadow_fixed: bool


def prepare(image: Image.Image) -> Prepared:
    scale = _pick_scale(image.size)
    if scale != 1.0:
        size = (round(image.width * scale), round(image.height * scale))
        image = image.resize(size, Image.LANCZOS)
    image, shadow_fixed = _flatten_shadow(image)
    return Prepared(image, scale, shadow_fixed)


def _pick_scale(size: tuple[int, int]) -> float:
    long_side = max(size)
    if long_side < MIN_LONG_SIDE:
        return min(MIN_LONG_SIDE / long_side, MAX_UPSCALE)
    if long_side > MAX_LONG_SIDE:
        return MAX_LONG_SIDE / long_side
    return 1.0


def _background(gray: Image.Image) -> np.ndarray:
    # Фон считаем на уменьшенной копии: буквы исчезают, остаются тень и блик
    small = gray.reduce(8) if min(gray.size) >= 64 else gray
    radius = max(small.size) / 25
    blurred = small.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(radius))
    return np.asarray(blurred.resize(gray.size, Image.BILINEAR), dtype=np.float32)


def _flatten_shadow(image: Image.Image) -> tuple[Image.Image, bool]:
    gray = image.convert("L")
    bg = _background(gray)
    low, high = np.percentile(bg, [5, 95])
    if high - low < SHADOW_MIN_SPREAD:
        return image, False

    rgb = np.asarray(image, dtype=np.float32)
    flat = rgb / np.maximum(bg, 1.0)[..., None] * 255.0
    return Image.fromarray(np.clip(flat, 0, 255).astype(np.uint8)), True
