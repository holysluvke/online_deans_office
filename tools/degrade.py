#!/usr/bin/env python3
"""
Бонус #15: портит снимки, чтобы измерить, как падает точность на плохих фото.

    python tools/degrade.py                      # data/open -> data/degraded/level_0..4
    python tools/degrade.py --levels 0,2,4 --seed 7

Для каждого уровня создаётся готовая папка данных, которую понимает run_batch:

    data/degraded/level_2/documents/<те же имена файлов>
    data/degraded/level_2/documents.json, questions.json, reference_results.json  (копии)

    python tools/run_batch.py --mode ocr --data data/degraded/level_2 --out data/degraded/r2.json

Уровни портят снимок сразу всеми способами (чем выше уровень, тем сильнее):

    уровень  поворот  тень   размытие  масштаб  JPEG-качество
       0       0°      0      0         1.0      без потерь (копия оригинала)
       1       5°      0.15   0.5       0.80     85
       2      10°      0.30   1.0       0.60     70
       3      20°      0.45   1.5       0.45     55
       4      30°      0.60   2.0       0.35     40

Только PNG/JPG/WEBP (PDF не портим). Результат детерминирован: seed + id документа + уровень.
"""
import argparse
import hashlib
import io
import random
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# поворот (градусы), тень (0..1), размытие (радиус), масштаб, качество JPEG
LEVELS = {
    0: (0, 0.00, 0.0, 1.00, None),
    1: (5, 0.15, 0.5, 0.80, 85),
    2: (10, 0.30, 1.0, 0.60, 70),
    3: (20, 0.45, 1.5, 0.45, 55),
    4: (30, 0.60, 2.0, 0.35, 40),
}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
SIDE_FILES = ("documents.json", "questions.json", "reference_results.json")


def add_shadow(img, strength, rng):
    """Градиентная тень поперёк листа в случайном направлении."""
    if strength <= 0:
        return img
    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    h, w = arr.shape[:2]
    angle = rng.uniform(0, 2 * np.pi)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    proj = xs * np.cos(angle) + ys * np.sin(angle)
    proj = (proj - proj.min()) / max(proj.max() - proj.min(), 1e-6)
    ramp = 1.0 - strength * proj
    return Image.fromarray(np.clip(arr * ramp[..., None], 0, 255).astype(np.uint8))


def degrade(img, level, seed_key):
    """Возвращает испорченную копию (RGB). Один и тот же seed_key даёт одно и то же."""
    angle, shadow, blur, scale, quality = LEVELS[level]
    img = img.convert("RGB")
    if level == 0:
        return img
    rng = random.Random(int(hashlib.sha256(seed_key.encode()).hexdigest()[:12], 16))
    img = add_shadow(img, shadow, rng)
    if angle:
        sign = rng.choice((-1, 1))
        img = img.rotate(sign * angle * rng.uniform(0.8, 1.0), expand=True, fillcolor="white", resample=Image.BICUBIC)
    if scale < 1.0:
        img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.BILINEAR)
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    if quality:
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=quality)
        img = Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
    return img


def build_level(src, dst, level, seed):
    docs_src = src / "documents"
    docs_dst = dst / "documents"
    docs_dst.mkdir(parents=True, exist_ok=True)
    count = 0
    for file in sorted(docs_src.iterdir()):
        if file.suffix.lower() not in IMAGE_EXT:
            continue
        with Image.open(file) as opened:
            opened.load()
            out = degrade(opened, level, f"{seed}:{file.stem}:{level}")
        # имя и формат файла сохраняем, чтобы documents.json по-прежнему указывал на него
        target = docs_dst / file.name
        if file.suffix.lower() in (".jpg", ".jpeg"):
            out.save(target, "JPEG", quality=LEVELS[level][4] or 95)
        elif file.suffix.lower() == ".webp":
            out.save(target, "WEBP")
        else:
            out.save(target, "PNG")
        count += 1
    for name in SIDE_FILES:
        if (src / name).is_file():
            shutil.copy2(src / name, dst / name)
    return count


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--src", default="data/open")
    p.add_argument("--dst", default="data/degraded")
    p.add_argument("--levels", default="0,1,2,3,4")
    p.add_argument("--seed", type=int, default=7)
    args = p.parse_args(argv)

    src = Path(args.src) if Path(args.src).is_absolute() else ROOT / args.src
    dst = Path(args.dst) if Path(args.dst).is_absolute() else ROOT / args.dst
    if not (src / "documents").is_dir():
        raise SystemExit(f"Нет папки {src / 'documents'}")
    for level in (int(x) for x in args.levels.split(",")):
        if level not in LEVELS:
            raise SystemExit(f"Нет уровня {level}, доступны {sorted(LEVELS)}")
        n = build_level(src, dst / f"level_{level}", level, args.seed)
        print(f"уровень {level}: {n} снимков -> {dst / f'level_{level}'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
