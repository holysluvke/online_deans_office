"""
=====================  ЭТО МЕСТО ДЛЯ ML-ЧАСТИ  =====================

Сейчас здесь две ЗАГЛУШКИ: они возвращают фейковые данные, чтобы сайт можно было
разрабатывать и проверять, не дожидаясь настоящего распознавания.

Что нужно сделать:
    - заменить ТЕЛО функций extract_fields и answer_question на настоящий код
      (OCR и поиск по Положению);
    - НЕ менять названия функций, их аргументы и ФОРМАТ того, что они возвращают.
      Тогда очередь (jobs.py), бэкенд (main.py) и страница (ui/app.py) продолжат
      работать без правок.

Как это вызывается (backend/jobs.py), по порядку:
    fields = extract_fields(путь_к_фото, doc_type)
    result = answer_question(fields, doc_type, вопрос_студента)

Если внутри функции что-то пошло не так, достаточно сделать raise Exception("понятный текст").
Задача получит статус «Ошибка», а текст покажется на странице; остальные задачи не пострадают.

doc_type - одно из:
    "study_certificate"           справка об обучении
    "academic_leave_application"  заявление на академический отпуск
    "internship_certificate"      справка о практике

Прогрев (backend/warmup.py): при старте сервера в фоне вызывается warmup(). В нём нужно загрузить в память
все модели (Paddle, TrOCR, эмбеддинги и т. д.), чтобы первый документ не ждал загрузки. Загружать лучше в
глобальную переменную один раз, а extract_fields / answer_question пусть берут модель оттуда (см. пример ниже).

Что возвращают функции:
    extract_fields  -> словарь {имя_поля: значение}; не найденное поле = "не найдено", печать/подпись = True/False
    answer_question -> {"status": "ok" | "missing" | "no_answer", "message": "текст ответа", "sources": ["п. 3.4"]}
                       ok = документ в порядке, missing = чего-то не хватает, no_answer = ответа нет (не выдумывать)
"""
import time


def extract_fields(image_path: str, doc_type: str) -> dict:
    """ЗАГЛУШКА OCR: по фото вернуть поля документа."""
    #тестовая заглушка
    time.sleep(1)  # притворяемся, что думаем
    return {
        "fio": "Иванов Иван Иванович",
        "university": "Южный федеральный университет",
        "issue_date": "не найдено",
        "stamp": False,
    }


def answer_question(fields: dict, doc_type: str, question: str) -> dict:
    """ЗАГЛУШКА RAG: по полям и вопросу вернуть ответ со ссылкой на пункт."""
    #тестовая заглушка
    time.sleep(1)
    return {
        "status": "ok",  # ok / missing / no_answer
        "message": "Не хватает даты выдачи и печати вуза. Эти поля обязательны по п. 3.4 Положения.",
        "sources": ["п. 3.4"],
    }


def warmup() -> None:
    """Загружает модели в память заранее (вызывается при старте сервера и командой python -m backend.warmup).

    ЗАГЛУШКА: сейчас моделей нет, поэтому ничего не делает. Когда появятся, загружайте их здесь, например:

        global _ocr, _trocr
        from paddleocr import PaddleOCR
        _ocr = PaddleOCR(lang="ru")                      # при первом запуске скачает модели (нужна сеть)
        if os.getenv("USE_TROCR") == "1":                # TrOCR только если включён
            from transformers import TrOCRProcessor, VisionEncoderDecoderModel
            _trocr = (TrOCRProcessor.from_pretrained(...), VisionEncoderDecoderModel.from_pretrained(...))

    А в extract_fields использовать уже загруженные _ocr и _trocr, а не создавать их заново.
    """

