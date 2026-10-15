"""
Мини-страница, чтобы руками проверить всю цепочку до кента.

Это не сайт деканата. Запуск из корня проекта, с .venv:

    streamlit run ui/ocr_check.py

Фото -> строки OCR (печать или трансформер) -> плоский словарь fields
-> answer_question. Словарь тот же, который очередь отдаёт в pipeline.py.
"""
import json
import re
from pathlib import Path

import streamlit as st
from PIL import Image, ImageDraw

from backend.ocr import OcrError, load_document, run_ocr, save_result
from backend.ocr.fields import MISSING, pick_fields
from backend.ocr.marks import find_seals
from backend.pipeline import answer_question

ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "data" / "uploads" / "check"
OUT = ROOT / "data" / "ocr"
SAMPLE = ROOT / "data" / "samples" / "spravka_bad.jpg"
STAMP_SAMPLE = ROOT / "data" / "samples" / "spravka_stamp.jpg"

DOC_TYPES = {
    "Справка об обучении": "study_certificate",
    "Заявление на академический отпуск": "academic_leave",
    "Справка о практике": "practice_certificate",
}
FIELD_LABELS = {
    "student_name": "ФИО",
    "university": "вуз",
    "program": "направление",
    "study_form": "форма обучения",
    "study_start": "начало обучения",
    "study_end": "конец обучения",
    "document_number": "номер",
    "issue_date": "дата выдачи",
    "signature_present": "подпись",
    "seal_present": "печать",
    "group": "группа",
    "course": "курс",
    "leave_reason": "причина отпуска",
    "leave_start": "начало отпуска",
    "leave_end": "конец отпуска",
    "application_date": "дата заявления",
    "organization": "организация",
    "internship_start": "начало практики",
    "internship_end": "конец практики",
    "supervisor_name": "руководитель",
    "grade": "оценка",
}

st.set_page_config(page_title="Проверка OCR", layout="wide")
st.title("Проверка OCR")
st.caption("Фото → строки → плоский словарь fields → answer_question. Это та же передача, что на сайте.")


def draw_boxes(image: Image.Image, lines: list[dict], seals: list[list[int]]) -> Image.Image:
    shown = image.convert("RGB").copy()
    draw = ImageDraw.Draw(shown)
    for line in lines:
        if line.get("source") == "trocr":
            color = (210, 120, 0)
        elif line.get("low_confidence"):
            color = (180, 40, 40)
        else:
            color = (20, 140, 60)
        draw.polygon([tuple(p) for p in line["polygon"]], outline=color, width=3)
    for x, y, box_w, box_h in seals:
        box = (x, y, x + box_w, y + box_h)
        ratio = box_w / max(box_h, 1)
        if 0.75 <= ratio <= 1.35:
            draw.ellipse(box, outline=(20, 80, 220), width=5)
        else:
            draw.rectangle(box, outline=(20, 80, 220), width=5)
    return shown


def recognize(path: Path) -> dict:
    stamp = path.stat().st_mtime
    cached = st.session_state.get("ocr")
    if cached and cached["path"] == str(path) and cached["mtime"] == stamp:
        return cached["result"]
    result = run_ocr(path)
    txt_path, json_path = save_result(result, OUT)
    st.session_state["ocr"] = {
        "path": str(path),
        "mtime": stamp,
        "result": result,
        "txt": txt_path,
        "json": json_path,
    }
    return result


def ask(fields: dict, doc_type: str, question: str) -> dict:
    key = (doc_type, question, json.dumps(fields, ensure_ascii=False, sort_keys=True))
    if st.session_state.get("answer_key") == key:
        return st.session_state["answer"]
    result = answer_question(fields, doc_type, question)
    st.session_state["answer_key"] = key
    st.session_state["answer"] = result
    return result


def _tokens(value: str) -> list[str]:
    text = value.lower().replace("ё", "е")
    return [token for token in re.split(r"[^\w]+", text) if len(token) > 2]


