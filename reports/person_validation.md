# Anonymisation + PERSON validation (five supplied patients)

Generated 2026-10-22 by `scripts/etl_person.py` on the five-patient extract. All numbers below do not depend on the key. The run used a throwaway key, so no IDs, offsets or dates are shown here; re-run locally with the shared group key to produce the real outputs.

| Item | Result |
|---|---:|
| Patients / PERSON rows / DEATH rows | 5 / 5 / 2 |
| Source rows pseudonymised: person | 5 |
| Source rows pseudonymised: visit | 22 |
| Source rows pseudonymised: lab | 162 |
| Source rows pseudonymised: medication | 170 |
| Source rows pseudonymised: procedure | 7 |
| Unique cases in visit source | 21 |
| Cases only in other domains (visit FK left blank) | 5 |
| Rows with blank visit FK: lab | 162 |
| Rows with blank visit FK: medication | 0 |
| Rows with blank visit FK: procedure | 0 |
| Exact duplicate rows retained (flag for owner): visit | 1 |
| Exact duplicate rows retained (flag for owner): medication | 18 |
| Flag `dose_excel_date_corruption` | 2 |
| Gender concepts (8507 male / 8532 female) | 2 / 3 |
| Race concept 38003579 Chinese | 5 |

## Checks

- no source identifier in outputs: passed
- unique person ids: passed
- unique case ids: passed
- death after last event: passed
- death year preserved: passed
- nonzero concepts standard and verified: passed
- cross-domain consistency with the medication ETL (same key): every DRUG_EXPOSURE person_id is in PERSON, every DRUG_EXPOSURE visit_occurrence_id is in the anonymised visit table, and every drug start datetime equals a shifted order datetime: passed
- unit tests: 20 of 20 passed (`python -m unittest discover -s tests -v`)

## Re-identification risk (PERSON quasi-identifiers)

| Quasi-identifier set | Equivalence class sizes | Minimum k |
|---|---|---:|
| year_of_birth+sex+race | [1, 1, 1, 1, 1] | 1 |
| birth_decade+sex+race | [1, 1, 1, 1, 1] | 1 |
| sex+race | [2, 3] | 2 |

No full-anonymity, k-anonymity or l-diversity guarantee is claimed. See `docs/anonymisation_person_methods.md` section 5.
