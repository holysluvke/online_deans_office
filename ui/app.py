import requests
import streamlit as st
from style import render_header
import hashlib
import html
import re
import uuid

# Сколько последних задач показывать на странице (старые остаются в базе)
MAX_SHOWN = 20

# Сколько файлов можно отправить за один раз. Бэкенд отдельно ограничивает число задач
# посетителя в работе (MAX_ACTIVE_JOBS в backend/main.py), держите числа одинаковыми.
MAX_FILES = 10

API = "http://127.0.0.1:8000"

DOC_TYPES = {
    "Справка об обучении": "study_certificate",
    "Заявление на академический отпуск": "academic_leave_application",
    "Справка о практике": "internship_certificate",
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


def error_detail(resp: requests.Response) -> str:
    """Причина отказа от бэкенда; если ответ не JSON, то код и текст HTTP-статуса."""
    try:
        return resp.json().get("detail", resp.reason)
    except ValueError:
        return f"{resp.status_code} {resp.reason}"


st.set_page_config(page_title="Онлайн-деканат", page_icon="🎓")

render_header()

# ---------- Код посетителя ----------
# Регистрации нет: каждому посетителю придумываем случайный код и кладём его в адрес (?s=...).
# Бэкенд показывает только задачи с этим кодом. Обновление страницы историю не теряет,
# а кто откроет ту же ссылку, увидит ту же историю (поэтому ссылкой лучше не делиться).
session_id = st.query_params.get("s", "")
if not re.fullmatch(r"[A-Za-z0-9_-]{16,64}", session_id):  # тот же формат проверяет бэкенд
    session_id = uuid.uuid4().hex
    st.query_params["s"] = session_id

# ---------- Блок «Загрузка документов» (виден всегда) ----------
st.subheader("Загрузка документов")

doc_label = st.selectbox("Тип документа", list(DOC_TYPES))
question = st.text_input("Ваш вопрос", placeholder="Достаточно ли справки для перевода на 2 курс?")
files = st.file_uploader(
    "Фото или PDF документа",
    type=["jpg", "jpeg", "png", "webp", "pdf"],  # картинки и PDF (PDF бэкенд сам превращает в картинку)
    accept_multiple_files=True,
)

too_many = len(files) > MAX_FILES
if too_many:
    st.warning(f"За один раз можно отправить не больше {MAX_FILES} файлов, сейчас выбрано {len(files)}.")


def fingerprint(f) -> str:
    """Отпечаток отправки (содержимое файла + тип документа + вопрос): одинаковый отпечаток значит, что это та же отправка."""
    digest = hashlib.sha256(f.getvalue()).hexdigest()[:16]
    return f"{digest}|{DOC_TYPES[doc_label]}|{question.strip()}"


def already_sent() -> set:
    """Отпечатки отправок, задачи которых ещё есть на сервере (после очистки истории или через час файл можно слать снова)."""
    sent = st.session_state.setdefault("sent", {})  # отпечаток -> номер задачи
    try:
        jobs = requests.get(f"{API}/jobs", params={"session_id": session_id}, timeout=10).json()
        alive = {j["job_id"] for j in jobs}
    except (requests.RequestException, ValueError, TypeError, KeyError):
        return set(sent)  # нет связи с сервером: считаем, что всё отправленное там осталось
    return {fp for fp, job_id in sent.items() if job_id in alive}


def send_files(batch: dict) -> None:
    """Отправляет файлы на бэкенд (batch: отпечаток -> файл), запоминает номера задач, а причины отказов откладывает для показа."""
    # Обращаемся к st.session_state один раз до цикла: Streamlit может прервать скрипт при очередном своём вызове
    # (например, при быстром втором клике), и тогда уже отправленный файл остался бы незаписанным и ушёл бы второй раз
    sent = st.session_state.setdefault("sent", {})
    errors = st.session_state.setdefault("send_errors", [])
    for fp, f in batch.items():
        try:
            resp = requests.post(
                f"{API}/documents",
                files={"file": (f.name, f.getvalue(), f.type)},
                data={"doc_type": DOC_TYPES[doc_label], "question": question, "session_id": session_id},
                timeout=30,
            )
        except requests.RequestException:
            errors.append("Не удалось связаться с сервером. Запущен ли uvicorn?")
            break
        if resp.ok:
            sent[fp] = resp.json()["job_id"]
        else:
            # Бэкенд отклонил файл (не картинка и не PDF, слишком большой, очередь заполнена): показываем причину
            errors.append(f"{f.name}: {error_detail(resp)}")


# Делим выбранные файлы на новые и уже отправленные с этим же вопросом и типом документа.
# Одинаковые файлы внутри одного выбора считаем одним.
by_fp = {fingerprint(f): f for f in files} if question.strip() else {}
sent_fps = already_sent() if by_fp else set()
new_files = {fp: f for fp, f in by_fp.items() if fp not in sent_fps}
sent_files = {fp: f for fp, f in by_fp.items() if fp in sent_fps}

# Кнопка активна только если есть что отправлять: повторное нажатие ничего не дублирует
if st.button("Отправить на проверку", type="primary", disabled=not new_files or too_many):
    if new_files:  # на случай двойного клика: новое могло уже уйти в предыдущем запуске
        send_files(new_files)
    st.rerun()

for message in st.session_state.pop("send_errors", []):
    st.error(message)

if sent_files:
    if st.button("Отправить повторно?"):
        send_files(sent_files)
        st.rerun()

# ---------- Блоки «Очередь проверки» и «Результаты» ----------
# Появляются по шагам: очередь, когда у посетителя есть хотя бы одна задача, результаты, когда
# готова хотя бы одна. Рисуются внутри одного фрагмента: он сам обновляется раз в 2 секунды,
# не трогая форму загрузки выше (файлы и вопрос не сбрасываются).


def show_result(job: dict) -> None:
    """Рисует карточку результата одной готовой задачи (вердикт, источник и распознанные поля)."""
    result = job["result"] or {}
    color, title = RESULT_STYLE.get(result.get("status"), ("var(--muted)", "РЕЗУЛЬТАТ"))
    sources = ", ".join(map(str, result.get("sources") or []))
    # анимацию показываем только при первом появлении результата
    seen = st.session_state.setdefault("seen_results", set())
    fresh = "" if job["job_id"] in seen else "fresh"
    seen.add(job["job_id"])
    st.markdown(
        f"""<div class="result {fresh}" style="border-left-color:{color}">
        <div class="tag" style="color:{color}">{title} · {html.escape(job['filename'])}</div>
        {html.escape(str(result.get("message", "")))}
        <div class="src">{"источник: " + html.escape(sources) if sources else ""}</div>
        </div>""",
        unsafe_allow_html=True,
    )
    with st.expander("Распознанные поля"):
        st.json(job["fields"])


def stage_text(job: dict) -> str:
    """Подпись этапа по статусу и прогрессу (прогресс задаёт backend/jobs.py: 10 - OCR, 60 - поиск ответа)."""
    if job["status"] == "queued":
        return "Ждёт своей очереди"
    if job["progress"] < 60:
        return "Распознаю текст на документе"
    return "Сверяю с Положением и готовлю ответ"


def stage_html(job: dict) -> str:
    """Строка «этап + процент» для документа в работе; у готовых и упавших пустая."""
    if job["status"] not in ("queued", "processing"):
        return ""
    percent = f"{job['progress']}%" if job["status"] == "processing" else ""
    return f'<div class="stage"><span>{stage_text(job)}</span><span>{percent}</span></div>'


def show_queue(jobs: list) -> None:
    """Рисует карточки очереди: имя файла, статус и полоса прогресса (ошибки показываются здесь же)."""
    st.subheader("Очередь проверки")
    # Срок совпадает с JOB_TTL_MINUTES в backend/cleanup.py
    st.caption("Фото и результаты хранятся час, потом удаляются автоматически.")
    if len(jobs) > MAX_SHOWN:
        st.caption(f"Показаны последние {MAX_SHOWN} из {len(jobs)}")
    for job in reversed(jobs[-MAX_SHOWN:]):
        # HTML одной строкой без отступов и пустых строк: иначе Markdown примет его за блок кода
        st.markdown(
            f'<div class="job {job["status"]}">'
            f'<div class="job-top"><span class="name">{html.escape(job["filename"])}</span>'
            f'<span class="pill">{STATUS_TEXT.get(job["status"], job["status"])}</span></div>'
            f'{stage_html(job)}'
            f'<div class="bar"><span style="width:{job["progress"]}%"></span></div></div>',
            unsafe_allow_html=True,
        )
        if job["status"] == "error":
            st.error(job["error"] or "Неизвестная ошибка")


@st.fragment(run_every=2)  # этот кусок сам обновляется каждые 2 секунды
def live_view() -> None:
    """Раз в 2 секунды берёт у бэкенда задачи посетителя и показывает блоки очереди и результатов, когда им есть что показать."""
    try:
        jobs = requests.get(f"{API}/jobs", params={"session_id": session_id}, timeout=10).json()
    except (requests.RequestException, ValueError):
        st.error("Нет связи с сервером.")
        return
    if not jobs:
        return  # ничего не отправлено: показываем только блок загрузки

    show_queue(jobs)

    done = [j for j in jobs if j["status"] == "done"]
    if done:
        st.subheader("Результаты")
        for job in reversed(done[-MAX_SHOWN:]):
            show_result(job)

    # Удаляет завершённые задачи этого посетителя вместе с фото; задачи в работе остаются
    if st.button("Очистить историю"):
        try:
            requests.delete(f"{API}/jobs", params={"session_id": session_id}, timeout=10)
        except requests.RequestException:
            st.error("Нет связи с сервером.")
        st.rerun()  # полный перезапуск: кнопка отправки узнает, что отправленного больше нет


live_view()
