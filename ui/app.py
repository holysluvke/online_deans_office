import hashlib
import html
import re
import uuid

import requests
import streamlit as st
from style import asset_uri, render_header, svg

# Сколько последних задач показывать на странице (старые остаются в базе)
MAX_SHOWN = 20

# Сколько файлов можно отправить за один раз. Бэкенд отдельно ограничивает число задач
# посетителя в работе (MAX_ACTIVE_JOBS в backend/main.py), держите числа одинаковыми.
MAX_FILES = 10

API = "http://127.0.0.1:8000"

# Ссылка на текст Положения для подвала и карточек результата (пока заглушка)
POLICY_URL = "#"

DOC_TYPES = {
    "Справка об обучении": "study_certificate",
    "Заявление на академический отпуск": "academic_leave_application",
    "Справка о практике": "internship_certificate",
}
DOC_LABELS = {code: label for label, code in DOC_TYPES.items()}

STATUS_PILL = {
    "queued": "В очереди",
    "processing": "Обрабатывается",
    "done": "Готово",
    "error": "Ошибка",
}

# Поле документа -> (заголовок, подсказка) для сообщения «чего не хватает»
MISSING_TEXT = {
    "issue_date": ("Не хватает даты выдачи", "На справке должна быть указана дата выдачи документа."),
    "application_date": ("Не хватает даты заявления", "На заявлении должна быть указана дата подачи."),
    "stamp": ("Не хватает штампа вуза", "Справка должна быть заверена штампом университета."),
    "seal_present": ("Не хватает штампа вуза", "Документ должен быть заверен печатью или штампом университета."),
    "signature_present": ("Не хватает подписи", "Документ должен быть подписан уполномоченным лицом."),
    "document_number": ("Не хватает номера документа", "На документе должен быть указан его номер."),
    "fio": ("Не найдены ФИО студента", "На документе должны быть указаны фамилия, имя и отчество."),
    "student_name": ("Не найдены ФИО студента", "На документе должны быть указаны фамилия, имя и отчество."),
    "university": ("Не найден университет", "На документе должно быть указано название университета."),
    "program": ("Не найдено направление подготовки", "На документе должно быть указано направление или программа."),
    "study_form": ("Не найдена форма обучения", "На документе должна быть указана форма обучения."),
    "study_start": ("Не найдена дата начала обучения", "На документе должна быть указана дата начала обучения."),
    "study_end": ("Не найдена дата окончания обучения", "На документе должна быть указана дата окончания обучения."),
    "group": ("Не найдена группа", "На документе должна быть указана учебная группа."),
    "course": ("Не найден курс", "На документе должен быть указан курс."),
    "leave_reason": ("Не найдена причина отпуска", "В заявлении должна быть указана причина академического отпуска."),
    "leave_start": ("Не найдена дата начала отпуска", "В заявлении должна быть указана дата начала отпуска."),
    "leave_end": ("Не найдена дата окончания отпуска", "В заявлении должна быть указана дата окончания отпуска."),
    "organization": ("Не найдена организация", "На документе должна быть указана организация, где проходила практика."),
    "internship_start": ("Не найдена дата начала практики", "На документе должна быть указана дата начала практики."),
    "internship_end": ("Не найдена дата окончания практики", "На документе должна быть указана дата окончания практики."),
    "supervisor_name": ("Не найден руководитель практики", "На документе должен быть указан руководитель практики."),
    "grade": ("Не найдена оценка", "На документе должна быть указана оценка или зачёт."),
}


def error_detail(resp: requests.Response) -> str:
    """Причина отказа от бэкенда; если ответ не JSON, то код и текст HTTP-статуса."""
    try:
        return resp.json().get("detail", resp.reason)
    except ValueError:
        return f"{resp.status_code} {resp.reason}"


def fetch_jobs() -> list | None:
    """Список задач посетителя с бэкенда; None, если сервер недоступен."""
    try:
        return requests.get(f"{API}/jobs", params={"session_id": session_id}, timeout=10).json()
    except (requests.RequestException, ValueError):
        return None


def fetch_health() -> dict:
    """Состояние бэкенда из /health (ready, state); пустой словарь, если сервер недоступен или старый и не знает про прогрев."""
    try:
        return requests.get(f"{API}/health", timeout=3).json()
    except (requests.RequestException, ValueError):
        return {}


