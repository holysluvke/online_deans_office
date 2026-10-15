"""
Внешний вид страницы: цвета, шрифт, карточки, шаги, кнопки, светлая и тёмная темы, иконки.
Логики здесь почти нет: она в app.py. Здесь CSS, набор иконок и скрипт перетаскивания файлов,
которые app.py подключает одной командой render_header() в начале страницы.

Как это устроено:
    - Streamlit сам не умеет рисовать такие карточки, поэтому мы добавляем блок CSS (строка CSS ниже)
      через st.markdown. Контейнеры с key="..." получают класс st-key-<key>, по нему их и красим.
    - Все цвета лежат переменными в блоке :root. Меняешь цвет там, и он меняется везде.
    - Основная тема тёмная (как в макете). Светлая включается по настройке системы.
    - Иконки это SVG-строки в словаре ICONS; svg("имя") вставляет их в HTML.
"""
import streamlit as st
import streamlit.components.v1 as components

# Иконки (набор Lucide), рисуются линией текущего цвета текста
ICONS = {
    "cap": '<path d="M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z"/><path d="M22 10v6"/><path d="M6 12.5V16a6 3 0 0 0 12 0v-3.5"/>',
    "help": '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "file_check": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="m9 15 2 2 4-4"/>',
    "file": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>',
    "file_image": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><circle cx="10" cy="13" r="2"/><path d="m20 17-1.1-1.1a2 2 0 0 0-2.8 0L10 22"/>',
    "clipboard": '<rect width="8" height="4" x="8" y="2" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="M12 11h4"/><path d="M12 16h4"/><path d="M8 11h.01"/><path d="M8 16h.01"/>',
    "shield": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
    "book": '<path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/>',
    "arrow_ur": '<path d="M7 7h10v10"/><path d="M7 17 17 7"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "circle_check": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    "circle_alert": '<circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/>',
    "minus": '<path d="M5 12h14"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/>',
    "list": '<path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M3 6h.01"/><path d="M3 12h.01"/><path d="M3 18h.01"/>',
}


def svg(name: str, size: int = 18) -> str:
    """Возвращает иконку как встроенный SVG заданного размера (цвет берёт из CSS color)."""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
            f'aria-hidden="true">{ICONS[name]}</svg>')


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ---------- палитра: тёмная тема (основная, как в макете) ----------
   Все цвета меняются здесь, в одном месте. */
:root {
    --bg: #0D111B;          /* фон страницы */
    --card: #151B28;        /* карточки */
    --field: #101622;       /* поля ввода, зона загрузки, вложенные блоки */
    --raised: #1B2333;      /* кнопки, строки файлов, плашки */
    --line: #2A3345;        /* границы */
    --text: #F1F3FA;
    --text2: #B2BCD0;       /* второстепенный текст */
    --muted: #8591AA;       /* подписи */
    --accent: #6266DC;      /* главная кнопка */
    --accent-text: #808BFA; /* акцентный текст и иконки */
    --accent-soft: #222744; /* фон под акцентной иконкой */
    --ok: #7BCEAE;  --ok-bg: rgba(76, 214, 160, .14);
    --warn: #E8BC78; --warn-bg: #30291F;
    --info: #808BFA; --info-bg: #222744;
    --err: #FF8E8E;  --err-bg: rgba(255, 123, 123, .12);
    --bar: var(--accent-text);
    --shadow: none;
}

/* ---------- палитра: светлая тема (включается по настройке системы) ---------- */
@media (prefers-color-scheme: light) {
    :root {
        --bg: #F4F5FA; --card: #FFFFFF; --field: #F6F7FB; --raised: #EEF0F7; --line: #DCE0EC;
        --text: #141826; --text2: #4A5268; --muted: #727A91;
        --accent: #4F53D8; --accent-text: #4F53D8; --accent-soft: #E6E8FB;
        --ok: #15805A; --ok-bg: #E3F5EC; --warn: #9A6410; --warn-bg: #FBF1DC;
        --info: #4F53D8; --info-bg: #E6E8FB; --err: #C23A3A; --err-bg: #FBE7E7;
        --shadow: 0 1px 2px rgba(20,24,38,.04);
    }
}

/* ---------- базовое ---------- */
#MainMenu, footer, header, [data-testid="stHeader"], [data-testid="stToolbar"] {display: none !important;}
[data-testid="stHeaderActionElements"] {display: none;}
[data-testid="stAppViewContainer"], .stApp {background: var(--bg) !important;}
[data-testid="stMainBlockContainer"] {max-width: 1160px !important; padding: 0 2rem 2rem !important;}
.stApp, .stApp p, .stApp label, .stApp li, .stApp small, .stApp input, .stApp textarea,
.stApp button, .stApp [data-testid="stMarkdownContainer"],
.stApp span:not([data-testid="stIconMaterial"]) {font-family: 'Inter', sans-serif !important;}
.stApp {color: var(--text);}
[data-testid="stVerticalBlock"] {gap: 1rem;}
.stApp svg {flex: none;}

/* ---------- верхняя полоса ---------- */
.topbar {display: flex; align-items: center; gap: 14px; height: 60px;}
.logo {width: 36px; height: 36px; border-radius: 10px; background: var(--accent-soft); color: var(--accent-text);
       display: grid; place-items: center;}
.brand {font-size: 1.15rem; font-weight: 500; letter-spacing: -.01em; color: var(--text);}
.brand-sub {font-size: .8rem; color: var(--muted); border-left: 1px solid var(--line); padding-left: 14px; line-height: 1;}
.st-key-topbar {position: relative; margin-bottom: 4px;}
.st-key-topbar::after {content: ""; position: absolute; left: 50%; bottom: 0; width: 100vw; transform: translateX(-50%);
                       border-bottom: 1px solid var(--line);}
.st-key-topbar [data-testid="stVerticalBlock"] {gap: 0;}
.st-key-help_btn button {background: transparent !important; border: 0 !important; color: var(--text2) !important;
                         box-shadow: none !important; justify-content: flex-end;}
.st-key-help_btn button:hover {color: var(--text) !important;}
.st-key-help_btn {width: 100%; display: flex; justify-content: flex-end;}
.st-key-help_btn [data-testid="stButton"] {width: auto;}

/* ---------- заголовок страницы ---------- */
.page-title {font-size: 2rem; font-weight: 400; letter-spacing: -.02em; line-height: 1.2; margin: 28px 0 8px; color: var(--text);}
.page-sub {color: var(--text2); font-size: .95rem; margin: 0 0 22px;}

/* ---------- шаги ---------- */
.stepper {display: flex; align-items: center; gap: 16px; margin: 0 0 26px;}
.step {display: flex; align-items: center; gap: 12px; min-width: 0;}
.step-ic {width: 36px; height: 36px; border-radius: 50%; display: grid; place-items: center; flex: none;
          background: var(--raised); color: var(--text2);}
.step.current .step-ic {background: var(--accent-soft); color: var(--accent-text);}
.step.pending .step-ic {opacity: .6;}
.step-t {font-size: .85rem; font-weight: 600; color: var(--text); line-height: 1.3;}
.step-s {font-size: .75rem; color: var(--muted); line-height: 1.3;}
.step.current .step-s.hl {color: var(--accent-text);}
.step-line {flex: 1; height: 1px; background: var(--line); min-width: 24px;}

/* ---------- карточки ---------- */
.st-key-upload_card, .card, [class*="st-key-res_"], .st-key-next_card, .st-key-empty_card {
    background: var(--card); border: 1px solid var(--line) !important; border-radius: 16px;
    padding: 22px 24px !important; box-shadow: var(--shadow);}
