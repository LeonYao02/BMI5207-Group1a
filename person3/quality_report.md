# BMI5207 Person 3: final clinical terminology audit

## Verified outcomes
- Source tests: 64; records: 162; patients: 5.
- Confirmed: 16 codes / 58 records (35.8%).
- Assumption-based: 45 codes / 97 records (59.9%).
- Unresolved: 3 codes / 7 records (4.3%).
- Confirmed measurement coverage only: 58/162 (35.8%). Unmapped rows retain concept_id=0.
- Athena source: uploaded official CONCEPT.csv; all approved IDs validated standard_concept=S, domain_id=Measurement, invalid_reason blank.

## Decision policy
Confirmed blood cell counts and differential fractions have consistent source hematology labels, paired blood cell counts and percent values; method-neutral LOINC selected. Blood grouping confirmed using transfusion chapter and result semantics. These are evidence-based clinical inferences, not proof of specific analyzer method. Source unit is absent and is not invented.

## Unresolved / assumption-specific caveats
- 25OHD (Assumption-based): Original D3-only candidate was wrong for total 25-OH vitamin D; revised total D2+D3 still assumes serum/plasma and mass units.
- ABS (Assumption-based): Titer candidate wrong for qualitative screen; revised presence candidate assumes serum/plasma.
- AGP (Assumption-based): Targeted LOINC candidate; requires source specimen/property/method confirmation. Do not promote automatically.
- ALB (Assumption-based): Verified active standard LOINC candidate only; assumed specimen Serum or Plasma; property, method and unit must be verified before promotion.
- ALP (Assumption-based): Verified active standard LOINC candidate only; assumed specimen Serum or Plasma; property, method and unit must be verified before promotion.
- ALT (Assumption-based): Verified active standard LOINC candidate only; assumed specimen Serum or Plasma; property, method and unit must be verified before promotion.
- APTT (Assumption-based): Verified active standard LOINC candidate only; assumed specimen Platelet poor plasma; property, method and unit must be verified before promotion.
- AST (Assumption-based): Verified active standard LOINC candidate only; assumed specimen Serum or Plasma; property, method and unit must be verified before promotion.
- BE (Assumption-based): Blood gas context evident but arterial vs venous vs capillary specimen and calculated vs measured properties are not explicit.
- BHCGT (Assumption-based): Previous mass concentration candidate inconsistent with likely IU/L; units and total-vs-intact assay remain unverified.
- BSAG (Assumption-based): Verified active standard LOINC candidate only; assumed specimen Serum or Plasma; property, method and unit must be verified before promotion.
- CA (Assumption-based): Verified active standard LOINC candidate only; assumed specimen Serum or Plasma; property, method and unit must be verified before promotion.
- CAC (Unresolved): Albumin-adjusted calcium formula and specimen not documented.
- CHSCL (Unresolved): Lipaemic index qualitative interference; no sufficiently supported standardized measurement concept or result code.
- CL (Assumption-based): Verified active standard LOINC candidate only; assumed specimen Serum or Plasma; property, method and unit must be verified before promotion.
- CO2 (Assumption-based): Verified active standard LOINC candidate only; assumed specimen Serum or Plasma; property, method and unit must be verified before promotion.
- CRE (Assumption-based): Verified active standard LOINC candidate only; assumed specimen Serum or Plasma; property, method and unit must be verified before promotion.
- DB (Assumption-based): Verified active standard LOINC candidate only; assumed specimen Serum or Plasma; property, method and unit must be verified before promotion.
- E2 (Assumption-based): Verified active standard LOINC candidate only; assumed specimen Serum or Plasma; property, method and unit must be verified before promotion.
- EGFRC (Assumption-based): Previous panel candidate was wrong; formula not stated. Generic eGFR candidate still assumes 1.73 m2 indexing.
- GHB (Assumption-based): Targeted LOINC candidate; requires source specimen/property/method confirmation. Do not promote automatically. Clinical subtyping/method or reporting format is especially important.
- GHB2 (Assumption-based): Value 40 suggests IFCC mmol/mol; method-agnostic ratio candidate may be used only after confirming reporting convention.
- GLU (Assumption-based): Verified active standard LOINC candidate only; assumed specimen Serum or Plasma; property, method and unit must be verified before promotion.
- HCO3 (Assumption-based): Blood gas context evident but arterial vs venous vs capillary specimen and calculated vs measured properties are not explicit.
- HCT (Assumption-based): Existing candidate specifies estimated hematocrit, which is not evidenced.
- IB (Assumption-based): Verified active standard LOINC candidate only; assumed specimen Serum or Plasma; property, method and unit must be verified before promotion.
- INR (Assumption-based): Verified active standard LOINC candidate only; assumed specimen Platelet poor plasma; property, method and unit must be verified before promotion.
- K (Assumption-based): Verified active standard LOINC candidate only; assumed specimen Serum or Plasma; property, method and unit must be verified before promotion.
- LDH (Assumption-based): Verified active standard LOINC candidate only; assumed specimen Serum or Plasma; property, method and unit must be verified before promotion.
- LH (Assumption-based): Verified active standard LOINC candidate only; assumed specimen Serum or Plasma; property, method and unit must be verified before promotion.
- MCH (Assumption-based): Verified active standard LOINC candidate only; assumed specimen Blood; property, method and unit must be verified before promotion.
- MCHC (Assumption-based): Verified active standard LOINC candidate only; assumed specimen Blood; property, method and unit must be verified before promotion.
- MCV (Assumption-based): Verified active standard LOINC candidate only; assumed specimen Blood; property, method and unit must be verified before promotion.
- MPV (Unresolved): MPV mean platelet volume supported; precise LOINC concept requires terminology review.
- NA (Assumption-based): Verified active standard LOINC candidate only; assumed specimen Serum or Plasma; property, method and unit must be verified before promotion.
- NRBC (Assumption-based): Absolute count vs count per 100 WBC not established.
- PCO2 (Assumption-based): Blood gas context evident but arterial vs venous vs capillary specimen and calculated vs measured properties are not explicit.
- PHPCT (Assumption-based): Blood gas context evident but arterial vs venous vs capillary specimen and calculated vs measured properties are not explicit.
- PO2 (Assumption-based): Blood gas context evident but arterial vs venous vs capillary specimen and calculated vs measured properties are not explicit.
- PO4 (Assumption-based): Verified active standard LOINC candidate only; assumed specimen Serum or Plasma; property, method and unit must be verified before promotion.
- PT (Assumption-based): Verified active standard LOINC candidate only; assumed specimen Platelet poor plasma; property, method and unit must be verified before promotion.
- RDW (Assumption-based): Existing RDW-SD entitic volume candidate inconsistent with result 12.7 and reference 11.4-14.8 (likely RDW-CV %).
- SAT (Assumption-based): Blood gas context evident but arterial vs venous vs capillary specimen and calculated vs measured properties are not explicit.
- SLIDE (Assumption-based): Reviewed is a workflow status, not a quantitative measurement; route to OBSERVATION or exclude with documented reason.
- TBIL (Assumption-based): Verified active standard LOINC candidate only; assumed specimen Serum or Plasma; property, method and unit must be verified before promotion.
- TNI (Assumption-based): Troponin I mass concentration supported; high-sensitivity assay and serum/plasma/blood specimen unspecified.
- URA (Assumption-based): Verified active standard LOINC candidate only; assumed specimen Serum or Plasma; property, method and unit must be verified before promotion.
- URE (Assumption-based): Verified active standard LOINC candidate only; assumed specimen Serum or Plasma; property, method and unit must be verified before promotion.

## Special results
- ABO=B and Rh=Positive: measurement concept represents blood group / Rh type; categorical value must be mapped separately to a verified standard answer concept; until then retain value_source_value and leave value_as_concept_id null.
- HBsAg Non-Reactive: do not silently equate non-reactive to every possible negative concept; preserve original value pending verified standard answer concept.
- B-HCG <2.0: value_as_number=2.0 and less-than operator, only after operator ID validation against Athena; raw value retained.
- measurement_type_concept_id=32856 (Lab) is a valid Athena standard Type Concept when vocabulary is supplied; if vocabulary absent, ETL leaves 0 and flags need for review.
- Observation-domain concepts should be exported to OBSERVATION with observation_concept_id, observation_type_concept_id and value_as_concept_id, not inserted in MEASUREMENT.
- Source units, analyzer methodology, blood gas specimen type, eGFR formula and visit linkage remain unverified.
- Do not publish raw records, test-key output, real private keys or patient-level MEASUREMENT exports.

## Execution evidence
- Real source files + isolated random test key, supplied shared.py: PASS; 162 MEASUREMENT rows, 58 with confirmed concept ID, 104 unmapped.
- Output and test key are excluded from the public ZIP.
