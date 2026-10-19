# Person 4 methods — full five-patient run

## Scope and reconciliation

Read 25 Excel tables across the five supplied patient folders without modifying
originals. Inventory: PERSON source 5 rows; visits 22; labs 162; procedures 7;
medication orders 170. Non-medication sources support coverage/linkage checks;
this contribution does not implement the other members' domain transformations.

The medication source has 74 distinct `(code, preferred name, dosage form)` keys.
Code alone is insufficient: potassium citrate has both tablet and mixture forms.
Source preferred name takes priority over order text, which is absent on some
fluid/diluent components. MED, FLD and DIL are retained as distinct source roles.

All 170 orders appear in the ledger: 158 Drug rows and 12 Device-domain handoffs.
Six Drug rows remain concept 0 after review. Three Device handoffs also remain
without an exact product target. No records were dropped to improve mapping rate.

## Mapping

Athena's rendered public results were reviewed on 2026-10-19 for Standard status,
validity, domain, vocabulary, concept class, ID and name. The catalogue is a small
verification snapshot, **not** a downloaded vocabulary release or a complete
CONCEPT/DRUG_STRENGTH/CONCEPT_RELATIONSHIP database.

Use Clinical Drug where source label supplies ingredients, strength and form;
Clinical Drug Form when strength is absent; Ingredient when the form itself is
insufficiently specific. Ordered dose is not used to infer product strength.
Brand text is preserved without assigning an unsupported branded pack. Combination
products retain all their ingredients. RxNorm Extension is used for supported
non-US products not available at that granularity in RxNorm.

Examples: co-amoxiclav 500/125 mg → 1713694; piperacillin/tazobactam 4000/500 mg →
46275444; pholcodine/bromhexine 15/12 mg per 15 mL → 43262567 (1/0.8 mg/mL).
Potassium chloride SR and tamsulosin prolonged-release use their extended-release
forms. A generic tablet is not assigned a strength merely because its order is
5 mg; the order could represent fractions or multiple units.

The glyceryl trinitrate/nitroglycerin synonym and source salt-to-active mappings
have separate evidence files. The earlier ingredient-level mappings were replaced
where the full source supports a more specific form/product. The rejected dm+d
mapping to `glyceryl` remains documented as an example of why textual and semantic
review must accompany automatic relationships.

Mylocaine suspension conflicts with Athena's topical-solution brand candidates;
Sangobion's complete compound formula is not supplied; Lynae calcium/vitamin D
lacks a calcium salt/equivalent complete standard product. These three descriptions
remain reviewed-unmapped, never replaced by just one ingredient.

Creams, wash, nutrition and fresh frozen plasma can be Standard Device-domain
products. Nine handoff rows have such targets. Glucerna lacks the package/energy
specification needed to select available candidates; Resource Plus is not silently
replaced by Resource Energy/Protein/Shake. Those three rows retain target 0.
The order does not prove a device was used or plasma transfused.

## Privacy and shared keys

Shared rules are implemented in `shared.py`: secret-key HMAC-SHA256 with separated
person, visit, medication-event and date-shift namespaces. IDs fit signed 31-bit
INTEGER; collisions stop export. This v2 scheme replaces the prototype's 63-bit
IDs; all group members must regenerate using this version and the same key.

One nonzero offset in [-180,-1] or [1,180] days is reused for every exact clinical
timestamp of a person. Within-person intervals/time of day are preserved; absolute
calendar dates, seasonal interpretation and between-person timing are distorted.
Original IDs, cases, offsets, filenames and linkage material remain private.
The known-identifier scan is not a general PHI detector.

## Dates, doses and missingness

Source provenance is an EHR order: Standard type 32838, EHR prescription. The older
38000177 Prescription written is Non-standard and is not used.

No stop date, duration, supply, frequency or total dispensed quantity is given.
THEMIS permits a written-prescription fallback end = start + 29 days; the exporter
uses this consistently, leaves verbatim end and end datetime empty, and flags
all 158 inferred ends. All extend beyond the recorded discharge dates. This is a
schema convention, not observed 30-day treatment, and is unsuitable for unqualified
continuous-use or adherence analyses. Administration data would instead support
same-day end or a real infusion stop time. Do not change order provenance to pretend
these are administrations.

Dose details remain outside the 23-column DRUG_EXPOSURE schema. Only supported
mass conversions (g/microgram to mg) and litre-to-mL volume conversions are made.
No conversion of mL, mmol, units, tablets, puffs or weight-based rates to mass is
attempted without the needed product/weight data. An insulin dose cell stored as
an Excel date is flagged, with normalized value missing; the private audit retains
the actual cell value. Norepinephrine's 0–2 mcg/kg/min stays a range.

Unknown standard concepts use 0 with a review status; unknown scalar values remain
empty. A genuine recorded numeric dose 0 remains 0. Quantity is not the ordered
mass dose, and strength unit alone is not a concentration.

## Data quality and integration

One exact repeated visit row is collapsed only in the shared registry (22 → 21).
Conflicting visits with the same patient/case stop processing. All medication rows
link to a source visit by exact patient/case. All 162 lab source rows have case
numbers absent from the visit source; this is reported to the lab/visit owners,
not repaired by a fuzzy date join.

Seventeen additional exact duplicate medication rows and 22 rows in same-time,
different-dose groups are retained/flagged. A drug name is not a unique order key.
There is no order status, parent-order ID or cancellation history to justify
merging, summing doses, deleting or choosing the last record. Seven DIL components
must not be mistaken for seven additional administrations of the active drug.

Fourteen invented-fixture tests exercise ranges, corruption, combination retention,
component roles, cross-domain routing, reviewed concept 0, duplicates, leakage,
coverage and stable identity. `validate_outputs.py` additionally reconciles the
actual outputs against private registries and vocabulary metadata. No full DQD or
completed foreign-key check against other members' not-yet-produced CDM tables is
claimed.

## References

- OMOP CDM 5.4: https://ohdsi.github.io/CommonDataModel/cdm54.html
- THEMIS end-date convention: https://ohdsi.github.io/Themis/drug_end_date_not_in_data.html
- Athena: https://athena.ohdsi.org/ ; exact concept links in the metadata CSV.
- Baxter compound sodium lactate SmPC: https://www.medicines.org.uk/emc/product/1812/smpc
