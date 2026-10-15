"""Интеграционный тест: матчинг + evaluate.py на эталонных данных."""
import json
from pathlib import Path

import pytest

from backend.knowledge import check_completeness
from backend.pipeline import answer_question

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_json(name: str) -> dict:
    path = PROJECT_ROOT / name
    if not path.is_file():
        pytest.skip(f"Нет файла организаторов: {name}")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _build_results(reference: dict, questions: list[dict]) -> dict:
    """Собирает results.json из эталона — без записи на диск."""
    questions_by_doc: dict[str, list[dict]] = {}
    for q in questions:
        questions_by_doc.setdefault(q["document_id"], []).append(q)

    documents = [
        _document_result(doc, questions_by_doc[doc["document_id"]])
        for doc in reference["documents"]
    ]
    return {"version": "1.0", "documents": documents}


def _document_result(doc: dict, questions: list[dict]) -> dict:
    fields = doc["fields"]
    doc_type = doc["document_type"]
    validation = check_completeness(fields, doc_type)

    return {
        "document_id":   doc["document_id"],
        "document_type": doc_type,
        "fields":        fields,
        "validation": {
            "status":         validation.value,
            "missing_fields": validation.missing_fields,
            "sources":        validation.sources,
        },
        "answers": [_answer_result(fields, doc_type, q) for q in questions],
    }


def _answer_result(fields: dict, doc_type: str, question: dict) -> dict:
    r = answer_question(fields, doc_type, question["question"])
    return {
        "question_id": question["question_id"],
        "answerable":  r["answerable"],
        "value":       r["value"],
        "answer":      r["message"],
        "sources":     r["sources"],
    }


# Тест

def test_evaluate_returns_perfect_scores_on_reference():
    """Полный прогон: answer_question на эталоне → evaluate.py → 1.0 по трём метрикам."""
    from evaluate import evaluate   # evaluate.py лежит в корне

    reference = _load_json("reference_results.json")
    questions = _load_json("questions.json")

    predictions = _build_results(reference, questions)
    report = evaluate(reference, predictions)

    assert report["format_valid"] is True
    assert report["errors"] == []
    assert report["field_accuracy_macro"] == 1.0
    assert report["validation_exact_match"] == 1.0
    assert report["question_exact_match"] == 1.0