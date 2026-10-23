#!/usr/bin/env python
# coding: utf-8

# In[1]:


from pathlib import Path
import pandas as pd


# In[2]:


BASE = Path.cwd()
INPUT = BASE / 'surgery patient1-5.xlsx'
OUTPUT = BASE / 'surgery_OMOP_Result.xlsx'
PROCEDURE_TYPE_CONCEPT_ID = 32817


# In[3]:


def norm(v):
    return '' if pd.isna(v) else str(v).strip()


# In[4]:


def main():
    if not INPUT.exists():
        raise FileNotFoundError(f'Put {INPUT.name} in the same folder as this script.')
    raw = pd.read_excel(INPUT, sheet_name='Raw_Procedures', dtype={'Surgical_Code': 'string', 'Patient_No': 'string', 'Case_No': 'string'})
    mapping = pd.read_excel(INPUT, sheet_name='Athena_Mapping', dtype={'original code': 'string'})
    raw.columns = raw.columns.astype(str).str.strip()
    mapping.columns = mapping.columns.astype(str).str.strip()
    raw_required = ['Surgical_Code', 'Surgical_Desc', 'Operation_Table_Code', 'Case_No', 'Patient_No', 'operation_date']
    map_required = ['original code', 'original description', 'standard concept name', 'concept ID', 'vocabulary', 'standard concept', 'status']
    for label, df, required in [('Raw_Procedures', raw, raw_required), ('Athena_Mapping', mapping, map_required)]:
        missing = set(required) - set(df.columns)
        if missing:
            raise ValueError(f'{label} missing columns: {sorted(missing)}')

    raw = raw.dropna(subset=['Surgical_Code']).copy()
    mapping = mapping.dropna(subset=['original code', 'standard concept name']).copy()
    for col in ['Surgical_Code', 'Case_No', 'Patient_No']:
        raw[col] = raw[col].map(norm)
    mapping['original code'] = mapping['original code'].map(norm)
    mapping['standard concept name'] = mapping['standard concept name'].map(norm)
    mapping['concept ID'] = pd.to_numeric(mapping['concept ID'].map(norm), errors='coerce').astype('Int64')
    mapping['status'] = mapping['status'].map(norm)
    mapping['standard concept'] = mapping['standard concept'].map(norm)
    mapping['vocabulary'] = mapping['vocabulary'].map(norm)
    if 'notes' not in mapping:
        mapping['notes'] = ''
    # The original workbook repeats DSIC004 for two actual encounters and
    # repeats ZSD714H to show two components of ONE original combined procedure.
    # Deduplicate original source events using all source fields, not just surgical code.
    source_cols = raw_required
    events = raw[source_cols].drop_duplicates(subset=source_cols).reset_index(drop=True).copy()
    events.insert(0, 'source_event_id', range(1, len(events) + 1))
    # Deduplicate mapping rows for same source code AND concept; keep distinct components.
    map_keys = ['original code', 'concept ID', 'standard concept name']
    mp = mapping.drop_duplicates(subset=map_keys).copy()
    merged = events.merge(mp, left_on='Surgical_Code', right_on='original code', how='left', validate='many_to_many')
    merged['procedure_datetime'] = pd.to_datetime(merged['operation_date'], errors='coerce')
    merged['procedure_date'] = merged['procedure_datetime'].dt.date
    merged['procedure_occurrence_id'] = range(1, len(merged) + 1)
    merged['procedure_concept_id'] = merged['concept ID'].astype('Int64')
    merged['procedure_type_concept_id'] = PROCEDURE_TYPE_CONCEPT_ID
    merged['person_id'] = pd.NA  # To be filled using group person_registry.csv
    merged['visit_occurrence_id'] = pd.NA  # To be filled using group visit_registry.csv
    merged['procedure_source_value'] = merged['Surgical_Code']
    merged['procedure_source_concept_id'] = 0  # Local source code is not a known Athena source concept
    status = merged['status'].fillna('').str.casefold().str.replace('vertified', 'verified', regex=False)
    merged['review_needed'] = (~status.eq('verified') |
                               ~merged['standard concept'].fillna('').str.casefold().eq('standard') |
                               merged['procedure_concept_id'].isna())
        # Source rows with combined operations require review before final OMOP export.
    count_by_event = merged.groupby('source_event_id')['source_event_id'].transform('size')
    merged['combined_procedure_review'] = count_by_event > 1
    omop_cols = ['procedure_occurrence_id', 'person_id', 'procedure_concept_id', 'procedure_date',
                 'procedure_datetime', 'procedure_type_concept_id', 'visit_occurrence_id',
                 'procedure_source_value', 'procedure_source_concept_id']
    omop = merged[omop_cols].copy()
    review_cols = ['source_event_id', 'Patient_No', 'Case_No', 'Surgical_Code', 'Surgical_Desc',
                   'standard concept name', 'concept ID', 'vocabulary', 'status', 'notes',
                   'review_needed', 'combined_procedure_review']
    review = merged[review_cols].copy()
    issues = []
    if len(events) != 7:
        issues.append(f'Expected 7 distinct source events, found {len(events)}.')
    if merged['procedure_concept_id'].isna().any():
        issues.append('Some source procedures lack a mapped Concept ID.')
    if merged['procedure_date'].isna().any():
        issues.append('Some procedure dates are missing or invalid.')
    if merged['review_needed'].any():
        issues.append('Some Athena mappings remain candidates or are incomplete.')
    if merged['combined_procedure_review'].any():
        issues.append('ZSD714H combined angiography/angioplasty: review whether to emit two procedure events or one combined concept.')
    issues.extend([
        'Final person_id: apply group person_registry.csv, matching Patient_No.',
        'Final visit_occurrence_id: apply group visit_registry.csv, matching Patient_No + Case_No.',
        'Apply group date_offset_days consistently before publishing.',
        'Confirm Athena Standard procedure_type_concept_id from record provenance; currently missing.',
        'Validate complete OMOP CDM 5.4 required columns and cross-table referential integrity.',
        'Do not upload Mapping_Review or other source identifiers to public GitHub.'
    ])
    with pd.ExcelWriter(OUTPUT, engine='openpyxl') as writer:
        omop.to_excel(writer, sheet_name='OMOP_Draft', index=False)
        review.to_excel(writer, sheet_name='Mapping_Review_PRIVATE', index=False)
        pd.DataFrame({'Validation / Next Steps': issues}).to_excel(writer, sheet_name='Validation', index=False)
    print(f'Created: {OUTPUT.name}')
    print(f'Raw rows: {len(raw)}; unique source events: {len(events)}; OMOP draft rows: {len(omop)}')
    print('DRAFT ONLY: not anonymized and not complete OMOP CDM 5.4.')


# In[5]:


if __name__ == '__main__':
    main()


# In[ ]:




