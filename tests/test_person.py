"""Anonymisation + PERSON/DEATH checks using invented fixtures, not the coursework data."""
from datetime import datetime, timedelta
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bmi5207.person import DEATH_COLUMNS, PERSON_COLUMNS, run_person_etl
from bmi5207.shared import date_offset, person_id, read_csv, write_csv


class PersonETLTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.input = self.root / "input"
        self.input.mkdir()
        self.key = b"P" * 32
        self.config = {"cdm_version": "5.4", "expected_patients": 5, "date_shift_max_days": 180,
                       "death_type_concept_id": 9100, "death_year_impute_month_day": "07-01",
                       "top_code_age": 90, "release_status": "synthetic_test"}
        # Fictional concept IDs: tests do not claim Athena provenance.
        self.concepts = self.root / "concepts.csv"
        cols = ["concept_id", "concept_name", "domain_id", "vocabulary_id", "concept_class_id",
                "standard_concept", "invalid_reason"]
        write_csv(self.concepts, cols, [
            {"concept_id": 9001, "concept_name": "fixture male", "domain_id": "Gender", "vocabulary_id": "Gender",
             "concept_class_id": "Gender", "standard_concept": "S", "invalid_reason": ""},
            {"concept_id": 9002, "concept_name": "fixture female", "domain_id": "Gender", "vocabulary_id": "Gender",
             "concept_class_id": "Gender", "standard_concept": "S", "invalid_reason": ""},
            {"concept_id": 9003, "concept_name": "fixture race", "domain_id": "Race", "vocabulary_id": "Race",
             "concept_class_id": "Race", "standard_concept": "S", "invalid_reason": ""},
            {"concept_id": 9100, "concept_name": "fixture EHR", "domain_id": "Type Concept",
             "vocabulary_id": "Type Concept", "concept_class_id": "Type Concept", "standard_concept": "S",
             "invalid_reason": ""},
        ])
        self.mapping = self.root / "demographics.csv"
        write_csv(self.mapping, ["field", "source_value", "target_concept_id", "target_concept_name", "mapping_notes"], [
            {"field": "gender", "source_value": "Male", "target_concept_id": 9001, "target_concept_name": "m", "mapping_notes": ""},
            {"field": "gender", "source_value": "Female", "target_concept_id": 9002, "target_concept_name": "f", "mapping_notes": ""},
            {"field": "race", "source_value": "Chinese", "target_concept_id": 9003, "target_concept_name": "r", "mapping_notes": ""},
            {"field": "ethnicity", "source_value": "", "target_concept_id": 0, "target_concept_name": "", "mapping_notes": ""},
        ])

    def tearDown(self):
        self.tmp.cleanup()

    def fixture(self, patients=5, race="Chinese", yob=1960, leak=False):
        demo, visit, lab, med, proc = [], [], [], [], []
        for i in range(patients):
            p, case, lab_case = f"PRIVATE-PATIENT-{i}", f"PRIVATE-CASE-{i}", f"PRIVATE-LABCASE-{i}"
            demo.append({"Patient_No": p, "Patient_DOB": yob, "Religion": "Secret", "Race": race,
                         "Gender": "Male" if i % 2 else "Female", "Marital_Status": "Secret",
                         "Deceased_Ind": "True" if i == 0 else "False", "Death_Date": 2017 if i == 0 else ""})
            visit.append({"Case_No": case, "Adm_DateTime": "2016-12-20 10:00:00", "Dis_DateTime": "2016-12-28 09:30:00",
                          "Dis_DateTime_Planned": "", "Adm_Physical_Class_Desc": "B1 Class Bed", "LOS_Days": 8,
                          "Patient_No": p})
            lab.append({"Case_No": lab_case, "Test_Code": "NA", "Test_Result": 140,
                        "Result_Test_Date": "2016-12-19 23:00:00",
                        "Short_Text": p if leak else "Sodium", "Patient_No": p})
            med.append({"Case_No": case, "Order_Text": "free text", "Order_Creation_Date": "2016-12-20 11:00:00",
                        "Dosage_Ordered": "10", "Patient_No": p})
            proc.append({"Surgical_Code": "XX000", "Surgical_Desc": "Fixture", "Case_No": case, "Patient_No": p,
                         "operation_date": "2016-12-21 08:00:00"})
        for name, rows in (("demo.csv", demo), ("visit.csv", visit), ("lab.csv", lab), ("med.csv", med), ("proc.csv", proc)):
            write_csv(self.input / name, list(rows[0]), rows)

    def run_etl(self, key=None, private=None):
        return run_person_etl(self.input, self.root / "out/person", self.root / "out/anon",
                              private or self.root / "private", key or self.key, self.config,
                              self.mapping, self.concepts)

    def test_person_death_ids_dates_and_suppression(self):
        self.fixture()
        report = self.run_etl()
        person = read_csv(self.root / "out/person/person.csv")
        death = read_csv(self.root / "out/person/death.csv")
        self.assertEqual(list(person[0]), PERSON_COLUMNS)
        self.assertEqual(list(death[0]), DEATH_COLUMNS)
        self.assertEqual(len(person), 5)
        self.assertEqual({r["person_id"] for r in person},
                         {str(person_id(self.key, f"PRIVATE-PATIENT-{i}")) for i in range(5)})
        self.assertTrue(all(r["month_of_birth"] == r["day_of_birth"] == r["birth_datetime"] == "" for r in person))
        self.assertEqual(len(death), 1)
        self.assertTrue(death[0]["death_date"].startswith("2017-"), "death year must be preserved")
        # Every output file: no raw identifiers, no suppressed fields
        for f in list((self.root / "out").rglob("*.csv")):
            text = f.read_text()
            self.assertNotIn("PRIVATE-", text)
            self.assertNotIn("Secret", text)
            self.assertNotIn("B1 Class Bed", text)
            self.assertNotIn("free text", text)
        # Shared per-patient offset applied; intervals preserved
        visit = read_csv(self.root / "out/anon/visit_anonymised.csv")
        p0 = str(person_id(self.key, "PRIVATE-PATIENT-0"))
        row = next(r for r in visit if r["person_id"] == p0)
        expected = datetime(2016, 12, 20, 10) + timedelta(days=date_offset(self.key, "PRIVATE-PATIENT-0"))
        self.assertEqual(row["Adm_DateTime"], expected.strftime("%Y-%m-%d %H:%M:%S"))
        los = datetime.fromisoformat(row["Dis_DateTime"]) - datetime.fromisoformat(row["Adm_DateTime"])
        self.assertEqual(los, timedelta(days=7, hours=23, minutes=30))
        # Lab Case_No absent from visit source: FK blank, but grouped by case_group_id
        lab = read_csv(self.root / "out/anon/lab_results_anonymised.csv")
        self.assertTrue(all(r["visit_occurrence_id"] == "" and r["case_group_id"] for r in lab))
        self.assertEqual(report["unique_cases_by_source"]["only_in_other_domains_fk_left_blank"], 5)

    def test_unreviewed_demographic_value_stops(self):
        self.fixture(race="Unreviewed")
        with self.assertRaisesRegex(ValueError, "Unreviewed demographic value"):
            self.run_etl()

    def test_identifier_in_free_text_stops_release(self):
        self.fixture(leak=True)
        with self.assertRaisesRegex(ValueError, "Source identifier found"):
            self.run_etl()

    def test_partial_dataset_stops(self):
        self.fixture(patients=4)
        with self.assertRaisesRegex(ValueError, "Expected 5 patients"):
            self.run_etl()

    def test_age_is_top_coded(self):
        self.fixture(yob=1920)
        report = self.run_etl()
        person = read_csv(self.root / "out/person/person.csv")
        self.assertTrue(all(int(r["year_of_birth"]) >= 1925 for r in person))
        self.assertEqual(report["flags"]["age_top_coded"], 5)

    def test_registry_from_a_different_key_is_not_overwritten(self):
        self.fixture()
        self.run_etl()
        with self.assertRaisesRegex(ValueError, "disagrees with this run"):
            self.run_etl(key=b"Q" * 32)


if __name__ == "__main__":
    unittest.main()
