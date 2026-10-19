# Full five-patient medication validation

Prepared 2026-10-19. Supersedes the one-patient prototype.

| Source patient order | Source orders | Drug rows | Standard Drug | Drug concept 0 | Device handoff |
|---|---:|---:|---:|---:|---:|
| 1 | 13 | 12 | 11 | 1 | 1 |
| 2 | 12 | 12 | 12 | 0 | 0 |
| 3 | 1 | 1 | 1 | 0 | 0 |
| 4 | 103 | 94 | 94 | 0 | 9 |
| 5 | 41 | 39 | 34 | 5 | 2 |
| Total | **170** | **158** | **152** | **6** | **12** |

170 = 158 + 12; no order dropped. Of 74 source descriptions, 63 map to Standard
Drug concepts, three remain reviewed-unmapped, eight are Device-domain handoffs.
Drug nonzero concept coverage: 152/158 = 96.2%; this is not mapping accuracy.
Nine Device handoff rows have verified targets; three await an exact product.

## Unresolved products

- Mylocaine suspension: one Drug row; conflicts with Athena topical-solution brand.
- Ferrous gluconate compound/Sangobion: three Drug rows; complete formula unavailable.
- Lynae calcium/vitamin D: two Drug rows; calcium salt/equivalent complete product unclear.
- Glucerna: two Device handoffs; source lacks candidate-discriminating specification.
- Resource Plus chocolate: one Device handoff; other Resource formulations not substituted.

Every unresolved row retains source information and a review reason. Product
clarification or a curated local formulary is needed to resolve these targets.

## Actual quality findings

- Two insulin doses are Excel dates: normalized dose missing, no reconstructed range.
- One norepinephrine order has a 0–2 mcg/kg/min range; retained as a range.
- Seventeen additional exact duplicate medication rows retained/flagged.
- Twenty-two rows affected by same-time/different-dose groups retained/flagged.
- Twenty orders precede recorded admission; chronology is not silently altered.
- All 158 end dates inferred by written-prescription fallback; all exceed discharge.
- One source form missing; no route invented. MED/FLD/DIL roles retained (155/8/7).
- One exact visit duplicate collapsed in registry: 22 source rows → 21 visit keys.
- All 170 medication rows link to an exact patient/case in the visit source.
- All 162 lab source rows have case IDs absent from the visit source: group follow-up.

The source inventory includes 25 Excel files: five demographic records, 22 visit
rows, 162 labs, seven procedure rows and 170 medication orders. Only medication
CDM rows are produced here; other members remain responsible for their domains.

## Verification and limitations

Fourteen unit tests passed. Actual-output checks reconcile all 170 order IDs,
ensure disjoint Drug/handoff destinations, enforce signed-integer ranges, verify
registry foreign keys and confirm nonzero concept status/domain. Known original
patient/case identifiers are checked in public export fields. Raw Excel files
remain unchanged; hashes and filenames are kept only in a private manifest.

No integrated PERSON/VISIT table or full OHDSI DQD was available for validation.
Orders are not administrations. Duration, route, supply and quantity remain
unknown; start + 29 day ends are a documented convention, not observed treatment.
The vocabulary catalogue is a live Athena metadata snapshot, not a release.

For input QIs birth year + sex, five equivalence classes each contain one person;
birth decade + sex also gives five singletons (observed minimum k=1). This narrow
demographic check does not assess the complete clinical trajectory or prove
anonymity. No l-diversity, k-map, delta-presence or PHI precision/recall is claimed.

See full_validation.json for machine-readable counts, privacy_assessment.json
for the narrow QI check, and docs/PERSON4_GUIDE_ZH.md for lecture-linked discussion.
