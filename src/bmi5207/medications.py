"""Conservative OMOP CDM 5.4 medication-order ETL.

Orders are retained as orders. Dose is never interpreted as product strength,
tablet count, frequency, route, or actual administration.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile

from .shared import (ID_SCHEME, clean, date_offset, event_id, load_key, person_id,
                     read_csv, shift_datetime, visit_id, write_csv)
from .source import SourceTable, discover

ROOT = Path(__file__).resolve().parents[2]
DRUG_COLUMNS = [
    "drug_exposure_id", "person_id", "drug_concept_id",
    "drug_exposure_start_date", "drug_exposure_start_datetime",
    "drug_exposure_end_date", "drug_exposure_end_datetime", "verbatim_end_date",
    "drug_type_concept_id", "stop_reason", "refills", "quantity", "days_supply",
    "sig", "route_concept_id", "lot_number", "provider_id",
    "visit_occurrence_id", "visit_detail_id", "drug_source_value",
    "drug_source_concept_id", "route_source_value", "dose_unit_source_value",
]
MAPPING_COLUMNS = [
    "source_code", "source_name", "source_form", "target_concept_id",
    "target_concept_name", "mapping_level", "mapping_notes", "mapping_status", "target_domain",
]
DETAIL_COLUMNS = [
    "source_order_id", "drug_exposure_id", "person_id", "source_code", "source_name", "order_text",
    "dose_original", "dose_unit_original", "dose_normalized", "dose_unit_normalized",
    "dose_form_source", "dose_form_category", "strength_unit_source", "modified_release_source",
    "mapped_concept_name", "mapping_level", "end_date_inferred", "end_date_policy",
    "actual_duration_known", "component_type", "component_description", "mapping_status",
    "target_domain", "target_concept_id", "order_datetime_shifted", "visit_occurrence_id", "flags",
]
HANDOFF_COLUMNS = ["source_order_id", "person_id", "order_datetime_shifted", "visit_occurrence_id",
                   "source_code", "source_name", "source_form", "target_concept_id",
                   "target_concept_name", "target_domain", "mapping_status", "reason"]
ISSUE_COLUMNS = ["severity", "code", "drug_exposure_id", "person_id", "detail"]


def norm(value: object) -> str:
    return " ".join(clean(value).casefold().split())


def source_name(row: dict) -> str:
    return clean(row.get("Cluster_Preferred_Name_Description")) or clean(
        row.get("Medication_Order_Component_Text")) or clean(row.get("Order_Text"))


def mapping_key(row: dict, *, source: bool = True) -> tuple[str, str, str]:
    if source:
        return (clean(row.get("Cluster_Preferred_Name_Code")), norm(source_name(row)),
                norm(row.get("Dosage_Form")))
    return (clean(row.get("source_code")), norm(row.get("source_name")), norm(row.get("source_form")))


def inventory(tables: list[SourceTable]) -> list[dict]:
    items = {}
    for table in tables:
        if table.kind != "medication":
            continue
        for row in table.rows:
            key = mapping_key(row)
            if key not in items:
                items[key] = {
                    "source_code": key[0], "source_name": source_name(row),
                    "source_form": clean(row.get("Dosage_Form")),
                    "target_concept_id": "", "target_concept_name": "",
                    "mapping_level": "", "mapping_notes": "Requires Athena review",
                }
    return [items[key] for key in sorted(items)]


def concept_catalogue(path: Path) -> dict[int, dict]:
    concepts = {}
    for row in read_csv(path):
        cid = int(row["concept_id"])
        if cid in concepts:
            raise ValueError(f"Duplicate concept_id in concept catalogue: {cid}")
        concepts[cid] = row
    return concepts


def require_standard(concepts: dict, cid: int, domain: str) -> dict:
    if cid not in concepts:
        raise ValueError(f"Concept {cid} has no verification metadata.")
    concept = concepts[cid]
    if concept["domain_id"] != domain or concept["standard_concept"] != "S":
        raise ValueError(f"Concept {cid} is not a Standard {domain} concept.")
    if clean(concept.get("invalid_reason")):
        raise ValueError(f"Concept {cid} is invalid.")
    today = date.today().isoformat()
    if concept.get("valid_start_date", "0001-01-01") > today or concept.get("valid_end_date", "9999-12-31") < today:
        raise ValueError(f"Concept {cid} is outside its recorded validity interval.")
    return concept


def load_mappings(path: Path, concepts: dict) -> dict[tuple, dict]:
    mappings = {}
    for row in read_csv(path):
        key = mapping_key(row, source=False)
        if key in mappings:
            raise ValueError(f"Duplicate source mapping: {key}")
        if not clean(row.get("target_concept_id")):
            raise ValueError(f"Unreviewed source mapping: {key}")
        row["mapping_status"] = clean(row.get("mapping_status")) or "mapped"
        row["target_domain"] = clean(row.get("target_domain")) or "Drug"
        cid = int(row["target_concept_id"])
        if row["mapping_status"] not in {"mapped", "reviewed_unmapped", "cross_domain_handoff"}:
            raise ValueError(f"Unknown mapping status: {key}")
        if row["mapping_status"] == "reviewed_unmapped":
            if cid != 0 or row["target_concept_name"] or row["target_domain"] != "Drug":
                raise ValueError(f"Unmapped drug must use concept 0 and no invented name: {key}")
        else:
            if row["mapping_status"] == "mapped" and row["target_domain"] != "Drug":
                raise ValueError(f"Non-Drug concept requires a cross-domain handoff: {key}")
            if row["mapping_status"] == "cross_domain_handoff" and row["target_domain"] != "Device":
                raise ValueError(f"Only reviewed Device handoffs are implemented: {key}")
            if cid:
                concept = require_standard(concepts, cid, row["target_domain"])
                if row["target_domain"] == "Drug" and concept["vocabulary_id"] not in {"RxNorm", "RxNorm Extension"}:
                    raise ValueError(f"Unexpected drug vocabulary for {key}")
                if row["target_concept_name"] != concept["concept_name"]:
                    raise ValueError(f"Concept name/ID mismatch for {key}")
                if row["mapping_level"] != concept["concept_class_id"]:
                    raise ValueError(f"Concept class/ID mismatch for {key}")
            elif row["mapping_status"] != "cross_domain_handoff" or row["target_concept_name"]:
                raise ValueError(f"Concept 0 requires an explicit reviewed exception: {key}")
        if not clean(row.get("mapping_notes")):
            raise ValueError(f"Missing mapping rationale for {key}")
        mappings[key] = row
    return mappings


def normalize_dose(value: object, unit: object) -> tuple[str, str, list[str]]:
    text = clean(value)
    if not text:
        return "", "", ["missing_dose"]
    if isinstance(value, (date, datetime)) or re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[ T].*)?", text):
        return "", "", ["dose_excel_date_corruption"]
    dose_range = re.fullmatch(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)", text)
    if dose_range:
        low, high = dose_range.groups()
        if Decimal(low) > Decimal(high):
            return "", "", ["invalid_dose"]
        # A range in a weight-based rate cannot become one scalar dose without a patient weight.
        return f"{low} - {high}", clean(unit), ["dose_range_retained", "unit_not_mass_standardized"]
    try:
        amount = Decimal(text)
    except InvalidOperation:
        return "", "", ["non_numeric_dose"]
    if not amount.is_finite() or amount < 0:
        return "", "", ["invalid_dose"]
    factors = {"mg": Decimal(1), "g": Decimal(1000), "mcg": Decimal("0.001"),
               "ug": Decimal("0.001"), "µg": Decimal("0.001"), "μg": Decimal("0.001")}
    source_unit = clean(unit)
    if source_unit in factors:
        result = format(amount * factors[source_unit], "f")
        if "." in result:
            result = result.rstrip("0").rstrip(".")
        return result, "mg", []
    if source_unit == "Litre":
        return format(amount * 1000, "f"), "mL", ["volume_only_not_mass"]
    # Do not convert mL, IU, mmol, tablets, or mEq to mass without supporting data.
    return format(amount, "f"), source_unit, ["unit_not_mass_standardized"]


def run_etl(input_dir: Path, output_dir: Path, private_dir: Path, key: bytes,
            config: dict, mappings_path: Path, concepts_path: Path,
            allow_partial: bool = False) -> dict:
    if config.get("cdm_version") != "5.4":
        raise ValueError("This exporter implements OMOP CDM 5.4 only.")
    tables = discover(input_dir)
    all_rows = [row for table in tables for row in table.rows]
    all_patients = {clean(row.get("Patient_No")) for row in all_rows if clean(row.get("Patient_No"))}
    meds = [(table, row) for table in tables if table.kind == "medication" for row in table.rows]
    if not meds:
        raise ValueError("No medication-order records were found.")
    if any(not clean(row.get("Patient_No")) for _, row in meds):
        raise ValueError("Medication record missing Patient_No; cannot link or date-shift safely.")
    if len(all_patients) > config["expected_patients"]:
        raise ValueError("More patients than expected; check the input folder for mixed datasets.")
    medication_patients = {clean(row["Patient_No"]) for _, row in meds}
    coverage_complete = (len(all_patients) == config["expected_patients"]
                         and medication_patients == all_patients)
    if not coverage_complete and not allow_partial:
        raise ValueError(f"Incomplete coverage: {len(all_patients)}/{config['expected_patients']} patients, "
                         f"{len(medication_patients)} with medication records. "
                         "Supply all files or explicitly use --allow-partial for a labelled demonstration.")
    concepts = concept_catalogue(concepts_path)
    mappings = load_mappings(mappings_path, concepts)
    drug_type = require_standard(concepts, int(config["drug_type_concept_id"]), "Type Concept")
    if config["drug_end_date_policy"] != "themis_prescription_30_days" or config["drug_end_date_inference_days"] != 30:
        raise ValueError("Unimplemented end-date policy; do not change its label without implementing it.")
    missing = sorted({mapping_key(row) for _, row in meds} - set(mappings))
    if missing:
        raise ValueError(f"{len(missing)} drug descriptions lack verified mappings. Run inventory and review Athena: {missing}")

    pids = {patient: person_id(key, patient) for patient in all_patients}
    if len(set(pids.values())) != len(pids):
        raise ValueError("Patient ID collision; coordinate a new shared key before any release.")
    visit_records = defaultdict(list)
    for table in tables:
        if table.kind == "visit":
            for row in table.rows:
                visit_records[(clean(row.get("Patient_No")), clean(row.get("Case_No")))].append(row)
    duplicate_visit_rows = 0
    for pair, rows in visit_records.items():
        if len(rows) > 1:
            signatures = {tuple((h, clean(row.get(h))) for h in sorted(row) if not h.startswith("_")) for row in rows}
            if len(signatures) > 1:
                raise ValueError("Conflicting repeated patient/Case_No in visit source; resolve before linking medications.")
            duplicate_visit_rows += len(rows) - 1
    registered_visits = {pair: visit_id(key, *pair) for pair in visit_records if all(pair)}
    if len(set(registered_visits.values())) != len(registered_visits):
        raise ValueError("Visit ID collision.")

    drug_rows, detail_rows, issues, lineage, handoffs = [], [], [], [], []
    fingerprints = Counter()
    simultaneous = defaultdict(list)
    for table, row in meds:
        patient, case = clean(row["Patient_No"]), clean(row.get("Case_No"))
        # Ignore parent-folder layout: selecting the extracted root or its parent
        # must not change order IDs. Repeated basenames for one patient collide
        # deliberately and stop export rather than silently merging source files.
        source_key = f"{table.path.name}::{table.sheet}::{row['_source_row']}"
        did = event_id(key, patient, source_key)
        start = shift_datetime(key, patient, row.get("Order_Creation_Date"), config["date_shift_max_days"])
        end = start.date() + timedelta(days=29)
        mapping = mappings[mapping_key(row)]
        is_drug = mapping["target_domain"] == "Drug"
        flags = ["order_not_administration"]
        if is_drug:
            flags.append("duration_unknown_default_30_days")
        if mapping["mapping_status"] != "mapped":
            flags.append(mapping["mapping_status"])
        value, unit, dose_flags = normalize_dose(row.get("Dosage_Ordered"), row.get("Dosage_Ordered_Unit"))
        flags.extend(dose_flags)
        form_aliases = {"tablet": "tablet", "tablets": "tablet", "tab": "tablet", "tabs": "tablet",
                        "capsule": "capsule", "capsules": "capsule", "cap": "capsule", "caps": "capsule",
                        "inj": "injection", "inf": "infusion", "syrup": "oral_liquid", "mixture": "oral_liquid",
                        "liquid": "liquid", "suspension": "suspension", "suppository": "suppository",
                        "lotion": "lotion", "cream": "cream", "plaster": "plaster", "gargle": "gargle",
                        "ext solution": "external_solution", "inhaler": "inhaler", "evohaler": "inhaler",
                        "nasal spray": "nasal_spray"}
        form_category = form_aliases.get(norm(row.get("Dosage_Form")), "")
        if not form_category:
            flags.append("dose_form_requires_review")
        matching_visit = registered_visits.get((patient, case), "")
        if not matching_visit:
            flags.append("visit_not_linked")
        else:
            source_visit = visit_records[(patient, case)][0]
            visit_start = shift_datetime(key, patient, source_visit["Adm_DateTime"], config["date_shift_max_days"])
            visit_end_raw = source_visit.get("Dis_DateTime")
            if start < visit_start:
                flags.append("order_before_recorded_admission")
            if clean(visit_end_raw):
                visit_end = shift_datetime(key, patient, visit_end_raw, config["date_shift_max_days"])
                if start > visit_end:
                    flags.append("order_after_recorded_discharge")
                if is_drug and end > visit_end.date():
                    flags.append("inferred_end_after_discharge")
        fingerprint = tuple(clean(row.get(h)) for h in sorted(h for h in row if not h.startswith("_")))
        fingerprints[fingerprint] += 1
        if fingerprints[fingerprint] > 1:
            flags.append("exact_duplicate_retained")
        drug = dict.fromkeys(DRUG_COLUMNS, "")
        drug.update({
            "drug_exposure_id": did, "person_id": pids[patient],
            "drug_concept_id": int(mapping["target_concept_id"]),
            "drug_exposure_start_date": start.date().isoformat(),
            "drug_exposure_start_datetime": start.isoformat(sep=" "),
            "drug_exposure_end_date": end.isoformat(),
            "drug_type_concept_id": int(drug_type["concept_id"]),
            "route_concept_id": 0, "visit_occurrence_id": matching_visit,
            "drug_source_value": clean(row.get("Cluster_Preferred_Name_Code")),
            "drug_source_concept_id": 0,
            "dose_unit_source_value": clean(row.get("Dosage_Ordered_Unit")),
        })
        if is_drug:
            drug_rows.append(drug)
        else:
            handoffs.append({"source_order_id": did, "person_id": pids[patient],
                "order_datetime_shifted": start.isoformat(sep=" "), "visit_occurrence_id": matching_visit,
                "source_code": mapping["source_code"], "source_name": source_name(row),
                "source_form": clean(row.get("Dosage_Form")), "target_concept_id": mapping["target_concept_id"],
                "target_concept_name": mapping["target_concept_name"], "target_domain": mapping["target_domain"],
                "mapping_status": mapping["mapping_status"], "reason": mapping["mapping_notes"]})
        text = clean(row.get("Order_Text"))
        modified = any(token in norm(text + " " + source_name(row)).replace("[", " ").replace("]", " ").split()
                       for token in ("sr", "cr", "er", "mr", "xr"))
        modified = modified or any(phrase in norm(text + " " + source_name(row))
                                  for phrase in ("prolonged release", "extended release", "sustained release"))
        detail_rows.append({
            "source_order_id": did, "drug_exposure_id": did if is_drug else "", "person_id": pids[patient],
            "source_code": clean(row.get("Cluster_Preferred_Name_Code")), "source_name": source_name(row),
            "order_text": text, "dose_original": "[invalid Excel date value]" if "dose_excel_date_corruption" in dose_flags else clean(row.get("Dosage_Ordered")),
            "dose_unit_original": clean(row.get("Dosage_Ordered_Unit")),
            "dose_normalized": value, "dose_unit_normalized": unit,
            "dose_form_source": clean(row.get("Dosage_Form")), "dose_form_category": form_category,
            "strength_unit_source": clean(row.get("Strength_Unit")),
            "modified_release_source": "yes" if modified else "not_recorded",
            "mapped_concept_name": mapping["target_concept_name"], "mapping_level": mapping["mapping_level"],
            "end_date_inferred": "yes" if is_drug else "not_applicable", "end_date_policy": config["drug_end_date_policy"] if is_drug else "",
            "actual_duration_known": "no", "component_type": clean(row.get("Component_Type_Code")),
            "component_description": clean(row.get("Component_Type_Description")),
            "mapping_status": mapping["mapping_status"], "target_domain": mapping["target_domain"],
            "target_concept_id": mapping["target_concept_id"], "order_datetime_shifted": start.isoformat(sep=" "),
            "visit_occurrence_id": matching_visit, "flags": ";".join(flags),
        })
        simultaneous[(pids[patient], case, mapping_key(row), start)].append(len(detail_rows) - 1)
        lineage.append({"drug_exposure_id": did, "source_file": table.path.as_posix(),
                        "source_sheet": table.sheet, "source_row": row["_source_row"],
                        "dose_original_private": clean(row.get("Dosage_Ordered"))})

    for indices in simultaneous.values():
        doses = {(detail_rows[i]["dose_normalized"], detail_rows[i]["dose_unit_normalized"]) for i in indices}
        if len(indices) > 1 and len(doses) > 1:
            for i in indices:
                detail_rows[i]["flags"] += ";same_time_different_dose_retained"
    for detail in detail_rows:
        for flag in detail["flags"].split(";"):
            issues.append({"severity": "warning" if flag not in {"order_not_administration"} else "information",
                           "code": flag, "drug_exposure_id": detail["drug_exposure_id"],
                           "person_id": detail["person_id"], "detail": FLAG_EXPLANATIONS.get(flag, flag)})
    if len({row["source_order_id"] for row in detail_rows}) != len(detail_rows):
        raise ValueError("Drug event ID collision or duplicate file identity.")
    if len(drug_rows) + len(handoffs) != len(meds):
        raise ValueError("Input/output record count mismatch.")
    # Prevent source identifiers from slipping back through free text or mappings.
    public_text = json.dumps([drug_rows, detail_rows, issues, handoffs,
                              [mappings[k] for k in {mapping_key(row) for _, row in meds}]],
                             ensure_ascii=False)
    identifiers = all_patients | {clean(row.get("Case_No")) for row in all_rows if clean(row.get("Case_No"))}
    for identifier in identifiers:
        if len(identifier) >= 4 and re.search(r"(?<![A-Za-z0-9])" + re.escape(identifier) + r"(?![A-Za-z0-9])", public_text):
            raise ValueError("Original patient/case identifier found in an export field; review source text before releasing.")

    report = {
        "cdm_version": config["cdm_version"], "expected_patients": config["expected_patients"],
        "id_scheme": ID_SCHEME,
        "patients_in_available_sources": len(all_patients), "patients_with_medication_records": len(medication_patients),
        "coverage_complete": coverage_complete, "all_five_patients_completed": coverage_complete,
        "source_medication_rows": len(meds), "output_drug_exposure_rows": len(drug_rows),
        "unique_source_drug_descriptions": len({mapping_key(row) for _, row in meds}),
        "mapped_drug_rows": sum(int(r["drug_concept_id"]) != 0 for r in drug_rows),
        "unmapped_drug_rows": sum(int(r["drug_concept_id"]) == 0 for r in drug_rows),
        "cross_domain_handoff_rows": len(handoffs), "source_orders_accounted_for": len(detail_rows),
        "handoff_rows_with_standard_device_target": sum(int(r["target_concept_id"]) != 0 for r in handoffs),
        "handoff_rows_awaiting_exact_product_target": sum(int(r["target_concept_id"]) == 0 for r in handoffs),
        "mapping_status_by_unique_description": dict(sorted(Counter(mappings[k]["mapping_status"] for k in {mapping_key(row) for _, row in meds}).items())),
        "all_orders_have_nonzero_target": all(int(r["target_concept_id"]) != 0 for r in detail_rows),
        "rows_dropped": 0, "exact_duplicate_visit_rows_collapsed_in_registry": duplicate_visit_rows,
        "unique_registered_visits": len(registered_visits),
        "checks": {"unique_event_ids": True, "record_count_reconciled": True,
                   "nonzero_drug_concepts_standard_and_verified": True, "shared_person_ids_used": True},
        "warnings_by_code": dict(sorted(Counter(issue["code"] for issue in issues).items())),
        "privacy_status": config["release_status"], "full_anonymity_claimed": False,
        "duration_policy": config["drug_end_date_policy"], "duration_is_observed": False,
        "vocabulary_metadata_sha256": hashlib.sha256(concepts_path.read_bytes()).hexdigest(),
        "mapping_sha256": hashlib.sha256(mappings_path.read_bytes()).hexdigest(),
        "key_fingerprint": hashlib.sha256(key).hexdigest()[:16],
    }
    unlinked_cases = Counter()
    for table in tables:
        if table.kind in {"visit", "person"}:
            continue
        for row in table.rows:
            patient, case = clean(row.get("Patient_No")), clean(row.get("Case_No"))
            if case and (patient, case) not in registered_visits:
                unlinked_cases[(table.kind, patient, case)] += 1
    report["source_rows_with_unlinked_case_by_domain"] = dict(sorted(Counter(
        {kind: sum(n for (k, _, _), n in unlinked_cases.items() if k == kind)
         for kind, _, _ in unlinked_cases}).items()))
    # Never replace successful outputs until every record and mapping has passed.
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="medications-", dir=output_dir.parent) as tmp:
        stage = Path(tmp)
        write_csv(stage / "drug_exposure.csv", DRUG_COLUMNS, drug_rows)
        write_csv(stage / "medication_details.csv", DETAIL_COLUMNS, detail_rows)
        write_csv(stage / "cross_domain_handoff.csv", HANDOFF_COLUMNS, handoffs)
        write_csv(stage / "patient_summary.csv", ["person_id", "source_orders", "drug_exposure_rows", "mapped_drug_rows", "unmapped_drug_rows", "handoff_rows"], [
            {"person_id": pid, "source_orders": sum(r["person_id"] == pid for r in detail_rows),
             "drug_exposure_rows": sum(r["person_id"] == pid for r in drug_rows),
             "mapped_drug_rows": sum(r["person_id"] == pid and int(r["drug_concept_id"]) != 0 for r in drug_rows),
             "unmapped_drug_rows": sum(r["person_id"] == pid and int(r["drug_concept_id"]) == 0 for r in drug_rows),
             "handoff_rows": sum(r["person_id"] == pid for r in handoffs)} for pid in sorted(pids.values())])
        write_csv(stage / "quality_issues.csv", ISSUE_COLUMNS, issues)
        used_keys = {mapping_key(row) for _, row in meds}
        write_csv(stage / "medication_mapping.csv", MAPPING_COLUMNS,
                  [mappings[k] for k in sorted(used_keys)])
        (stage / "quality_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        output_dir.mkdir(parents=True, exist_ok=True)
        for file in stage.iterdir():
            shutil.copy2(file, output_dir / file.name)

    private_dir.mkdir(parents=True, exist_ok=True)
    write_csv(private_dir / "person_registry.csv", ["Patient_No", "person_id", "date_offset_days"], [
        {"Patient_No": patient, "person_id": pids[patient],
         "date_offset_days": date_offset(key, patient, config["date_shift_max_days"])}
        for patient in sorted(all_patients)])
    write_csv(private_dir / "visit_registry.csv", ["Patient_No", "Case_No", "person_id", "visit_occurrence_id"], [
        {"Patient_No": patient, "Case_No": case, "person_id": pids[patient], "visit_occurrence_id": vid}
        for (patient, case), vid in sorted(registered_visits.items())])
    write_csv(private_dir / "drug_lineage.csv", ["drug_exposure_id", "source_file", "source_sheet", "source_row", "dose_original_private"], lineage)
    write_csv(private_dir / "unlinked_source_cases.csv", ["domain", "Patient_No", "Case_No", "source_row_count"], [
        {"domain": kind, "Patient_No": patient, "Case_No": case, "source_row_count": count}
        for (kind, patient, case), count in sorted(unlinked_cases.items())])
    for file in private_dir.glob("*.csv"):
        file.chmod(0o600)
    return report


FLAG_EXPLANATIONS = {
    "order_not_administration": "Source is an order, not evidence that a dose was administered.",
    "duration_unknown_default_30_days": "End date is inferred as start + 29 days; actual duration is unknown.",
    "visit_not_linked": "No exact patient/Case_No match in the available visit source; FK left blank.",
    "order_before_recorded_admission": "Order precedes admission time; source chronology retained.",
    "order_after_recorded_discharge": "Order follows discharge time; source chronology retained.",
    "inferred_end_after_discharge": "Default duration extends beyond discharge; not evidence of continued use.",
    "same_time_different_dose_retained": "Different doses at the same time are retained; no order status supports merging or cancellation.",
    "exact_duplicate_retained": "Identical source record retained pending source-level reconciliation.",
    "missing_dose": "No dose was supplied; no value imputed.",
    "non_numeric_dose": "Dose could not be converted to a number; original value retained.",
    "invalid_dose": "Negative or non-finite dose; original value retained for review.",
    "unit_not_mass_standardized": "No safe mass conversion is available; original unit retained.",
    "dose_form_requires_review": "Source form is missing or outside the reviewed categories; original form retained.",
    "dose_excel_date_corruption": "Excel supplied a date in the dose cell; no numerical dose reconstructed.",
    "dose_range_retained": "A dose/rate range is retained as a range; no scalar or weight imputed.",
    "volume_only_not_mass": "Litres converted to mL; volume is not mass or ingredient dose.",
    "reviewed_unmapped": "Reviewed drug remains concept 0 because its product composition is ambiguous.",
    "cross_domain_handoff": "Order retained in cross_domain_handoff; no Device concept inserted into DRUG_EXPOSURE.",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init-key", help="Generate the group key once; share it securely with group members.")
    init.add_argument("--key-file", type=Path, default=Path("private/group_key.hex"))
    inv = commands.add_parser("inventory", help="Produce a source-drug mapping worksheet as CSV.")
    inv.add_argument("--input", type=Path, required=True)
    inv.add_argument("--output", type=Path, default=Path("private/medication_mapping_to_review.csv"))
    run = commands.add_parser("run", help="Validate then transform medication orders.")
    run.add_argument("--input", type=Path, required=True)
    run.add_argument("--output", type=Path, default=Path("outputs/medications"))
    run.add_argument("--private-dir", type=Path, default=Path("private"))
    run.add_argument("--key-file", type=Path, default=Path("private/group_key.hex"))
    run.add_argument("--config", type=Path, default=ROOT / "config/project.json")
    run.add_argument("--mapping", type=Path, default=ROOT / "mappings/medications.csv")
    run.add_argument("--concepts", type=Path, default=ROOT / "mappings/concepts_verified.csv")
    run.add_argument("--allow-partial", action="store_true", help="Explicitly label an incomplete-patient demonstration.")
    args = parser.parse_args(argv)
    try:
        if args.command == "init-key":
            load_key(args.key_file, create=True)
            print("Group key is ready. Keep this file private and reuse it for every domain.")
        elif args.command == "inventory":
            rows = inventory(discover(args.input))
            write_csv(args.output, MAPPING_COLUMNS, rows)
            print(f"Wrote {len(rows)} unique drug descriptions for review.")
        else:
            config = json.loads(args.config.read_text(encoding="utf-8"))
            report = run_etl(args.input, args.output, args.private_dir, load_key(args.key_file),
                             config, args.mapping, args.concepts, args.allow_partial)
            print(json.dumps(report, indent=2))
    except (ValueError, KeyError, OSError) as error:
        parser.exit(2, f"ETL stopped: {error}\n")
    return 0
