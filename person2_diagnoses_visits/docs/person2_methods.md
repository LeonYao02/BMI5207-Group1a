# Person 2: Data Cleaning, Pseudonymization and OMOP Conversion

## Scope

Person 2 processed the case-visit and diagnosis data for all five patients and prepared provisional OMOP CDM 5.4 VISIT_OCCURRENCE and CONDITION_OCCURRENCE tables.

## Source Data and Cleaning

The five source workbooks contained 22 non-empty data rows with 40 columns each. One exact duplicate row was removed, leaving 21 unique visits.

Primary and secondary diagnosis codes were expanded into individual source events. Two repeated codes within visits were removed, leaving 147 diagnosis events covering 72 distinct source codes. Repeated diagnoses across different visits were retained.

Original Excel files were not modified.

## Pseudonymization

Patient IDs were obtained from the shared person registry. Visit IDs were obtained by exact matching on the original patient and case identifiers.

The same patient-specific date offset was applied consistently to admission, actual discharge and planned discharge dates. Missing dates remained missing, and visit durations were preserved.

Original patient and case identifiers were excluded from the processed outputs. Shared registries, date offsets and group keys were retained privately.

These measures provide pseudonymization. They do not, by themselves, establish that patient-level data are suitable for public release.

## Visit Conversion

The 21 visits were provisionally classified as:

- 19 inpatient visits: concept ID 9201.
- 2 outpatient day-surgery visits: concept ID 9202.

Classification used admission type, admission/discharge dates and the day-surgery-to-inpatient indicator. Emergency admission was not automatically treated as a separate emergency-room visit.

Actual discharge dates were used instead of planned discharge dates. Previous visits were linked within each patient.

Record provenance provisionally used concept ID 32817 (EHR). This assumption requires confirmation.

## Diagnosis Mapping

All 72 source codes received a documented processing decision:

- 40 codes had a single distinct valid standard Condition target among the retrieved candidates.
- 14 codes remained unresolved and were retained with condition concept ID 0.
- 18 codes required separate review for context, history, status, services, morphology or other target domains.

J189 and I214 were manually checked in Athena, including the source-to-standard relationship and the target concept's domain, standard status and validity.

Additional candidates were retrieved from the OHDSI demonstration vocabulary snapshot identified as `v5.0 29-FEB-24`. This vocabulary version string is separate from the OMOP CDM 5.4 version.

The supplied files did not explicitly identify the source diagnosis coding system or edition. ICD10 and ICD10CM search results were therefore treated as candidate evidence rather than proof of the local coding system. Conflicting meanings were not resolved by selecting the first search result.

## Condition Conversion

The provisional CONDITION_OCCURRENCE table contained 92 records:

- 68 records with candidate standard Condition concept IDs.
- 24 records with concept ID 0.

The remaining 55 diagnosis source events were retained in a separate routing-review file. No source diagnosis event was silently discarded.

Condition start dates used shifted admission dates as proxies because actual diagnosis dates were unavailable. Condition start datetimes and end dates were left empty. Discharge was not interpreted as disease resolution.

Primary and secondary diagnosis roles used status concept IDs 32902 and 32908, respectively. Source concept IDs remained 0 because the local source vocabulary was unconfirmed.

## Validation

Checks confirmed:

- All 21 visits matched the shared patient and visit registries.
- Shared person IDs were consistent across registries.
- All 63 date fields, including missing values, matched the expected patient-specific date shifts.
- Visit durations were preserved.
- Condition records linked to the correct patient and visit.
- Condition proxy dates matched the shifted visit start dates.
- All 147 diagnosis source events had a documented destination.
- The checked CSV files contained no original patient/case identifiers or designated private columns.

Identifier checks do not constitute a complete re-identification risk assessment.

## Submission and Limitations

Public repository materials contain code, vocabulary-level mapping decisions and aggregate documentation. Patient-level outputs and private linkage material are shared through the group's private channel.

The outputs remain provisional where source coding, provenance or routing decisions are unresolved. Missing mappings and limitations are documented rather than replaced with unsupported concepts.

Final integration requires coordination with Persons 5 and 6, particularly for cross-domain events and duplicate procedure information.
