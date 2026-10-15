"""Локальная проверка answer_question на эталонных полях из reference_results.json."""
import json

from backend.knowledge import check_completeness
from backend.pipeline import answer_question


def build_results(reference_path: str, questions_path: str) -> dict:
    with open(reference_path, encoding="utf-8") as f:
        ref = json.load(f)
    with open(questions_path, encoding="utf-8") as f:
        questions = json.load(f)

    q_by_doc: dict[str, list[dict]] = {}
    for q in questions:
        q_by_doc.setdefault(q["document_id"], []).append(q)

    documents = [_document_result(doc, q_by_doc[doc["document_id"]]) for doc in ref["documents"]]
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


if __name__ == "__main__":
    result = build_results("reference_results.json", "questions.json")
    with open("results_mine.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"saved results_mine.json: {len(result['documents'])} documents")