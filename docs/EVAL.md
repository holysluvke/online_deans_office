# Eval-стенд: как мерить качество

Всё запускается из корня проекта, с включённым окружением (`.venv\Scripts\activate`).
Стенд не ходит в сеть и не трогает веб-часть: он вызывает те же `extract_fields` и `answer_question`, что и очередь.

## 1. Данные организаторов

Распакуйте открытый набор так (папка `data/` в `.gitignore`, в git не попадает):

```
data/open/
├── documents/            все PNG и PDF (open-001.png, open-001.pdf, ...)
├── documents.json
├── questions.json
└── reference_results.json
```

`documents.json` читается терпимо: подойдёт список, `{"documents": [...]}` или `{id: {...}}`;
файл ищется по любому строковому значению с расширением png/jpg/webp/pdf, а если не нашёлся,
то по имени `documents/<document_id>.*`. Тип документа берётся из `documents.json`, иначе из эталона.

## 2. Команды

| Что | Команда |
|---|---|
| Уровень A (эталонные поля → правила). Обязан дать 1.0 | `python tools/run_batch.py --mode gold` |
| Уровень B, фото (baseline OCR) | `python tools/run_batch.py --mode ocr --source png` |
| Уровень B, PDF как на сайте (PDF → PNG 300 dpi) | `python tools/run_batch.py --mode ocr --source pdf` |
| Уровень B, PDF напрямую в OCR (200 dpi) | `... --source pdf --pdf-direct` |
| Только часть документов | `--ids open-001,open-005` или `--limit 5` |
| Перечитать OCR, игнорируя кэш | `--no-cache` |
| Сохранить отчёт в файл | `--md report.md` |
| Отчёт по уже готовому results.json | `python tools/field_report.py --results results.json` |
| Спайк #4: текстовый слой в PDF | `python tools/pdf_text_probe.py --ocr-results results.json` |
| Бонус #15: испортить снимки | `python tools/degrade.py` |
| Бонус #15: кривая точности | `python tools/degrade_curve.py` |
| Тесты | `python -m pytest tests -q` |

`run_batch` печатает: секунды на документ, метрики `evaluate.py`, таблицу ошибок.
Код возврата: `0` ок, `1` уровень A не дал 1.0, `2` формат `results.json` неверен.

## 3. Как читать отчёт

- **F** — ложное «найдено»: в эталоне «не найдено», а мы вернули значение. Самая дорогая ошибка:
  Q1 скажет «документ в порядке», когда это не так, и обнулится весь документ в `validation_exact_match`.
- **M** — ложное «не найдено»: значение есть, мы его не увидели.
- **W** — неверное значение (в том числе промах подписи или печати).
- Подпись и печать: precision и recall раздельно для «есть» и «нет». Цель #7: ≥ 95%.
- Матрица «документ × поле» показывает, на каких именно документах ломается поле.

## 4. Кэш и скорость

Кэшируется только результат `run_ocr` (самое долгое), в `data/cache/ocr`, по хешу файла и настроек OCR.
`fields.py` и `knowledge/*` кэш не сбрасывают: разбор полей пересчитывается каждый раз за миллисекунды.
Цикл `@ocr`: поправил `fields.py` → `python tools/run_batch.py --mode ocr` (секунды) → смотрит F/M/W.
Правки `engine.py`, `preprocess.py`, `text.py`, `intake.py`, `handwriting.py`, смена `USE_HANDWRITING`
и настроек Paddle сбрасывают кэш автоматически. Первый прогон на 30 документах долгий, остальные мгновенные.

## 5. Закрытая проверка и итоговый results.json

```
python tools/run_batch.py --mode ocr --source png --data data/closed --out results.json
```

Эталона в `data/closed` нет, поэтому метрики не считаются, но формат проверяется (и по
`results.schema.json`, если положить его в корень или в `data/open/` и поставить `pip install jsonschema`).
Рядом ляжет `results.meta.json` с секундами на документ: по нему видно, уложитесь ли во время.
Если OCR упал на файле, документ всё равно попадает в `results.json` (все поля «не найдено»),
а причина записывается в `results.meta.json` и в консоль.

## 6. Бонус #15: порча снимков

`python tools/degrade.py` делает `data/degraded/level_0..4/` (готовые папки данных), затем
`python tools/degrade_curve.py` прогоняет их и пишет `data/degraded/curve.csv` и `curve.png` (нужен `matplotlib`).
Один и тот же `--seed` даёт одни и те же снимки.