.card {padding: 22px 24px; margin-bottom: 1rem;}
.card-head {display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;}
.card-title {font-size: 1.25rem; font-weight: 600; letter-spacing: -.01em; color: var(--text); margin: 0;}
.card-desc {font-size: .85rem; color: var(--text2); line-height: 1.5; margin: 6px 0 4px;}
.count-pill {background: var(--raised); color: var(--text2); font-size: .72rem; font-weight: 600; padding: 4px 12px; border-radius: 999px;}
.card-note {font-size: .78rem; color: var(--muted); margin-top: 14px;}
.sec-head {display: flex; justify-content: space-between; align-items: baseline; margin: 8px 0 0;}
.sec-title {font-size: 1.25rem; font-weight: 600; color: var(--text);}
.sec-side {font-size: .8rem; color: var(--muted);}
.privacy {display: flex; gap: 10px; color: var(--muted); font-size: .75rem; line-height: 1.5; padding: 0 8px;}
.privacy svg {margin-top: 2px;}

/* ---------- подписи полей ---------- */
.stApp label p, [data-testid="stWidgetLabel"] p {font-size: .8rem !important; color: var(--text2) !important; font-weight: 500;}
.field-label {display: flex; justify-content: space-between; font-size: .8rem; color: var(--text2); font-weight: 500; margin-bottom: 2px; line-height: 1.2;}
.field-label .opt {color: var(--muted); font-weight: 400;}

