# Person 4 presentation notes

The complete group has 10 minutes plus 5 minutes for Q&A. Suggested Person 4 share:
about 2 minutes, using 2–3 slides; this is not a demand to use all 10 minutes.

## Slide 1 — task and shared design (about 30 s)

- Five patients, 170 medication orders, 74 source descriptions.
- Shared HMAC person/visit IDs and one date shift per patient preserve linkage.
- Medication orders mapped into CDM 5.4; missing facts are not fabricated.

Suggested speech:
“I processed all five patients' medication orders using shared pseudonymous IDs
and consistent patient-level date shifts. I kept the orders traceable while
separating their source meaning from what the CDM actually asserts.”

## Slide 2 — examples (about 50 s)

Show a source drug description beside its standard concept, not original patient
IDs or real clinical dates. Suitable examples: co-amoxiclav 500/125 mg → 1713694;
potassium chloride SR → 40075734; tamsulosin prolonged release → 40130136.
Explain that 1.2 g ordered dose becomes 1200 mg in a companion field, not quantity.
A second example can show the insulin Excel-date anomaly and missing normalized
dose; this is stronger evidence of careful cleaning than a 100% mapping claim.

Suggested speech:
“Where the product label gave strength and form, I used a Clinical Drug. Where it
gave only a tablet form, I used a Clinical Drug Form. I retained both ingredients
of combination products and preserved modified release. I never inferred product
strength from the dose ordered.”

## Slide 3 — actual reconciliation and limitations (about 40 s)

170 source orders = 158 DRUG_EXPOSURE rows + 12 cross-domain handoffs.
Of the Drug rows, 152 have verified Standard targets and six use reviewed concept
0. Nine handoffs have Standard Device targets and three need product clarification.
No rows dropped. Fourteen unit tests and actual-output reconciliation pass.

Suggested speech:
“Some nutrition, skin-care and blood products belong to the Device domain. I
retained those orders in an explicit handoff rather than putting Device concepts
in the Drug table. Uncertain product composition remains concept zero. These are
orders, not confirmed administrations, and the default end date is an assumption.
Pseudonymisation and date shifting also do not establish complete anonymity.”

## Prepare for Q&A

Use the detailed Chinese guide for AES/HMAC, k-anonymity, date utility,
concept hierarchy, unresolved mapping, duplicates and duration questions.
Avoid claiming that 170 rows means 170 patients, 100% standard mapping, real
30-day use, complete anonymisation, or a full integrated CDM database.
