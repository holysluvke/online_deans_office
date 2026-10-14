"""
Русские названия полей — для текста ответа и для разбора вопроса «Укажи значение поля «X»».
"""

# Машинный ключ → русская подпись. Нужен для message в ответе.
LABELS: dict[str, str] = {
    "student_name":     "ФИО студента",
    "university":       "Название вуза",
    "program":          "Направление подготовки",
    "study_form":       "Форма обучения",
    "study_start":      "Начало периода обучения",
    "study_end":        "Окончание периода обучения",
    "document_number":  "Номер справки",
    "issue_date":       "Дата выдачи",
    "group":            "Учебная группа",
    "course":           "Курс",
    "leave_reason":     "Причина отпуска",
    "leave_start":      "Дата начала отпуска",
    "leave_end":        "Дата окончания отпуска",
    "application_date": "Дата заявления",
    "organization":     "Название организации",
    "internship_start": "Дата начала практики",
    "internship_end":   "Дата окончания практики",
    "supervisor_name":  "ФИО руководителя практики",
    "grade":            "Оценка",
}

# Русская подпись флага зависит от типа документа: у заявления — «Подпись студента»,
# у справки о практике — «Подпись руководителя».
SIGN_LABELS: dict[str, dict[str, str]] = {
    "study_certificate":          {"signature_present": "Подпись сотрудника",
                                   "seal_present":      "Печать вуза"},
    "academic_leave_application": {"signature_present": "Подпись студента"},
    "internship_certificate":     {"signature_present": "Подпись руководителя",
                                   "seal_present":      "Печать организации"},
}

# Обратный словарь для Q2: подпись в нижнем регистре → ключ поля.
LABEL_TO_FIELD: dict[str, str] = {
    "фио студента":               "student_name",
    "название вуза":              "university",
    "направление подготовки":     "program",
    "форма обучения":             "study_form",
    "начало периода обучения":    "study_start",
    "окончание периода обучения": "study_end",
    "номер справки":              "document_number",
    "дата выдачи":                "issue_date",
    "учебная группа":             "group",
    "курс":                       "course",
    "причина отпуска":            "leave_reason",
    "дата начала отпуска":        "leave_start",
    "дата окончания отпуска":     "leave_end",
    "дата заявления":             "application_date",
    "название организации":       "organization",
    "дата начала практики":       "internship_start",
    "дата окончания практики":    "internship_end",
    "фио руководителя практики":  "supervisor_name",
    "оценка":                     "grade",
}


def label_for(field: str, doc_type: str) -> str:
    """Русская подпись поля. Для флагов подписи/печати — подпись зависит от типа."""
    if field in SIGN_LABELS.get(doc_type, {}):
        return SIGN_LABELS[doc_type][field]
    return LABELS.get(field, field)