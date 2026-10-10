version: 1
A health-professions faculty member described a simulated patient for a teaching case. Propose words for the case builder form. Output JSON only. The faculty member reviews and edits every field.

Rules:
1. Use only what the description and notes state or clearly imply. If a field is not supported, return an empty string or an empty list. Do not invent diagnoses, medications or allergies.
2. Never write vital signs, lab values or any measurement. Age is the only number you may return.
3. "chief_complaint" is the reason for the visit in the patient's own spoken words, first person.
4. "hidden" is what the patient holds back until they trust the student, if the description says so.
5. "student_role" is a profession and training level a learner actually holds (for example "third-year medical student"), never a specialist title.
6. "objectives" is one to three short learning objectives, one per line.
7. "speaker" is who talks in the visit when it is not the patient (for example "her mother"); otherwise empty.
8. Plain words. No markdown.

Output exactly:
{"name":"","age":0,"sex":"female","pronouns":"","occupation":"","speaker":"",
 "setting":"","reason_for_visit":"","student_role":"","goal":"",
 "chief_complaint":"","social":"","goals_fears":"","hidden":"","personal_cue":"","objectives":"",
 "conditions":["..."],"medications":[{"name":"","dose":"","frequency":"","purpose":""}],
 "allergies":[{"substance":"","reaction":""}],"no_known_allergies":false,
 "personality":"","communication_style":"","health_literacy":"medium","mood":"",
 "documentation_template":"SOAP"}
