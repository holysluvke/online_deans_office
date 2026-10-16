```
== Точность по полям (документов: 30, всего значений: 280, верно: 100.0%)
F: ложное «найдено», M: ложное «не найдено», W: неверное значение
тип документа               поле               n   верно %  F  M  W
--------------------------  -----------------  --  -------  -  -  -
academic_leave_application  application_date   10  100.0    0  0  0
academic_leave_application  course             10  100.0    0  0  0
academic_leave_application  group              10  100.0    0  0  0
academic_leave_application  leave_end          10  100.0    0  0  0
academic_leave_application  leave_reason       10  100.0    0  0  0
academic_leave_application  leave_start        10  100.0    0  0  0
academic_leave_application  signature_present  10  100.0    0  0  0
academic_leave_application  student_name       10  100.0    0  0  0
internship_certificate      document_number    10  100.0    0  0  0
internship_certificate      grade              10  100.0    0  0  0
internship_certificate      internship_end     10  100.0    0  0  0
internship_certificate      internship_start   10  100.0    0  0  0
internship_certificate      issue_date         10  100.0    0  0  0
internship_certificate      organization       10  100.0    0  0  0
internship_certificate      seal_present       10  100.0    0  0  0
internship_certificate      signature_present  10  100.0    0  0  0
internship_certificate      student_name       10  100.0    0  0  0
internship_certificate      supervisor_name    10  100.0    0  0  0
study_certificate           document_number    10  100.0    0  0  0
study_certificate           issue_date         10  100.0    0  0  0
study_certificate           program            10  100.0    0  0  0
study_certificate           seal_present       10  100.0    0  0  0
study_certificate           signature_present  10  100.0    0  0  0
study_certificate           student_name       10  100.0    0  0  0
study_certificate           study_end          10  100.0    0  0  0
study_certificate           study_form         10  100.0    0  0  0
study_certificate           study_start        10  100.0    0  0  0
study_certificate           university         10  100.0    0  0  0

Итого ошибок: F=0 (опасные), M=0, W=0

== Подпись и печать (цель из #7: precision и recall >= 95%)
флаг               класс  precision %  recall %  в эталоне  ложно +  ложно -
-----------------  -----  -----------  --------  ---------  -------  -------
signature_present  есть   100.0        100.0     25         0        0      
signature_present  нет    100.0        100.0     5          0        0      
seal_present       есть   100.0        100.0     16         0        0      
seal_present       нет    100.0        100.0     4          0        0      

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
  open-001  .  .  .  .  .  .  .  .  .  .
  open-002  .  .  .  .  .  .  .  .  .  .
  open-003  .  .  .  .  .  .  .  .  .  .
  open-004  .  .  .  .  .  .  .  .  .  .
  open-005  .  .  .  .  .  .  .  .  .  .
  open-006  .  .  .  .  .  .  .  .  .  .
  open-007  .  .  .  .  .  .  .  .  .  .
  open-008  .  .  .  .  .  .  .  .  .  .
  open-009  .  .  .  .  .  .  .  .  .  .
  open-010  .  .  .  .  .  .  .  .  .  .

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
  open-011  .  .  .  .  .  .  .  .
  open-012  .  .  .  .  .  .  .  .
  open-013  .  .  .  .  .  .  .  .
  open-014  .  .  .  .  .  .  .  .
  open-015  .  .  .  .  .  .  .  .
  open-016  .  .  .  .  .  .  .  .
  open-017  .  .  .  .  .  .  .  .
  open-018  .  .  .  .  .  .  .  .
  open-019  .  .  .  .  .  .  .  .
  open-020  .  .  .  .  .  .  .  .

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
  open-021  .  .  .  .  .  .  .  .  .  .
  open-022  .  .  .  .  .  .  .  .  .  .
  open-023  .  .  .  .  .  .  .  .  .  .
  open-024  .  .  .  .  .  .  .  .  .  .
  open-025  .  .  .  .  .  .  .  .  .  .
  open-026  .  .  .  .  .  .  .  .  .  .
  open-027  .  .  .  .  .  .  .  .  .  .
  open-028  .  .  .  .  .  .  .  .  .  .
  open-029  .  .  .  .  .  .  .  .  .  .
  open-030  .  .  .  .  .  .  .  .  .  .

== Ошибки полей: ожидалось -> получено (первые 60)
  нет

== validation_exact_match: неверных документов 0 из 30

== Точность по типам вопросов
тип вопроса                 n   верно  %    
--------------------------  --  -----  -----
Q1 комплектность            30  30     100.0
Q2 поле (есть в документе)  13  13     100.0
Q2 поле (пропущено)         17  17     100.0
Q3 кто решает               30  30     100.0
Q4 нет в документе          30  30     100.0
```
