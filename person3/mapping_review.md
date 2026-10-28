# Mapping review / release blockers

1. The source laboratory workbooks have no explicit unit or specimen column. Athena LOINC concepts cannot be selected reliably solely from test name when multiple specimens or measurement properties exist. Keep missing IDs blank until supported by source evidence.
2. Athena must verify concept_id, domain_id=Measurement, standard_concept=S, validity=Valid, and the specific specimen/property/method. Some lab results may belong to Observation rather than Measurement; handle them separately if Athena confirms that domain.
3. For qualitative results (Positive, Non-Reactive, ABO blood group, etc.), map value_as_concept_id using verified standard concepts. For results such as <2.0, map operator_concept_id before claiming complete OMOP conversion.
4. The current script uses measurement_type_concept_id=0 as a **review placeholder**; replace with a verified appropriate standard type concept before final delivery.
5. Source Case_No values in labs do not match exact visits; visit_occurrence_id must remain blank unless group verifies true source linkage.
6. Raw files, group key and any patient-level outputs stay private; GitHub public repo gets only code, mapping review, and non-identifying aggregate counts.
