"""Read-only acceptance check for a D21 vocabulary delivered by DS2."""

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from .legal_retrieval_prompt import normalize_sector_text

ROOT = Path(__file__).resolve().parents[2]


def audit_vocabulary(data: dict, *, expected_sectors: int | None = None) -> dict:
    schema = json.loads((ROOT / 'data/mock_cards/schemas/legal_retrieval_vocabulary.v0.schema.json').read_text(encoding='utf-8'))
    errors = [f'{"/".join(map(str, e.path))}: {e.message}' for e in Draft202012Validator(schema).iter_errors(data)]
    if errors:
        sectors = data.get('sectors') if isinstance(data, dict) else None
        return {
            'passed': False, 'errors': errors,
            'sector_count': len(sectors) if isinstance(sectors, list) else 0,
            'shared_aliases_require_clarification': [],
            'note': 'Invalid vocabulary schema: aliases were not assessed. D30 is not modified.',
        }
    sectors = data['sectors']
    codes = [s['code'] for s in sectors]
    if len(codes) != len(set(codes)):
        errors.append('Duplicate sector codes')
    if expected_sectors is not None and len(sectors) != expected_sectors:
        errors.append(f'Expected {expected_sectors} sectors, received {len(sectors)}')
    aliases: dict[str, set[str]] = {}
    for sector in sectors:
        for term in [sector['code'], sector['source_id'], sector['label_fr'], sector['label_ar'], *sector['aliases']]:
            normalized = normalize_sector_text(term)
            if not normalized:
                errors.append(f'Empty normalized alias in {sector["code"]}')
            else:
                aliases.setdefault(normalized, set()).add(sector['code'])
    rules = data.get('sector_ambiguities', [])
    if not isinstance(rules, list):
        errors.append('sector_ambiguities must be an array')
        rules = []
    for rule in rules:
        if not isinstance(rule, dict) or not isinstance(rule.get('codes'), list) or not rule['codes']:
            errors.append('Each ambiguity requires a nonempty codes array')
            continue
        terms = rule.get('aliases') or rule.get('alias', '').split('/')
        if not isinstance(terms, list) or not all(isinstance(t, str) and t.strip() for t in terms):
            errors.append('Each ambiguity requires aliases or a slash-separated alias')
        if any(not isinstance(code, str) or code not in codes for code in rule['codes']):
            errors.append('Ambiguity references an unknown sector code')
    return {
        'passed': not errors, 'sector_count': len(sectors), 'errors': errors,
        'shared_aliases_require_clarification': [
            {'alias': alias, 'codes': sorted(matches)} for alias, matches in sorted(aliases.items()) if len(matches) > 1
        ],
        'note': 'Exact alias collisions are reported, not resolved by list order. D30 is not modified.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', nargs='?', type=Path, default=ROOT / 'data/mock_cards/legal_retrieval_vocabulary.v0.json')
    parser.add_argument('--expected-sectors', type=int)
    args = parser.parse_args()
    result = audit_vocabulary(json.loads(args.path.read_text(encoding='utf-8-sig')), expected_sectors=args.expected_sectors)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
