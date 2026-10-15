"""
Внешний вид страницы: цвета, шрифты, карточки, кнопки, светлая и тёмная темы.
Логики здесь нет: она в app.py. Здесь только CSS, который app.py подключает одной
командой render_header() в начале страницы.

Как это устроено:
    - Streamlit сам не умеет красить карточки статусов и менять шрифт, поэтому мы
      добавляем небольшой блок CSS (строка CSS ниже). Он подключается через st.markdown.
    - Все цвета лежат переменными в блоке :root. Меняешь цвет там, и он меняется везде.
    - Тёмная тема включается сама по настройке системы (блок @media prefers-color-scheme).
    - Цвета самих виджетов Streamlit (поля, кнопки) задаются в .streamlit/config.toml,
      секции [theme.light] и [theme.dark]. Если меняешь палитру, меняй её в обоих местах.

Классы, которые использует app.py (если переименуешь здесь, поменяй и там):
    .job, .job-top, .name, .pill, .bar   карточка задачи в очереди
    .job.queued/.processing/.done/.error цвет плашки статуса (через переменную --c)
    .result, .tag, .src                  карточка ответа
"""
import streamlit as st
import streamlit.components.v1 as components

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;500;600;700&display=swap');

/* ---------- палитра: светлая тема (по умолчанию) ----------
   Все цвета меняются здесь, в одном месте. */
:root {
    --bg: #F4F4F2;
    --card: #FFFFFF;
    --line: #E3E3DE;
    --text: #111111;
    --muted: #6B6F76;
    --blue: #1A1AE6;
    --ok: #1F9D6B;      /* документ в порядке */
    --warn: #E07A1F;    /* чего-то не хватает */
    --info: #2B3BE0;    /* ответа нет */
    --err: #D64545;     /* ошибка */
    --mint: #5FE0B0;
    --bar: var(--ok); 
    --shadow: 0 1px 2px rgba(17,17,17,.04), 0 10px 28px -14px rgba(17,17,17,.18);
    --aura-1: rgba(30, 30, 240, .42);    /* «аура» в шапке: синий центр */
    --aura-2: rgba(80, 225, 175, .55);  /* и мятный ореол */
}

/* ---------- палитра: тёмная тема (включается по настройке системы) ----------
   Названия переменных те же, что выше: перекрашивается всё, что их использует. */
@media (prefers-color-scheme: dark) {
    :root {
        --bg: #0B0C10;
        --card: #14161C;
        --bar: var(--blue);
        --line: #262A33;
        --text: #F2F2F0;
        --muted: #9AA0AA;
        --blue: #8C97FF;
        --ok: #4CD6A0;
        --warn: #FF9A4D;
        --info: #8C97FF;
        --err: #FF7B7B;
        --shadow: 0 10px 28px -14px rgba(0,0,0,.7);
        --aura-1: rgba(40, 40, 255, .60);
        --aura-2: rgba(110, 208, 168, .35);
    }
}

/* ---------- базовое ---------- */
#MainMenu, footer, header {visibility: hidden;}
[data-testid="stHeaderActionElements"] {display: none;}  /* ссылки-якоря у заголовков */

/* ---------- фон с «аурой» в шапке ---------- */
[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(ellipse 45% 70% at 50% 0%, var(--aura-1) 0%, transparent 100%) top / 100% 560px no-repeat,
        radial-gradient(ellipse 80% 80% at 50% 0%, var(--aura-2) 0%, transparent 100%) top / 100% 560px no-repeat,
        var(--bg) !important;
}

/* ---------- шрифт ---------- */
.stApp, .stApp p, .stApp label, .stApp li, .stApp small, .stApp input, .stApp textarea,
.stApp button, .stApp [data-testid="stMarkdownContainer"],
.stApp span:not([data-testid="stIconMaterial"]) {
    font-family: 'Manrope', sans-serif !important;
}

/* ---------- заголовки ---------- */
h1 {font-size: 2.6rem !important; font-weight: 300 !important; line-height: 1.15 !important;
    letter-spacing: -0.02em;}
h2, h3 {font-weight: 400 !important; letter-spacing: -0.01em;}
/* заголовок страницы прижат к верху: убираем большой верхний отступ Streamlit */
[data-testid="stMainBlockContainer"] {padding-top: 2rem !important;}
h1 {padding-top: 0 !important;}

