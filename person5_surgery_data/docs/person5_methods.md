# Person 5 methods — full five-patient Procedures run

**Owner:** Person 5 (Procedures)  
**Target:** OMOP CDM 5.4 — `PROCEDURE_OCCURRENCE`  
**Status:** Conversion output generated; identity/date lineage and final release validation still to be confirmed.

## Scope and reconciliation

The five-patient surgical source was organised into `Raw_Procedures` and `Athena_Mapping`. The working source workbook has **8 rows**, representing **7 distinct source procedure events** and **6 distinct surgical codes**. The draft produces **8 OMOP procedure rows** because one combined coronary angiography/angioplasty event is provisionally represented by two component concepts. Two occurrences of `DSIC004` represent distinct source events and are retained. These counts describe the working dataset, not eight independently confirmed procedures.

The latest supplied `procedure_occurrence.xlsx` contains **8 rows and 9 columns**. All eight rows have populated `person_id`, `visit_occurrence_id`, `procedure_date`, `procedure_datetime`, `procedure_concept_id`, and `procedure_type_concept_id`. There are **5 distinct person IDs**, **7 distinct visit IDs**, and **7 distinct standard procedure concept IDs**. `procedure_type_concept_id` is **32817** in all rows, and `procedure_source_concept_id` is **0** in all rows. These are output checks, **not proof** that the IDs and dates were generated using the group's authoritative registries.

## Mapping

The original `Surgical_Code` is retained in `procedure_source_value`. The clinical descriptions were manually searched in Athena, prioritising **Procedure domain**, **Standard concept**, **Valid** status and the closest clinically justified meaning. The chosen Athena concept identifier is written to `procedure_concept_id`. The source codes have not been confirmed as recognised Athena source vocabulary concepts; `procedure_source_concept_id = 0` is used provisionally.

| Original code | Current standard concept | Concept ID | Review status |
|---|---|---:|---|
| `ESF701I` | Esophagogastroduodenoscopy | 4294382 | Check whether biopsy is a separately documented procedure |
| `XSC718T` | Biopsy of thorax | 4308384 | Broader candidate: percutaneous approach not represented |
| `ZSD714H` (angiography) | Angiography of coronary artery | 4142645 | Angiography component reviewed |
| `ZSD714H` (angioplasty) | Transluminal angioplasty of blood vessel | 40489873 | Broader candidate: coronary site not represented; transluminal approach not independently confirmed |
| `DSIC004` | Dilation of cervical canal | 4337799 | Two source events retained |
| `CSM700N` | Nasendoscopy | 37153412 | Reviewed |
| `SSB705F` | Intramedullary nailing of femur | 4231432 | Some fracture/locking detail not represented |

**Important:** A valid Standard concept is not automatically an exact clinical match. The two broader candidates remain documented for group/instructor review. The combined `ZSD714H` representation is provisional until the group decides whether two procedure occurrences or a more suitable combined concept is appropriate.

## Transformation method and Python code

The supplied `convert_surgery_omop.py` script performs the following operations:

1. Reads `Raw_Procedures` and `Athena_Mapping` from the workbook using pandas.
2. Checks mandatory input column names and normalises identifier text.
3. Removes rows missing essential mapping inputs and deduplicates **complete source events**, not merely surgical codes.
4. Deduplicates concept mapping pairs, then joins source events to mapped concepts on `Surgical_Code`.
5. Populates draft OMOP fields (`procedure_occurrence_id`, `procedure_concept_id`, date/time, `procedure_source_value`, and `procedure_source_concept_id`).
6. Creates `review_needed` and `combined_procedure_review` flags.
7. Exports `OMOP_Draft`, `Mapping_Review_PRIVATE` and `Validation` sheets to an internal workbook.

**Code lineage caveat:** The supplied version of `convert_surgery_omop.py` sets `person_id` and `visit_occurrence_id` to missing and uses the original `operation_date` as the draft procedure date. It also leaves the procedure type as `None`. The *later supplied Excel output* contains populated IDs and `32817`, indicating additional changes or processing, but the precise code that generated these final values has not been verified. Do not claim the uploaded converter alone produced the current output.

