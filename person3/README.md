# Person 3 — Laboratory data ETL (OMOP CDM 5.4)

## Deliverables
- `labs_mapping.csv`: all unique source test codes, counts, and mapping review fields. **Unverified concept IDs are intentionally blank.**
- `etl_labs.py`: deterministic pseudonymised measurement export using group shared.py and group private key.
- `mapping_review.md`: limitations and release blockers.

## Run from repository root
Install `openpyxl`, ensure `src/bmi5207/shared.py` is present and receive the **same** `private/group_key.hex` from Person 1 via private channel. Never commit it.

```bash
PYTHONPATH=src python person3_labs/etl_labs.py --input-dir private/raw_labs --key private/group_key.hex --mapping person3_labs/labs_mapping.csv --output-dir private/person3_output
```

For strict validation append `--strict`. The output is a **review-only staging file** until every concept, measurement type, unit, and qualitative result is reviewed. Do not submit it as fully standardized OMOP output.

Raw Excel, private key, anonymised record-level exports and source filename crosswalks must stay out of public GitHub. The script reads source workbooks locally and does not export raw Patient_No, Case_No or source filename.
