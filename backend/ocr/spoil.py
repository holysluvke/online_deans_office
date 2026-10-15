"""
Набросок порчи снимка для бонуса «плохие фото».

Поворот до 30°, тень, размытие, понижение разрешения.
График падения точности — когда появится набор документов: field_recall сравнивает поля.
Запуск: python -m backend.ocr.spoil путь/к/фото --out data/spoiled
"""
import argparse
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageFilter


def spoil(
    image: Image.Image,
    *,
    turn: float = 12,
    blur: float = 1.6,
    scale: float = 0.5,
    shadow: float = 0.55,
) -> Image.Image:
    """turn — градусы, не больше 30. scale — доля стороны до обратного растягивания."""
    turn = max(-30.0, min(30.0, turn))
    scale = min(1.0, max(0.2, scale))
    sheet = image.convert("RGB")
    turned = sheet.rotate(turn, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=(255, 255, 255))
    gradient = Image.linear_gradient("L").resize(turned.size)
    darkness = ImageEnhance.Brightness(gradient).enhance(max(0.15, min(shadow, 1.0)))
    shade = Image.merge("RGB", (darkness, darkness, darkness))
    shaded = ImageChops.multiply(turned, shade)
    blurred = shaded.filter(ImageFilter.GaussianBlur(radius=max(0.0, blur)))
    width, height = blurred.size
    small = (
        max(1, int(width * scale)),
        max(1, int(height * scale)),
    )
    return blurred.resize(small, Image.Resampling.BILINEAR).resize((width, height), Image.Resampling.BILINEAR)


def field_recall(expected: dict, got: dict) -> float:
    """Доля совпавших полей. Для будущего графика «до порчи / после»."""
    if not expected:
        return 1.0
    hits = sum(1 for key, value in expected.items() if got.get(key) == value)
    return hits / len(expected)


def main() -> None:
    parser = argparse.ArgumentParser(description="Испортить снимок документа: поворот, тень, размытие, разрешение")
    parser.add_argument("photo", type=Path)
    parser.add_argument("--out", type=Path, default=Path("data/spoiled"))
    parser.add_argument("--turn", type=float, default=12)
    args = parser.parse_args()
    image = Image.open(args.photo)
    args.out.mkdir(parents=True, exist_ok=True)
    target = args.out / f"{args.photo.stem}_spoiled.png"
    spoil(image, turn=args.turn).save(target)
    print(target)


if __name__ == "__main__":
    main()
