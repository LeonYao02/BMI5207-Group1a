# Person 2 Validation Summary

## Processing Results

| Check | Result |
| --- | ---: |
| Patients | 5 |
| Original visit records | 22 |
| Exact duplicate visit rows removed | 1 |
| Unique visits | 21 |
| Inpatient / outpatient day-surgery visits | 19 / 2 |
| Diagnosis tokens before within-visit deduplication | 149 |
| Duplicate diagnosis tokens removed | 2 |
| Diagnosis source events retained | 147 |
| Distinct source codes | 72 |

## Mapping and Conversion Results

| Outcome | Codes | Source events |
| --- | ---: | ---: |
| Condition candidates | 40 | 68 |
| Unresolved Condition mappings, concept ID 0 | 14 | 24 |
| Routing review | 18 | 55 |
| Total | 72 | 147 |

The provisional CONDITION_OCCURRENCE table contains 92 records. Another 55 source events are retained for routing review.

## Checks Passed

- All 21 source visits matched the shared registries.
- Person IDs were consistent between the patient and visit registries.
- All 63 date fields matched the shared patient-specific offsets.
- Missing dates remained missing.
- Visit durations were preserved.
- Saved Condition records matched their patient and visit IDs.
- Condition proxy dates matched shifted visit start dates.
- All 147 diagnosis source events were accounted for.
- No original patient/case identifiers or designated private columns were detected in the checked CSV outputs.

## Remaining Limitations

The source diagnosis coding system and edition are not specified in the supplied files. Candidate mappings, EHR provenance and cross-domain routing remain subject to review.

The identifier and date checks support pseudonymization validation. They do not establish that patient-level data are safe for public release.
