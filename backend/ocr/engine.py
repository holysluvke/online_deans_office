"""
Движок распознавания: PaddleOCR PP-OCRv5 с русской моделью, на CPU.

Почему PaddleOCR и такие настройки - см. задачу #1:
    - распознаватель eslav_PP-OCRv5_mobile_rec (русский, украинский, белорусский);
    - мобильная модель детекции: серверная на плотных страницах даёт +2 п.п. и вдвое дольше;
    - поворот листа (0/90/180/270) включён: фото боком и вверх ногами;
    - разворот отдельных строк выключен: на печатных договорах модель ошибочно
      крутит половину строк на 180° и выдаёт мусор вместо русского текста;
    - «разглаживание» листа выключено: на CPU оно съедает несколько секунд на страницу.

Модель грузится один раз при первом вызове (первый раз ещё и скачивается, ~100 МБ).
"""
import os
import threading
from pathlib import Path

import numpy as np
from PIL import Image

from backend.ocr.intake import OcrError

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _pick_model_dir() -> None:
    """
    Paddle не открывает модели по пути с кириллицей (C:\\Users\\Иван\\.paddlex).
    Если домашняя папка не латиницей, кладём модели в data/paddlex внутри проекта,
    а если и проект лежит в русской папке - в C:\\Users\\Public\\paddlex.
    Переменную надо выставить ДО первого import paddleocr.
    """
    if os.environ.get("PADDLE_PDX_CACHE_HOME"):
        return
    if str(Path.home()).isascii():
        return
    for candidate in (PROJECT_ROOT / "data" / "paddlex", Path(os.environ.get("PUBLIC", r"C:\Users\Public")) / "paddlex"):
        if str(candidate).isascii():
            os.environ["PADDLE_PDX_CACHE_HOME"] = str(candidate)
            return


_pick_model_dir()
# Иначе при каждом старте PaddleX стучится на сервера моделей, а на защите может не быть сети
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

# Обе модели указаны явно: если задать только одну, PaddleOCR молча игнорирует lang="ru"
# и берёт распознаватель по умолчанию (PP-OCRv6), в котором нет кириллицы
SETTINGS = {
    "text_detection_model_name": "PP-OCRv5_mobile_det",
    "text_recognition_model_name": "eslav_PP-OCRv5_mobile_rec",
    "use_doc_orientation_classify": True,
    "use_doc_unwarping": False,
    "use_textline_orientation": False,
    "text_det_limit_side_len": 1920,
    "text_det_limit_type": "max",
    "text_det_box_thresh": 0.4,
    "text_det_unclip_ratio": 1.8,
    "device": "cpu",
}

# Строки с уверенностью ниже порога остаются в JSON, но не попадают в чистый текст.
# Лучше «не найдено» в карточке, чем выдуманная буква.
MIN_CONFIDENCE = 0.5

_engine = None
_engine_lock = threading.Lock()
_predict_lock = threading.Lock()


def get_engine():
    global _engine
    with _engine_lock:
        if _engine is None:
            try:
                from paddleocr import PaddleOCR
            except ImportError as e:
                raise OcrError("OCR не установлен: pip install -r requirements.txt") from e
            _engine = PaddleOCR(**SETTINGS)
        return _engine


def engine_info() -> dict:
    try:
        import paddleocr
        version = paddleocr.__version__
    except ImportError:
        version = None
    return {"name": "PaddleOCR", "version": version, **SETTINGS}


def recognize(image: Image.Image) -> tuple[list[dict], int]:
    """
    Распознаёт одну страницу. Возвращает (строки, сколько четвертей повернули лист).
    Строки в координатах ПЕРЕДАННОЙ картинки, даже если PaddleOCR развернул лист перед чтением.
    """
    bgr = np.ascontiguousarray(np.asarray(image.convert("RGB"))[:, :, ::-1])
    engine = get_engine()
    # PaddleOCR не потокобезопасен: сайт и скрипт не должны читать одновременно
    with _predict_lock:
        results = engine.predict(bgr)
    if not results:
        return [], 0
    res = results[0]

    turns = _detect_turns(bgr, res)
    texts = res["rec_texts"]
    scores = res["rec_scores"]
    polys = res["rec_polys"]

    lines = []
    for text, score, poly in zip(texts, scores, polys):
        if not str(text).strip():
            continue
        points = [_unrotate(float(x), float(y), bgr.shape, turns) for x, y in np.asarray(poly)]
        lines.append({"text": text, "confidence": float(score), "polygon": points})
    return lines, turns


def _detect_turns(original: np.ndarray, res) -> int:
    """
    На сколько четвертей (np.rot90) PaddleOCR повернул лист перед чтением.
    Сравниваем выход предобработки с четырьмя поворотами оригинала - так не зависим
    от того, в какую сторону модель считает угол.
    """
    pre = res.get("doc_preprocessor_res") if hasattr(res, "get") else None
    if not pre:
        return 0
    out = pre.get("output_img") if hasattr(pre, "get") else None
    if out is None:
        return 0
    out = np.asarray(out)

    best_turns, best_diff = 0, None
    for k in range(4):
        cand = np.rot90(original, k)
        if cand.shape[:2] != out.shape[:2]:
            continue
        diff = np.abs(cand[::16, ::16].astype(np.int16) - out[::16, ::16].astype(np.int16)).mean()
        if best_diff is None or diff < best_diff:
            best_turns, best_diff = k, diff
    return best_turns


def _unrotate(x: float, y: float, shape: tuple, turns: int) -> list[float]:
    """Переводит точку с повёрнутого на np.rot90(img, turns) листа обратно на исходный."""
    height, width = shape[:2]
    # Размеры листа после каждого поворота: 0 - исходный, 1 - после первого и т. д.
    sizes = [(width, height) if i % 2 == 0 else (height, width) for i in range(turns + 1)]
    for step in range(turns, 0, -1):
        prev_width = sizes[step - 1][0]
        x, y = prev_width - 1 - y, x
    return [x, y]
