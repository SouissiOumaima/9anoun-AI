# DS4 Lawyer Track - Version 1

## 1. Scope

Owner: Ghofran Maaoui

DS4 v1 implements preparatory legal case analysis, reference
validation, evidence mapping, and structured responses.

The implementation follows the principle "Citation ou Silence":
no legal conclusion or citation is invented.

This version does not provide final legal advice.

## 2. Main components

| Module | Responsibility |
|---|---|
| `v1_handler.py` | Public entry point and structured responses |
| `v1_case_analysis.py` | Case analysis and status determination |
| `v1_timeline.py` | Timeline processing |
| `v1_reference_validation.py` | Reference checks |
| `v1_document_fact_validation.py` | Document fact assessment |
| `v1_legal_source_validation.py` | Legal source assessment |
| `v1_legal_version_validation.py` | Legal version checks |
| `v1_temporal_consistency.py` | Temporal consistency checks |

## 3. JSON contracts

Request schema:

`data/mock_cards/schemas/track_a_request.v1.schema.json`

Response schema:

`data/mock_cards/schemas/track_a_response.v1.schema.json`

Contract version: `track_a.v1`.

The official schemas are the source of truth for field-level
requirements and response constraints.

## 4. Entry point

```python
from src.track_a_legal.v1_handler import handle_v1

# Submit a request conforming to the official Request v1 schema.
response = handle_v1(request)
```

Possible response statuses:

- `ok`: a structured analysis result is returned.
- `refus`: the request is refused with a structured reason.
- `erreur`: an internal processing error is reported safely.

## 5. Analysis behavior

The analysis validates the request and checks references,
document facts, legal sources, and temporal information.

Evidence mapping uses explicit event-to-evidence references.
It does not invent evidence relationships.

The current analysis does not generate a legal conclusion.

## 6. Analysis statuses

The current decision priority is:

1. `contradictory_evidence`: explicit contradictions are declared.
2. `insufficient_evidence`: validation or evidence issues exist.
3. `preparatory`: neither condition above is detected.

Contradictions are not inferred automatically.

This priority is an implementation rule of DS4 v1, not a
requirement established by the JSON Schema alone.

## 7. Known contract limitations

The Response v1 schema currently requires
`result.contradictions` to contain zero items (`maxItems: 0`).

Therefore, declared contradiction details cannot be returned
in that field.

The status `contradictory_evidence` can indicate their presence,
but does not provide their detailed explanation.

Internal reference errors may contain more diagnostic
information than the public response exposes.

The `supported` analysis status is not produced by the current
case-analysis implementation.

No final legal conclusion or unsupported citation is generated.

## 8. Testing

Run DS4 tests:

```powershell
# Execute all DS4 tests.
python -m pytest src/track_a_legal/tests -q
```

Run the complete repository test suite:

```powershell
# Execute all discovered project tests.
python -m pytest -q
```

Latest verified full-suite result before this documentation:

747 passed (2026-11-17).

## 9. Integration notes

DS1 should consume the structured response through `handle_v1()`.

DS2 legal source assessments remain conservative when temporal
applicability cannot be confirmed.

DS3 document facts must be assessed before being treated as
confirmed support.

Any change to the official JSON contracts must be coordinated
with the team before integration.

## 10. Pending work

- Coordinate integration with DS1, DS2, and DS3.
- Clarify how detailed contradictions should be exposed.
- Complete domain-specific golden sets and evaluation metrics.
- Review and merge the v1 implementation through a Pull Request.