def plural(n: int, one: str, few: str, many: str) -> str:
    """Склоняет слово по числу: 1 документ, 2 документа, 5 документов."""
    if 10 < n % 100 < 15:
        return many
    return {1: one, 2: few, 3: few, 4: few}.get(n % 10, many)


def html_line(*parts: str) -> str:
    """Склеивает куски HTML в одну строку: пустые строки и отступы Markdown принимает за блок кода."""
    return "".join(p.strip() for p in parts)


st.set_page_config(page_title="Онлайн-деканат", page_icon="🎓", layout="wide")

render_header()

# ---------- Код посетителя ----------
# Регистрации нет: каждому посетителю придумываем случайный код и кладём его в адрес (?s=...).
# Бэкенд показывает только задачи с этим кодом. Обновление страницы историю не теряет,
# а кто откроет ту же ссылку, увидит ту же историю (поэтому ссылкой лучше не делиться).
session_id = st.query_params.get("s", "")
if not re.fullmatch(r"[A-Za-z0-9_-]{16,64}", session_id):  # тот же формат проверяет бэкенд
    session_id = uuid.uuid4().hex
    st.query_params["s"] = session_id


# ---------- Шапка ----------
@st.dialog("Как это работает")
def how_it_works() -> None:
    """Окно с короткой инструкцией."""
    st.markdown(
        "1. **Загрузите** фото или PDF справки либо заявления и напишите вопрос.\n"
        "2. **Дождитесь** проверки: документы обрабатываются по очереди.\n"
        "3. **Посмотрите** результат: что найдено, чего не хватает и на какой пункт Положения это опирается.\n\n"
        "Сервис ничего не принимает и не отклоняет: окончательное решение принимает сотрудник деканата."
    )


with st.container(key="topbar"):
    bar_left, bar_right = st.columns([4, 1], vertical_alignment="center")
    bar_left.markdown(
        html_line('<div class="topbar"><div class="logo">', svg("file_check", 20), "</div>",
                  '<span class="brand-tag">Проверка документов</span></div>'),
        unsafe_allow_html=True,
    )
    with bar_right:
        if st.button("Как это работает", icon=":material/help:", key="help_btn"):
            how_it_works()

# Картинка справа: для светлой темы своя версия (folder_light.webp)
folder_img = asset_uri("folder.webp")
st.markdown(
    html_line(
        '<div class="hero"><div class="hero-text"><h1 class="hero-title">Онлайн-<br>деканат.</h1>',
        '<p class="page-sub">Загрузите справки, дождитесь проверки и узнайте, что нужно исправить в каждом документе.</p></div>',
        (f'<div class="hero-art"><picture><source media="(prefers-color-scheme: light)" srcset="{asset_uri("folder_light.webp") or folder_img}">'
         f'<img src="{folder_img}" alt=""></picture></div></div>') if folder_img else "</div>",
    ),
    unsafe_allow_html=True,
)

# ---------- Шаги: свой блок, обновляется раз в 2 секунды независимо от остальной страницы ----------
stepper_box = st.container()


def render_stepper(n_files: int, jobs: list) -> None:
    """Рисует три шага (загрузка, очередь, результаты) и в каждом пишет, на чём сейчас посетитель."""
    total = len(jobs)
    finished = sum(j["status"] in ("done", "error") for j in jobs)
    done = [j for j in jobs if j["status"] == "done"]
    need_fix = sum(bool(missing_issues(j)) for j in done)

    n = n_files or total
    if n:
        s1 = ("done", f"{n} {plural(n, 'файл загружен', 'файла загружены', 'файлов загружены')}", False)
    else:
        s1 = ("current", "Добавьте документы", False)

    if not total:
        s2 = ("pending", "Появится после отправки", False)
    elif finished == total:
        s2 = ("done", f"Обработка завершена · {finished} из {total}", False)
    else:
        s2 = ("current", f"Идёт проверка · {finished} из {total}", False)

    if not done:
        s3 = ("pending", "Появятся после проверки", False)
    elif need_fix:
        s3 = ("current", f"Нужны исправления · {need_fix} {plural(need_fix, 'документ', 'документа', 'документов')}", True)
    else:
        s3 = ("current", f"Проверено · {len(done)} {plural(len(done), 'документ', 'документа', 'документов')}", True)

    steps = [("Загрузка документов", s1), ("Очередь проверки", s2), ("Результаты", s3)]
    parts = []
    for i, (title, (state, sub, hl)) in enumerate(steps):
        icon_html = svg("check", 14) if state == "done" else f"{i + 1:02d}"  # галочка у пройденных, номер у остальных
        parts.append(html_line(
            f'<div class="step {state}"><div class="step-ic">{icon_html}</div><div>',
            f'<div class="step-t">{title}</div><div class="step-s {"hl" if hl else ""}">{html.escape(sub)}</div></div></div>',
        ))
        if i < len(steps) - 1:
            parts.append('<div class="step-line"></div>')
    st.markdown(f'<div class="stepper">{"".join(parts)}</div>', unsafe_allow_html=True)