/* ---------- карточка задачи в очереди (app.py, функция queue_view) ---------- */
.job {border: 1px solid var(--line); background: var(--card); border-radius: 16px;
      padding: 14px 18px; margin: 10px 0;}
.job .name {color: var(--text); font-weight: 500;}
.job-top {display: flex; justify-content: space-between; align-items: center; gap: 12px;}

/* ---------- плашка статуса и линия прогресса ----------
   Цвет плашки берётся из переменной --c, которую задаёт класс статуса ниже. */
.job.queued {--c: var(--muted);}
.job.processing {--c: var(--blue);}
.job.done {--c: var(--ok);}
.job.error {--c: var(--err);}
.pill {display: inline-flex; align-items: center; font-size: .72rem; font-weight: 600;
       letter-spacing: .04em; padding: 4px 12px; border-radius: 999px; white-space: nowrap;
       color: var(--c); background: color-mix(in srgb, var(--c) 14%, transparent);}
.pill::before {content: ""; width: 6px; height: 6px; border-radius: 50%;
               background: var(--c); margin-right: 8px;}
.bar {height: 8px; border-radius: 999px; background: var(--line); margin-top: 12px; overflow: hidden;}
.bar span {display: block; height: 100%; border-radius: 999px;
           background: var(--bar); transition: width .6s ease;}
/* в работе: бегущие полосы на заполненной части, чтобы было видно, что процесс идёт */
.job.processing .bar span {
    background-image: repeating-linear-gradient(45deg, rgba(255,255,255,.22) 0 8px, transparent 8px 16px);
    background-size: 22.6px 22.6px; animation: bar-move 1s linear infinite;}
@keyframes bar-move {to {background-position: 22.6px 0;}}
/* в очереди: неопределённая полоса, которая бежит туда-сюда (сколько ждать, неизвестно) */
.job.queued .bar span {width: 30% !important; background: var(--muted); opacity: .6;
                       animation: bar-wait 1.4s ease-in-out infinite alternate;}
@keyframes bar-wait {from {margin-left: 0;} to {margin-left: 70%;}}
.job.done .bar, .job.error .bar {display: none;}  /* у готовых и упавших линия не нужна */
/* строка под именем: что делается сейчас и сколько процентов */
.stage {display: flex; justify-content: space-between; margin-top: 8px;
        color: var(--muted); font-size: .8rem;}
@media (prefers-reduced-motion: reduce) {.job .bar span {animation: none !important;}}
/* карточка ответа (app.py, функция show_result); цвет левой черты задаёт app.py */
.result {background: var(--card); border: 1px solid var(--line); border-left-width: 4px;
         border-radius: 16px; padding: 14px 18px; margin: 8px 0 4px 0;}
.result .tag {font-size: .7rem; font-weight: 600; letter-spacing: .12em; margin-bottom: 6px;}
.result .src {color: var(--muted); font-size: .8rem; margin-top: 8px;}
.job, .result {box-shadow: var(--shadow);}

/* ---------- кнопки-«пилюли» ----------
   primary - главная кнопка («Отправить на проверку»), secondary - вторичная («Очистить список») */
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-secondary"] {
    border-radius: 999px; padding: .5rem 1.6rem; font-weight: 500;
    transition: transform .15s ease, box-shadow .15s ease;
}
[data-testid="stBaseButton-primary"] {background: var(--text); border: 1px solid var(--text);}
[data-testid="stBaseButton-primary"] p {color: var(--bg) !important;}
[data-testid="stBaseButton-primary"]:hover:not(:disabled) {
    background: var(--text); transform: translateY(-1px); box-shadow: var(--shadow);
}
/* неактивная кнопка: контур с пунктиром и приглушённая подпись вместо сплошной заливки.
   Так она хорошо видна на любом фоне, но сразу понятно, что пока нажать нельзя */
[data-testid="stBaseButton-primary"]:disabled {
    opacity: 1; cursor: not-allowed;
    background: color-mix(in srgb, var(--text) 10%, transparent);
    border: 1px dashed color-mix(in srgb, var(--text) 50%, transparent);
}
[data-testid="stBaseButton-primary"]:disabled p {
    color: color-mix(in srgb, var(--text) 65%, transparent) !important;
}
[data-testid="stBaseButton-secondary"] {background: transparent; border: 1px solid var(--muted);}
[data-testid="stBaseButton-secondary"] p {color: var(--text) !important;}
[data-testid="stBaseButton-secondary"] {margin-top: .6rem;}
[data-testid="stBaseButton-secondary"]:hover {border-color: var(--blue); background: transparent;}

