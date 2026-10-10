version: 1
A faculty member answered one question about a simulated patient. Split the answer into facts the patient could share. Output JSON only.

Rules:
1. Use only what the answer says. Never add details, numbers or diagnoses.
2. "text": third-person chart sentence. "say": how the patient would say it, first person, plain spoken words.
3. Use the default tier and topics unless the answer clearly says otherwise (for example "only if they trust you" means "reluctant").
4. One to four facts.

Output exactly:
{"facts":[{"id":"f_short_name","category":"social","text":"...","say":"...","tier":"discoverable","topics":["social_living"],"cue":false,"safety":false}]}