# Поле документа -> подпись для списка «Распознанные поля»
FIELD_LABELS = {
    "student_name": "ФИО студента", "university": "Название вуза", "program": "Направление подготовки",
    "study_form": "Форма обучения", "study_start": "Начало обучения", "study_end": "Окончание обучения",
    "document_number": "Номер документа", "issue_date": "Дата выдачи", "group": "Учебная группа", "course": "Курс",
    "leave_reason": "Причина отпуска", "leave_start": "Начало отпуска", "leave_end": "Окончание отпуска",
    "application_date": "Дата заявления", "organization": "Организация", "internship_start": "Начало практики",
    "internship_end": "Окончание практики", "supervisor_name": "Руководитель практики", "grade": "Оценка",
    "signature_present": "Подпись", "seal_present": "Печать",
}
# Флаги подписи и печати: подпись зависит от типа документа
FLAG_LABELS = {
    ("signature_present", "study_certificate"): "Подпись сотрудника",
    ("signature_present", "academic_leave_application"): "Подпись студента",
    ("signature_present", "internship_certificate"): "Подпись руководителя",
    ("seal_present", "study_certificate"): "Печать вуза",
    ("seal_present", "internship_certificate"): "Печать организации",
}


def missing_issues(job: dict) -> list:
    """Чего не хватает на документе: берёт missing_fields из ответа бэкенда, запасной путь - пустые поля."""
    result = job.get("result") or {}
    if result.get("value") != "missing_fields":  # только ответ про комплектность, не про одно поле
        return []
    keys = result.get("missing_fields") or [
        k for k, v in (job.get("fields") or {}).items() if v in ("не найдено", False, None, "")
    ]
    issues = []
    for key in keys:
        title, hint = MISSING_TEXT.get(key, (f"Не найдено: {key}", "Это поле обязательно по Положению."))
        if (title, hint) not in issues:  # stamp и seal_present дают одно и то же сообщение
            issues.append((title, hint))
    return issues


# ---------- Основная часть: слева загрузка, справа очередь и результаты ----------
col_left, col_right = st.columns([1, 1.9], gap="large")


@st.fragment(run_every=2)
def stepper_view() -> None:
    """Шаги: число файлов берёт из загрузчика (его состояние известно до отрисовки), остальное у бэкенда."""
    n_files = len(st.session_state.get(f"uploader_{st.session_state.get('uploader_n', 0)}") or [])
    render_stepper(n_files, fetch_jobs() or [])


with stepper_box:
    stepper_view()

history = fetch_jobs()  # нужна кнопке «Очистить историю»: она неактивна, пока истории нет

