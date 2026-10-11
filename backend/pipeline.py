import time


def extract_fields(image_path: str, doc_type: str) -> dict:
    """ЗАГЛУШКА OCR: по фото вернуть поля документа."""
    #тестовая заглушка
    time.sleep(2)  # притворяемся, что думаем
    return {
        "fio": "Иванов Иван Иванович",
        "university": "Южный федеральный университет",
        "issue_date": "не найдено",
        "stamp": False,
    }


def answer_question(fields: dict, doc_type: str, question: str) -> dict:
    """ЗАГЛУШКА RAG: по полям и вопросу вернуть ответ со ссылкой на пункт."""
    #тестовая заглушка
    time.sleep(2)
    return {
        "status": "missing",  # ok / missing / no_answer
        "message": "Не хватает даты выдачи и печати вуза. Эти поля обязательны по п. 3.4 Положения.",
        "sources": ["п. 3.4"],
    }