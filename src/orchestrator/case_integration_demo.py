"""Provision fictitious PDF and run an explicitly automated integration check."""

import argparse
import json
import os
from pathlib import Path
import shutil


def main():
    from dotenv import load_dotenv
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare-storage', action='store_true')
    parser.add_argument('--live-test', action='store_true', help='Automated test confirmation, not human legal approval')
    args = parser.parse_args()
    from .web_app import _E2E_SCENARIO, case_integration_action
    scenario = json.loads(_E2E_SCENARIO.read_text(encoding='utf-8'))
    if args.prepare_storage:
        from src.document_intelligence.evaluation.fictive_documents import DOCS_DIR
        repo = Path(__file__).resolve().parents[2]
        root = Path(os.environ.get('DS3_STORAGE_ROOT') or repo / 'tmp/ds3_storage').resolve()
        if not root.is_relative_to(repo):
            raise ValueError('Demo storage must be inside the project workspace')
        doc = scenario['card']['data']['documents'][0]
        target = root / 'cards' / scenario['card']['card_id'] / 'documents' / doc['document_id'] / doc['file_name']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(DOCS_DIR / doc['file_name'], target)
        print('Fictitious payslip provisioned in the case-scoped DS3 storage.')
    if args.live_test:
        prepared = case_integration_action({'language': 'fr'})
        if prepared['status'] != 'pending_confirmation':
            print(json.dumps(prepared, ensure_ascii=False))
            raise SystemExit(1)
        ids = [f['fact_id'] for f in prepared['facts'] if f['selectable']]
        result = case_integration_action({
            'review_id': prepared['review_id'], 'confirmed_fact_ids': ids, 'confirm_document_link': True,
        }, complete=True)
        if result['status'] != 'completed':
            print(json.dumps(result, ensure_ascii=False))
            raise SystemExit(1)
        report = {
            'confirmation_kind': 'automated_test_only',
            'status': result['status'], 'ds3_mode': result['ds3_mode'], 'ds2_mode': result['ds2_mode'],
            'confirmed_fact_count': len(result['confirmed_facts']),
            'legal_sources': [{k: s.get(k) for k in ['article_id', 'reference', 'effective_from', 'effective_to', 'applicable_at_reference_date']} | {'page': (s.get('citation') or {}).get('page')} for s in result['legal_sources']],
            'analysis_status': result['analysis']['analysis_status'],
            'legal_conclusion': result['analysis']['legal_conclusion'],
            'final_citation_count': len(result['final_citations']),
            'review_required': result['review_required'], 'timings_ms': result['timings_ms'],
        }
        output = Path(__file__).resolve().parents[2] / 'tmp/case_e2e_validation.json'
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