/* ---------- поля ввода ---------- */
[data-testid="stTextInput"] input, [data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stSelectbox"] [role="group"], [data-testid="stSelectbox"] input {background: var(--field) !important; color: var(--text) !important;}
[data-testid="stTextInput"] > div > div, [data-testid="stSelectbox"] [data-baseweb="select"] > div {
    background: var(--field) !important; border: 1px solid var(--line) !important; border-radius: 10px !important;}
[data-testid="stTextInput"] input::placeholder {color: var(--muted);}

/* ---------- зона загрузки ---------- */
[data-testid="stFileUploaderDropzone"] {
    background: var(--field); border: 1.5px dashed var(--line); border-radius: 14px; padding: 28px 16px;
    display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; cursor: pointer;}
[data-testid="stFileUploaderDropzone"]:hover {border-color: var(--accent-text);}
/* настоящую кнопку и английские подписи прячем: клик по всей зоне и так открывает окно выбора файлов */
[data-testid="stFileUploaderDropzone"] > span {display: none;}
[data-testid="stFileUploaderDropzoneInstructions"] > div {display: none;}
[data-testid="stFileUploaderDropzoneInstructions"] {
    display: flex; flex-direction: column; align-items: center; gap: 4px; padding-top: 44px; position: relative;
    background: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 24 24' fill='none' stroke='%23808BFA' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><path d='M12 13v8'/><path d='M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242'/><path d='m8 17 4-4 4 4'/></svg>") top center / 32px no-repeat;}
[data-testid="stFileUploaderDropzoneInstructions"]::before {content: "Перетащите файлы сюда"; color: var(--text); font-size: .85rem; font-weight: 500;}
[data-testid="stFileUploaderDropzoneInstructions"]::after {content: "или выберите на устройстве"; color: var(--accent-text); font-size: .8rem; font-weight: 500;}
/* когда файлы выбраны, Streamlit показывает их внутри зоны: оформляем как строки списка */
[data-testid="stFileUploaderDropzone"]:has([data-testid="stFileChips"]) {padding: 10px; align-items: stretch; text-align: left; cursor: default;}
[data-testid="stFileChips"], [data-testid="stFileChips"] * {text-align: left;}
[data-testid="stFileChips"] > div {display: flex; flex-direction: column; align-items: stretch; gap: 8px;}
[data-testid="stFileChips"] > div > div {display: flex; flex-direction: column; gap: 8px;}
[data-testid="stFileChip"] {display: flex !important; align-items: center; gap: 12px; background: var(--raised) !important;
                            border: 0; border-radius: 10px !important; padding: 10px 12px !important; width: 100%;}
[data-testid="stFileChip"] > div:first-child {width: 36px; height: 36px; border-radius: 10px; background: var(--accent-soft) !important;
                                              display: grid; place-items: center; flex: none;}
[data-testid="stFileChip"] > div:first-child svg {color: var(--accent-text); fill: var(--accent-text);}
[data-testid="stFileChip"] > div:nth-child(2) {flex: 1; min-width: 0;}
[data-testid="stFileChipName"] {color: var(--text) !important; font-size: .82rem; font-weight: 600; text-align: left !important; overflow: hidden; text-overflow: ellipsis;}
[data-testid="stFileChip"] small, [data-testid="stFileChip"] div div + div {color: var(--muted); font-size: .72rem;}
[data-testid="stBaseButton-borderlessIcon"] {align-self: flex-start; background: transparent; color: var(--accent-text);}
.upload-count {font-size: .75rem; color: var(--muted);}
.st-key-clear_files {width: 100%; display: flex; justify-content: flex-end;}
.st-key-clear_files [data-testid="stButton"] {width: auto;}
.st-key-clear_files button {padding: 0 !important; min-height: 0 !important;}
.st-key-clear_files button p {font-size: .75rem !important; color: var(--muted) !important;}

/* ---------- кнопки ---------- */
[data-testid="stBaseButton-secondary"] {
    background: var(--raised); border: 1px solid var(--line); color: var(--text) !important; border-radius: 10px;
    min-height: 44px; font-weight: 500; width: 100%; box-shadow: none;}
[data-testid="stBaseButton-secondary"]:hover {border-color: var(--accent-text); background: var(--raised);}
[data-testid="stBaseButton-secondary"] p {color: var(--text) !important; font-size: .85rem !important;}
/* неактивная: пунктирная рамка и приглушённый текст, чтобы было видно, что кнопка временно недоступна */
[data-testid="stBaseButton-secondary"]:disabled {
    opacity: 1; cursor: not-allowed; background: transparent; border: 1px dashed var(--line);}
[data-testid="stBaseButton-secondary"]:disabled p, [data-testid="stBaseButton-secondary"]:disabled span {color: var(--muted) !important;}
[data-testid="stBaseButton-primary"] {background: var(--accent); border: 0; border-radius: 10px; color: #fff !important; font-weight: 600;}
[data-testid="stBaseButton-primary"] p {color: #fff !important;}
.st-key-send_btn, .st-key-resend_btn, .st-key-send_btn [data-testid="stButton"], .st-key-resend_btn [data-testid="stButton"] {width: 100%;}
.st-key-help_btn [data-testid="stBaseButton-secondary"], .st-key-clear_files [data-testid="stBaseButton-secondary"],
.st-key-clear_hist [data-testid="stBaseButton-secondary"] {width: auto; min-height: 0; background: transparent; border: 0;}
.st-key-clear_hist {display: flex; justify-content: flex-end;}
.st-key-clear_hist button p {color: var(--muted) !important; font-size: .78rem !important;}

/* ---------- очередь ---------- */
.qrow {display: grid; grid-template-columns: 44px 1fr auto; gap: 4px 14px; align-items: center; padding: 14px 0; border-top: 1px solid var(--line);}
.qrow:first-of-type {border-top: 0; padding-top: 4px;}
.qicon {width: 44px; height: 44px; border-radius: 12px; background: var(--raised); color: var(--text2); display: grid; place-items: center;}
.qname {font-size: .9rem; font-weight: 600; color: var(--text); overflow-wrap: anywhere;}
.qsub {font-size: .75rem; color: var(--muted);}
.qside {display: flex; flex-direction: column; align-items: flex-end; gap: 6px;}
.qstat {font-size: .75rem; color: var(--muted);}
.pill {display: inline-flex; align-items: center; gap: 6px; font-size: .72rem; font-weight: 600; padding: 4px 12px; border-radius: 999px; white-space: nowrap;}
.pill.done {color: var(--ok); background: var(--ok-bg);}
.pill.processing {color: var(--info); background: var(--info-bg);}
.pill.queued {color: var(--text2); background: var(--raised);}
.pill.error {color: var(--err); background: var(--err-bg);}
.qbar {grid-column: 1 / -1; height: 6px; border-radius: 999px; background: var(--raised); overflow: hidden;}
.qbar span {display: block; height: 100%; border-radius: 999px; background: var(--bar); transition: width .6s ease;}
.qrow.processing .qbar span {background-image: repeating-linear-gradient(45deg, rgba(255,255,255,.22) 0 8px, transparent 8px 16px);
    background-size: 22.6px 22.6px; animation: bar-move 1s linear infinite;}
@keyframes bar-move {to {background-position: 22.6px 0;}}
.qrow.queued .qbar span {width: 30% !important; background: var(--muted); opacity: .6; animation: bar-wait 1.4s ease-in-out infinite alternate;}
@keyframes bar-wait {from {margin-left: 0;} to {margin-left: 70%;}}
.qrow.done .qbar, .qrow.error .qbar {display: none;}
.qerr {grid-column: 1 / -1; color: var(--err); font-size: .8rem;}
@media (prefers-reduced-motion: reduce) {.qbar span {animation: none !important;}}

/* ---------- результаты ---------- */
.rhead {display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;}
.rname {display: flex; align-items: center; gap: 10px; font-weight: 600; font-size: .95rem; color: var(--text); overflow-wrap: anywhere;}
.rname svg {color: var(--accent-text);}
.rtag {font-size: .75rem; color: var(--muted); white-space: nowrap;}
.verdict {display: flex; gap: 12px; border-radius: 12px; padding: 16px 18px; margin-bottom: 16px;}
.verdict svg {margin-top: 2px;}
.verdict b {display: block; font-size: 1rem; font-weight: 600; margin-bottom: 4px;}
.verdict span {font-size: .82rem; color: var(--text2); line-height: 1.5;}
.verdict.missing {background: var(--warn-bg); color: var(--warn);}
.verdict.ok {background: var(--ok-bg); color: var(--ok);}
.verdict.no_answer {background: var(--info-bg); color: var(--info);}
.issue {display: flex; gap: 14px; margin: 14px 0;}
.issue-ic {width: 28px; height: 28px; border-radius: 8px; background: var(--warn-bg); color: var(--warn); display: grid; place-items: center; flex: none;}
.issue b {display: block; font-size: .9rem; font-weight: 600; color: var(--text);}
.issue span {font-size: .82rem; color: var(--text2);}
.source {display: flex; align-items: center; gap: 10px; background: var(--field); border-radius: 10px; padding: 12px 14px; margin-top: 16px;
         font-size: .82rem; color: var(--text2);}
.source a {margin-left: auto; color: var(--accent-text); display: flex;}
[class*="st-key-res_"] [data-testid="stExpander"] details {background: transparent; border: 0;}
[class*="st-key-res_"] [data-testid="stExpander"] summary {padding-left: 0; color: var(--text2);}
[class*="st-key-res_"] [data-testid="stExpander"] summary p {font-size: .8rem !important;}

/* ---------- «что делать дальше» ---------- */
.next-t {font-size: 1rem; font-weight: 600; color: var(--text); margin-bottom: 6px;}
.next-p {font-size: .85rem; color: var(--text2); margin-bottom: 16px;}
.cta {display: inline-flex; align-items: center; gap: 10px; background: var(--accent); color: #fff !important; text-decoration: none !important;
      font-weight: 600; font-size: .85rem; padding: 12px 18px; border-radius: 10px;}
.cta:hover {filter: brightness(1.1);}

/* ---------- подвал ---------- */
.footer {display: flex; justify-content: space-between; border-top: 1px solid var(--line); margin-top: 28px; padding-top: 22px;
         font-size: .8rem; color: var(--muted);}
.footer a {color: var(--text2) !important; text-decoration: none !important; display: inline-flex; gap: 6px; align-items: center;}

/* ---------- плейсхолдер справа, пока ничего не отправлено ---------- */
.empty {text-align: center; color: var(--muted); font-size: .85rem; padding: 36px 12px;}
.empty .qicon {margin: 0 auto 14px;}
.empty b {display: block; color: var(--text); font-size: 1rem; margin-bottom: 6px; font-weight: 600;}

/* ---------- перетаскивание файлов на всю страницу (скрипт PAGE_DROP_JS ниже) ----------
   Пока над окном тащат файл, страница размывается и появляется рамка; бросить можно в любое место. */
[data-testid="stMainBlockContainer"] {transition: filter .2s ease;}
body.page-drop-active [data-testid="stMainBlockContainer"] {filter: blur(8px) brightness(.75);}
.page-drop {position: fixed; inset: 14px; z-index: 1000000; pointer-events: none; opacity: 0;
            border: 2px dashed var(--accent-text); border-radius: 28px; transition: opacity .2s ease;
            display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px;
            background: color-mix(in srgb, var(--accent-text) 10%, transparent);}
body.page-drop-active .page-drop {opacity: 1;}
.page-drop b {font-size: 1.8rem; font-weight: 400; color: var(--text);}
.page-drop span {font-size: .95rem; color: var(--muted);}
/* невидимый iframe со скриптом не должен занимать место в странице */
[data-testid="stElementContainer"]:has(iframe[height="0"], [data-testid="stIFrame"]) {position: absolute; height: 0; margin: 0; overflow: hidden;}

/* ---------- узкий экран: колонки встают друг под друга ---------- */
@media (max-width: 800px) {
    [data-testid="stMainBlockContainer"] {padding: 0 1rem 2rem !important;}
    .stepper {flex-direction: column; align-items: flex-start;} .step-line {display: none;}
    .brand-sub {display: none;}
}
</style>
"""

# Скрипт запускается в невидимом iframe, но вешает слушатели на саму страницу (iframe того же origin).
# Брошенные файлы кладём в настоящее поле загрузки Streamlit и сообщаем ему об изменении.
PAGE_DROP_JS = """
<script>
(function () {
  const P = window.parent, D = P.document;
  if (P.__pageDrop) P.__pageDrop.off();           // после перезапуска скрипта не плодим слушателей

  const overlay = D.createElement('div');
  overlay.className = 'page-drop';
  overlay.innerHTML = '<b>Отпустите файлы в любом месте</b><span>Фото или PDF документа</span>';
  D.body.appendChild(overlay);

  let timer = null;
  const show = on => D.body.classList.toggle('page-drop-active', on);
  const hasFiles = e => e.dataTransfer && Array.from(e.dataTransfer.types || []).includes('Files');

  // dragover приходит непрерывно, пока файл над окном; если события замолчали, значит файл увели
  const onOver = e => {
    if (!hasFiles(e)) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    show(true);
    clearTimeout(timer);
    timer = setTimeout(() => show(false), 250);
  };
  const onDrop = e => {
    if (!hasFiles(e)) return;
    e.preventDefault();
    e.stopPropagation();                           // чтобы встроенная зона Streamlit не добавила файлы второй раз
    clearTimeout(timer);
    show(false);
    const input = D.querySelector('[data-testid="stFileUploaderDropzoneInput"]');
    if (!input || !e.dataTransfer.files.length) return;
    const dt = new P.DataTransfer();
    Array.from(e.dataTransfer.files).forEach(f => dt.items.add(f));
    input.files = dt.files;
    input.dispatchEvent(new P.Event('change', {bubbles: true}));
  };

  D.addEventListener('dragover', onOver, true);
  D.addEventListener('drop', onDrop, true);
  P.__pageDrop = {off() {
    D.removeEventListener('dragover', onOver, true);
    D.removeEventListener('drop', onDrop, true);
    overlay.remove(); show(false);
  }};
})();
</script>
"""


def render_header() -> None:
    """Подключает стили и скрипт перетаскивания файлов на всю страницу."""
    st.markdown(CSS, unsafe_allow_html=True)
    if hasattr(st, "iframe"):  # components.html объявлен устаревшим, в новых версиях Streamlit его заменяет st.iframe
        st.iframe(PAGE_DROP_JS, height=1)
    else:
        components.html(PAGE_DROP_JS, height=0)