A separate supplied `visit occurrence id.py` script reads `visit_registry.csv` and matches `Patient_No + Case_No` with `validate="many_to_one"`; the visible script **prints** the matching results but does not itself export a final OMOP table. A separate Jupyter date-offset workflow was shown, but its final integration into the uploaded Excel has not yet been demonstrated.

## Anonymisation and shared rules

The group has specified one shared `person_registry.csv` for `person_id` and `date_offset_days`, and one `visit_registry.csv` for `visit_occurrence_id` keyed by `Patient_No + Case_No`. A patient's date offset must be applied consistently to all of that patient's records. Shared private keys and registries must remain private.

The current `procedure_occurrence.xlsx` has **no `Patient_No` or `Case_No` columns**, which is a positive data-minimisation step. However, removal of direct identifiers alone does **not** establish that the output is anonymised. Before public release, confirm that every person and visit ID matches the group registries; verify each procedure date against the original date plus the appropriate patient offset; check `procedure_datetime` as well; and inspect any additional exported columns, metadata or auxiliary sheets for source identifiers.

## Validation and limitations

| Check | Observed | Remaining action |
|---|---|---|
| Source events | 7 distinct events | Preserve both genuine `DSIC004` events |
| OMOP rows | 8 provisional rows | Resolve combined coronary procedure treatment |
| Person IDs | All 8 populated, 5 unique | Verify against group person registry |
| Visit IDs | All 8 populated, 7 unique | Verify against group visit registry and patient consistency |
| Procedure dates/times | All 8 populated | Confirm correct **single** date offset for each patient |
| Procedure concept IDs | All 8 populated | Review broader mappings and combined event |
| Procedure type | All 8 equal 32817 | Confirm EHR provenance and concept suitability with group/instructor |
| Source concept | All 8 equal 0 | Confirm local source codes have no known Athena source concept |
| OMOP 5.4 schema | 9 columns in uploaded output | Check against the **full** CDM 5.4 `PROCEDURE_OCCURRENCE` field specification, types and constraints; add required structural columns as appropriate |
| Public release | Not yet signed off | Complete provenance, referential integrity and privacy review |

The 9-column spreadsheet is a **working OMOP-shaped extract**, not yet a demonstrated full CDM 5.4-compliant and safe-to-publish dataset.

## Suggested viva / presentation answers

**Why do 7 source events produce 8 rows?** One combined coronary angiography/angioplasty source event was provisionally split into two candidate procedure concepts. The final representation is under review.

**How did you avoid losing repeated procedures?** Events were distinguished using the complete source fields, rather than deleting rows with a repeated surgical code.

**How were concepts standardised?** Procedure descriptions were searched in Athena, checking Standard/Valid status and clinical meaning. Imperfect broader matches are explicitly flagged rather than presented as exact.

**How is privacy protected?** The team uses shared pseudonymous IDs and patient-level date offsets, and excludes original patient/visit identifiers from the intended public output. The final registry/date reconciliation and release review remain to be evidenced.

**Why is the source concept ID zero?** The original local surgical codes have not been verified as Athena source vocabulary concepts; the original codes are retained in `procedure_source_value`.

## Files and publication guidance

- **`docs/person5_methods.md`** — this methods and review document; suitable for GitHub after review.
- **`scripts/` or `src/bmi5207/`** — cleaned, reproducible conversion code aligned with the team's existing project structure.
- **`mappings/`** — a de-identified concept-level mapping file; no `Patient_No`, `Case_No`, or linkable event identifiers.
- **Final `procedure_occurrence.csv`** — publish only after ID/date verification, schema validation, mapping decisions and privacy sign-off.
- **Private only:** original surgical workbook, `Mapping_Review_PRIVATE`, `person_registry.csv`, `visit_registry.csv`, `group_key.hex`, and any patient-level source-to-output crosswalks.

## References

- OMOP CDM 5.4: https://ohdsi.github.io/CommonDataModel/cdm54.html
- Athena OHDSI: https://athena.ohdsi.org/
- Project working files: `surgery patient1-5.xlsx`, `surgery_OMOP_Result(1).xlsx`, `procedure_occurrence.xlsx`, `convert_surgery_omop.py`, and `visit occurrence id.py`.