with col_left:
    with st.container(key="upload_card"):
        st.markdown(
            '<div id="upload-anchor"></div><div class="card-title">Загрузка документов</div>'
            '<div class="card-desc">Выберите тип документа и добавьте фото или PDF для проверки. До 10 МБ на файл.</div>',
            unsafe_allow_html=True,
        )
        doc_label = st.selectbox("Тип документа", list(DOC_TYPES))
        st.markdown('<div class="field-label"><span>Ваш вопрос</span><span class="opt">Обязательно</span></div>', unsafe_allow_html=True)
        question = st.text_input("Ваш вопрос", label_visibility="collapsed", placeholder="Например: достаточно ли справки для перевода?").strip()
        # Смена ключа сбрасывает загрузчик: так работает «Удалить все»
        uploader_n = st.session_state.setdefault("uploader_n", 0)
        files = st.file_uploader(
            "Фото или PDF документов",
            type=["jpg", "jpeg", "png", "webp", "pdf"],  # картинки и PDF (PDF бэкенд сам превращает в картинку)
            accept_multiple_files=True,
            key=f"uploader_{uploader_n}",
        )

        if files:
            count_col, clear_col = st.columns([1, 1], vertical_alignment="center")
            n = len(files)
            count_col.markdown(f'<div class="upload-count">Загружено {n} {plural(n, "файл", "файла", "файлов")}</div>', unsafe_allow_html=True)
            with clear_col:
                if st.button("Удалить все", key="clear_files"):
                    st.session_state["uploader_n"] = uploader_n + 1
                    st.rerun()

        too_many = len(files) > MAX_FILES
        if too_many:
            st.warning(f"За один раз можно отправить не больше {MAX_FILES} файлов, сейчас выбрано {len(files)}.")

        # Вопрос обязателен: без него ничего не отправляется
        def fingerprint(f) -> str:
            """Отпечаток отправки (содержимое файла + тип документа + вопрос): одинаковый отпечаток значит, что это та же отправка."""
            digest = hashlib.sha256(f.getvalue()).hexdigest()[:16]
            return f"{digest}|{DOC_TYPES[doc_label]}|{question}"

        def already_sent() -> set:
            """Отпечатки отправок, задачи которых ещё есть на сервере (после очистки истории или через час файл можно слать снова)."""
            sent = st.session_state.setdefault("sent", {})  # отпечаток -> номер задачи
            jobs = fetch_jobs()
            if jobs is None:
                return set(sent)  # нет связи с сервером: считаем, что всё отправленное там осталось
            alive = {j["job_id"] for j in jobs}
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
        by_fp = {fingerprint(f): f for f in files} if question else {}
        sent_fps = already_sent() if by_fp else set()
        new_files = {fp: f for fp, f in by_fp.items() if fp not in sent_fps}
        sent_files = {fp: f for fp, f in by_fp.items() if fp in sent_fps}

        # Кнопка активна только если есть что отправлять: повторное нажатие ничего не дублирует.
        # «Отправить повторно» появляется под ней, если файл уже отправлен с этим вопросом.
        send_clicked = st.button("Отправить на проверку", icon=":material/arrow_forward:", disabled=not new_files or too_many, key="send_btn")
        resend_clicked = st.button("Отправить повторно", icon=":material/refresh:", key="resend_btn") if sent_files else False

        # Строка занимает место всегда (текст в ней то есть, то нет), иначе всё, что ниже, прыгает при вводе вопроса
        hint = "Введите вопрос, чтобы отправить документы на проверку." if files and not question else "&nbsp;"
        st.markdown(f'<div class="upload-count upload-hint">{hint}</div>', unsafe_allow_html=True)

        if send_clicked:
            if new_files:  # на случай двойного клика: новое могло уже уйти в предыдущем запуске
                send_files(new_files)
            st.rerun()
        if resend_clicked:
            send_files(sent_files)
            st.rerun()

        for message in st.session_state.pop("send_errors", []):
            st.error(message)

    st.markdown(
        f'<div class="privacy">{svg("shield", 16)}<span>Фото и результаты хранятся 1 час, потом удаляются автоматически.</span></div>',
        unsafe_allow_html=True,
    )
    # Удаляет завершённые задачи этого посетителя вместе с фото; задачи в работе остаются
    if st.button("Очистить историю", icon=":material/delete:", key="clear_hist", disabled=not history):
        try:
            requests.delete(f"{API}/jobs", params={"session_id": session_id}, timeout=10)
        except requests.RequestException:
            st.error("Нет связи с сервером.")
        st.rerun()  # полный перезапуск: кнопка отправки узнает, что отправленного больше нет


def fields_view(job: dict) -> str:
    """Распознанные поля списком: галочка - нашлось, крестик - нет (вместо сырого JSON)."""
    rows = []
    for key, value in (job.get("fields") or {}).items():
        label = FLAG_LABELS.get((key, job.get("doc_type")), FIELD_LABELS.get(key, key))
        if isinstance(value, bool):  # подпись / печать
            found, shown = value, "Есть" if value else "Нет"
        else:
            found = value not in ("не найдено", None, "")
            shown = str(value) if found else "не найдено"  # даты бэкенд уже прислал словами
        rows.append(html_line(
            '<div class="frow">', f'<span class="f-ic {"yes" if found else "no"}">', svg("check" if found else "x", 14), "</span>",
            f'<span class="f-label">{html.escape(label)}</span>',
            f'<span class="f-val{"" if found else " none"}">{html.escape(shown)}</span></div>'))
    return '<div class="fields">' + "".join(rows) + "</div>" if rows else ""


