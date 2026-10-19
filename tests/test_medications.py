"""Behavioural checks using invented fixtures, not the coursework patient data."""
from datetime import datetime
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bmi5207.medications import DRUG_COLUMNS, normalize_dose, run_etl
from bmi5207.shared import date_offset, person_id, read_csv, shift_datetime, visit_id, write_csv


class SharedRulesTests(unittest.TestCase):
    def test_cross_domain_identity_and_nonzero_patient_shift(self):
        key = b"T" * 32
        self.assertEqual(person_id(key, "EXAMPLE-PATIENT"), person_id(key, "EXAMPLE-PATIENT"))
        self.assertNotEqual(person_id(key, "EXAMPLE-PATIENT"), person_id(b"Z" * 32, "EXAMPLE-PATIENT"))
        self.assertNotEqual(visit_id(key, "PATIENT-A", "CASE-A"), visit_id(key, "PATIENT-B", "CASE-A"))
        for i in range(100):
            self.assertIn(date_offset(key, str(i)), list(range(-180, 0)) + list(range(1, 181)))
        before = shift_datetime(key, "EXAMPLE-PATIENT", "2020-02-28 22:00:00")
        after = shift_datetime(key, "EXAMPLE-PATIENT", "2020-03-01 22:00:00")
        self.assertEqual((after - before).total_seconds(), 2 * 24 * 3600)

    def test_mass_conversion_is_not_a_strength_or_tablet_count(self):
        self.assertEqual(normalize_dose(1.2, "g"), ("1200", "mg", []))
        self.assertEqual(normalize_dose(500, "mcg"), ("0.5", "mg", []))
        self.assertEqual(normalize_dose(0, "mg"), ("0", "mg", []))
        self.assertEqual(normalize_dose(5, "mL"), ("5", "mL", ["unit_not_mass_standardized"]))
        self.assertEqual(normalize_dose(None, "mg")[2], ["missing_dose"])
        self.assertEqual(normalize_dose(-1, "mg")[2], ["invalid_dose"])

    def test_range_volume_and_corrupt_excel_dose(self):
        self.assertEqual(normalize_dose("0 - 2", "mcg/kg/min"),
                         ("0 - 2", "mcg/kg/min", ["dose_range_retained", "unit_not_mass_standardized"]))
        self.assertEqual(normalize_dose(datetime(2022, 7, 3), "unit"),
                         ("", "", ["dose_excel_date_corruption"]))
        self.assertEqual(normalize_dose("2022-07-03 00:00:00", "unit")[0], "")
        self.assertEqual(normalize_dose(1.5, "Litre"), ("1500.0", "mL", ["volume_only_not_mass"]))
        self.assertTrue(0 < person_id(b"A" * 32, "fixture") <= 2**31 - 1)


class MedicationETLTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.input = self.root / "input"
        self.input.mkdir()
        self.output = self.root / "output"
        self.private = self.root / "private"
        self.key = b"F" * 32
        self.config = {"cdm_version": "5.4", "expected_patients": 5, "date_shift_max_days": 180,
                       "drug_type_concept_id": 9001, "drug_end_date_policy": "themis_prescription_30_days",
                       "drug_end_date_inference_days": 30, "release_status": "synthetic_test"}
        # Fictional concept IDs in tests deliberately do not claim Athena provenance.
        self.concepts = self.root / "concepts.csv"
        self.catalogue = [
            {"concept_id": 101, "concept_name": "fixture ingredient", "domain_id": "Drug", "vocabulary_id": "RxNorm",
             "concept_class_id": "Ingredient", "standard_concept": "S", "invalid_reason": ""},
            {"concept_id": 9001, "concept_name": "fixture order type", "domain_id": "Type Concept", "vocabulary_id": "Type Concept",
             "concept_class_id": "Type Concept", "standard_concept": "S", "invalid_reason": ""},
        ]
        self.save_catalogue()
        self.mapping = self.root / "mapping.csv"
        write_csv(self.mapping, ["source_code", "source_name", "source_form", "target_concept_id", "target_concept_name", "mapping_level", "mapping_notes"],
                  [{"source_code": "DRUG-EXAMPLE", "source_name": "Fixture Drug", "source_form": "Tablet", "target_concept_id": 101,
                    "target_concept_name": "fixture ingredient", "mapping_level": "Ingredient", "mapping_notes": "No source product strength."}])

    def tearDown(self):
        self.tmp.cleanup()

    def save_catalogue(self):
        write_csv(self.concepts, list(self.catalogue[0]), self.catalogue)

    def fixture(self, patients=5, duplicate_dose=False, leak_identifier=False):
        meds, visits = [], []
        for i in range(patients):
            patient, case = f"PRIVATE-PATIENT-{i}", f"PRIVATE-CASE-{i}"
            med = {"Patient_No": patient, "Case_No": case, "Order_Text": patient if leak_identifier else "Fixture Drug",
                   "Order_Creation_Date": "2020-01-10 09:00:00", "Cluster_Preferred_Name_Code": "DRUG-EXAMPLE",
                   "Cluster_Preferred_Name_Description": "Fixture Drug", "Dosage_Form": "Tablet",
                   "Dosage_Ordered": 1.2, "Dosage_Ordered_Unit": "g", "Strength_Unit": "mg"}
            meds.append(med)
            if duplicate_dose and i == 0:
                meds.append({**med, "Dosage_Ordered": 0.6})
            visits.append({"Patient_No": patient, "Case_No": case, "Adm_DateTime": "2020-01-10 10:00:00",
                           "Dis_DateTime": "2020-01-12 10:00:00"})
        write_csv(self.input / "meds.csv", list(meds[0]), meds)
        write_csv(self.input / "visits.csv", list(visits[0]), visits)

    def run_pipeline(self, allow_partial=False):
        return run_etl(self.input, self.output, self.private, self.key, self.config,
                       self.mapping, self.concepts, allow_partial)

    def test_five_patient_counts_linkage_and_no_fabricated_quantity(self):
        self.fixture()
        report = self.run_pipeline()
        self.assertTrue(report["all_five_patients_completed"])
        rows = read_csv(self.output / "drug_exposure.csv")
        self.assertEqual(len(rows), 5)
        self.assertEqual(list(rows[0]), DRUG_COLUMNS)
        self.assertEqual(len({r["person_id"] for r in rows}), 5)
        for row in rows:
            self.assertEqual(row["quantity"], "")
            self.assertEqual(row["days_supply"], "")
            self.assertEqual(row["sig"], "")
            self.assertEqual(row["route_concept_id"], "0")
            self.assertTrue(row["visit_occurrence_id"])
            self.assertEqual((datetime.fromisoformat(row["drug_exposure_end_date"]) - datetime.fromisoformat(row["drug_exposure_start_date"])).days, 29)
        public = "".join(p.read_text() for p in self.output.iterdir())
        self.assertNotIn("PRIVATE-PATIENT", public)
        self.assertNotIn("PRIVATE-CASE", public)
        details = read_csv(self.output / "medication_details.csv")
        self.assertEqual({r["dose_normalized"] for r in details}, {"1200"})
        self.assertEqual(report["warnings_by_code"]["order_before_recorded_admission"], 5)
        self.assertFalse(report["duration_is_observed"])

    def test_partial_dataset_cannot_masquerade_as_complete(self):
        self.fixture(patients=1)
        with self.assertRaisesRegex(ValueError, "Incomplete coverage"):
            self.run_pipeline()
        self.assertFalse(self.output.exists())
        report = self.run_pipeline(allow_partial=True)
        self.assertFalse(report["all_five_patients_completed"])
        self.assertEqual(report["patients_in_available_sources"], 1)

    def test_simultaneous_different_doses_retained_and_flagged(self):
        self.fixture(duplicate_dose=True)
        report = self.run_pipeline()
        self.assertEqual(report["output_drug_exposure_rows"], 6)
        self.assertEqual(report["warnings_by_code"]["same_time_different_dose_retained"], 2)

    def test_nonstandard_or_unmapped_concept_stops_export(self):
        self.fixture()
        self.catalogue[0]["standard_concept"] = ""
        self.save_catalogue()
        with self.assertRaisesRegex(ValueError, "not a Standard"):
            self.run_pipeline()
        self.assertFalse(self.output.exists())
        self.catalogue[0]["standard_concept"] = "S"
        self.save_catalogue()
        self.mapping.write_text(self.mapping.read_text().replace("DRUG-EXAMPLE", "OTHER-CODE"))
        with self.assertRaisesRegex(ValueError, "lack verified mappings"):
            self.run_pipeline()

    def test_identifier_in_free_text_stops_release(self):
        self.fixture(leak_identifier=True)
        with self.assertRaisesRegex(ValueError, "identifier found"):
            self.run_pipeline()
        self.assertFalse(self.output.exists())

    def test_missing_visit_is_not_assigned_to_some_other_visit(self):
        self.fixture()
        visits = read_csv(self.input / "visits.csv")
        visits[0]["Case_No"] = "DIFFERENT-PRIVATE-CASE"
        write_csv(self.input / "visits.csv", list(visits[0]), visits)
        report = self.run_pipeline()
        rows = read_csv(self.output / "drug_exposure.csv")
        self.assertEqual(sum(row["visit_occurrence_id"] == "" for row in rows), 1)
        self.assertEqual(report["warnings_by_code"]["visit_not_linked"], 1)

    def test_identical_visit_duplicates_collapse_but_conflicts_stop(self):
        self.fixture()
        visits = read_csv(self.input / "visits.csv")
        visits.append(dict(visits[0]))
        write_csv(self.input / "visits.csv", list(visits[0]), visits)
        report = self.run_pipeline()
        self.assertEqual(report["exact_duplicate_visit_rows_collapsed_in_registry"], 1)
        self.assertEqual(report["unique_registered_visits"], 5)
        visits[-1]["Dis_DateTime"] = "2020-01-13 10:00:00"
        write_csv(self.input / "visits.csv", list(visits[0]), visits)
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            self.run_pipeline()

    def test_device_standard_never_enters_drug_exposure(self):
        self.fixture()
        self.catalogue[0].update(domain_id="Device", vocabulary_id="dm+d", concept_class_id="VMP")
        self.save_catalogue()
        mappings = read_csv(self.mapping)
        mappings[0].update(target_domain="Device", mapping_status="cross_domain_handoff", mapping_level="VMP")
        write_csv(self.mapping, list(mappings[0]), mappings)
        report = self.run_pipeline()
        self.assertEqual(report["output_drug_exposure_rows"], 0)
        self.assertEqual(report["cross_domain_handoff_rows"], 5)
        self.assertEqual(len(read_csv(self.output / "medication_details.csv")), 5)
        self.assertEqual(len(read_csv(self.output / "cross_domain_handoff.csv")), 5)

    def test_unmapped_requires_explicit_review_and_accounts_for_every_order(self):
        self.fixture()
        mappings = read_csv(self.mapping)
        mappings[0].update(target_concept_id=0, target_concept_name="", mapping_level="Unmapped",
                           mapping_status="reviewed_unmapped", target_domain="Drug",
                           mapping_notes="Insufficient composition evidence; no single ingredient substituted.")
        write_csv(self.mapping, list(mappings[0]), mappings)
        report = self.run_pipeline()
        self.assertEqual(report["unmapped_drug_rows"], 5)
        self.assertEqual(report["mapped_drug_rows"], 0)
        self.assertEqual(report["source_orders_accounted_for"], 5)
        mappings[0]["mapping_status"] = "mapped"
        write_csv(self.mapping, list(mappings[0]), mappings)
        with self.assertRaisesRegex(ValueError, "explicit reviewed exception"):
            self.run_pipeline()

    def test_combination_product_and_component_role_survive(self):
        self.fixture()
        self.catalogue[0].update(concept_name="fixture A / fixture B Oral Tablet", concept_class_id="Clinical Drug Form")
        self.save_catalogue()
        mappings = read_csv(self.mapping)
        mappings[0].update(target_concept_name=self.catalogue[0]["concept_name"], mapping_level="Clinical Drug Form")
        write_csv(self.mapping, list(mappings[0]), mappings)
        meds = read_csv(self.input / "meds.csv")
        for med in meds:
            med["Component_Type_Code"] = "DIL"
            med["Component_Type_Description"] = "Diluent"
        write_csv(self.input / "meds.csv", list(meds[0]), meds)
        report = self.run_pipeline()
        self.assertEqual(report["output_drug_exposure_rows"], 5)
        details = read_csv(self.output / "medication_details.csv")
        self.assertTrue(all("fixture A / fixture B" in r["mapped_concept_name"] and r["component_type"] == "DIL" for r in details))

    def test_input_parent_folder_does_not_change_order_ids(self):
        self.fixture()
        self.run_pipeline()
        first = read_csv(self.output / "medication_details.csv")
        nested = self.input / "nested"
        nested.mkdir()
        (self.input / "meds.csv").rename(nested / "meds.csv")
        self.run_pipeline()
        self.assertEqual(first, read_csv(self.output / "medication_details.csv"))