def destinations(line_text: str, fields: dict) -> str:
    """В какие поля строки ушёл кусок текста. Остальное остаётся только в общем тексте."""
    low = line_text.lower().replace("ё", "е")
    hits = []
    for key, value in fields.items():
        if isinstance(value, str) and value != MISSING and _value_in_line(value, low):
            hits.append(key)
    return ", ".join(hits) if hits else "только общий текст"


def _in_seal(line: dict, seals: list[list[int]]) -> bool:
    x, y, box_w, box_h = line["bbox"]
    center_x = x + box_w / 2
    center_y = y + box_h / 2
    return any(
        seal_x <= center_x <= seal_x + seal_w and seal_y <= center_y <= seal_y + seal_h
        for seal_x, seal_y, seal_w, seal_h in seals
    )


def _value_in_line(value: str, low: str) -> bool:
    iso = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", value)
    if iso:
        year, month, day = iso.groups()
        dotted = f"{day}.{month}.{year}"
        return dotted in low or value in low
    tokens = [token for token in _tokens(value) if not re.fullmatch(r"\d{4}", token)]
    if not tokens:
        return value.lower() in low
    return any(token in low or token[: max(4, len(token) - 2)] in low for token in tokens)


def field_rows(fields: dict) -> list[dict]:
    rows = []
    for key, value in fields.items():
        if isinstance(value, bool):
            state = "да" if value else "нет"
        elif value == MISSING:
            state = "не найдено"
        else:
            state = "найдено"
        rows.append({
            "ключ для кента": key,
            "поле": FIELD_LABELS.get(key, key),
            "значение": value,
            "состояние": state,
        })
    return rows


def check(path: Path, doc_type: str, question: str) -> None:
    try:
        with st.spinner("Читаю документ. Первый запуск ещё грузит модели."):
            result = recognize(path)
    except OcrError as e:
        st.error(str(e))
        return

    cached = st.session_state["ocr"]
    saved_txt = cached["txt"].read_text(encoding="utf-8")
    saved_json = json.loads(cached["json"].read_text(encoding="utf-8"))
    if saved_txt == result["text"] + "\n" and saved_json == result:
        st.success(f"Текст и JSON записаны: {cached['txt'].name}, {cached['json'].name}")
    else:
        st.error("Файл на диске не совпал с результатом OCR.")

    pages = load_document(path)[1]
    fields = pick_fields(doc_type, result, [page.image for page in pages])
    with st.spinner("Отдаю словарь в answer_question. Сейчас там заглушка."):
        answer = ask(fields, doc_type, question)

    engine = result["engine"]
    trocr_lines = sum(1 for page in result["pages"] for line in page["lines"] if line.get("source") == "trocr")
    st.write(
        f"Формат: {result['source']['format']}. Страниц: {result['source']['pages']}. "
        f"Чтение {result['timings']['ocr']} с. "
        f"Текст: {engine.get('text_recognition_model_name')}. "
        f"Трансформер: {engine.get('handwriting')}. "
        f"Строк через трансформер: {trocr_lines}. "
        f"Печать на листе: {'да' if fields.get('seal_present') else 'нет'}."
    )
    for warning in result["warnings"]:
        st.warning(warning)

    photo_col, flow_col = st.columns(2)
    index = 0
    with photo_col:
        if len(pages) > 1:
            index = st.selectbox("Страница", range(len(pages)), format_func=lambda i: i + 1)
        page = result["pages"][index]
        seals = find_seals(pages[index].image)
        st.image(
            draw_boxes(pages[index].image, page["lines"], seals),
            caption="Зелёная рамка — строка текста. Оранжевая — её переписал трансформер. "
                    "Красная — модель текста не уверена. Синяя рамка — найденная печать.",
        )
    with flow_col:
        st.subheader("Куда уходит")
        st.markdown(
            f"1. Строки этой страницы: **{len(page['lines'])}**\n"
            f"2. `extract_fields` собирает плоский словарь для типа `{doc_type}`\n"
            f"3. `answer_question(fields, {doc_type!r}, вопрос)` — это уже зона кента"
        )
        st.code(
            "fields = extract_fields(путь, doc_type)\n"
            "result = answer_question(fields, doc_type, question)",
            language="python",
        )
        st.text_area("Общий текст, он не выбрасывается", result["text"], height=220)

    st.subheader("Строки")
    st.dataframe(
        [
            {
                "текст": line["text"],
                "движок": "трансформер" if line.get("source") == "trocr" else "печать текста",
                "уверенность": line["confidence"],
                "куда попало": (
                    "seal_present"
                    if _in_seal(line, seals)
                    else destinations(line["text"], fields)
                ),
            }
            for line in page["lines"]
        ],
        hide_index=True,
        width="stretch",
    )

    st.subheader("Словарь, который уходит кенту")
    st.dataframe(field_rows(fields), hide_index=True, width="stretch")
    st.json(fields)

    st.subheader("Ответ answer_question")
    st.caption("Пока заглушка: статус, текст, источник, answerable и value. Тело функции кент заменит сам.")
    status = answer["status"]
    if status == "ok":
        st.success(answer["message"])
    elif status == "missing":
        st.warning(answer["message"])
    else:
        st.info(answer["message"])
    st.write(
        f"status: `{status}`. value: `{answer['value']}`. "
        f"answerable: `{answer['answerable']}`. sources: {', '.join(answer['sources']) or '—'}"
    )

    fields_dump = json.dumps(fields, ensure_ascii=False, indent=2)
    left, mid, right = st.columns(3)
    left.download_button("Скачать txt", saved_txt, file_name=cached["txt"].name)
    mid.download_button(
        "Скачать json строк",
        json.dumps(saved_json, ensure_ascii=False, indent=2),
        file_name=cached["json"].name,
        mime="application/json",
    )
    right.download_button(
        "Скачать словарь fields",
        fields_dump,
        file_name=f"{path.stem}.fields.json",
        mime="application/json",
    )