/* ---------- зона загрузки и раскрывающийся блок ---------- */
[data-testid="stFileUploaderDropzone"] {
    background: var(--card); border: 1px dashed var(--muted); border-radius: 18px;
}
[data-testid="stFileUploaderFile"] {border-radius: 12px;}
[data-testid="stExpander"] details {
    background: var(--card); border: 1px solid var(--line); border-radius: 16px;
}
[data-testid="stElementContainer"]:has([data-testid="stButton"]) {margin-top: .2rem;}
/* колонки по ширине содержимого и рядом (в них стоят кнопки отправки) */
[data-testid="stHorizontalBlock"] {gap: .8rem; flex-wrap: wrap;}
[data-testid="stColumn"] [data-testid="stBaseButton-secondary"], [data-testid="column"] [data-testid="stBaseButton-secondary"] {margin-top: 0;}
[data-testid="stColumn"], [data-testid="column"] {flex: 0 0 auto !important; width: auto !important; min-width: 0 !important;}

/* ---------- русские надписи в зоне загрузки ----------
   Streamlit пишет их по-английски и не даёт поменять, поэтому прячем оригинал (font-size: 0)
   и рисуем свой текст через ::after. Если поменяете лимит файла, поправьте «10 МБ» (MAX_UPLOAD_MB в backend/main.py). */
[data-testid="stFileUploaderDropzone"] button [data-testid="stMarkdownContainer"] p {font-size: 0 !important;}
[data-testid="stFileUploaderDropzone"] button [data-testid="stMarkdownContainer"] p::after {
    content: "Выбрать файлы"; font-size: 1rem;}
[data-testid="stFileUploaderDropzoneInstructions"] span {font-size: 0 !important;}
[data-testid="stFileUploaderDropzoneInstructions"] span::after {
    content: "До 10 МБ на файл · JPG, PNG, WEBP, PDF"; font-size: .875rem;}

/* ---------- перетаскивание файлов на всю страницу (скрипт PAGE_DROP_JS ниже) ----------
   Пока над окном тащат файл, страница размывается и появляется рамка; бросить можно в любое место. */
[data-testid="stMainBlockContainer"] {transition: filter .2s ease;}
body.page-drop-active [data-testid="stMainBlockContainer"] {filter: blur(8px) brightness(.75);}
.page-drop {position: fixed; inset: 14px; z-index: 1000000; pointer-events: none; opacity: 0;
            border: 2px dashed var(--blue); border-radius: 28px; transition: opacity .2s ease;
            display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px;
            background: color-mix(in srgb, var(--blue) 10%, transparent);}
body.page-drop-active .page-drop {opacity: 1;}
.page-drop b {font-size: 1.8rem; font-weight: 400; color: var(--text);}
.page-drop span {font-size: .95rem; color: var(--muted);}
/* невидимый iframe со скриптом не должен занимать место в странице */
[data-testid="stElementContainer"]:has(iframe[height="0"]) {position: absolute; height: 0; margin: 0; overflow: hidden;}

/* ===== ВРЕМЕННО: выравнивание по центру (чтобы откатить, удалите всё до метки КОНЕЦ) ===== */
.stApp h1, .stApp h2, .stApp h3, [data-testid="stCaptionContainer"],
.result {text-align: center;}
[data-testid="stElementContainer"]:has([data-testid="stButton"]) {align-self: center;}
[data-testid="stHorizontalBlock"] {justify-content: center;}
[data-testid="stButton"] {display: flex; justify-content: center; width: auto;}
[data-testid="stAlertContainer"] {justify-content: center; text-align: center;}
[data-testid="stSelectbox"] input {text-align: center;}
[data-testid="stTextInput"] input {text-align: center;}
/* ===== КОНЕЦ временного блока ===== */
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
    """Подключает стили и рисует шапку страницы."""
    st.markdown(CSS, unsafe_allow_html=True)
    st.title("Онлайн-деканат")
    components.html(PAGE_DROP_JS, height=0)  # перетаскивание файлов на всю страницу
