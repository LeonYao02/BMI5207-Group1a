# BMI5207 Person 3 — Labs (OMOP CDM 5.4)

Place these files in `person3/` on branch `person3-labs`. `labs_mapping.csv` contains separate strict and assumption-based concept columns. Only Confirmed concepts are exported to `measurement_concept_id`; others become 0 and retain source values. The source has no unit/method dictionary.

Run from repository root (local only):

```bash
PYTHONPATH=src python person3/etl_labs.py --input-dir private/raw_labs --key private/group_key.hex --mapping person3/labs_mapping.csv --vocabulary private/athena/CONCEPT.csv --output-dir private/person3_output
PYTHONPATH=src:person3 python -m unittest discover -s person3 -p 'test_*.py'
```

Never commit raw files, private key, or generated row-level exports. See `quality_report.md` for limitations and coverage.

## Independent final QA

See `test_report.md` for the reproducible test commands, results, strict-mode expected failure, and two QA fixes. `candidate_audit.csv` now contains 454 review rows. Only confirmed mappings are emitted as nonzero `measurement_concept_id`. Do not commit private workbooks, test or production keys, or record-level MEASUREMENT exports.
