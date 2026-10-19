# Shared rules for Group 1a

The user has defined these initial group conventions. Other members should reuse
`src/bmi5207/shared.py` and the same private key. Domain ETLs remain owned by their
respective members. This contribution does not populate PERSON or VISIT_OCCURRENCE.

## IDs and linkage

1. The private handover package already contains `private/group_key.hex`. Reuse
   that exact key through a private group channel; do not generate independent keys.
   `init-key` is only for a deliberately new project whose outputs will all be rebuilt.
2. `person_id(key, Patient_No)` returns a positive, deterministic 31-bit integer (scheme `hmac-sha256-int31-v2`).
   It uses HMAC-SHA256 with domain separation. No raw or plain-hashed patient IDs
   are exported. A group-key fingerprint in each quality report identifies
   accidental key mismatches without exposing the key.
3. `visit_id(key, Patient_No, Case_No)` identifies a visit. Both components matter.
   A Case_No appearing only in labs is not assumed to equal a different Case_No
   in the visit source just because the patient or dates look similar.
4. Person 2 should use `visit_registry.csv`/the shared function when producing
   VISIT_OCCURRENCE. All event ETLs must match an actual source visit before
   populating its visit FK. Unmatched optional FKs stay blank and are reported.
5. IDs are positive signed INTEGER-compatible values, at most 2147483647.
   Collision checks stop an export if needed. The older one-patient prototype used
   63-bit IDs: discard its outputs and regenerate every domain with this version.
6. Medication event IDs use private HMACs of source basename, sheet, row, and
   patient. Changing the input parent folder leaves IDs unchanged. Renaming a
   source file or moving rows changes event IDs. Keep the source
   snapshot immutable. Person and visit IDs are independent of row/file order.

## Dates

- Every patient receives one nonzero offset in [-180,-1] or [1,180] days. Reuse
  that offset for all exact clinical timestamps across all five source domains.
- Preserve time of day and within-patient intervals. Real season/calendar-time
  analyses and between-patient timing can be distorted and must be described.
- Full birth/death dates, if present, require the same offset. For a year-only
  birth value, retain that year in PERSON.year_of_birth and leave month/day/birth
  datetime blank. Never manufacture January 1. With shifted clinical dates and
  an unshifted year-only birth value, calendar-year age can differ by one year;
  document that limitation. Birth year remains a quasi-identifier requiring the
  final group-wide release assessment. The medication ETL does not itself
  populate or modify demographic data.
- Do not use the group key or offset registry in a public release. Do not publish
  a before/after table containing original clinical dates.

## Public versus private outputs

Raw Excel/CSV data, keys, old-to-new ID crosswalks, offsets and source filenames
stay local and are git-ignored. Pseudonymised exports omit source patient/visit IDs
and raw source filenames. The ETL stops if a known long source identifier is found
again in an export field. This check does not detect all possible names or PHI.

The dataset is described by the assignment as synthetic, but follow its requested
assumption that patient numbers are original identifiers. Pseudonymisation and
date shifting are **not proof of anonymisation**. With only five people, combinations
of demographics and clinical trajectories may remain distinctive. The final group
must assess all tables together; no k-anonymity or l-diversity guarantee is claimed.

## Stable conventions and missing data

- Target OMOP CDM 5.4 across all members; source concept IDs are different from
  OMOP concept IDs. Standard analytic concept fields use valid Standard concepts.
- A missing optional concept can be represented by 0. Missing optional scalar
  values stay empty, not fabricated as 0. Required fields need documented ETL rules.
- Local drug codes are retained as drug_source_value. They have no automatically
  assumed OMOP source concept, so drug_source_concept_id is 0.
- No silent fuzzy visit joins, dose-based strength guesses, or removal of unresolved
  duplicate/conflicting orders.

## Domain exceptions and shared integration

- 170 medication-source orders are fully accounted for: 158 DRUG_EXPOSURE rows
  plus 12 Device-domain handoff rows. The handoff is an audit/coordination table,
  not a claim that a device was used or a transfusion performed.
- Three unresolved Drug descriptions (six orders) use concept 0 with explicit
  review notes. Unknown composition is never reduced to only one ingredient.
- The 22 visit rows contain one exact duplicate; the registry contains 21 unique
  patient/Case_No pairs. Only identical duplicates may collapse; conflicts stop.
- All 170 medication orders have exact visit links. By contrast, all 162 laboratory
  rows have Case_No values absent from the visit source. The lab/visit owners must
  reconcile source semantics or leave optional visit FKs empty; no nearest-date join.
- This package does not populate PERSON, VISIT_OCCURRENCE, MEASUREMENT or
  PROCEDURE_OCCURRENCE. Their owners must import the shared registries/functions,
  then run cross-domain foreign-key checks after combining their actual CDM tables.
