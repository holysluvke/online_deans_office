"""
Страница «Онлайн-деканата» (Streamlit). Вся страница пишется на Python: HTML/JS здесь нет.

Файлы интерфейса:
    app.py    - ЭТОТ файл: что показываем и как общаемся с бэкендом
    style.py  - внешний вид (цвета, шрифты, карточки, тёмная тема); логики там нет

Запуск (из корня проекта, бэкенд должен уже работать):
    uvicorn backend.main:app --reload     <- терминал 1
    streamlit run ui/app.py               <- терминал 2

Как работает страница:
    1. Пользователь выбирает тип документа, пишет вопрос, загружает фото.
    2. Кнопка «Отправить» шлёт каждое фото в бэкенд (POST /documents) и запоминает job_id.
    3. Блок «Очередь» каждые 2 секунды спрашивает у бэкенда статус всех задач
       (GET /jobs/{job_id}) и рисует карточки со статусом, прогрессом и ответом.

Streamlit выполняет этот файл ЗАНОВО сверху вниз при каждом действии пользователя.
Поэтому всё, что должно сохраняться между перерисовками, лежит в st.session_state.
"""
import requests
import streamlit as st
from style import render_header
import html

# Адрес бэкенда (uvicorn). Если бэкенд запущен на другом порту или компьютере - менять здесь.
API = "http://127.0.0.1:8000"

# Типы документов: что видит пользователь -> что уходит на бэкенд.
# Значения справа должны совпадать с DOC_TYPES в backend/main.py.
DOC_TYPES = {
    "Справка об обучении": "study_certificate",
    "Заявление на академический отпуск": "academic_leave",
    "Справка о практике": "practice_certificate",
}

# Статусы задачи (приходят с бэкенда из backend/jobs.py) -> подпись на плашке
STATUS_TEXT = {
    "queued": "В очереди",
    "processing": "Обрабатывается",
    "done": "Готово",
    "error": "Ошибка",
}

# Вид ответа: ключ - это result["status"] из backend/pipeline.py (answer_question),
# значение - (цвет, заголовок карточки). Цвета - переменные из ui/style.py.
RESULT_STYLE = {
    "ok": ("var(--ok)", "ДОКУМЕНТ В ПОРЯДКЕ"),
    "missing": ("var(--warn)", "ЧЕГО-ТО НЕ ХВАТАЕТ"),
    "no_answer": ("var(--info)", "ОТВЕТА НЕТ"),
}


# set_page_config должна быть первой командой Streamlit на странице
st.set_page_config(page_title="Онлайн-деканат", page_icon="🎓")

# Подключает стили из style.py и рисует шапку страницы
render_header()

# Память между перезапусками страницы: список номеров наших задач
if "job_ids" not in st.session_state:
    st.session_state.job_ids = []

# ---------- Блок 1: загрузка ----------
st.subheader("1. Загрузите документ")

doc_label = st.selectbox("Тип документа", list(DOC_TYPES))
question = st.text_input("Ваш вопрос", placeholder="Достаточно ли справки для перевода на 2 курс?")
files = st.file_uploader(
    "Фото документа",
    type=["jpg", "jpeg", "png", "webp"],  # только картинки
    accept_multiple_files=True,
)

# Кнопка неактивна, пока нет ни фото, ни вопроса
if st.button("Отправить на проверку", type="primary", disabled=not (files and question)):
    # Бэкенд принимает по одному фото за запрос, поэтому шлём в цикле
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
        if resp.ok:
            # Запоминаем номер задачи - по нему блок ниже будет узнавать статус
            st.session_state.job_ids.append(resp.json()["job_id"])
        else:
            # Бэкенд отклонил файл (например, не картинка): показываем его причину
            st.error(f"{f.name}: {resp.json().get('detail')}")

# ---------- Блок 2: очередь и результаты ----------
st.subheader("2. Очередь и результаты")


def show_result(job: dict) -> None:
    """Рисует карточку ответа и список распознанных полей для готовой задачи."""
    result = job["result"]  # словарь из answer_question: status, message, sources
    color, title = RESULT_STYLE.get(result["status"], ("var(--muted)", "РЕЗУЛЬТАТ"))
    sources = ", ".join(result["sources"])
    # анимацию показываем только при первом появлении результата
    seen = st.session_state.setdefault("seen_results", set())
    fresh = "" if job["job_id"] in seen else "fresh"
    seen.add(job["job_id"])
    # html.escape защищает от того, что текст ответа сломает разметку
    st.markdown(
        f"""<div class="result {fresh}" style="border-left-color:{color}">
        <div class="tag" style="color:{color}">{title}</div>
        {html.escape(result["message"])}
        <div class="src">{"источник: " + html.escape(sources) if sources else ""}</div>
        </div>""",
        unsafe_allow_html=True,
    )
    with st.expander("Распознанные поля"):
        st.json(job["fields"])  # словарь из extract_fields, показываем как есть

@st.fragment(run_every=2)  # этот кусок сам обновляется каждые 2 секунды
def queue_view() -> None:
    """Блок очереди: раз в 2 секунды запрашивает статус каждой задачи у бэкенда и рисует карточки."""
    if not st.session_state.job_ids:
        st.write("Пока пусто. Загрузите документ выше.")
        return
    for job_id in reversed(st.session_state.job_ids):  # новые сверху
        try:
            job = requests.get(f"{API}/jobs/{job_id}", timeout=10).json()
        except requests.RequestException:
            st.error("Нет связи с сервером.")
            return

        # Карточка задачи: имя файла, плашка статуса, линия прогресса.
        # Классы (job, pill, bar...) описаны в style.py; класс "queued/processing/done/error"
        # красит плашку в нужный цвет.
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

# Очищает только список на странице; задачи на бэкенде остаются
if st.session_state.job_ids and st.button("Очистить список"):
    st.session_state.job_ids = []
    st.rerun()