def result_view(job: dict) -> None:
    """Карточка результата одной готовой задачи: вердикт, что не найдено, основание и распознанные поля."""
    result = job["result"] or {}
    status = result.get("status") if result.get("status") in ("ok", "missing", "no_answer") else "no_answer"
    issues = missing_issues(job)
    message = str(result.get("message") or "")
    kind = result.get("value")  # "document_ok" / "missing_fields" / значение поля / None
    raw_sources = [str(s) for s in (result.get("sources") or [])]
    clauses = [s.removeprefix("rule:") for s in raw_sources if not s.startswith("field:")]  # пункты Положения
    source_text = ", ".join(c if c.startswith("п.") else f"п. {c}" for c in clauses)
    from_document = any(s.startswith("field:") for s in raw_sources)  # ответ взят из полей документа

    if status == "missing" and kind == "missing_fields":
        title = "Документ требует исправлений"
        text = ""  # что именно не хватает, видно в списке ниже
        icon_name = "alert"
    elif status == "missing":
        title = "Не найдено в документе"
        text = message
        icon_name = "alert"
    elif status == "ok" and kind == "document_ok":
        title = "Обязательные сведения на месте"
        text = message or "Окончательное решение принимает сотрудник деканата."
        icon_name = "circle_check"
    elif status == "ok":
        title = "Ответ найден"
        text = message
        icon_name = "circle_check"
    else:
        title = "Ответа нет"
        text = message
        icon_name = "circle_alert"

    issues_html = "".join(
        html_line('<div class="issue"><div class="issue-ic">', svg("minus", 16), "</div><div>",
                  f"<b>{html.escape(t)}</b><span>{html.escape(h)}</span></div></div>")
        for t, h in issues
    )
    if source_text or from_document:
        if not source_text:
            phrase = "Основание: данные, распознанные на документе."
        elif issues:
            phrase = f"Эти реквизиты обязательны по {source_text} Положения."
        else:
            phrase = f"Основание: {source_text} Положения."
        source_html = html_line('<div class="source">', svg("book", 16), f"<span>{html.escape(phrase)}</span></div>")
    else:
        source_html = ""

    text_html = f"<span>{html.escape(str(text))}</span>" if text else ""  # пустой текст - без второй строки
    with st.container(key=f"res_{job['job_id']}"):
        st.markdown(
            html_line(
                '<div class="rhead"><span class="rname">', svg("file_image", 18), html.escape(job["filename"]),
                '</span><span class="rtag">Ответ агента</span></div>',
                f'<div class="verdict {status}">', svg(icon_name, 20),
                f"<div><b>{title}</b>{text_html}</div></div>",
                issues_html, source_html,
            ),
            unsafe_allow_html=True,
        )
        with st.expander("Распознанные поля"):
            st.markdown(fields_view(job), unsafe_allow_html=True)


def toggle(flag: str) -> None:
    """Переключает «раскрыто или свёрнуто» для блока (вызывается кнопкой, перерисовывается только очередь с результатами)."""
    st.session_state[flag] = not st.session_state.get(flag, False)


def toggle_button(flag: str, n: int, what: str, visible: int = 1) -> None:
    """Кнопка «Показать все ...» или «Свернуть» под списком; нужна, только если пунктов больше, чем видно в свёрнутом виде."""
    if n <= visible:
        return
    opened = st.session_state.get(flag, False)
    st.button(
        "Свернуть" if opened else f"Показать все {what} ({n})",
        icon=":material/expand_less:" if opened else ":material/expand_more:",
        key=f"{flag}_btn", on_click=toggle, args=(flag,),
    )


