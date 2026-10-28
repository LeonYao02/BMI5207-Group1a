# BMI5207 Person 3 — final delivery audit

## Coverage (Athena verified, strict vs candidate)

- Confirmed: 22 / 64 codes, 76 / 162 records (46.9%).
- Assumption-based: 38 codes, 75 records (46.3%).
- Unresolved: 4 codes, 11 records (6.8%).
- Strict concept coverage: 76/162 (46.9%).
- Candidate-inclusive concept coverage: 151/162 (93.2%); NOT fully standardized.

## Audit decisions
No additional serum/plasma chemistry candidate was promoted solely from common practice. Missing unit alone is not disqualifying; specimen and measurement property must match. HbA1c ratio code does not imply a reported unit. RDW was downgraded because prior candidate is an entitic-volume measure, while the source range supports RDW-CV percentage. HCT was downgraded because previous candidate explicitly says Estimated, which is not supported. CAC and CHSCL remain unresolved.

## Qualitative values
Athena verified standard Meas Value concepts: ABO=B -> 45878244 (B); RH=Positive -> 45884084 (Positive); BSAG=Non-Reactive -> 4305306 (Non-Reactive), applied only when the measurement concept itself is Confirmed. BSAG is assumption-based, so its result remains text and no unconfirmed test concept is emitted. BHCGT '<2.0' -> numeric 2.0 with operator 4171756 (<), verified standard concept, with source string preserved. Measurement type 32856 (Lab) is a verified standard Type Concept.

## Data release policy
No source patient files, keys or patient-level outputs included. ETL uses shared.py pseudonymization. A value_as_concept_id alone does not make a measurement standardized if measurement_concept_id=0. Null unit_concept_id is deliberate because source units are missing. Unlinked visits stay blank. Strict mode is expected to reject incomplete mapping.

## Actual integration verification
Executed against all five original Lab workbooks with a disposable test key and Athena CONCEPT.csv: PASS; 162 rows, 5 pseudonymized persons, 64 codes, 76 strictly mapped rows. Unit tests: PASS (3 tests). No test outputs included in release.

## Final independent validation addendum (2026-10-28)

See `test_report.md` for actual commands and evidence. Unit tests 3/3 passed; normal ETL exit 0 (162 rows); strict mode exit 1 as expected for 86 unmapped rows. All 21 distinct nonzero output measurement concept IDs were independently verified against Athena CONCEPT.csv (valid standard Measurement). The candidate audit was repaired from 446 to 454 rows to cover all 64 codes and six previously missing selected candidates. An ABS result exceeded the OMOP `value_source_value` 50-character limit; ETL now truncates that target field with a review warning while the original stays in private source input. The original mapping statuses remain 22 Confirmed (76 rows), 38 Assumption-based (75 rows), and 4 Unresolved (11 rows). Integration foreign keys to PERSON/VISIT_OCCURRENCE cannot be proven without the group's exported tables; Person 6 must verify these.
