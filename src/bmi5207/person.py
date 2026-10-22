"""Group-wide anonymisation staging + OMOP CDM 5.4 PERSON/DEATH ETL.

Owner: Person 1 (Anonymisation + Demographics). Uses the SAME shared key, person_id,
visit_id and date-offset rules as every other domain (src/bmi5207/shared.py), so the
tables produced here join directly with the other members' CDM tables.

Outputs
  outputs/person/person.csv, death.csv, quality_report.json      (patient-level, git-ignored)
  outputs/anonymised/<domain>_anonymised.csv                      (patient-level, git-ignored)
  private/person_registry.csv, private/case_registry.csv          (linkage secrets, git-ignored)

Pseudonymisation and date shifting reduce disclosure; they do not prove anonymity.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from .shared import (ID_SCHEME, clean, date_offset, load_key, parse_datetime, person_id,
                     read_csv, visit_id, write_csv)
from .source import SourceTable, discover

ROOT = Path(__file__).resolve().parents[2]

PERSON_COLUMNS = [
    "person_id", "gender_concept_id", "year_of_birth", "month_of_birth", "day_of_birth",
    "birth_datetime", "race_concept_id", "ethnicity_concept_id", "location_id", "provider_id",
    "care_site_id", "person_source_value", "gender_source_value", "gender_source_concept_id",
    "race_source_value", "race_source_concept_id", "ethnicity_source_value",
    "ethnicity_source_concept_id",
]
DEATH_COLUMNS = [
    "person_id", "death_date", "death_datetime", "death_type_concept_id", "cause_concept_id",
    "cause_source_value", "cause_source_concept_id",
]

# Exact clinical timestamps: shifted with the patient's shared offset.
DATE_FIELDS = {
    "visit": ["Adm_DateTime", "Dis_DateTime", "Dis_DateTime_Planned"],
    "lab": ["Result_Test_Date"],
    "medication": ["Order_Creation_Date"],
    "procedure": ["operation_date"],
}
# Removed from the shareable staging tables (reasons in docs/anonymisation_person_methods.md).
SUPPRESSED_FIELDS = {
    "person": ["Religion", "Marital_Status"],
    "visit": ["Adm_Trt_Cat_Desc", "Adm_Physical_Class_Desc", "Dis_Physical_Class_Desc"],
    "medication": ["Order_Text"],
}
DOMAIN_FILE = {"person": "person", "visit": "visit", "lab": "lab_results",
               "medication": "medication_orders", "procedure": "procedures"}
MOJIBAKE = {"Â®": "®", "Â©": "©", "Â°": "°"}


# --------------------------------------------------------------------------- helpers
def concept_catalogue(path: Path) -> dict[int, dict]:
    return {int(r["concept_id"]): r for r in read_csv(path)}


def require_standard(concepts: dict, cid: int, domain: str) -> dict:
    row = concepts.get(cid)
    if row is None:
        raise ValueError(f"Concept {cid} is not in the verified catalogue; check it in Athena first.")
    if row["domain_id"] != domain or row["standard_concept"] != "S" or row["invalid_reason"]:
        raise ValueError(f"Concept {cid} is not a valid Standard {domain} concept.")
    return row


def load_demographic_mapping(path: Path, concepts: dict) -> dict[tuple[str, str], int]:
    """(field, source_value) -> concept_id. Nonzero targets must be verified Standard concepts."""
    domains = {"gender": "Gender", "race": "Race", "ethnicity": "Ethnicity"}
    mapping = {}
    for row in read_csv(path):
        field, value, cid = clean(row["field"]).lower(), clean(row["source_value"]), int(row["target_concept_id"])
        if cid:
            require_standard(concepts, cid, domains[field])
        mapping[(field, value.lower())] = cid
    return mapping


def fmt(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    for bad, good in MOJIBAKE.items():
        text = text.replace(bad, good)
    return text


def year_only(value: object, label: str) -> int | None:
    text = clean(value)
    if not text:
        return None
    if isinstance(value, (datetime, date)):
        raise ValueError(f"{label} holds a full date; this ETL expects year-only values. Update the rules first.")
    if not text.replace(".0", "").isdigit() or len(text.replace(".0", "")) != 4:
        raise ValueError(f"{label} is not a 4-digit year: {text!r}")
    return int(text.replace(".0", ""))


def is_true(value: object) -> bool:
    return clean(value).lower() in {"true", "1", "y", "yes"}


# --------------------------------------------------------------------------- main ETL
def run_person_etl(input_dir: Path, output_dir: Path, anonymised_dir: Path, private_dir: Path,
                   key: bytes, config: dict, mapping_path: Path, concepts_path: Path) -> dict:
    if config.get("cdm_version") != "5.4":
        raise ValueError("This exporter implements OMOP CDM 5.4 only.")
    max_days = int(config["date_shift_max_days"])
    if max_days > 182:
        raise ValueError("Mid-year death imputation keeps the death year only if the shift is <= 182 days.")
    top_code_age = int(config.get("top_code_age", 90))

    tables = discover(input_dir)
    by_kind: dict[str, list[tuple[SourceTable, dict]]] = defaultdict(list)
    for table in tables:
        for row in table.rows:
            by_kind[table.kind].append((table, row))
    if not by_kind["person"]:
        raise ValueError("No patient demographic records were found.")
    for kind, rows in by_kind.items():
        if any(not clean(row.get("Patient_No")) for _, row in rows):
            raise ValueError(f"{kind} record without Patient_No; cannot pseudonymise or date-shift safely.")

    patients = sorted({clean(row["Patient_No"]) for rows in by_kind.values() for _, row in rows})
    demo_patients = sorted({clean(row["Patient_No"]) for _, row in by_kind["person"]})
    if len(patients) != config["expected_patients"] or demo_patients != patients:
        raise ValueError(f"Expected {config['expected_patients']} patients with demographics in every case; "
                         f"found {len(patients)} patients, {len(demo_patients)} with demographic rows.")
    pids = {p: person_id(key, p) for p in patients}
    offsets = {p: date_offset(key, p, max_days) for p in patients}
    if len(set(pids.values())) != len(pids):
        raise ValueError("Patient ID collision; coordinate a new shared key before any release.")

    # Visits that really exist in the visit source (exact patient + Case_No).
    visit_pairs = {(clean(r["Patient_No"]), clean(r["Case_No"])) for _, r in by_kind["visit"]}
    all_cases: dict[tuple[str, str], set[str]] = defaultdict(set)
    for kind, rows in by_kind.items():
        for _, row in rows:
            case = clean(row.get("Case_No"))
            if case:
                all_cases[(clean(row["Patient_No"]), case)].add(kind)
    case_ids = {pair: visit_id(key, *pair) for pair in all_cases}
    if len(set(case_ids.values())) != len(case_ids):
        raise ValueError("Case/visit ID collision.")

    issues = Counter()
    staged: dict[str, tuple[list[str], list[dict]]] = {}
    last_event: dict[str, datetime] = {}
    first_event: dict[str, datetime] = {}

    # ---- pseudonymise + shift every domain --------------------------------
    for kind in ("person", "visit", "lab", "medication", "procedure"):
        rows = by_kind.get(kind, [])
        if not rows:
            continue
        source_cols = [c for c in rows[0][1] if not c.startswith("_")]
        out_cols: list[str] = []
        for col in source_cols:
            if col in SUPPRESSED_FIELDS.get(kind, []):
                continue
            if col == "Patient_No":
                out_cols.append("person_id")
            elif col == "Case_No":
                out_cols += ["visit_occurrence_id", "case_group_id"]
            elif kind == "person" and col == "Patient_DOB":
                out_cols.append("year_of_birth")
            elif kind == "person" and col == "Death_Date":
                out_cols.append("death_date")
            else:
                out_cols.append(col)
        if kind == "medication":
            out_cols.append("anonymisation_flags")
        if kind == "person":
            out_cols.append("anonymisation_flags")

        out_rows = []
        for _, row in rows:
            patient = clean(row["Patient_No"])
            out = {}
            flags = []
            for col in source_cols:
                if col in SUPPRESSED_FIELDS.get(kind, []):
                    continue
                value = row.get(col)
                if col == "Patient_No":
                    out["person_id"] = pids[patient]
                elif col == "Case_No":
                    pair = (patient, clean(value))
                    out["visit_occurrence_id"] = case_ids[pair] if pair in visit_pairs else ""
                    out["case_group_id"] = case_ids[pair] if clean(value) else ""
                elif col in DATE_FIELDS.get(kind, []):
                    if not clean(value):
                        out[col] = ""
                        continue
                    shifted = parse_datetime(value) + timedelta(days=offsets[patient])
                    out[col] = fmt(shifted)
                    first_event[patient] = min(first_event.get(patient, shifted), shifted)
                    last_event[patient] = max(last_event.get(patient, shifted), shifted)
                elif kind == "person" and col in ("Patient_DOB", "Death_Date"):
                    out["year_of_birth" if col == "Patient_DOB" else "death_date"] = value  # resolved below
                elif kind == "medication" and col == "Dosage_Ordered" and isinstance(value, (datetime, date)):
                    out[col] = ""
                    flags.append("dose_excel_date_corruption")
                    issues["dose_excel_date_corruption"] += 1
                else:
                    out[col] = fmt(value)
            if kind in ("medication", "person"):
                out["anonymisation_flags"] = flags
            out["_patient"] = patient
            out_rows.append(out)
        staged[kind] = (out_cols, out_rows)

    # ---- demographics: PERSON + DEATH -------------------------------------
    demo_mapping = load_demographic_mapping(mapping_path, concepts := concept_catalogue(concepts_path))
    death_type = int(config["death_type_concept_id"])
    require_standard(concepts, death_type, "Type Concept")
    imp_month, imp_day = (int(x) for x in config.get("death_year_impute_month_day", "07-01").split("-"))

    person_rows, death_rows = [], []
    seen_demo = {}
    for out in staged["person"][1]:
        patient = out["_patient"]
        signature = tuple(sorted((k, str(v)) for k, v in out.items()))
        if patient in seen_demo:
            if seen_demo[patient] != signature:
                raise ValueError("Conflicting demographic rows for one patient; resolve before export.")
            issues["exact_duplicate_demographic_row"] += 1
            continue
        seen_demo[patient] = signature

        yob = year_only(out["year_of_birth"], "Patient_DOB")
        if yob is None:
            raise ValueError("year_of_birth is required by OMOP PERSON.")
        if patient in first_event and first_event[patient].year - yob >= top_code_age:
            yob = first_event[patient].year - top_code_age
            out["anonymisation_flags"].append("age_top_coded")
            issues["age_top_coded"] += 1
        out["year_of_birth"] = yob

        death_year = year_only(out["death_date"], "Death_Date")
        deceased = is_true(out.get("Deceased_Ind"))
        death_date = ""
        if deceased and death_year is None:
            issues["deceased_without_death_year"] += 1
        if death_year is not None:
            imputed = date(death_year, imp_month, imp_day) + timedelta(days=offsets[patient])
            if imputed.year != death_year:
                raise ValueError("Death year changed after shifting; check the imputation/shift settings.")
            if patient in last_event and imputed < last_event[patient].date():
                raise ValueError("Shifted death date precedes a shifted clinical event; review source.")
            death_date = imputed.isoformat()
            out["anonymisation_flags"].append("death_date_imputed_from_year")
            if not deceased:
                issues["death_year_without_deceased_flag"] += 1
        out["death_date"] = death_date

        gender_src, race_src = clean(out.get("Gender")), clean(out.get("Race"))
        try:
            gender_cid = demo_mapping[("gender", gender_src.lower())]
            race_cid = demo_mapping[("race", race_src.lower())]
        except KeyError as exc:
            raise ValueError(f"Unreviewed demographic value {exc}; add it to mappings/demographics.csv.") from None
        ethnicity_cid = demo_mapping.get(("ethnicity", ""), 0)

        person_rows.append({
            "person_id": pids[patient], "gender_concept_id": gender_cid, "year_of_birth": yob,
            "month_of_birth": "", "day_of_birth": "", "birth_datetime": "",
            "race_concept_id": race_cid, "ethnicity_concept_id": ethnicity_cid,
            "location_id": "", "provider_id": "", "care_site_id": "",
            "person_source_value": "", "gender_source_value": gender_src, "gender_source_concept_id": 0,
            "race_source_value": race_src, "race_source_concept_id": 0,
            "ethnicity_source_value": "", "ethnicity_source_concept_id": 0,
        })
        if death_date:
            death_rows.append({
                "person_id": pids[patient], "death_date": death_date, "death_datetime": "",
                "death_type_concept_id": death_type, "cause_concept_id": 0,
                "cause_source_value": "", "cause_source_concept_id": 0,
            })
    person_rows.sort(key=lambda r: r["person_id"])
    death_rows.sort(key=lambda r: r["person_id"])

    for kind in ("person", "medication"):
        if kind in staged:
            for out in staged[kind][1]:
                out["anonymisation_flags"] = ";".join(out["anonymisation_flags"])

    # ---- release checks ----------------------------------------------------
    raw_identifiers = set(patients) | {case for _, case in all_cases}
    for kind, (cols, rows) in staged.items():
        for out in rows:
            for col in cols:
                text = str(out.get(col, ""))
                if any(ident and ident in text for ident in raw_identifiers):
                    raise ValueError(f"Source identifier found in {kind}.{col}; export stopped.")
    for row in person_rows + death_rows:
        if any(ident in str(v) for v in row.values() for ident in raw_identifiers):
            raise ValueError("Source identifier found in PERSON/DEATH; export stopped.")

    def k_classes(fields):
        return sorted(Counter(tuple(f(r) for f in fields) for r in person_rows).values())
    sex = lambda r: r["gender_concept_id"]
    race = lambda r: r["race_concept_id"]
    yob_ = lambda r: r["year_of_birth"]
    decade = lambda r: r["year_of_birth"] // 10 * 10
    k_report = {
        "year_of_birth+sex+race": k_classes([yob_, sex, race]),
        "birth_decade+sex+race": k_classes([decade, sex, race]),
        "sex+race": k_classes([sex, race]),
    }

    exact_dup = {}
    for kind, (cols, rows) in staged.items():
        sig = Counter(tuple(str(r.get(c, "")) for c in cols) for r in rows)
        exact_dup[kind] = sum(n - 1 for n in sig.values() if n > 1)

    report = {
        "cdm_version": "5.4", "id_scheme": ID_SCHEME,
        "patients": len(patients), "person_rows": len(person_rows), "death_rows": len(death_rows),
        "source_rows_by_domain": {k: len(v[1]) for k, v in staged.items()},
        "unique_cases_by_source": {
            "in_visit_source": len(visit_pairs),
            "only_in_other_domains_fk_left_blank": len(set(all_cases) - visit_pairs),
        },
        "rows_with_blank_visit_fk_by_domain": {
            k: sum(1 for r in v[1] if "visit_occurrence_id" in r and r["visit_occurrence_id"] == "")
            for k, v in staged.items() if k not in ("visit", "person")},
        "exact_duplicate_rows_retained_by_domain": exact_dup,
        "suppressed_fields": SUPPRESSED_FIELDS,
        "shifted_fields": DATE_FIELDS,
        "date_shift_range_days": [-max_days, max_days], "zero_shift_allowed": False,
        "gender_concept_counts": dict(Counter(str(r["gender_concept_id"]) for r in person_rows)),
        "race_concept_counts": dict(Counter(str(r["race_concept_id"]) for r in person_rows)),
        "flags": dict(sorted(issues.items())),
        "k_anonymity_equivalence_class_sizes": k_report,
        "observed_minimum_k": {k: min(v) for k, v in k_report.items()},
        "checks": {"no_source_identifier_in_outputs": True, "unique_person_ids": True,
                   "unique_case_ids": True, "death_after_last_event": True,
                   "death_year_preserved": True, "nonzero_concepts_standard_and_verified": True},
        "full_anonymity_claimed": False,
        "privacy_status": config.get("release_status", ""),
        "key_fingerprint": hashlib.sha256(key).hexdigest()[:16],
        "mapping_sha256": hashlib.sha256(mapping_path.read_bytes()).hexdigest(),
        "vocabulary_metadata_sha256": hashlib.sha256(concepts_path.read_bytes()).hexdigest(),
    }

    # ---- write (all-or-nothing staging) -----------------------------------
    for target in (output_dir, anonymised_dir):
        target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="person-", dir=output_dir.parent) as tmp:
        stage = Path(tmp)
        write_csv(stage / "person" / "person.csv", PERSON_COLUMNS, person_rows)
        write_csv(stage / "person" / "death.csv", DEATH_COLUMNS, death_rows)
        (stage / "person" / "quality_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        for kind, (cols, rows) in staged.items():
            write_csv(stage / "anonymised" / f"{DOMAIN_FILE[kind]}_anonymised.csv", cols,
                      [{c: r.get(c, "") for c in cols} for r in rows])
        for sub, target in (("person", output_dir), ("anonymised", anonymised_dir)):
            target.mkdir(parents=True, exist_ok=True)
            for file in (stage / sub).iterdir():
                shutil.copy2(file, target / file.name)

    # ---- private registries -----------------------------------------------
    private_dir.mkdir(parents=True, exist_ok=True)
    registry = [{"Patient_No": p, "person_id": pids[p], "date_offset_days": offsets[p]} for p in patients]
    reg_path = private_dir / "person_registry.csv"
    if reg_path.exists():
        existing = {r["Patient_No"]: (r["person_id"], r["date_offset_days"]) for r in read_csv(reg_path)}
        mine = {r["Patient_No"]: (str(r["person_id"]), str(r["date_offset_days"])) for r in registry}
        if existing != mine:
            raise ValueError("private/person_registry.csv disagrees with this run: wrong group key or config. "
                             "Use the shared group key; do not overwrite another member's registry.")
    else:
        write_csv(reg_path, ["Patient_No", "person_id", "date_offset_days"], registry)
    write_csv(private_dir / "case_registry.csv",
              ["Patient_No", "Case_No", "person_id", "case_group_id", "in_visit_source", "found_in_domains"],
              [{"Patient_No": p, "Case_No": c, "person_id": pids[p], "case_group_id": case_ids[(p, c)],
                "in_visit_source": (p, c) in visit_pairs, "found_in_domains": ";".join(sorted(all_cases[(p, c)]))}
               for (p, c) in sorted(all_cases)])
    for file in private_dir.glob("*.csv"):
        file.chmod(0o600)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Pseudonymise all five source domains and build PERSON/DEATH.")
    run.add_argument("--input", type=Path, required=True)
    run.add_argument("--output", type=Path, default=Path("outputs/person"))
    run.add_argument("--anonymised-dir", type=Path, default=Path("outputs/anonymised"))
    run.add_argument("--private-dir", type=Path, default=Path("private"))
    run.add_argument("--key-file", type=Path, default=Path("private/group_key.hex"))
    run.add_argument("--config", type=Path, default=ROOT / "config/project.json")
    run.add_argument("--mapping", type=Path, default=ROOT / "mappings/demographics.csv")
    run.add_argument("--concepts", type=Path, default=ROOT / "mappings/concepts_verified.csv")
    args = parser.parse_args(argv)
    try:
        report = run_person_etl(args.input, args.output, args.anonymised_dir, args.private_dir,
                                load_key(args.key_file), json.loads(args.config.read_text()),
                                args.mapping, args.concepts)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps({k: report[k] for k in ("patients", "person_rows", "death_rows",
                                             "source_rows_by_domain", "observed_minimum_k",
                                             "key_fingerprint")}, indent=2))
    return 0
