"""
Мини-страница, чтобы руками проверить OCR: текст, JSON и рамки на фото.

Это не сайт деканата, а проверка задачи #2. Запуск из корня проекта, с .venv:

    streamlit run ui/ocr_check.py

Страница берёт файл, вызывает run_ocr, пишет txt и json через save_result,
читает файлы обратно и показывает, совпали ли они с результатом в памяти.
"""
import json
from pathlib import Path

import streamlit as st
from PIL import Image, ImageDraw

from backend.ocr import OcrError, load_document, run_ocr, save_result

ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "data" / "uploads" / "check"
OUT = ROOT / "data" / "ocr"
SAMPLE = ROOT / "data" / "samples" / "spravka_bad.jpg"

st.set_page_config(page_title="Проверка OCR", layout="wide")
st.title("Проверка OCR")
st.caption("Загрузите фото или PDF. Страница распознает текст, запишет txt и json и сверит файлы с результатом.")


def draw_boxes(image: Image.Image, lines: list[dict]) -> Image.Image:
    shown = image.convert("RGB").copy()
    draw = ImageDraw.Draw(shown)
    for line in lines:
        color = (210, 120, 0) if line["low_confidence"] else (20, 140, 60)
        draw.polygon([tuple(p) for p in line["polygon"]], outline=color, width=3)
    return shown


def check(path: Path) -> None:
    try:
        with st.spinner("Читаю документ. Первый запуск ещё грузит модель, это около минуты."):
            result = run_ocr(path)
            txt_path, json_path = save_result(result, OUT)
    except OcrError as e:
        st.error(str(e))
        return

    saved_txt = txt_path.read_text(encoding="utf-8")
    saved_json = json.loads(json_path.read_text(encoding="utf-8"))
    txt_ok = saved_txt == result["text"] + "\n"
    json_ok = saved_json == result

    if txt_ok and json_ok:
        st.success(f"Файлы записаны и совпали с результатом: {txt_path.name} и {json_path.name}")
    else:
        st.error("Файл на диске не совпал с тем, что вернул OCR. txt: "
                 + ("совпал" if txt_ok else "НЕ совпал")
                 + ", json: " + ("совпал" if json_ok else "НЕ совпал"))

    meta = result["source"]
    st.write(
        f"Формат: {meta['format']}. Страниц: {meta['pages']}. "
        f"Чтение заняло {result['timings']['ocr']} с."
    )
    if result["warnings"]:
        for warning in result["warnings"]:
            st.warning(warning)

    pages = load_document(path)[1]
    index = 0
    if len(pages) > 1:
        index = st.selectbox("Страница", range(len(pages)), format_func=lambda i: i + 1)

    page = result["pages"][index]
    photo, text = st.columns(2)
    with photo:
        st.image(
            draw_boxes(pages[index].image, page["lines"]),
            caption=f"Поворот {page['rotation']}°. Тень выровнена: {'да' if page['shadow_fixed'] else 'нет'}. "
                    "Зелёная рамка — строка в тексте, оранжевая — уверенность ниже 0.5, в текст не попала.",
        )
    with text:
        st.subheader("Текст из файла")
        st.text(saved_txt or "(пусто)")

    st.subheader("Строки")
    st.dataframe(
        [
            {
                "текст": line["text"],
                "уверенность": line["confidence"],
                "в текст": "нет" if line["low_confidence"] else "да",
                "рамка": line["bbox"],
            }
            for line in page["lines"]
        ],
        hide_index=True,
        width="stretch",
    )

    with st.expander("JSON из файла"):
        st.json(saved_json, expanded=False)

    left, right = st.columns(2)
    left.download_button("Скачать txt", saved_txt, file_name=txt_path.name)
    right.download_button(
        "Скачать json",
        json.dumps(saved_json, ensure_ascii=False, indent=2),
        file_name=json_path.name,
        mime="application/json",
    )


uploaded = st.file_uploader("Документ", type=["jpg", "jpeg", "png", "webp", "pdf"])
sample = st.button("Проверить на примере", disabled=not SAMPLE.is_file())

if uploaded is not None:
    INBOX.mkdir(parents=True, exist_ok=True)
    path = INBOX / Path(uploaded.name).name
    path.write_bytes(uploaded.getvalue())
    check(path)
elif sample:
    check(SAMPLE)
else:
    st.info("Пока ничего не загружено. Можно нажать «Проверить на примере»: это справка с наклоном и тенью.")
