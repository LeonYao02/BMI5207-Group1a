# Person 5 — Procedures Python Code Explanation

## 1. Overview

Three Python scripts were prepared to process the surgical records for five synthetic patients. They cover OMOP draft conversion, patient-specific date shifting, and visit ID matching. These scripts currently run separately; their outputs have not yet been integrated into one verified, anonymised `PROCEDURE_OCCURRENCE` file.

| Script | Purpose | Current output |
|---|---|---|
| `surgery omop convert.py` | Prepare and check OMOP procedure records | `surgery_OMOP_Result.xlsx` with draft, private mapping review and validation sheets |
| `date offset days.py` | Match patient registry and calculate shifted procedure dates | Prints `person_id` and shifted `procedure_date` |
| `visit occurrence id(1).py` | Match source visits to shared OMOP visit IDs | Prints `Patient_No`, `Case_No` and `visit_occurrence_id` |

## 2. `surgery omop convert.py` — OMOP draft conversion

### 2.1 Set file paths and procedure type

```python
BASE = Path.cwd()
INPUT = BASE / 'surgery patient1-5.xlsx'
OUTPUT = BASE / 'surgery_OMOP_Result.xlsx'
PROCEDURE_TYPE_CONCEPT_ID = 32817
```

The script uses the current working directory to locate the input workbook and save its output. `32817` is configured as the EHR procedure type; this assumption should be confirmed against the synthetic dataset's intended provenance before final submission.

### 2.2 Read and validate the two worksheets

```python
raw = pd.read_excel(INPUT, sheet_name='Raw_Procedures', dtype={'Surgical_Code': 'string', 'Patient_No': 'string', 'Case_No': 'string'})
mapping = pd.read_excel(INPUT, sheet_name='Athena_Mapping', dtype={'original code': 'string'})
```

The script reads original procedure records and the manually prepared Athena mapping table. It strips whitespace from column headers and checks required column names. A missing input file raises `FileNotFoundError`; missing columns raise `ValueError`.

### 2.3 Clean values and concept IDs

```python
def norm(v):
    return '' if pd.isna(v) else str(v).strip()

mapping['concept ID'] = pd.to_numeric(
    mapping['concept ID'].map(norm), errors='coerce'
).astype('Int64')
```

`norm()` turns missing values into empty strings and removes extra spaces. `pd.to_numeric` converts concept IDs to numbers; unparseable entries become missing values. The script also drops rows missing essential source codes or mapping descriptions. Removed records should be checked during quality assurance.

### 2.4 Distinguish events from mapping components

```python
events = raw[raw_required].drop_duplicates(subset=raw_required).reset_index(drop=True).copy()
events.insert(0, 'source_event_id', range(1, len(events) + 1))
mp = mapping.drop_duplicates(subset=['original code', 'concept ID', 'standard concept name']).copy()
merged = events.merge(mp, left_on='Surgical_Code', right_on='original code', how='left', validate='many_to_many')
```

The script removes exact duplicate source rows, not every repeated surgical code. This preserves distinct events such as repeated cervical dilation procedures. A combined coronary angiography and angioplasty source record may match two mapping rows, resulting in more draft output rows than source events. The decision to represent the combined operation as one or two OMOP records still requires review.

### 2.5 Construct the OMOP draft fields

```python
merged['procedure_datetime'] = pd.to_datetime(merged['operation_date'], errors='coerce')
merged['procedure_date'] = merged['procedure_datetime'].dt.date
merged['procedure_occurrence_id'] = range(1, len(merged) + 1)
merged['procedure_concept_id'] = merged['concept ID'].astype('Int64')
merged['procedure_type_concept_id'] = PROCEDURE_TYPE_CONCEPT_ID
merged['person_id'] = pd.NA
merged['visit_occurrence_id'] = pd.NA
merged['procedure_source_value'] = merged['Surgical_Code']
merged['procedure_source_concept_id'] = 0
```

The output uses OMOP-style field names and Athena standard procedure concept IDs. `procedure_source_value` retains the original surgical code; `procedure_source_concept_id` is set to `0` because the script does not establish an Athena source concept for the local code. Importantly, the script leaves `person_id` and `visit_occurrence_id` empty, and its procedure dates are still the original dates at this stage.

### 2.6 Flag mappings that need review

```python
status = merged['status'].fillna('').str.casefold().str.replace('vertified', 'verified', regex=False)
merged['review_needed'] = (
    ~status.eq('verified') |
    ~merged['standard concept'].fillna('').str.casefold().eq('standard') |
    merged['procedure_concept_id'].isna()
)
count_by_event = merged.groupby('source_event_id')['source_event_id'].transform('size')
merged['combined_procedure_review'] = count_by_event > 1
```

