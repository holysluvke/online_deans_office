"""Тесты матчинга Q2: пары начало/окончание, синонимы, опечатки, чужие типы."""
import unittest

from backend.knowledge import field_lookup


def _study_fields(**overrides) -> dict:
    base = {
        "student_name": "Иванов Иван Иванович",
        "university": "ЮФУ",
        "program": "ПИ",
        "study_form": "очная",
        "study_start": "2023-09-01",
        "study_end": "2027-06-30",
        "document_number": "123",
        "issue_date": "2024-05-15",
        "signature_present": True,
        "seal_present": True,
    }
    base.update(overrides)
    return base


def _leave_fields(**overrides) -> dict:
    base = {
        "student_name": "Петров Пётр Петрович",
        "group": "ИВТ-22-3",
        "course": "3",
        "leave_reason": "по состоянию здоровья",
        "leave_start": "2026-11-01",
        "leave_end": "2027-08-31",
        "application_date": "2026-10-07",
        "signature_present": True,
    }
    base.update(overrides)
    return base


def _practice_fields(**overrides) -> dict:
    base = {
        "student_name": "Сидоров Сидор Сидорович",
        "organization": "Спектр",
        "internship_start": "2026-06-01",
        "internship_end": "2026-07-15",
        "supervisor_name": "Соколова Анна Викторовна",
        "grade": "отлично",
        "document_number": "ПР-1",
        "issue_date": "2026-07-18",
        "signature_present": True,
        "seal_present": True,
    }
    base.update(overrides)
    return base


class TestQuotedLabels(unittest.TestCase):
    """Все Q2 из questions.json — точные подписи в кавычках."""

    def test_all_known_labels(self):
        cases = [
            (_study_fields(), "study_certificate", "ФИО студента", "student_name"),
            (_study_fields(), "study_certificate", "Дата выдачи", "issue_date"),
            (_study_fields(), "study_certificate", "Направление подготовки", "program"),
            (_study_fields(), "study_certificate", "Форма обучения", "study_form"),
            (_study_fields(), "study_certificate", "Название вуза", "university"),
            (_study_fields(), "study_certificate", "Окончание периода обучения", "study_end"),
            (_leave_fields(), "academic_leave_application", "Учебная группа", "group"),
            (_leave_fields(), "academic_leave_application", "Дата заявления", "application_date"),
            (_leave_fields(), "academic_leave_application", "Причина отпуска", "leave_reason"),
            (_leave_fields(), "academic_leave_application", "Дата начала отпуска", "leave_start"),
            (_leave_fields(), "academic_leave_application", "Дата окончания отпуска", "leave_end"),
            (_practice_fields(), "internship_certificate", "Дата начала практики", "internship_start"),
            (_practice_fields(), "internship_certificate", "Дата окончания практики", "internship_end"),
            (_practice_fields(), "internship_certificate", "ФИО руководителя практики", "supervisor_name"),
            (_practice_fields(), "internship_certificate", "Оценка", "grade"),
            (_practice_fields(), "internship_certificate", "Название организации", "organization"),
        ]
        for fields, doc_type, label, expected in cases:
            with self.subTest(label=label):
                r = field_lookup(fields, doc_type, f"Укажи значение поля «{label}».")
                self.assertEqual(r.sources, [f"field:{expected}"],
                                 f"{label} → {r.sources}, ожидалось field:{expected}")


class TestStartEndPairs(unittest.TestCase):
    """Критичные пары начало/окончание — не должны путаться."""

    def test_study_period(self):
        f = _study_fields()
        start = field_lookup(f, "study_certificate", "Начало периода обучения")
        end   = field_lookup(f, "study_certificate", "Окончание периода обучения")
        self.assertEqual(start.sources, ["field:study_start"])
        self.assertEqual(end.sources,   ["field:study_end"])

    def test_leave_period(self):
        f = _leave_fields()
        start = field_lookup(f, "academic_leave_application", "Дата начала отпуска")
        end   = field_lookup(f, "academic_leave_application", "Дата окончания отпуска")
        self.assertEqual(start.sources, ["field:leave_start"])
        self.assertEqual(end.sources,   ["field:leave_end"])

    def test_internship_period(self):
        f = _practice_fields()
        start = field_lookup(f, "internship_certificate", "Дата начала практики")
        end   = field_lookup(f, "internship_certificate", "Дата окончания практики")
        self.assertEqual(start.sources, ["field:internship_start"])
        self.assertEqual(end.sources,   ["field:internship_end"])

    def test_student_vs_supervisor(self):
        """ФИО студента ≠ ФИО руководителя практики."""
        f = _practice_fields()
        student    = field_lookup(f, "internship_certificate", "ФИО студента")
        supervisor = field_lookup(f, "internship_certificate", "ФИО руководителя практики")
        self.assertEqual(student.sources,    ["field:student_name"])
        self.assertEqual(supervisor.sources, ["field:supervisor_name"])


class TestSynonyms(unittest.TestCase):
    def test_when_issued(self):
        r = field_lookup(_study_fields(), "study_certificate", "Когда выдана справка?")
        self.assertEqual(r.sources, ["field:issue_date"])

    def test_grade(self):
        r = field_lookup(_practice_fields(), "internship_certificate", "Какая оценка?")
        self.assertEqual(r.value, "отлично")
        self.assertEqual(r.sources, ["field:grade"])

    def test_who_supervisor(self):
        r = field_lookup(_practice_fields(), "internship_certificate",
                         "Кто руководитель практики?")
        self.assertEqual(r.sources, ["field:supervisor_name"])

    def test_how_student_named(self):
        r = field_lookup(_study_fields(), "study_certificate", "Как зовут студента?")
        self.assertEqual(r.sources, ["field:student_name"])


