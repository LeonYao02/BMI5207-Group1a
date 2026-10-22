# Anonymisation and Demographics (PERSON / DEATH)

Owner: Person 1 (Anonymisation + Demographics). Code: `src/bmi5207/person.py`, run through `scripts/etl_person.py`.
Target: OMOP CDM 5.4. Shared identity and date rules: `docs/team_rules.md` and `src/bmi5207/shared.py`.

This module does two jobs:

1. **Anonymisation staging for all five source domains.** It produces pseudonymised copies of the person, visit, lab, medication and procedure sources that every member can build their CDM table from. Each copy uses the same keyed IDs and the same per-patient date offset.
2. **Demographics conversion** into CDM `PERSON` and `DEATH`.

Pseudonymisation and date shifting reduce disclosure risk. They are **not** proof of anonymity.

## Run

```bash
python scripts/etl_person.py run --input "<path>/Sample data for 5 patients_v2"
python -m unittest discover -s tests -v
```

The run needs the shared `private/group_key.hex`. Never generate a separate key: if `private/person_registry.csv` already exists and this run gives different IDs or offsets, the run stops.

## 1. Identifier rules

| Source field | Output | Rule |
|---|---|---|
| Patient_No | `person_id` | `person_id(key, Patient_No)` = HMAC-SHA256 with domain separation, reduced to a positive 31-bit integer (scheme `hmac-sha256-int31-v2`). Deterministic across members, irreversible without the key, collision-checked |
| Case_No | `case_group_id` | `visit_id(key, Patient_No, Case_No)`. Every source row that carries a Case_No gets one, so rows from the same episode stay grouped |
| Case_No | `visit_occurrence_id` | The same value, but **only** when that exact (Patient_No, Case_No) pair exists in the visit source. Otherwise it stays blank, with no nearest-date join (team rule 4) |
| none | `person_source_value` | Left blank. The ID is not repeated, and neither a raw nor a plain-hashed ID is exported |

In the supplied data, all 162 lab rows use 5 Case_No values that are absent from the visit source. These rows keep a `case_group_id` and get a blank `visit_occurrence_id`. The owners of the visit and measurement tables decide how to represent these episodes.

The private linkage files are never published:

- `private/person_registry.csv`: Patient_No, person_id, date_offset_days. It has the same schema as the medication ETL's registry and is verified, not overwritten.
- `private/case_registry.csv`: every (Patient_No, Case_No) pair, its case_group_id, whether it is in the visit source, and the domains it appears in.

## 2. Date rules

| Rule | Detail |
|---|---|
| Offset | `date_offset(key, Patient_No, 180)`: one nonzero offset per patient, in the range [-180, -1] or [1, 180] days |
| Fields shifted | Adm_DateTime, Dis_DateTime, Dis_DateTime_Planned, Result_Test_Date, Order_Creation_Date, operation_date |
| Preserved | Time of day, length of stay, order-to-surgery intervals, and event sequence within each patient |
| Birth | `Patient_DOB` holds only a year. It is kept as `year_of_birth`, not shifted; month and day stay blank (no 1 January is invented). Computed age can differ by 1 year |
| Death | `Death_Date` holds only a year, but CDM `DEATH.death_date` is required. The ETL imputes **1 July** (the mid-year point, which minimises the maximum error) and shifts it by the patient's offset. Because the offset is at most 180 days, the death year is always preserved. The run checks this, and checks that the death date falls after the patient's last shifted event. Every such row carries the flag `death_date_imputed_from_year` |
| Top-coding | If age at the first shifted event is 90 or more, `year_of_birth` is set so that age = 90 (HIPAA Safe Harbor convention). No patient in the supplied data qualifies |

## 3. Field-by-field decisions

| Domain | Pseudonymised | Shifted | Suppressed (reason) | Other |
|---|---|---|---|---|
| person | Patient_No | Death year (imputed, see above) | Religion, Marital_Status: sensitive or quasi-identifying, not needed, no PERSON field | Gender and Race are kept for concept mapping |
| visit | Patient_No, Case_No | Adm, Dis and Dis_Planned datetimes | Adm_Trt_Cat_Desc, Adm_Physical_Class_Desc, Dis_Physical_Class_Desc: ward or bed class is an income or subsidy proxy in Singapore and is not needed | Diagnoses, LOS and indicators are kept |
| lab | Patient_No, Case_No | Result_Test_Date | none | Visit FK blank (see section 1) |
| medication | Patient_No, Case_No | Order_Creation_Date | Order_Text: free text; the drug is fully kept in the component text and cluster code | 2 doses that Excel turned into dates are blanked and flagged `dose_excel_date_corruption`; "Â®" encoding fixed |
| procedure | Patient_No, Case_No | operation_date | none | TOSP code and description are kept |

Release guard: the export **stops** if any raw Patient_No or Case_No string appears in any output cell.

## 4. PERSON and DEATH mapping

Concepts were checked live in Athena on 2026-10-22 and are recorded in `mappings/concepts_verified.csv`. The source-value mapping is in `mappings/demographics.csv`. An unreviewed source value stops the export.

| CDM field | Source | Value |
|---|---|---|
| gender_concept_id | Gender | Male → 8507 MALE, Female → 8532 FEMALE |
| race_concept_id | Race | Chinese → 38003579 Chinese (Race vocabulary code 2.06, child of 8515 Asian) |
| ethnicity_concept_id | none | 0. OMOP ethnicity is only Hispanic or Not Hispanic; the source has no such field, and it is not inferred from race |
| year_of_birth | Patient_DOB | Year as recorded (section 2) |
| month_of_birth, day_of_birth, birth_datetime | none | Blank |
| gender_source_value, race_source_value | Gender, Race | Source text kept |
| *_source_concept_id | none | 0 (local text values) |
| location_id, provider_id, care_site_id | none | Blank |
| DEATH.death_date | Death_Date (year) | Imputed 1 July, then shifted (section 2) |
| DEATH.death_type_concept_id | none | 32817 EHR |
| DEATH.cause_concept_id | none | 0 (cause not recorded) |

## 5. Re-identification risk (honest statement)

- With 5 people, all Chinese, `year_of_birth + sex + race` gives minimum k = 1. Birth decade still gives k = 1, and sex + race alone gives k = 2 (`reports/person_validation.md`).
- No k-anonymity, l-diversity or full-anonymity claim is made.
- Mitigation is **controlled access**: share within the group or course only, under a data-use agreement, with the key held separately.
- A wider release would need 10-year age bands, suppression of rare diagnoses (for example IVF), and a joint assessment across all tables.
- Under Singapore's PDPA, pseudonymised data stays personal data while the key exists.
- **Coursework exception:** the group key is published with the assignment so results can be reproduced from the synthetic extract (see README). In real use the key would be held by a custodian and never published; with the key published, these pseudonyms are reversible by anyone who also holds the raw extract.

## 6. References

1. OHDSI. OMOP CDM v5.4, PERSON and DEATH. https://ohdsi.github.io/CommonDataModel/cdm54.html
2. OHDSI Athena. https://athena.ohdsi.org (concepts 8507, 8532, 38003579, 32817)
3. PDPC Singapore. *Guide to Basic Anonymisation* (2022).
4. U.S. HHS. HIPAA De-identification Standard, 45 CFR §164.514(b).
5. Sweeney L. k-Anonymity: a model for protecting privacy. *IJUFKS* 2002;10(5):557–570.
6. Hripcsak G, et al. Preserving temporal relations in clinical data while maintaining privacy. *JAMIA* 2016;23(6):1040–1045.
