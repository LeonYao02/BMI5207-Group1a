# Person 2: Diagnoses and Visits

This folder contains code and documentation for data cleaning, pseudonymization, and provisional conversion to OMOP CDM 5.4 VISIT_OCCURRENCE and CONDITION_OCCURRENCE.

Patient identifiers and visit identifiers reuse the shared registries. Dates use the shared patient-specific offsets.

Diagnosis mappings remain provisional where the source coding system or mapping interpretation is unresolved.

Original data, patient-level outputs, private registries, date offsets, and group keys are excluded from this public folder.
## How to Run

### Requirements

Use Python 3 with Jupyter Notebook and openpyxl:

    python -m pip install notebook openpyxl

### Required Files

Download the repository and retain this structure:

    person2_diagnoses_visits/
        Person2_Cleaning_and_OMOP.ipynb
        scripts/
            batch_mapping.py

Obtain the five original case-visit Excel files and the shared
registry files through the group's private channel.

Required registry files:

- person_registry.csv
- visit_registry.csv
- source_manifest.csv
- unlinked_source_cases.csv

Original patient files, registries, date offsets and group keys
must remain outside the public repository.

### Execution

1. Start Jupyter from the person2_diagnoses_visits folder.
2. Open Person2_Cleaning_and_OMOP.ipynb.
3. Update raw_folder and registry_folder to the local input locations.
4. Review other input and output paths before running.
5. Run the cells in order from top to bottom.

The batch vocabulary retrieval step requires an internet connection.
Its results are mapping candidates and require review.

### Expected Results

- 21 unique visits across 5 patients.
- 147 diagnosis events covering 72 distinct source codes.
- 92 provisional Condition records: 68 with candidate concepts
  and 24 with concept ID 0.
- 55 diagnosis events retained for routing review.

Patient-level outputs are shared privately. Public materials contain
code, vocabulary-level mapping decisions and aggregate reports.

### Limitations

The source diagnosis vocabulary and edition remain unconfirmed.
The outputs are provisional and do not represent fully approved
clinical mappings.
