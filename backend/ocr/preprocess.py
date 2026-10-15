"""
Лёгкая подготовка страницы перед OCR.

Делаем только то, что не портит нейросеть:
    - небольшой наклон (до 30°) выпрямляем по линиям текста;
    - мелкое фото увеличиваем, огромное уменьшаем (рамки потом делим на scale);
    - выравниваем тень: делим кадр на размытый фон, если освещение неровное;
    - если края букв почти стёрты, возвращаем их обратной свёрткой;
    - просто мелкий кадр увеличиваем сильнее, чем обычный.
Чёрно-белую бинаризацию сознательно не делаем: на бликах PaddleOCR от неё читает хуже.
Поворот на прямой угол делает PaddleOCR (см. engine.py). Разворот отдельных строк выключен.
"""
import math
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image, ImageFilter

# Длинная сторона после подготовки. Меньше - мелкий шрифт теряется, больше - долго на CPU
MIN_LONG_SIDE = 1600
MAX_LONG_SIDE = 2600
MAX_UPSCALE = 2.5

# Насколько неровным должен быть фон (разброс яркости), чтобы включать выравнивание тени
SHADOW_MIN_SPREAD = 40

# Ниже этого лапласиана буквы уже мыльные. Обычный снимок сюда не попадает.
SOFT_LAPLACIAN = 25
# Между этим и порогом выше кадр просто мелкий: его выгоднее увеличить до потолка.
MILD_LAPLACIAN = 80
# Ядро и число шагов Люси–Ричардсона. Подобраны на размытии радиусом 1.6.
RESTORE_SIGMA = 1.2
RESTORE_STEPS = 14


@dataclass
class Prepared:
    image: Image.Image
    scale: float
    shadow_fixed: bool
    # Обратная матрица поворота: точка выпрямленного кадра -> точка исходного фото
    matrix: tuple[float, float, float, float, float, float] | None = None


def prepare(image: Image.Image) -> Prepared:
    image = image.convert("RGB")
    softness = _softness(image)
    if softness is not None and softness < SOFT_LAPLACIAN:
        image = _restore(image)
    angle = _skew_angle(image)
    matrix = None
    if angle:
        matrix, _ = _rotation_matrix(image.size, angle)
        image = image.rotate(angle, resample=Image.BICUBIC, expand=True, fillcolor=(255, 255, 255))
    bigger = softness is not None and SOFT_LAPLACIAN <= softness < MILD_LAPLACIAN
    scale = _pick_scale(image.size, bigger=bigger)
    image, scale = _resize(image, scale)
    image, shadow_fixed = _flatten_shadow(image)
    return Prepared(image, scale, shadow_fixed, matrix)


def map_to_page(x: float, y: float, prepared: Prepared) -> tuple[float, float]:
    """Точка на подготовленном кадре -> точка на исходном фото."""
    x /= prepared.scale
    y /= prepared.scale
    matrix = prepared.matrix
    if matrix:
        a, b, c, d, e, f = matrix
        x, y = a * x + b * y + c, d * x + e * y + f
    return x, y


def _resize(image: Image.Image, scale: float) -> tuple[Image.Image, float]:
    if abs(scale - 1.0) < 1e-6:
        return image, 1.0
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    return image.resize(size, Image.LANCZOS), scale


def _rotation_matrix(size: tuple[int, int], angle: float) -> tuple[tuple[float, ...], tuple[int, int]]:
    """Та же матрица, что у PIL.Image.rotate(..., expand=True): из нового кадра в старый."""
    width, height = size
    center = (width / 2, height / 2)
    radians = -math.radians(angle)
    matrix = [
        round(math.cos(radians), 15),
        round(math.sin(radians), 15),
        0.0,
        round(-math.sin(radians), 15),
        round(math.cos(radians), 15),
        0.0,
    ]

    def apply(px: float, py: float) -> tuple[float, float]:
        a, b, c, d, e, f = matrix
        return a * px + b * py + c, d * px + e * py + f

    matrix[2], matrix[5] = apply(-center[0], -center[1])
    matrix[2] += center[0]
    matrix[5] += center[1]
    xs, ys = [], []
    for px, py in ((0, 0), (width, 0), (width, height), (0, height)):
        tx, ty = apply(px, py)
        xs.append(tx)
        ys.append(ty)
    new_width = math.ceil(max(xs)) - math.floor(min(xs))
    new_height = math.ceil(max(ys)) - math.floor(min(ys))
    matrix[2], matrix[5] = apply(-(new_width - width) / 2.0, -(new_height - height) / 2.0)
    return tuple(matrix), (new_width, new_height)


def _skew_angle(image: Image.Image) -> float:
    """Угол, на который надо повернуть кадр, чтобы строки легли горизонтально. 0 — не трогаем."""
    gray = np.asarray(image.convert("L"))
    height, width = gray.shape
    long_side = max(height, width)
    if long_side > 900:
        ratio = 900 / long_side
        gray = cv2.resize(
            gray,
            (max(1, int(width * ratio)), max(1, int(height * ratio))),
            interpolation=cv2.INTER_AREA,
        )
    gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
    edges = cv2.Canny(gray, 40, 120)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, 70)
    if lines is None:
        return 0.0
    angles = []
    for line in lines[:100]:
        deg = float(line[0][1]) * 180.0 / np.pi - 90.0
        if deg > 90:
            deg -= 180
        if deg < -90:
            deg += 180
        if abs(deg) <= 30:
            angles.append(deg)
    if len(angles) < 8:
        return 0.0
    median = float(np.median(angles))
    support = sum(abs(item - median) <= 3 for item in angles)
    if support < max(8, int(0.4 * len(angles))):
        return 0.0
    if abs(median) < 2 or abs(median) > 30:
        return 0.0
    return median


def _is_soft(image: Image.Image) -> bool:
    score = _softness(image)
    return score is not None and score < SOFT_LAPLACIAN


def _softness(image: Image.Image) -> float | None:
    gray = np.asarray(image.convert("L"))
    if float(gray.std()) < 12:
        return None
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _restore(image: Image.Image) -> Image.Image:
    """Люси–Ричардсон: снимает небольшое гауссово размытие. Резкий кадр сюда не приходит."""
    rgb = np.asarray(image.convert("RGB")).astype(np.float32) / 255.0
    size = max(3, int(round(RESTORE_SIGMA * 6)) | 1)
    kernel = cv2.getGaussianKernel(size, RESTORE_SIGMA)
    psf = (kernel @ kernel.T).astype(np.float32)
    psf /= psf.sum()
    flipped = psf[::-1, ::-1]
    planes = []
    for channel in range(3):
        latent = rgb[:, :, channel].copy()
        observed = rgb[:, :, channel]
        for _ in range(RESTORE_STEPS):
            estimate = cv2.filter2D(latent, -1, psf, borderType=cv2.BORDER_REFLECT)
            ratio = observed / np.maximum(estimate, 1e-6)
            latent *= cv2.filter2D(ratio, -1, flipped, borderType=cv2.BORDER_REFLECT)
        planes.append(np.clip(latent, 0, 1))
    return Image.fromarray((np.stack(planes, axis=-1) * 255).astype(np.uint8))


def _pick_scale(size: tuple[int, int], bigger: bool = False) -> float:
    long_side = max(size)
    if bigger and long_side < MAX_LONG_SIDE:
        return min(MAX_LONG_SIDE / long_side, MAX_UPSCALE)
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
