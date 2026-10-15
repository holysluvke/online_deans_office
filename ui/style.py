"""
Внешний вид страницы: CSS (цвета, шрифты, сетка, карточки, кнопки, светлая и тёмная темы), иконки и скрипт.
Логика страницы в app.py, он подключает всё это одной командой render_header().

Как это устроено:
    - CSS вставляется через st.markdown. Контейнеры с key="..." получают класс st-key-<key>, по нему их и красим.
    - Цвета лежат переменными в блоке :root (тёмная тема) и в @media (светлая, по настройке системы).
    - Радиусы скругления это три переменные --r-* в начале CSS.
    - Картинки (папка справа) лежат в ui/assets и вставляются в HTML как data-URI: asset_uri("имя").
    - Шрифты Unbounded (заголовки) и Manrope (текст) лежат в ui/assets/fonts и вставляются в страницу (font_css),
      поэтому страница выглядит так же без интернета. Если шрифт всё же не загрузится, подставится системный.
    - Иконки это SVG-строки в словаре ICONS: svg("имя") вставляет их в HTML.
"""
import base64
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

ASSETS = Path(__file__).parent / "assets"


def asset_uri(name: str) -> str:
    """Картинка из ui/assets как data-URI (вставляется прямо в HTML); пустая строка, если файла нет."""
    path = ASSETS / name
    if not path.exists():
        return ""
    mime = {"webp": "image/webp", "png": "image/png", "jpg": "image/jpeg", "svg": "image/svg+xml"}[path.suffix[1:]]
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()

# Иконки (набор Lucide): рисуются линией цвета текста
ICONS = {
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
    "x": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "minus": '<path d="M5 12h14"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/>',
}


def svg(name: str, size: int = 18) -> str:
    """Возвращает иконку как встроенный SVG заданного размера (цвет берёт из CSS color)."""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
            f'aria-hidden="true">{ICONS[name]}</svg>')


