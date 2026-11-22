# Track A ? S9 Lawyer Review Protocol

## 1. Objective

Evaluate the legal relevance, clarity, completeness and traceability
of the seven fictitious Track A cases.

This protocol does not constitute legal validation.

## 2. Reference materials

- track_a_case_cards_v1.json
- track_a_business_validation_s6.v1.json
- track_a_golden_set_technical_v1.json
- track_a_golden_set_lawyer_s9.v1.json
- S7 preparatory deliverables
- S8 preparatory legal reports

## 3. Review criteria

The lawyer reviews the following S6 criteria:

- S6-C02: Chronology traceability
- S6-C03: Claims prudence
- S6-C04: Evidence traceability
- S6-C05: Contradictions and gaps
- S6-C06: Legal source prudence
- S6-C08: Legal relevance, clarity and completeness

S6-C01 and S6-C07 remain automated controls.

## 4. Review procedure

For each case and each applicable criterion:

1. Examine the original case and supporting materials.
2. Compare the DS4 output with the available evidence.
3. Record an explicit assessment.
4. Document the justification and supporting references.
5. Identify any required correction.

## 5. Proposed decision vocabulary

- approved: Criterion accepted by the lawyer.
- issues_found: Corrections required.
- blocked: Insufficient information for assessment.

These values are proposed for the future human-review workflow.
They are not accepted by the current preparation-only JSON schema.

## 6. Validation safeguards

- Never generate lawyer decisions automatically.
- Never interpret technical tests as legal approval.
- Preserve reviewer identity and review date in the future
  validated-review record.
- Keep all decisions pending until genuine human review.
- Do not set lawyer_validated to true without an authorized,
  documented validation process.

## 7. Current status

- Cases: 7
- Lawyer-review criteria per case: 6
- Total pending assessments: 42
- Lawyer validation: pending


## Rapports préparatoires conservés

Les 14 fichiers de `track_a_lawyer_reviews_s9/generated_reports/` sont conservés comme instantané de la livraison initiale pour comparer la revue humaine aux sorties préparatoires. Ils ne sont ni régénérés automatiquement ni une preuve de validation juridique. Après une évolution des fixtures, les nouveaux rapports doivent être identifiés séparément ; ne pas écraser cet historique comme s’il avait été validé.
