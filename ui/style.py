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
    .tagline                             строка над заголовком
"""
import streamlit as st

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
.tagline {color: var(--blue); font-size: .75rem; font-weight: 500;
          letter-spacing: .1em; text-transform: uppercase; margin-bottom: 4px;}

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
.bar {height: 4px; border-radius: 999px; background: var(--line); margin-top: 12px; overflow: hidden;}
.bar span {display: block; height: 100%; border-radius: 999px;
           background: var(--bar);}
.job.done .bar {display: none;}  /* у готовых карточек линия не нужна */
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
</style>
"""


def render_header() -> None:
    """Подключает стили и рисует шапку страницы."""
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="tagline">Цифровой секретарь · OCR → поля → Положение</div>',
        unsafe_allow_html=True,
    )
    st.title("Онлайн-деканат")