def ensure_stamp_sample() -> Path:
    image = Image.open(SAMPLE).convert("RGB")
    draw = ImageDraw.Draw(image)
    draw.ellipse((700, 360, 880, 540), outline=(30, 75, 180), width=8)
    draw.ellipse((745, 405, 835, 495), outline=(30, 75, 180), width=5)
    STAMP_SAMPLE.parent.mkdir(parents=True, exist_ok=True)
    image.save(STAMP_SAMPLE, quality=90)
    return STAMP_SAMPLE


doc_label = st.selectbox("Тип документа", list(DOC_TYPES))
question = st.text_input(
    "Вопрос, он уйдёт в answer_question",
    value="Содержит ли документ все обязательные сведения?",
)
uploaded = st.file_uploader("Документ", type=["jpg", "jpeg", "png", "webp", "pdf"])
sample_col, stamp_col = st.columns(2)
sample = sample_col.button("Проверить на примере", disabled=not SAMPLE.is_file())
stamped = stamp_col.button("Пример с печатью", disabled=not SAMPLE.is_file())

doc_type = DOC_TYPES[doc_label]
target = None
if stamped and SAMPLE.is_file():
    target = ensure_stamp_sample()
elif sample and SAMPLE.is_file():
    target = SAMPLE
elif uploaded is not None:
    INBOX.mkdir(parents=True, exist_ok=True)
    target = INBOX / Path(uploaded.name).name
    target.write_bytes(uploaded.getvalue())
elif st.session_state.get("shown"):
    target = Path(st.session_state["shown"])

if target is not None:
    st.session_state["shown"] = str(target)
    check(target, doc_type, question)
else:
    st.info("Загрузите фото или нажмите пример. «Пример с печатью» — та же справка, на ней синий круглый штамп.")
