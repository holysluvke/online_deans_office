```
== Точность по полям (документов: 30, всего значений: 280, верно: 73.6%)
F: ложное «найдено», M: ложное «не найдено», W: неверное значение
тип документа               поле               n   верно %  F  M  W
--------------------------  -----------------  --  -------  -  -  -
academic_leave_application  application_date   10  100.0    0  0  0
academic_leave_application  course             10   10.0    0  9  0
academic_leave_application  group              10   90.0    0  1  0
academic_leave_application  leave_end          10   80.0    1  0  1
academic_leave_application  leave_reason       10   80.0    1  0  1
academic_leave_application  leave_start        10   90.0    1  0  0
academic_leave_application  signature_present  10   10.0    0  0  9
academic_leave_application  student_name       10  100.0    0  0  0
internship_certificate      document_number    10   90.0    1  0  0
internship_certificate      grade              10  100.0    0  0  0
internship_certificate      internship_end     10   60.0    1  0  3
internship_certificate      internship_start   10   70.0    1  0  2
internship_certificate      issue_date         10  100.0    0  0  0
internship_certificate      organization       10   40.0    1  0  5
internship_certificate      seal_present       10   90.0    0  0  1
internship_certificate      signature_present  10   20.0    0  0  8
internship_certificate      student_name       10  100.0    0  0  0
internship_certificate      supervisor_name    10   90.0    1  0  0
study_certificate           document_number    10   90.0    1  0  0
study_certificate           issue_date         10  100.0    0  0  0
study_certificate           program            10   60.0    1  0  3
study_certificate           seal_present       10   90.0    0  0  1
study_certificate           signature_present  10   20.0    0  0  8
study_certificate           student_name       10  100.0    0  0  0
study_certificate           study_end          10   80.0    1  0  1
study_certificate           study_form         10  100.0    0  0  0
study_certificate           study_start        10   90.0    1  0  0
study_certificate           university         10   10.0    0  0  9

Итого ошибок: F=12 (опасные), M=10, W=52

== Подпись и печать (цель из #7: precision и recall >= 95%)
флаг               класс  precision %  recall %  в эталоне  ложно +  ложно -
-----------------  -----  -----------  --------  ---------  -------  -------
signature_present  есть     -            0.0     25         0        25     
signature_present  нет     16.7        100.0     5          25       0      
seal_present       есть    88.9        100.0     16         2        0      
seal_present       нет    100.0         50.0     4          0        2      
промахи signature_present: open-001, open-002, open-004, open-005, open-006, open-007, open-008, open-009, open-011, open-012, open-014, open-015, open-016, open-017, open-018, open-019, open-020, open-021, open-022, open-024, open-025, open-026, open-027, open-028, open-029
промахи seal_present: open-004, open-024

== Матрица документ x поле  (. верно, F ложное найдено, M ложное не найдено, W неверно)

study_certificate
   1 = student_name
   2 = university
   3 = program
   4 = study_form
   5 = study_start
   6 = study_end
   7 = document_number
   8 = issue_date
   9 = signature_present
  10 = seal_present
  id        1  2  3  4  5  6  7  8  9 10
  open-001  .  W  .  .  .  .  .  .  W  .
  open-002  .  W  W  .  .  .  .  .  W  .
  open-003  .  W  .  .  .  .  .  .  .  .
  open-004  .  W  W  .  .  .  .  .  W  W
  open-005  .  W  W  .  .  .  F  .  W  .
  open-006  .  .  .  .  F  W  .  .  W  .
  open-007  .  W  F  .  .  .  .  .  W  .
  open-008  .  W  .  .  .  .  .  .  W  .
  open-009  .  W  .  .  .  F  .  .  W  .
  open-010  .  W  .  .  .  .  .  .  .  .

academic_leave_application
   1 = student_name
   2 = group
   3 = course
   4 = leave_reason
   5 = leave_start
   6 = leave_end
   7 = application_date
   8 = signature_present
  id        1  2  3  4  5  6  7  8
  open-011  .  .  M  .  .  .  .  W
  open-012  .  .  M  .  .  .  .  W
  open-013  .  M  M  .  .  .  .  .
  open-014  .  .  M  F  .  .  .  W
  open-015  .  .  M  W  .  .  .  W
  open-016  .  .  .  .  .  .  .  W
  open-017  .  .  M  .  F  W  .  W
  open-018  .  .  M  .  .  .  .  W
  open-019  .  .  M  .  .  F  .  W
  open-020  .  .  M  .  .  .  .  W

internship_certificate
   1 = student_name
   2 = organization
   3 = internship_start
   4 = internship_end
   5 = supervisor_name
   6 = grade
   7 = document_number
   8 = issue_date
   9 = signature_present
  10 = seal_present
  id        1  2  3  4  5  6  7  8  9 10
  open-021  .  W  .  .  .  .  .  .  W  .
  open-022  .  .  .  .  .  .  .  .  W  .
  open-023  .  W  .  .  .  .  .  .  .  .
  open-024  .  W  .  .  .  .  .  .  W  W
  open-025  .  .  W  W  .  .  F  .  W  .
  open-026  .  F  F  W  .  .  .  .  W  .
  open-027  .  .  W  W  F  .  .  .  W  .
  open-028  .  W  .  .  .  .  .  .  W  .
  open-029  .  .  .  F  .  .  .  .  W  .
  open-030  .  W  .  .  .  .  .  .  .  .

== Ошибки полей: ожидалось -> получено (первые 60)
  [W] open-001 university: 'Учебный университет «Меридиан»' -> 'Название вуза: Учебный университет «Меридиан»'
  [W] open-001 signature_present: True -> False
  [W] open-002 university: 'Учебная академия «Горизонт»' -> 'Название вуза: Учебная академия'
  [W] open-002 program: '09.03.01 Информатика и вычислительная техника' -> 'О9.03.01 Информатика и вычислительная техника'
  [W] open-002 signature_present: True -> False
  [W] open-003 university: 'Учебная академия «Горизонт»' -> 'Название вуза: Учебная академия «Горизонт»'
  [W] open-004 university: 'Учебный университет «Меридиан»' -> 'Название вуза: Учебный университет «Меридиан»'
  [W] open-004 program: '09.03.01 Информатика и вычислительная техника' -> 'О9.о3.01 Информатика и вычислительная техника'
  [W] open-004 signature_present: True -> False
  [W] open-004 seal_present: False -> True
  [W] open-005 university: 'Учебная академия «Горизонт»' -> 'Название вуза: Учебная академия'
  [W] open-005 program: '09.03.01 Информатика и вычислительная техника' -> 'О9.о3.01 Информатика и вычислительная техника'
  [F] open-005 document_number: 'не найдено' -> 'справки'
  [W] open-005 signature_present: True -> False
  [F] open-006 study_start: 'не найдено' -> '2026-08-31'
  [W] open-006 study_end: '2026-08-31' -> '2026-09-20'
  [W] open-006 signature_present: True -> False
  [W] open-007 university: 'Учебный университет «Меридиан»' -> 'Название вуза: Учебный университет «Меридиан»'
  [F] open-007 program: 'не найдено' -> 'Форма обучения:'
  [W] open-007 signature_present: True -> False
  [W] open-008 university: 'Учебный университет «Меридиан»' -> 'Название вуза: Учебный университет «Меридиан»'
  [W] open-008 signature_present: True -> False
  [W] open-009 university: 'Учебная академия «Горизонт»' -> 'Название вуза: Учебная академия «Горизонт»'
  [F] open-009 study_end: 'не найдено' -> '2026-09-21'
  [W] open-009 signature_present: True -> False
  [W] open-010 university: 'Учебный институт «Вектор»' -> 'Название вуза: Учебный институт «Вектор»'
  [M] open-011 course: '3' -> 'не найдено'
  [W] open-011 signature_present: True -> False
  [M] open-012 course: '3' -> 'не найдено'
  [W] open-012 signature_present: True -> False
  [M] open-013 group: 'ЭК-24-2' -> 'не найдено'
  [M] open-013 course: '4' -> 'не найдено'
  [M] open-014 course: '2' -> 'не найдено'
  [F] open-014 leave_reason: 'не найдено' -> 'отпуска:'
  [W] open-014 signature_present: True -> False
  [M] open-015 course: '4' -> 'не найдено'
  [W] open-015 leave_reason: 'в связи с уходом за родственником' -> 'отпуска: в связи с уходом за родственником'
  [W] open-015 signature_present: True -> False
  [W] open-016 signature_present: True -> False
  [M] open-017 course: '1' -> 'не найдено'
  [F] open-017 leave_start: 'не найдено' -> '2027-08-31'
  [W] open-017 leave_end: '2027-08-31' -> '2026-10-08'
  [W] open-017 signature_present: True -> False
  [M] open-018 course: '3' -> 'не найдено'
  [W] open-018 signature_present: True -> False
  [M] open-019 course: '2' -> 'не найдено'
  [F] open-019 leave_end: 'не найдено' -> '2026-10-02'
  [W] open-019 signature_present: True -> False
  [M] open-020 course: '2' -> 'не найдено'
  [W] open-020 signature_present: True -> False
  [W] open-021 organization: 'Учебная организация «Спектр»' -> 'Учебная организация «Спектр'
  [W] open-021 signature_present: True -> False
  [W] open-022 signature_present: True -> False
  [W] open-023 organization: 'Учебная организация «Спектр»' -> 'Учебная организация «Спектр'
  [W] open-024 organization: 'Учебная организация «Спектр»' -> 'Учебная организация «Спектр'
  [W] open-024 signature_present: True -> False
  [W] open-024 seal_present: False -> True
  [W] open-025 internship_start: '2026-06-01' -> '2026-07-15'
  [W] open-025 internship_end: '2026-07-15' -> '2026-07-16'
  [F] open-025 document_number: 'не найдено' -> 'справки'
  ... и ещё 14

== validation_exact_match: неверных документов 26 из 30
  open-001: ожидалось missing=[], получено missing=['signature_present']
  open-002: ожидалось missing=['issue_date'], получено missing=['issue_date', 'signature_present']
  open-004: ожидалось missing=['seal_present'], получено missing=['signature_present']
  open-005: ожидалось missing=['student_name', 'document_number'], получено missing=['student_name', 'signature_present']
  open-006: ожидалось missing=['university', 'study_start'], получено missing=['university', 'signature_present']
  open-007: ожидалось missing=['program', 'study_form'], получено missing=['study_form', 'signature_present']
  open-008: ожидалось missing=[], получено missing=['signature_present']
  open-009: ожидалось missing=['study_end'], получено missing=['signature_present']
  open-011: ожидалось missing=[], получено missing=['course', 'signature_present']
  open-012: ожидалось missing=['application_date'], получено missing=['course', 'application_date', 'signature_present']
  open-013: ожидалось missing=['signature_present'], получено missing=['group', 'course', 'signature_present']
  open-014: ожидалось missing=['leave_reason'], получено missing=['course', 'signature_present']
  open-015: ожидалось missing=['student_name'], получено missing=['student_name', 'course', 'signature_present']
  open-016: ожидалось missing=['group', 'course'], получено missing=['group', 'course', 'signature_present']
  open-017: ожидалось missing=['leave_start'], получено missing=['course', 'signature_present']
  open-018: ожидалось missing=[], получено missing=['course', 'signature_present']
  open-019: ожидалось missing=['leave_end'], получено missing=['course', 'signature_present']
  open-020: ожидалось missing=['group', 'application_date'], получено missing=['group', 'course', 'application_date', 'signature_present']
  open-021: ожидалось missing=[], получено missing=['signature_present']
  open-022: ожидалось missing=['issue_date'], получено missing=['issue_date', 'signature_present']

== Точность по типам вопросов
тип вопроса                 n   верно  %    
--------------------------  --  -----  -----
Q1 комплектность            30  4       13.3
Q2 поле (есть в документе)  13  11      84.6
Q2 поле (пропущено)         17  9       52.9
Q3 кто решает               30  30     100.0
Q4 нет в документе          30  30     100.0

== Время: документов без кэша 30, среднее 13.2 с, максимум 34.9 с
```