def queue_view(jobs: list) -> None:
    """Карточка очереди: строка на документ; в свёрнутом виде видны одна-две, остальные прокручиваются."""
    opened = st.session_state.get("q_open", False)
    n = len(jobs)
    shown_note = f" Показаны последние {MAX_SHOWN} из {n}." if n > MAX_SHOWN else ""
    with st.container(key="queue_card"):
        st.markdown(
            html_line('<div class="card-head"><div class="card-title">Очередь проверки</div>',
                      f'<span class="count-pill">{n} {plural(n, "документ", "документа", "документов")}</span></div>'),
            unsafe_allow_html=True,
        )
        # В свёрнутом виде видно 1 документ, если он один, и 2, если их больше. Ключ задаёт высоту списка в style.py
        visible = 1 if n < 2 else 2
        with st.container(key="qlist_open" if opened else f"qlist_closed{visible}"):
            for job in reversed(jobs[-MAX_SHOWN:]):
                status = job["status"]
                if status == "queued":
                    stat_text = "Ждёт своей очереди"
                elif status == "processing":
                    stat_text = ("Распознаю текст" if job["progress"] < 60 else "Готовлю ответ") + f" · {job['progress']}%"
                elif status == "done":
                    stat_text = "Обработка завершена"
                else:
                    stat_text = "Не удалось обработать"
                pill_icon = svg("check", 12) if status == "done" else ""
                err = f'<div class="qerr">{html.escape(job["error"] or "Неизвестная ошибка")}</div>' if status == "error" else ""
                st.markdown(html_line(
                    f'<div class="qrow {status}"><div class="qicon">', svg("file_check" if status == "done" else "file", 22), "</div>",
                    f'<div><div class="qname">{html.escape(job["filename"])}</div>',
                    f'<div class="qsub">{html.escape(DOC_LABELS.get(job.get("doc_type"), ""))}</div></div>',
                    f'<div class="qside"><span class="pill {status}">{pill_icon}{STATUS_PILL.get(status, status)}</span>',
                    f'<span class="qstat">{stat_text}</span></div>',
                    f'<div class="qbar"><span style="width:{job["progress"]}%"></span></div>{err}</div>',
                ), unsafe_allow_html=True)
        toggle_button("q_open", n, "документы", visible)
        st.markdown(f'<div class="card-note">Решение по каждому документу показано в результатах ниже.{shown_note}</div>', unsafe_allow_html=True)


@st.fragment(run_every=2)  # этот кусок сам обновляется каждые 2 секунды, не трогая форму слева
def live_view() -> None:
    """Раз в 2 секунды берёт у бэкенда задачи посетителя и рисует очередь и результаты, когда им есть что показать."""
    jobs = fetch_jobs()
    if jobs is None:
        st.error("Нет связи с сервером.")
        return
    # Пока в фоне грузятся модели, документы ждут в очереди: объясняем это, а не показываем «ошибку»
    health = fetch_health()
    if health.get("state") == "loading":
        st.markdown(html_line('<div class="model-banner"><div class="spinner"></div><div><b>Модель загружается</b>',
                              "<span>Первая проверка начнётся, как только она будет готова, обычно это до минуты. Документы можно отправлять уже сейчас.</span></div></div>"),
                    unsafe_allow_html=True)
    elif health.get("state") == "failed":
        st.markdown(html_line('<div class="model-banner failed"><div><b>Модель не загрузилась</b>',
                              "<span>Проверка может не сработать. Подробности в логе бэкенда (data/logs/app.log).</span></div></div>"),
                    unsafe_allow_html=True)

    if not jobs:
        with st.container(key="empty_card"):
            st.markdown(
                html_line('<div class="empty"><div class="qicon">', svg("clipboard", 22), "</div>",
                          "<b>Здесь появятся очередь и результаты</b>Добавьте документы и нажмите «Отправить на проверку».</div>"),
                unsafe_allow_html=True,
            )
        return

    queue_view(jobs)

    done = [j for j in jobs if j["status"] == "done"]
    if done:
        need_fix = sum(bool(missing_issues(j)) for j in done)
        side = (f"{need_fix} {plural(need_fix, 'документ требует', 'документа требуют', 'документов требуют')} исправлений"
                if need_fix else f"Проверено: {len(done)}")
        st.markdown(f'<div class="sec-head"><span class="sec-title">Результаты</span><span class="sec-side">{side}</span></div>', unsafe_allow_html=True)
        r_opened = st.session_state.get("r_open", False)
        # Свёрнутый список показывает один результат, остальные прокручиваются (высоту задаёт style.py)
        with st.container(key="rlist_open" if r_opened else "rlist_closed"):
            for job in reversed(done[-MAX_SHOWN:]):
                result_view(job)
        toggle_button("r_open", len(done), "результаты")
        if need_fix:
            with st.container(key="next_card"):
                st.markdown(
                    html_line(
                        '<div class="next-t">Что делать дальше</div>',
                        '<div class="next-p">Исправьте указанные недочёты в документах и загрузите их заново для повторной проверки.</div>',
                        '<a class="cta" href="#upload-anchor" target="_self">', svg("upload", 18), "Загрузить исправленные документы</a>",
                    ),
                    unsafe_allow_html=True,
                )


with col_right:
    live_view()

st.markdown(
    html_line('<div class="footer"><span>Онлайн-деканат · Сервис проверки документов</span>',
              f'<a href="{POLICY_URL}" target="_blank" rel="noopener">Положение о документах ', svg("arrow_ur", 14), "</a></div>"),
    unsafe_allow_html=True,
)