CSS = """
<style>
/* ---------- палитра: тёмная тема (основная) ---------- */
:root {
    --bg: #09090B;          /* фон страницы */
    --card: #101113;        /* карточки и поля */
    --field: #0D0E10;       /* зона загрузки и вложенные блоки */
    --raised: #17181B;      /* плашки, строки файлов */
    --line: #212226;        /* границы */
    --line-hi: #3A3C42;     /* рамки полей и кнопок */
    --grid: rgba(255, 255, 255, .035);
    --text: #FFFFFD;
    --title: #F0ECE3;       /* большой заголовок */
    --text2: #BEBFC1;       /* второстепенный текст */
    --muted: #868789;       /* подписи */
    --btn: #1C2C4D;         /* главная кнопка */
    --btn-text: #FFFFFF;
    --accent-text: #A9B6EE; /* акцент в тексте */
    --ok: #7BCEAE;  --ok-bg: rgba(76, 214, 160, .13);
    --warn: #E8BC78; --warn-bg: #2A2419;
    --info: #A9B6EE; --info-bg: #1A2240;
    --err: #FF8E8E;  --err-bg: rgba(255, 123, 123, .12);
    --bar: var(--accent-text);
    --glow: rgba(70, 90, 190, .16);   /* свечение сверху справа */
    --tint: rgba(255, 255, 255, .06); /* лёгкая заливка цветом текста (вместо color-mix: старый Safari его не знает) */
    --r-card: 18px; --r-field: 12px; --r-small: 8px;   /* скругления */
    --font-body: 'Manrope', system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;   /* запас: системный */
    --font-head: 'Unbounded', 'Segoe UI', system-ui, -apple-system, Arial, sans-serif;
}

/* ---------- палитра: светлая тема (включается по настройке системы) ---------- */
@media (prefers-color-scheme: light) {
    :root {
        --bg: #F4F4F2; --card: #FFFFFF; --field: #FAFAF8; --raised: #EDEDE8; --line: #E3E3DE; --line-hi: #B9B9B2;
        --grid: rgba(17, 17, 17, .045);
        --text: #111111; --title: #111111; --text2: #4A4D55; --muted: #6B6F76;
        --btn: #1A1AE6; --btn-text: #FFFFFF; --accent-text: #1A1AE6;
        --ok: #15805A; --ok-bg: #E3F5EC; --warn: #9A6410; --warn-bg: #FBF1DC;
        --info: #1A1AE6; --info-bg: #E6E6FB; --err: #C23A3A; --err-bg: #FBE7E7;
        --glow: rgba(26, 26, 230, .08);
        --tint: rgba(17, 17, 17, .06);
    }
    /* для светлой темы своя картинка папки (folder_light.webp) и мягкая тень */
    .hero-art img {filter: drop-shadow(0 14px 26px rgba(90, 100, 130, .14)) !important;}
}

/* ---------- базовое ---------- */
#MainMenu, footer, header, [data-testid="stHeader"], [data-testid="stToolbar"] {display: none !important;}
/* значок-ссылка, который Streamlit показывает у заголовков при наведении */
[data-testid="stHeaderActionElements"], [data-testid="stHeadingActionElements"] {display: none !important;}
/* линия под шапкой шире окна на ширину прокрутки: без этого внизу появляется горизонтальная прокрутка */
html, body, .stApp, [data-testid="stMain"], [data-testid="stAppViewContainer"] {overflow-x: hidden !important;}
/* Streamlit при перерисовке на миг тускнит старые блоки, из-за чего страница мерцает: отключаем */
[data-stale="true"], [data-stale="true"] * {opacity: 1 !important; transition: none !important;}
/* фон: тонкая сетка и мягкое свечение сверху */
[data-testid="stAppViewContainer"], .stApp {
    background:
        radial-gradient(ellipse 60% 40% at 80% 0%, var(--glow), transparent 70%),
        linear-gradient(var(--grid) 1px, transparent 1px) 0 0 / 64px 64px,
        linear-gradient(90deg, var(--grid) 1px, transparent 1px) 0 0 / 64px 64px,
        var(--bg) !important;}
[data-testid="stMainBlockContainer"] {max-width: 1160px !important; padding: 0 2rem 2rem !important;}
.stApp, .stApp p, .stApp label, .stApp li, .stApp small, .stApp input, .stApp textarea,
.stApp button, .stApp [data-testid="stMarkdownContainer"],
.stApp span:not([data-testid="stIconMaterial"]) {font-family: var(--font-body) !important;}
.stApp {color: var(--text);}
/* macOS по умолчанию рисует светлый текст на тёмном фоне жирнее и размытее, чем Windows: включаем тонкое сглаживание */
html, body, .stApp {-webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; text-rendering: optimizeLegibility;
                    -webkit-text-size-adjust: 100%; text-size-adjust: 100%;}
[data-testid="stVerticalBlock"] {gap: 1rem;}
.stApp svg {flex: none;}
.card-title, .sec-title, .next-t, .page-drop b, .step-ic, .step-t, .brand-tag, .count-pill {font-family: var(--font-head) !important;}

/* ---------- шапка: иконка слева, «Как это работает» справа ---------- */
.topbar {display: flex; align-items: center; gap: 14px; height: 36px;}
.brand-tag {font-size: .68rem; font-weight: 700; letter-spacing: .16em; text-transform: uppercase; color: var(--muted); white-space: nowrap;}
.logo {width: 34px; height: 34px; border: 1px solid var(--line-hi); border-radius: var(--r-field); display: grid; place-items: center; background: var(--raised); color: var(--text);}
.st-key-topbar {position: relative; margin-bottom: 4px; padding: 12px 0 27px !important;}
.st-key-topbar::after {content: ""; position: absolute; left: 50%; bottom: 0; width: 100vw; transform: translateX(-50%);
                       border-bottom: 1px solid var(--line);}
.st-key-topbar [data-testid="stVerticalBlock"] {gap: 0;}
.st-key-help_btn button {background: transparent !important; border: 0 !important; color: var(--text2) !important; border-radius: var(--r-small) !important;
                         box-shadow: none !important; justify-content: flex-end;}
.st-key-help_btn button:hover {color: var(--text) !important;}
.st-key-help_btn {width: 100%; display: flex; justify-content: flex-end; position: relative; top: 7px;}
.st-key-help_btn [data-testid="stButton"] {width: auto;}

/* ---------- верхний блок: заголовок и папка ---------- */
.hero {display: flex; justify-content: space-between; align-items: center; gap: 24px; padding: 8px 0 14px;}
.stApp h1.hero-title {font-family: var(--font-head) !important; font-size: clamp(1.7rem, 7.4vw, 5.8rem) !important; font-weight: 800 !important;
             line-height: 1 !important; letter-spacing: -.015em !important; text-transform: uppercase; padding: 0 !important;
             color: var(--title) !important; margin: 0 0 22px !important; overflow-wrap: anywhere;}
.page-sub {color: var(--text2); font-size: .95rem; max-width: 520px; line-height: 1.55; margin: 0;}
.hero-art {flex: none; width: clamp(84px, 20vw, 220px);}
.hero-art img {width: 100%; height: auto; display: block; filter: drop-shadow(0 18px 40px rgba(0,0,0,.35));}

/* ---------- шаги ---------- */
.stepper {display: flex; align-items: center; gap: 16px; margin: 0 0 22px; padding: 18px 0; border-top: 1px solid var(--line);}
.step {display: flex; align-items: center; gap: 14px; min-width: 0;}
.step-ic {width: 28px; height: 28px; border: 1px solid var(--line-hi); border-radius: var(--r-small); display: grid; place-items: center; flex: none;
          font-size: .62rem; font-weight: 500; color: var(--muted); background: transparent;}
.step.done .step-ic {color: var(--text2);}
.step.current .step-ic {border-color: var(--text); color: var(--text); background: var(--tint);}
.step.pending .step-ic {opacity: .7;}
.step-t {font-size: .85rem; font-weight: 600; color: var(--text); line-height: 1.3;}
.step-s {font-size: .72rem; color: var(--muted); line-height: 1.3;}
.step.current .step-s.hl {color: var(--accent-text);}
.step-line {flex: 1; height: 1px; background: var(--line); min-width: 24px; align-self: center;}

/* ---------- карточки ---------- */
.st-key-upload_card, .st-key-queue_card, [class*="st-key-res_"], .st-key-next_card, .st-key-empty_card {
    border: 1px solid var(--line) !important; border-radius: var(--r-card) !important; padding: 22px 24px !important;
    background: var(--card) !important;}
.card-head {display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;}
.card-title {font-size: 1.35rem; font-weight: 700; letter-spacing: -.015em; color: var(--text); margin: 0; line-height: 1.2;}
.card-desc {font-size: .85rem; color: var(--text2); line-height: 1.5; margin: 8px 0 4px;}
.count-pill {border-radius: 999px; border: 1px solid var(--line-hi); color: var(--text2); font-size: .68rem; font-weight: 600; padding: 4px 10px; letter-spacing: .04em;}
.card-note {font-size: .78rem; color: var(--muted); margin-top: 14px;}
.sec-head {display: flex; justify-content: space-between; align-items: baseline; margin: 8px 0 0;}
.sec-title {font-size: 1.35rem; font-weight: 700; letter-spacing: -.015em; color: var(--text);}
.sec-side {font-size: .8rem; color: var(--muted);}
.privacy {display: flex; gap: 10px; color: var(--muted); font-size: .75rem; line-height: 1.5; padding: 0 4px;}
.privacy svg {margin-top: 2px;}

/* ---------- подписи полей: мелкие заглавные ---------- */
.stApp label p, [data-testid="stWidgetLabel"] p {font-size: .68rem !important; color: var(--muted) !important; font-weight: 600;
                                                text-transform: uppercase; letter-spacing: .09em;}
.field-label {display: flex; justify-content: space-between; font-size: .68rem; color: var(--muted); font-weight: 600; margin-bottom: 2px;
              text-transform: uppercase; letter-spacing: .09em; line-height: 1.2;}
.field-label .opt {text-transform: none; letter-spacing: 0; font-weight: 500; font-size: .75rem;}

/* ---------- поля ввода ---------- */
[data-testid="stTextInput"] input, [data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stSelectbox"] [role="group"], [data-testid="stSelectbox"] input {background: var(--card) !important; color: var(--text) !important;}
[data-testid="stTextInput"] > div > div, [data-testid="stSelectbox"] [data-baseweb="select"] > div {
    background: var(--card) !important; border: 1px solid var(--line-hi) !important;}
[data-testid="stTextInput"] [data-baseweb], [data-testid="stSelectbox"] [data-baseweb="select"],
[data-testid="stSelectbox"] [data-baseweb="select"] * {border-radius: var(--r-field) !important;}
[data-testid="InputInstructions"] {display: none !important;}
[data-testid="stTextInput"] input::placeholder {color: var(--muted);}

/* ---------- зона загрузки ---------- */
[data-testid="stFileUploaderDropzone"] {
    background: var(--field); border: 1px dashed var(--line-hi); border-radius: var(--r-field); padding: 28px 16px;
    display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; cursor: pointer;}
[data-testid="stFileUploaderDropzone"]:hover {border-color: var(--text2);}
/* настоящую кнопку и английские подписи прячем: клик по всей зоне и так открывает окно выбора файлов */
[data-testid="stFileUploaderDropzone"] > span {display: none;}
[data-testid="stFileUploaderDropzoneInstructions"] > div {display: none;}
[data-testid="stFileUploaderDropzoneInstructions"] {
    display: flex; flex-direction: column; align-items: center; gap: 6px; padding-top: 40px; position: relative;
    background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='26' height='26' viewBox='0 0 24 24' fill='none' stroke='%23BEBFC1' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4'/%3E%3Cpolyline points='17 8 12 3 7 8'/%3E%3Cline x1='12' x2='12' y1='3' y2='15'/%3E%3C/svg%3E") top center / 26px no-repeat;}
[data-testid="stFileUploaderDropzoneInstructions"]::before {content: "Перетащите файлы сюда"; color: var(--text); font-size: .85rem; font-weight: 500;}
[data-testid="stFileUploaderDropzoneInstructions"]::after {content: "или выберите на устройстве"; color: var(--text); font-size: .8rem; font-weight: 500;
    text-decoration: underline; text-underline-offset: 4px; text-decoration-color: var(--line-hi);}
/* когда файлы выбраны, Streamlit показывает их внутри зоны: оформляем как строки списка */
[data-testid="stFileUploaderDropzone"]:has([data-testid="stFileChips"]) {padding: 10px; align-items: stretch; text-align: left; cursor: default;}
[data-testid="stFileChips"], [data-testid="stFileChips"] * {text-align: left;}
[data-testid="stFileChips"] > div {display: flex; flex-direction: column; align-items: stretch; gap: 8px;}
[data-testid="stFileChips"] > div > div {display: flex; flex-direction: column; gap: 8px;}
[data-testid="stFileChip"] {display: flex !important; align-items: center; gap: 12px; background: var(--raised) !important;
                            border: 1px solid var(--line); border-radius: var(--r-field) !important; padding: 10px 12px !important; width: 100%;}
[data-testid="stFileChip"] > div:first-child {width: 34px; height: 34px; border-radius: var(--r-small); background: var(--card) !important; border: 1px solid var(--line-hi);
                                              display: grid; place-items: center; flex: none;}
[data-testid="stFileChip"] > div:first-child svg {color: var(--text2); fill: var(--text2);}
[data-testid="stFileChip"] > div:nth-child(2) {flex: 1; min-width: 0;}
[data-testid="stFileChipName"] {color: var(--text) !important; font-size: .82rem; font-weight: 600; text-align: left !important; overflow: hidden; text-overflow: ellipsis;}
[data-testid="stFileChip"] small, [data-testid="stFileChip"] div div + div {color: var(--muted); font-size: .72rem;}
[data-testid="stBaseButton-borderlessIcon"] {align-self: flex-start; background: transparent; color: var(--text2);}
.upload-count {font-size: .75rem; color: var(--muted);}
.upload-hint {min-height: 1.2em; line-height: 1.2;}
.st-key-clear_files {width: 100%; display: flex; justify-content: flex-end;}
.st-key-clear_files [data-testid="stButton"] {width: auto;}
.st-key-clear_files button {padding: 0 !important; min-height: 0 !important;}
.st-key-clear_files button p {font-size: .75rem !important; color: var(--muted) !important; text-transform: none !important; letter-spacing: 0 !important;}

/* ---------- кнопки ---------- */
[data-testid="stBaseButton-secondary"] {
    background: transparent; border: 1px solid var(--line-hi); color: var(--text) !important; border-radius: var(--r-field);
    min-height: 44px; font-weight: 500; width: 100%; box-shadow: none;}
[data-testid="stBaseButton-secondary"]:hover {border-color: var(--text); background: var(--tint);}
[data-testid="stBaseButton-secondary"] p {color: var(--text) !important; font-size: .85rem !important;}
/* главная кнопка отправки: залитая; неактивная: пунктир и приглушённый текст, чтобы было видно, что она временно недоступна */
.st-key-send_btn [data-testid="stBaseButton-secondary"] {background: var(--btn); border-color: var(--btn); color: var(--btn-text) !important;}
.st-key-send_btn [data-testid="stBaseButton-secondary"] p, .st-key-send_btn [data-testid="stBaseButton-secondary"] span {color: var(--btn-text) !important;}
.st-key-send_btn [data-testid="stBaseButton-secondary"]:hover {filter: brightness(1.15); background: var(--btn);}
[data-testid="stBaseButton-secondary"]:disabled, .st-key-send_btn [data-testid="stBaseButton-secondary"]:disabled {
    opacity: 1; cursor: not-allowed; background: transparent; border: 1px dashed var(--line-hi); filter: none;}
[data-testid="stBaseButton-secondary"]:disabled p, [data-testid="stBaseButton-secondary"]:disabled span,
.st-key-send_btn [data-testid="stBaseButton-secondary"]:disabled p, .st-key-send_btn [data-testid="stBaseButton-secondary"]:disabled span {color: var(--muted) !important;}
[data-testid="stBaseButton-primary"] {background: var(--btn); border: 0; border-radius: var(--r-field); color: var(--btn-text) !important; font-weight: 600;}
[data-testid="stBaseButton-primary"] p {color: var(--btn-text) !important;}
.st-key-send_btn, .st-key-resend_btn, .st-key-send_btn [data-testid="stButton"], .st-key-resend_btn [data-testid="stButton"] {width: 100%;}
.st-key-help_btn [data-testid="stBaseButton-secondary"], .st-key-clear_files [data-testid="stBaseButton-secondary"] {width: auto; min-height: 0; background: transparent; border: 0;}
.st-key-clear_hist {margin-top: 6px;}
.st-key-clear_hist, .st-key-clear_hist [data-testid="stButton"] {width: 100%;}
.st-key-clear_hist [data-testid="stBaseButton-secondary"] {width: 100%; min-height: 40px; background: transparent; border: 1px solid var(--line-hi);}
.st-key-clear_hist [data-testid="stBaseButton-secondary"]:hover:not(:disabled) {border-color: var(--text2);}
.st-key-clear_hist button p, .st-key-clear_hist button span {color: var(--text2) !important; font-size: .82rem !important;}
.st-key-clear_hist button:disabled p, .st-key-clear_hist button:disabled span {color: var(--muted) !important;}

/* ---------- очередь и результаты: свёрнутый список показывает один пункт, остальные прокручиваются ---------- */
.st-key-queue_card [data-testid="stVerticalBlock"] {gap: 0;}
.st-key-queue_card {gap: 0;}
.st-key-qlist_open [data-testid="stElementContainer"] ~ [data-testid="stElementContainer"] .qrow {border-top: 1px solid var(--line);}
.st-key-qlist_closed1 {max-height: 84px; overflow-y: auto; scroll-snap-type: y mandatory;}
.st-key-qlist_closed2 {max-height: 168px; overflow-y: auto; scroll-snap-type: y mandatory;}
.st-key-qlist_closed2 [data-testid="stElementContainer"] ~ [data-testid="stElementContainer"] .qrow {border-top: 1px solid var(--line);}
.st-key-rlist_closed {max-height: 470px; overflow-y: auto; scroll-snap-type: y proximity; padding-right: 2px;}
.st-key-qlist_closed1 [data-testid="stElementContainer"], .st-key-qlist_closed2 [data-testid="stElementContainer"], .st-key-rlist_closed > [data-testid="stVerticalBlock"] > * {scroll-snap-align: start;}
/* Полоса прокрутки списков. На macOS системная полоса прячется, пока список не крутят, и не видно, что там есть ещё пункты;
   Safari к тому же не понимает scrollbar-width/scrollbar-color. Поэтому рисуем свою через ::-webkit-scrollbar
   (Chrome, Edge, Safari: так она видна всегда), а scrollbar-width оставляем только Firefox: если Chrome видит
   scrollbar-width, он игнорирует ::-webkit-scrollbar. */
.st-key-qlist_closed1::-webkit-scrollbar, .st-key-qlist_closed2::-webkit-scrollbar, .st-key-rlist_closed::-webkit-scrollbar {width: 6px;}
.st-key-qlist_closed1::-webkit-scrollbar-track, .st-key-qlist_closed2::-webkit-scrollbar-track, .st-key-rlist_closed::-webkit-scrollbar-track {background: transparent;}
.st-key-qlist_closed1::-webkit-scrollbar-thumb, .st-key-qlist_closed2::-webkit-scrollbar-thumb, .st-key-rlist_closed::-webkit-scrollbar-thumb {
    background: var(--line-hi); border-radius: 999px;}
@supports not selector(::-webkit-scrollbar) {
    .st-key-qlist_closed1, .st-key-qlist_closed2, .st-key-rlist_closed {scrollbar-width: thin; scrollbar-color: var(--line-hi) transparent;}
}
/* Результат бывает выше списка, а Safari с жёсткой привязкой (mandatory) не даёт докрутить до его середины:
   у результатов привязка мягкая (proximity). Инерция трекпада не должна прокручивать всю страницу. */
.st-key-qlist_closed1, .st-key-qlist_closed2, .st-key-rlist_closed {-webkit-overflow-scrolling: touch; overscroll-behavior: contain;}
.st-key-rlist_open [data-testid="stVerticalBlock"], .st-key-rlist_closed [data-testid="stVerticalBlock"] {gap: 1rem;}
/* кнопка «Показать все» / «Свернуть»: спокойная, на всю ширину блока */
.st-key-q_open_btn, .st-key-r_open_btn {margin-top: 10px;}
.st-key-q_open_btn, .st-key-r_open_btn, .st-key-q_open_btn [data-testid="stButton"], .st-key-r_open_btn [data-testid="stButton"] {width: 100%;}
.st-key-q_open_btn button, .st-key-r_open_btn button {width: 100%; min-height: 38px; background: transparent !important; border: 1px solid var(--line) !important; border-radius: var(--r-field) !important;}
.st-key-q_open_btn button p, .st-key-r_open_btn button p, .st-key-q_open_btn button span, .st-key-r_open_btn button span {color: var(--text2) !important; font-size: .8rem !important;}
.st-key-q_open_btn button:hover, .st-key-r_open_btn button:hover {border-color: var(--text2) !important;}

/* ---------- очередь ---------- */
.qrow {display: grid; grid-template-columns: 44px 1fr auto; gap: 4px 14px; align-items: center; align-content: center; padding: 6px 0; box-sizing: border-box; min-height: 84px;}
.st-key-queue_card [data-testid="stMarkdownContainer"]:has(.qrow) {margin-bottom: 0 !important;}
.qicon {width: 44px; height: 44px; border: 1px solid var(--line-hi); border-radius: var(--r-field); color: var(--text2); display: grid; place-items: center;}
.qname {font-size: .9rem; font-weight: 600; color: var(--text); overflow-wrap: anywhere;}
.qsub {font-size: .75rem; color: var(--muted);}
.qside {display: flex; flex-direction: column; align-items: flex-end; gap: 6px;}
.qstat {font-size: .75rem; color: var(--muted);}
.pill {display: inline-flex; align-items: center; gap: 6px; font-size: .68rem; font-weight: 700; padding: 4px 10px; white-space: nowrap;
       text-transform: uppercase; letter-spacing: .06em; border-radius: 999px;}
.pill.done {color: var(--ok); background: var(--ok-bg);}
.pill.processing {color: var(--info); background: var(--info-bg);}
.pill.queued {color: var(--text2); background: var(--raised);}
.pill.error {color: var(--err); background: var(--err-bg);}
.qbar {grid-column: 1 / -1; height: 4px; background: var(--raised); overflow: hidden; border-radius: 999px;}
.qbar span {display: block; height: 100%; background: var(--bar); border-radius: 999px; transition: width .6s ease;}
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
.rname svg {color: var(--text2);}
.rtag {font-size: .75rem; color: var(--muted); white-space: nowrap;}
.verdict {display: flex; gap: 12px; padding: 16px 18px; margin-bottom: 16px; border-left: 3px solid currentColor; border-radius: var(--r-field);}
.verdict svg {margin-top: 2px;}
.verdict b {display: block; font-size: 1rem; font-weight: 600; margin-bottom: 4px;}
.verdict span {font-size: .82rem; color: var(--text2); line-height: 1.5;}
.verdict.missing {background: var(--warn-bg); color: var(--warn);}
.verdict.ok {background: var(--ok-bg); color: var(--ok);}
.verdict.no_answer {background: var(--info-bg); color: var(--info);}
.issue {display: flex; gap: 14px; margin: 14px 0;}
.issue-ic {width: 28px; height: 28px; border-radius: var(--r-small); background: var(--warn-bg); color: var(--warn); display: grid; place-items: center; flex: none;}
.issue b {display: block; font-size: .9rem; font-weight: 600; color: var(--text);}
.issue span {font-size: .82rem; color: var(--text2);}
.fields {margin: 4px 0 2px;}
.frow {display: flex; align-items: center; gap: 12px; padding: 9px 0; border-bottom: 1px solid var(--line);}
.frow:last-child {border-bottom: 0;}
.f-ic {width: 22px; height: 22px; border-radius: 50%; display: grid; place-items: center; flex: none;}
.f-ic.yes {background: var(--ok-bg); color: var(--ok);}
.f-ic.no {background: var(--warn-bg); color: var(--warn);}
.f-label {flex: 1; font-size: .82rem; color: var(--text2);}
.f-val {font-size: .88rem; font-weight: 600; color: var(--text); text-align: right; overflow-wrap: anywhere;}
.f-val.none {color: var(--warn); font-weight: 500;}
.source {display: flex; align-items: center; gap: 10px; background: var(--field); border: 1px solid var(--line); padding: 12px 14px; margin-top: 16px; border-radius: var(--r-field);
         font-size: .82rem; color: var(--text2);}
.source a {margin-left: auto; color: var(--text2); display: flex;}
[class*="st-key-res_"] [data-testid="stExpander"] details {background: transparent; border: 0;}
[class*="st-key-res_"] [data-testid="stExpander"] summary {padding-left: 0; color: var(--text2);}
[class*="st-key-res_"] [data-testid="stExpander"] summary p {font-size: .8rem !important; text-transform: none !important; letter-spacing: 0 !important;}

/* ---------- «что делать дальше» ---------- */
.next-t {font-size: 1rem; font-weight: 700; color: var(--text); margin-bottom: 6px;}
.next-p {font-size: .85rem; color: var(--text2); margin-bottom: 16px;}
.cta {display: inline-flex; align-items: center; gap: 10px; background: var(--btn); color: var(--btn-text) !important; text-decoration: none !important;
      font-weight: 600; font-size: .85rem; padding: 12px 18px; border-radius: var(--r-field);}
.cta:hover {filter: brightness(1.15);}

/* ---------- подвал ---------- */
.footer {display: flex; justify-content: space-between; border-top: 1px solid var(--line); margin-top: 28px; padding-top: 22px;
         font-size: .8rem; color: var(--muted);}

/* ---------- плейсхолдер справа, пока ничего не отправлено ---------- */
.empty {text-align: center; color: var(--muted); font-size: .85rem; padding: 36px 12px;}
.empty .qicon {margin: 0 auto 14px;}
.empty b {display: block; color: var(--text); font-size: 1rem; margin-bottom: 6px; font-weight: 600;}

/* ---------- перетаскивание файлов на всю страницу (скрипт PAGE_DROP_JS ниже) ----------
   Пока над окном тащат файл, страница размывается и появляется рамка; бросить можно в любое место. */
[data-testid="stMainBlockContainer"] {transition: filter .2s ease;}
body.page-drop-active [data-testid="stMainBlockContainer"] {filter: blur(8px) brightness(.75);}
.page-drop {position: fixed; inset: 14px; z-index: 1000000; pointer-events: none; opacity: 0;
            border: 1px dashed var(--text); border-radius: var(--r-card); transition: opacity .2s ease;
            display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px;
            background: var(--tint);}
body.page-drop-active .page-drop {opacity: 1;}
.page-drop b {font-size: 1.6rem; font-weight: 600; color: var(--text);}
.page-drop span {font-size: .95rem; color: var(--muted);}
/* невидимый iframe со скриптом не должен занимать место в странице */
[data-testid="stElementContainer"]:has(iframe[height="0"], [data-testid="stIFrame"]) {position: absolute; height: 0; margin: 0; overflow: hidden;}

/* ---------- плашка «модель загружается» ---------- */
.model-banner {margin-bottom: 1rem; display: flex; align-items: center; gap: 14px; padding: 14px 18px; border-radius: var(--r-field);
               background: var(--info-bg); color: var(--info); font-size: .85rem; line-height: 1.5;}
.model-banner b {display: block; font-size: .95rem; font-weight: 600; margin-bottom: 2px;}
.model-banner span {color: var(--text2);}
.model-banner.failed {background: var(--warn-bg); color: var(--warn);}
.spinner {flex: none; width: 18px; height: 18px; border: 2px solid currentColor; border-right-color: transparent; border-radius: 50%; animation: spin 1s linear infinite;}
@keyframes spin {to {transform: rotate(360deg);}}
@media (prefers-reduced-motion: reduce) {.spinner {animation: none;}}

/* ---------- узкий экран ---------- */
@media (max-width: 800px) {
    [data-testid="stMainBlockContainer"] {padding: 0 1rem 2rem !important;}
    .hero {gap: 12px; padding: 12px 0;}
    .hero-art {width: 26vw;}
    .stepper {flex-direction: column; align-items: flex-start;} .step-line {display: none;}
}
</style>
"""

