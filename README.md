# BMI5207 Group 1a — Person 4

Medication-order ETL for **all five synthetic patients**, targeting OMOP CDM 5.4.
Prepared 2026-10-19. This version supersedes the earlier one-patient prototype.

| Result | Count |
|---|---:|
| Source medication orders / patients | 170 / 5 |
| Unique source code + name + form descriptions | 74 |
| DRUG_EXPOSURE rows | 158 |
| With verified Standard Drug targets | 152 |
| Reviewed unresolved Drug rows, concept 0 | 6 |
| Device-domain order handoffs | 12 |
| Handoffs with verified Standard Device targets / unresolved targets | 9 / 3 |
| Orders dropped | 0 |

Every source order is represented once in `medication_details.csv` and once in
either `drug_exposure.csv` or `cross_domain_handoff.csv`. All descriptions were
reviewed; **not every product could be mapped to a nonzero concept**. The handoff
is a coordination table, not a fabricated DEVICE_EXPOSURE or transfusion record.

## Run on macOS

Use Python 3.10+ and run from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
# Copy private/ from the private handover package into this checkout first.
# Reuse its group key; do not generate a different key for each member.
python scripts/etl_medications.py run \
  --input "$HOME/Downloads/Sample data for 5 patients_v2"
python scripts/validate_outputs.py
python -m unittest discover -s tests -v
```

The actual run uses the existing private group key. `init-key` is available only
for a deliberate new project whose outputs will all be regenerated. Parent-folder
layout does not change IDs; source filenames, sheet names and row positions do.

## Person 1 — Anonymisation + Demographics (PERSON / DEATH)

`scripts/etl_person.py` pseudonymises **all five source domains** with the shared
key (person_id, visit/case IDs, one date offset per patient) and builds CDM 5.4
`PERSON` and `DEATH`. Other members can build their tables from
`outputs/anonymised/*_anonymised.csv` instead of the raw Excel files.

```bash
python scripts/etl_person.py run \
  --input "$HOME/Downloads/Sample data for 5 patients_v2"
```

| Result | Count |
|---|---:|
| PERSON / DEATH rows | 5 / 2 |
| Source rows pseudonymised (person, visit, lab, medication, procedure) | 5, 22, 162, 170, 7 |
| Lab rows whose Case_No is absent from the visit source (FK blank) | 162 |
| Concepts | 8507 MALE, 8532 FEMALE, 38003579 Chinese, 32817 EHR |

Rules, field-by-field decisions and the risk statement are in
`docs/anonymisation_person_methods.md`. Aggregate validation is in `reports/person_validation.md`.

## Note on the published group key (coursework only)

The group key (`group_key.hex`) is shared openly for this coursework so that
markers and group members can reproduce every output from the supplied synthetic
dataset. This is a deliberate exception for an assignment, not a recommended
practice. In a real deployment the key, the ID crosswalks and the date offsets
would be held by a data custodian under access control, never published, and
rotated if exposed. Anyone holding both the key and the raw extract can reverse
the pseudonyms, so the published outputs here must not be treated as anonymised.

## Files to open

- `docs/PERSON4_GUIDE_ZH.md`: Chinese explanation and lecture-linked viva questions.
- `docs/team_rules.md`: group identity, date and linkage conventions.
- `reports/full_validation.md`: actual five-patient counts and limitations.
- `mappings/medications.csv`: all 74 source descriptions, targets and review reasons.
- `mappings/concepts_verified.csv`: live Athena concept metadata, checked 2026-10-19.
- `scripts/UPLOAD_TO_GITHUB.md`: manual GitHub upload commands.

## Generated files (git-ignored)

| File | Purpose |
|---|---|
| `outputs/medications/drug_exposure.csv` | 23 CDM 5.4 columns, 158 Drug orders |
| `outputs/medications/medication_details.csv` | Complete 170-order ledger; doses, forms, components, flags |
| `outputs/medications/cross_domain_handoff.csv` | 12 non-Drug product orders with target domain/review reason |
| `outputs/medications/medication_mapping.csv` | Mapping table used by this run |
| `outputs/medications/quality_issues.csv` | Row-level data quality notes |
| `outputs/medications/quality_report.json` | Counts, assumptions and mapping checks |
| `outputs/medications/patient_summary.csv` | Pseudonymous per-person reconciliation |
| `private/person_registry.csv`, `visit_registry.csv` | Shared linkage registries; never publish |
| `private/drug_lineage.csv` | Source file/sheet/row trace and original corrupt dose; never publish |
| `private/group_key.hex` | Shared secret; published for this coursework only (see the note above) |
| `outputs/person/person.csv`, `death.csv` | CDM 5.4 PERSON (18 columns) and DEATH (7 columns) |
| `outputs/anonymised/*_anonymised.csv` | Pseudonymised, date-shifted staging copies of all five source domains |
| `private/case_registry.csv` | Every Patient_No/Case_No pair, its case_group_id and source domains; never publish |

## Interpretation limits

Orders are not observed administrations. Missing duration is handled by the
THEMIS written-prescription fallback (start + 29 days), clearly flagged for every
Drug row. No observed quantity, frequency, route or duration is invented. These
inferred dates must not be used as evidence of 30-day treatment.

HMAC pseudonyms and per-person date shifts reduce disclosure; they do not prove
anonymity. Raw data, patient-level exports, keys and crosswalks are excluded from
GitHub. The other group members still own their PERSON, VISIT_OCCURRENCE,
MEASUREMENT and PROCEDURE_OCCURRENCE ETLs. Final database foreign-key and DQD
checks require those actual tables and the official vocabulary release.
