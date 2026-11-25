# Track A — S9 Lawyer Review Decisions

## 1. Objective

Document the technical contract for collecting human lawyer reviews
of the seven fictitious Track A cases.

This workflow does not constitute legal validation.

## 2. Components

- Schema: `data/mock_cards/schemas/track_a_lawyer_review_decisions_s9.v1.schema.json`
- Validator: `src/track_a_legal/lawyer_review_validator_s9.py`
- Schema tests: `src/track_a_legal/tests/test_lawyer_review_schema_s9.py`
- Validator tests: `src/track_a_legal/tests/test_lawyer_review_validator_s9.py`
- Review protocol: `docs/track_a_lawyer_review_protocol_s9.md`

## 3. Review scope

- Seven fictitious cases: CASE-A-001 to CASE-A-007
- Six criteria per case: S6-C02, S6-C03, S6-C04,
  S6-C05, S6-C06 and S6-C08
- Total expected assessments: 42

## 4. Review states

- `pending`: No human decision recorded.
- `completed`: A documented human assessment is recorded.

Possible decisions for completed reviews:

- `approved`
- `issues_found`
- `blocked`

Completed reviews require reviewer identity, review date,
decision and non-empty comments.

## 5. Validation

Two complementary controls are required:

1. JSON Schema validation for document structure and field constraints.
2. Business validation for unique case/criterion pairs and completeness.

The business validator supports partial collection.

`require_complete=True` requires all 42 unique pairs.

This completeness check does not prove that all decisions are approved
or that a lawyer is authorized.

## 6. Safeguards

- Do not generate lawyer decisions automatically.
- Do not change the original S9 preparation dataset.
- Do not infer legal approval from successful technical tests.
- The current collection schema requires `lawyer_validated=false`.
- Preserve the identity, date, justification and references
  associated with genuine human reviews.
- An authorized legal validation workflow is still required.

## 7. Tests

Run:

`python -m pytest src/track_a_legal/tests/test_v1_golden_set_lawyer_s9.py src/track_a_legal/tests/test_lawyer_review_validator_s9.py src/track_a_legal/tests/test_lawyer_review_schema_s9.py -q -p no:cacheprovider`

Expected: 19 passing tests.

## 8. Current status

- Technical preparation: completed for tested scenarios.
- Human assessments: 42 pending.
- Official lawyer validation: pending.
- DS1 integration and final E2E validation: pending.