`review_needed` identifies mappings that are not marked verified, not labelled standard, or missing a concept ID. The spelling correction handles `vertified` in the mapping sheet. `combined_procedure_review` flags source events expanded into multiple mapped rows. These are review indicators, not automatic proof of mapping correctness.

### 2.7 Save the workbook

```python
with pd.ExcelWriter(OUTPUT, engine='openpyxl') as writer:
    omop.to_excel(writer, sheet_name='OMOP_Draft', index=False)
    review.to_excel(writer, sheet_name='Mapping_Review_PRIVATE', index=False)
    pd.DataFrame({'Validation / Next Steps': issues}).to_excel(writer, sheet_name='Validation', index=False)
```

The generated workbook separates the OMOP draft, a **private** review table containing original patient/visit identifiers, and validation reminders. Do not upload the complete workbook to a public GitHub repository.

## 3. `date offset days.py` — Patient-specific date shifting

```python
raw = pd.read_excel('surgery patient1-5.xlsx', sheet_name='Raw_Procedures', dtype={'Patient_No': 'string'})
registry = pd.read_csv('person_registry.csv', dtype={'Patient_No': 'string'})
data = raw.merge(
    registry[['Patient_No', 'person_id', 'date_offset_days']],
    on='Patient_No', how='left', validate='many_to_one'
)
if data['date_offset_days'].isna().any():
    raise ValueError('Some patients have no date offset!')
data['operation_date'] = pd.to_datetime(data['operation_date'])
data['procedure_date'] = (
    data['operation_date'] + pd.to_timedelta(data['date_offset_days'], unit='D')
).dt.date
print(data[['person_id', 'procedure_date']])
```

This script joins each source patient to the group's shared `person_registry.csv`, checks for missing offsets, and applies the patient's `date_offset_days` to their surgery date. Using the same offset across tables preserves intervals between events for that patient. The script **prints** the shifted dates but does **not** save them to the OMOP draft or export a final file.

## 4. `visit occurrence id(1).py` — Visit ID mapping

```python
visit_registry = pd.read_csv(
    'visit_registry.csv', dtype={'Patient_No': 'string', 'Case_No': 'string'}
)
raw = pd.read_excel(
    'surgery patient1-5.xlsx', sheet_name='Raw_Procedures',
    dtype={'Patient_No': 'string', 'Case_No': 'string'}
)
data = raw.merge(
    visit_registry[['Patient_No', 'Case_No', 'visit_occurrence_id']],
    on=['Patient_No', 'Case_No'], how='left', validate='many_to_one'
)
print(data[['Patient_No', 'Case_No', 'visit_occurrence_id']])
```

The script links each surgical record to a shared visit using **both** `Patient_No` and `Case_No`. `how='left'` preserves source rows, while `validate='many_to_one'` checks that each patient-visit pair maps to at most one registry entry. The code displays results but does not yet check missing visit IDs or write the matched IDs into the OMOP draft.

## 5. Current status and remaining integration

| Step | Implemented in scripts? | Final output verified? |
|---|---|---|
| Read surgical and Athena mapping worksheets | Yes | Draft produced |
| Populate procedure standard concepts | Yes | Broader mappings require documented decisions |
| Produce OMOP-style fields | Yes | Complete CDM 5.4 validation pending |
| Calculate patient-specific date shifts | Yes, separate script | Not integrated into draft |
| Match shared visit IDs | Yes, separate script | Not integrated into draft |
| Apply shared anonymous person IDs | Available in date script | Not integrated into draft |
| Remove original identifiers from public output | Not yet an end-to-end export | Pending |

**Next step:** integrate the registry joins and date shifting into the conversion pipeline, validate that all output rows have the correct anonymised person and visit IDs, confirm the procedure type provenance and mapping decisions, and export only the approved public `procedure_occurrence.csv`. Keep the raw workbook, registries, group key and `Mapping_Review_PRIVATE` out of public GitHub.

## 6. Suggested explanation for presentation

> We used Python and pandas to read and clean five patients' surgical data, map the surgical descriptions to Athena standard concepts, and create an OMOP `PROCEDURE_OCCURRENCE` draft. Separate scripts match patients and visits to the group's shared registries and calculate patient-specific date shifts. Before publishing the final output, we need to integrate these steps and complete validation of the remaining broader concept mappings and combined procedure.

## 7. Reference

- OMOP CDM 5.4: https://ohdsi.github.io/CommonDataModel/cdm54.html
- Athena OHDSI: https://athena.ohdsi.org/
