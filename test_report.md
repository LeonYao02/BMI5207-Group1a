# Person 3 Labs — independent execution and QA report

Date: 2026-10-28. Tested the latest supplied final GitHub package, then applied only two QA repairs.

## Commands executed

```bash
PYTHONPATH=<private-test-src>:person3 python -m unittest discover -s person3 -p test_etl_labs.py -v
PYTHONPATH=<private-test-src> python person3/etl_labs.py --input-dir <private-source-workbooks> --key <disposable-test-key> --mapping person3/labs_mapping.csv --vocabulary <Athena-CONCEPT.csv> --output-dir <private-output>
PYTHONPATH=<private-test-src> python person3/etl_labs.py --input-dir <private-source-workbooks> --key <disposable-test-key> --mapping person3/labs_mapping.csv --vocabulary <Athena-CONCEPT.csv> --output-dir <private-strict-output> --strict
```

Actual full command paths are under `/mnt/data/` in the execution environment; paths here are portable and do not reveal source filenames or key material. Unit tests: 3 passed, 0 failed, 0 skipped, exit 0. Normal ETL: exit 0, 162 records, 5 persons, 64 source codes, 86 records with measurement_concept_id=0. Strict ETL: exit 1 with `Strict validation failed: resolve mapping and result review flags before final submission.` This is expected for incomplete medical mapping, not an unhandled exception. Strict mode currently writes review-only staging outputs *before* exiting; downstream consumers must not interpret those as approved strict outputs.

## Independent checks

- Source-to-output row-by-row code, pseudonymous person ID, and shifted date comparison: 162/162 matched, 0 mismatches. The shift uses shared.py `shift_datetime` and the disposable test key. This verifies deterministic consistency, not independent clinical accuracy of original dates.
- measurement_id unique: 162/162. Five distinct pseudonymous persons, 64 distinct source codes. No dropped records; no duplicated measurement IDs.
- Source mapping inventory: 64 codes, no duplicate source_test_code. Confirmed 22 codes/76 rows; Assumption-based 38 codes/75 rows; Unresolved 4 codes/11 rows. Strict coverage 76/162 = 46.91%; candidate-inclusive 151/162 = 93.21%.
- All 21 distinct nonzero measurement_concept_id values in the output exist in Athena CONCEPT.csv, are standard `S`, valid (empty invalid_reason), and in `Measurement` domain. Their names were inspected; this does not independently prove unavailable specimen/method metadata.
- measurement_type_concept_id 32856 is valid standard `Lab` in `Type Concept`. Operator `<` 4171756 is valid standard in `Meas Value Operator`. `value_as_concept_id` 45878244 (B) and 45884084 (Positive) are valid standard `Meas Value`. No nonblank unit_concept_id exists to validate.
- ABO=B -> measurement 3002529 and value 45878244; RH=Positive -> measurement 3003310 and value 45884084. BSAG Non-Reactive -> unconfirmed measurement_concept_id=0, source text retained, no premature value concept. BHCGT <2.0 -> unconfirmed measurement concept 0, value_as_number 2.0, operator 4171756, original inequality retained.
- Required measurement_id, person_id, measurement_concept_id, measurement_date, measurement_type_concept_id present; date formats valid. All 162 visit_occurrence_id and unit_concept_id blank due to unavailable source linkage/units. These are nullable CDM columns; unknown measurement_concept_id=0 is a recognized no-match placeholder, but 86 rows remain medically unmapped.
- No raw Patient_No or Case_No column is exported. Output contains pseudonymized IDs and clinical values, so record-level exports remain private. No actual PERSON/VISIT_OCCURRENCE reference tables were provided for cross-domain FK verification; this check is NOT PASSED and must be performed by Person 6.

## Findings and changes (before -> after)

1. `candidate_audit.csv`: 446 candidate rows, missing CAC/CHSCL source codes and six selected candidate audit rows -> 454 rows with all 64 source codes and selected candidates traceable. New rows do not promote mappings.
2. `etl_labs.py`: ABS free-text result length 65 exceeded OMOP CDM 5.4 MEASUREMENT.value_source_value VARCHAR(50) -> output truncates to 50 and records a review warning. Source workbook remains the private full-fidelity reference. This is a lossy target-field representation, not a claim that the original result is 50 characters.
3. `labs_mapping.csv`: no change needed; statuses remain 22/38/4. All 76 nonzero output concept assignments remain confirmed-only.

## Release assessment

Normal execution: PASS. Source completeness: PASS. Athena concept ID validity: PASS. Strict mode: EXPECTED REJECTION. OMOP full conformance: NOT ESTABLISHED because 86 measurements remain unstandardized and PERSON/VISIT foreign-key integration cannot be verified from isolated Labs inputs. Can commit as documented, limited Person 3 deliverable and hand off to Person 6; do not label the whole data model fully standardized. Draft PR can be marked Ready for review for code/QA review with these limitations disclosed, subject to team branch policy.