class TestNoQuotes(unittest.TestCase):
    """Вопросы без кавычек — по п. 6.4 Положения."""

    def test_issue_date_no_quotes(self):
        r = field_lookup(_study_fields(), "study_certificate", "Какова дата выдачи?")
        self.assertEqual(r.value, "2024-05-15")
        self.assertEqual(r.sources, ["field:issue_date"])

    def test_university_no_quotes(self):
        r = field_lookup(_study_fields(), "study_certificate", "Как называется вуз?")
        self.assertEqual(r.sources, ["field:university"])


class TestTypos(unittest.TestCase):
    def test_typo_date(self):
        r = field_lookup(_study_fields(), "study_certificate", "Дата выздачи")
        self.assertEqual(r.sources, ["field:issue_date"])

    def test_typo_group(self):
        r = field_lookup(_leave_fields(), "academic_leave_application", "Учеьная группа")
        self.assertEqual(r.sources, ["field:group"])


class TestMissingField(unittest.TestCase):
    """Поле есть в типе, но в документе его нет."""

    def test_missing_value(self):
        f = _study_fields(issue_date="не найдено")
        r = field_lookup(f, "study_certificate", "Укажи значение поля «Дата выдачи».")
        self.assertFalse(r.answerable)
        self.assertIsNone(r.value)
        self.assertEqual(r.sources, [])


class TestForeignField(unittest.TestCase):
    """Поле из чужого типа документа → no_answer."""

    def test_group_on_study_certificate(self):
        r = field_lookup(_study_fields(), "study_certificate",
                         "Укажи значение поля «Учебная группа».")
        self.assertEqual(r.status, "no_answer")
        self.assertFalse(r.answerable)
        self.assertEqual(r.sources, [])


class TestNoConfidentMatch(unittest.TestCase):
    """Не про поле — no_answer, не выдумываем."""

    def test_off_topic(self):
        r = field_lookup(_study_fields(), "study_certificate",
                         "Какова стоимость обучения?")
        self.assertEqual(r.status, "no_answer")

    def test_empty_question(self):
        r = field_lookup(_study_fields(), "study_certificate", "")
        self.assertEqual(r.status, "no_answer")


class TestMessageFormatting(unittest.TestCase):
    """Issue: дата — по-человечески в message, ISO в value."""

    def test_date_humanized_in_message(self):
        f = _study_fields(issue_date="2026-09-01")
        r = field_lookup(f, "study_certificate", "Укажи значение поля «Дата выдачи».")
        self.assertIn("1 сентября 2026", r.message)
        self.assertEqual(r.value, "2026-09-01")  # value остался ISO

    def test_non_date_not_changed(self):
        r = field_lookup(_study_fields(), "study_certificate", "Укажи значение поля «ФИО студента».")
        self.assertIn("Иванов Иван Иванович", r.message)
        self.assertNotIn("2026", r.message)


class TestTypeMismatchHint(unittest.TestCase):
    """Issue: если пропущена больше половины полей — hint про тип документа."""

    def test_majority_missing(self):
        from backend.knowledge import check_completeness
        # 5 из 8 полей отсутствуют — больше половины
        f = _study_fields(
            student_name="не найдено", university="не найдено",
            program="не найдено", study_form="не найдено",
            issue_date="не найдено",
        )
        r = check_completeness(f, "study_certificate")
        self.assertIn("Возможно, выбран не тот тип документа", r.message)

    def test_half_missing_no_hint(self):
        from backend.knowledge import check_completeness
        # 4 из 8 — ровно половина, порог не превышен
        f = _study_fields(
            student_name="не найдено", university="не найдено",
            program="не найдено", study_form="не найдено",
        )
        r = check_completeness(f, "study_certificate")
        self.assertNotIn("Возможно, выбран не тот тип документа", r.message)


class TestFioKeepsCase(unittest.TestCase):
    """Issue: убрать .lower() — «ФИО» не превращается в «фио»."""

    def test_fio_uppercase_in_message(self):
        from backend.knowledge import check_completeness
        f = _study_fields(student_name="не найдено")
        r = check_completeness(f, "study_certificate")
        self.assertIn("ФИО", r.message)
        self.assertNotIn("фио студента", r.message)


class TestTransferQuestion(unittest.TestCase):
    """Issue: «Хватит ли справки для перевода?» → п. 3.5, answerable: false."""

    def test_detector(self):
        from backend.knowledge.transfer import is_transfer_question
        self.assertTrue(is_transfer_question("Хватит ли справки для перевода на 2 курс?"))
        self.assertTrue(is_transfer_question("Можно ли перевестись?"))
        self.assertTrue(is_transfer_question("Есть ли академические задолженности?"))
        self.assertFalse(is_transfer_question("Содержит ли документ все обязательные сведения?"))

    def test_transfer_answer_shape(self):
        from backend.knowledge.transfer import transfer_answer
        r = transfer_answer(_study_fields(), "study_certificate")
        self.assertEqual(r.status, "no_answer")
        self.assertFalse(r.answerable)
        self.assertIsNone(r.value)
        self.assertEqual(r.sources, [])
        self.assertIn("3.5", r.message)

    def test_transfer_message_contains_completeness(self):
        """В message — и п. 3.5, и результат проверки комплектности."""
        from backend.knowledge.transfer import transfer_answer
        r = transfer_answer(_study_fields(), "study_certificate")
        # Документ полный — в message будет «содержит все обязательные сведения»
        self.assertIn("все обязательные сведения", r.message)


if __name__ == "__main__":
    unittest.main()