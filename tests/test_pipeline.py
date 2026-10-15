"""
Уровень A (issue #2 и #1): эталонные поля -> answer_question -> evaluate.py даёт 1.0.
Заменяет старый скрипт test_pipeline.py из корня: тот надо удалить.
"""
import json
from pathlib import Path

import pytest

from backend.pipeline import answer_question
from tools import run_batch

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = next((p for p in (ROOT / "data/open/reference_results.json", ROOT / "reference_results.json") if p.is_file()), None)

pytestmark = pytest.mark.skipif(REFERENCE is None, reason="нет reference_results.json")


def test_gold_level_a_is_perfect():
    results, _, ref = run_batch.run("gold", reference=str(REFERENCE), quiet=True)
    assert run_batch.check_format(results) == []
    report = run_batch.load_evaluate().evaluate(ref, results)
    assert report["format_valid"] is True
    assert report["documents"] == 30 and report["questions"] == 120
    assert report["field_accuracy_macro"] == 1.0
    assert report["validation_exact_match"] == 1.0
    assert report["question_exact_match"] == 1.0
    assert report["errors"] == []


def test_answer_question_contract_has_six_keys():
    fields = {"student_name": "Иванов", "issue_date": "не найдено"}
    result = answer_question(fields, "study_certificate", "Содержит ли документ все обязательные сведения?")
    assert set(result) == {"status", "message", "sources", "answerable", "value", "missing_fields"}
    assert result["status"] in {"ok", "missing", "no_answer"}
    assert isinstance(result["message"], str) and result["message"]
    assert all(isinstance(s, str) for s in result["sources"])
    assert isinstance(result["answerable"], bool)
    assert isinstance(result["missing_fields"], list)
    json.dumps(result, ensure_ascii=False)  # jobs.py кладёт ответ в SQLite как JSON
