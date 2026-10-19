#!/usr/bin/env python3
"""Validate the delivered order ledger against CDM rows and private registries."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bmi5207.shared import read_csv
from bmi5207.medications import DRUG_COLUMNS, concept_catalogue, require_standard


def validate(output: Path, private: Path, concepts_path: Path) -> dict:
    drugs = read_csv(output / "drug_exposure.csv")
    ledger = read_csv(output / "medication_details.csv")
    handoff = read_csv(output / "cross_domain_handoff.csv")
    people = {r["person_id"] for r in read_csv(private / "person_registry.csv")}
    visits = {r["visit_occurrence_id"]: r["person_id"] for r in read_csv(private / "visit_registry.csv")}
    lineage = read_csv(private / "drug_lineage.csv")
    concepts = concept_catalogue(concepts_path)
    report = json.loads((output / "quality_report.json").read_text())
    assert people and len(people) == 5, "Expected five registered people"
    assert not drugs or list(drugs[0]) == DRUG_COLUMNS, "Wrong CDM columns/order"
    ids = [r["source_order_id"] for r in ledger]
    drug_ids = {r["drug_exposure_id"] for r in drugs}
    handoff_ids = {r["source_order_id"] for r in handoff}
    assert len(ids) == len(set(ids)) == report["source_medication_rows"]
    assert drug_ids.isdisjoint(handoff_ids)
    assert drug_ids | handoff_ids == set(ids), "Order dropped or sent to two tables"
    assert {r["drug_exposure_id"] for r in lineage} == set(ids)
    for row in ledger:
        assert row["person_id"] in people
        if row["visit_occurrence_id"]:
            assert visits[row["visit_occurrence_id"]] == row["person_id"], "Wrong-patient visit"
        assert 0 < int(row["source_order_id"]) <= 2**31 - 1
    for row in drugs:
        cid = int(row["drug_concept_id"])
        if cid:
            require_standard(concepts, cid, "Drug")
        assert row["drug_exposure_end_date"] >= row["drug_exposure_start_date"]
        assert all(row[k] == "" for k in ("quantity", "days_supply", "sig", "verbatim_end_date")), "Unsupported value imputed"
    for row in handoff:
        if int(row["target_concept_id"]):
            require_standard(concepts, int(row["target_concept_id"]), "Device")
    return {"order_accounting": "passed", "id_uniqueness_and_int32_range": "passed",
            "person_and_visit_registry_links": "passed", "nonzero_concept_domain_and_status": "passed",
            "unobserved_values_not_fabricated": "passed", "rows_checked": len(ids),
            "limitation": "Checks registry links, not yet the other members' PERSON/VISIT tables; no full OHDSI DQD claim."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/medications"))
    parser.add_argument("--private-dir", type=Path, default=Path("private"))
    parser.add_argument("--concepts", type=Path, default=Path("mappings/concepts_verified.csv"))
    args = parser.parse_args()
    print(json.dumps(validate(args.output, args.private_dir, args.concepts), indent=2))