# Скрипт работает в невидимом iframe, но вешает слушатели на саму страницу (iframe того же origin):
# 1) перетаскивание файлов в любое место страницы; 2) применение вопроса без нажатия Enter.
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

  // Поле вопроса: Streamlit принимает текст только по Enter или при уходе из поля. Применяем сами через полсекунды
  // после последней набранной буквы, чтобы Enter не был нужен (на телефоне это особенно неудобно).
  let applyTimer = null;
  const onInput = e => {
    const el = e.target;
    if (!el || el.tagName !== 'INPUT' || !el.closest('[data-testid="stTextInput"]')) return;
    clearTimeout(applyTimer);
    applyTimer = setTimeout(() => {
      const opts = {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true};
      el.dispatchEvent(new P.KeyboardEvent('keydown', opts));
      el.dispatchEvent(new P.KeyboardEvent('keypress', opts));
      el.dispatchEvent(new P.KeyboardEvent('keyup', opts));
    }, 500);
  };

  D.addEventListener('dragover', onOver, true);
  D.addEventListener('drop', onDrop, true);
  D.addEventListener('input', onInput, true);
  P.__pageDrop = {off() {
    D.removeEventListener('dragover', onOver, true);
    D.removeEventListener('drop', onDrop, true);
    D.removeEventListener('input', onInput, true);
    clearTimeout(applyTimer);
    overlay.remove(); show(false);
  }};
})();
</script>
"""


# Какие участки символов в каком файле шрифта: кириллица и латиница лежат отдельно
_RANGES = {
    "cyrillic": "U+0301, U+0400-045F, U+0490-0491, U+04B0-04B1, U+2116",
    "latin": "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215",
}


def font_css() -> str:
    """@font-face для Unbounded (веса 700 и 800) и Manrope (переменный, 200-800): файлы из ui/assets/fonts вставляются в страницу, интернет не нужен."""
    faces = []
    sources = [("Unbounded", f"unbounded-{{subset}}-{w}-normal.woff2", str(w)) for w in (700, 800)]
    sources.append(("Manrope", "manrope-{subset}-wght-normal.woff2", "200 800"))
    for family, pattern, weight in sources:
        for subset, ranges in _RANGES.items():
            path = ASSETS / "fonts" / pattern.format(subset=subset)
            if path.exists():
                data = base64.b64encode(path.read_bytes()).decode()
                faces.append(
                    f"@font-face {{font-family: '{family}'; font-weight: {weight}; font-style: normal; font-display: swap; "
                    f"src: url(data:font/woff2;base64,{data}) format('woff2'); unicode-range: {ranges};}}"
                )
    return "<style>" + "".join(faces) + "</style>"


def render_header() -> None:
    """Подключает стили и скрипт перетаскивания файлов на всю страницу."""
    st.markdown(font_css(), unsafe_allow_html=True)
    st.markdown(CSS, unsafe_allow_html=True)
    if hasattr(st, "iframe"):  # components.html объявлен устаревшим, в новых версиях Streamlit его заменяет st.iframe
        st.iframe(PAGE_DROP_JS, height=1)
    else:
        components.html(PAGE_DROP_JS, height=0)
