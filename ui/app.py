import requests
import streamlit as st
from style import render_header
import html

# Сколько последних задач показывать на странице (старые остаются в базе)
MAX_SHOWN = 20

API = "http://127.0.0.1:8000"

DOC_TYPES = {
    "Справка об обучении": "study_certificate",
    "Заявление на академический отпуск": "academic_leave",
    "Справка о практике": "practice_certificate",
}
STATUS_TEXT = {
    "queued": "В очереди",
    "processing": "Обрабатывается",
    "done": "Готово",
    "error": "Ошибка",
}
#фронт
RESULT_STYLE = {
    "ok": ("var(--ok)", "ДОКУМЕНТ В ПОРЯДКЕ"),
    "missing": ("var(--warn)", "ЧЕГО-ТО НЕ ХВАТАЕТ"),
    "no_answer": ("var(--info)", "ОТВЕТА НЕТ"),
}


st.set_page_config(page_title="Онлайн-деканат", page_icon="🎓")

render_header()

# ---------- Блок 1: загрузка ----------
st.subheader("1. Загрузите документ")

doc_label = st.selectbox("Тип документа", list(DOC_TYPES))
question = st.text_input("Ваш вопрос", placeholder="Достаточно ли справки для перевода на 2 курс?")
files = st.file_uploader(
    "Фото документа",
    type=["jpg", "jpeg", "png", "webp"],  # только картинки
    accept_multiple_files=True,
)

if st.button("Отправить на проверку", type="primary", disabled=not (files and question)):
    for f in files:
        try:
            resp = requests.post(
                f"{API}/documents",
                files={"file": (f.name, f.getvalue(), f.type)},
                data={"doc_type": DOC_TYPES[doc_label], "question": question},
                timeout=30,
            )
        except requests.RequestException:
            st.error("Не удалось связаться с сервером. Запущен ли uvicorn?")
            break
        if not resp.ok:
            # Бэкенд отклонил файл (например, не картинка): показываем его причину
            st.error(f"{f.name}: {resp.json().get('detail')}")

# ---------- Блок 2: очередь и результаты ----------
st.subheader("2. Очередь и результаты")


def show_result(job: dict) -> None:
    result = job["result"]
    color, title = RESULT_STYLE.get(result["status"], ("var(--muted)", "РЕЗУЛЬТАТ"))
    sources = ", ".join(result["sources"])
    # анимацию показываем только при первом появлении результата
    seen = st.session_state.setdefault("seen_results", set())
    fresh = "" if job["job_id"] in seen else "fresh"
    seen.add(job["job_id"])
    st.markdown(
        f"""<div class="result {fresh}" style="border-left-color:{color}">
        <div class="tag" style="color:{color}">{title}</div>
        {html.escape(result["message"])}
        <div class="src">{"источник: " + html.escape(sources) if sources else ""}</div>
        </div>""",
        unsafe_allow_html=True,
    )
    with st.expander("Распознанные поля"):
        st.json(job["fields"])

@st.fragment(run_every=2)  # этот кусок сам обновляется каждые 2 секунды
def queue_view() -> None:
    """Блок очереди: раз в 2 секунды берёт у бэкенда список задач и рисует карточки."""
    try:
        jobs = requests.get(f"{API}/jobs", timeout=10).json()
    except requests.RequestException:
        st.error("Нет связи с сервером.")
        return
    if not jobs:
        st.write("Пока пусто. Загрузите документ выше.")
        return
    if len(jobs) > MAX_SHOWN:
        st.caption(f"Показаны последние {MAX_SHOWN} из {len(jobs)}")
    for job in reversed(jobs[-MAX_SHOWN:]):
        st.markdown(
            f"""<div class="job {job['status']}">
                <div class="job-top">
                    <span class="name">{html.escape(job['filename'])}</span>
                    <span class="pill">{STATUS_TEXT[job['status']]}</span>
                </div>
                <div class="bar"><span style="width:{job['progress']}%"></span></div>
            </div>""",
            unsafe_allow_html=True,
        )
        if job["status"] == "done":
            show_result(job)
        elif job["status"] == "error":
            st.error(job["error"])


queue_view()
# Удаляет завершённые задачи из базы вместе с фото; задачи в работе остаются
if st.button("Очистить историю"):
    try:
        requests.delete(f"{API}/jobs", timeout=10)
    except requests.RequestException:
        st.error("Нет связи с сервером.")
    st.rerun()
