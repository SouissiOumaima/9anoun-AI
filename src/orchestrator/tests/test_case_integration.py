"""Two-step orchestration tests use injected service fixtures, never a remote API."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from src.document_intelligence.evaluation.fictive_documents import DOCS_DIR
from src.document_intelligence.service import handle_request
from src.document_intelligence.tests.test_document_intelligence_gemini import _perfect_client
from src.legal_retrieval.contract.handler import handle as ds2_handle
from src.orchestrator.card_repository import MockCardRepository
from src.orchestrator.case_integration import CaseIntegrationWorkflow, CaseWorkflowError
from src.orchestrator.models import ActiveContext, CardType, UserIdentity
from src.orchestrator.audit import AuditTrail

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def setup_flow(tmp_path):
    scenario = json.loads((ROOT / 'data/mock_cards/orchestrator_case_e2e_demo.json').read_text(encoding='utf-8'))
    card = scenario['card']
    doc = card['data']['documents'][0]
    target = tmp_path / 'cards' / card['card_id'] / 'documents' / doc['document_id'] / doc['file_name']
    target.parent.mkdir(parents=True)
    target.write_bytes((DOCS_DIR / doc['file_name']).read_bytes())
    actor = UserIdentity('org-demo', 'test-user', 'lawyer', frozenset({card['card_id']}))
    context = ActiveContext('org-demo', card['card_id'], CardType.CASE, {
        'document_id': doc['document_id'], 'document_file_name': doc['file_name'],
        'document_mime_type': doc['mime_type'], 'document_storage_ref': doc['storage_ref'],
    })
    calls = []

    def ds3(request):
        calls.append('ds3')
        return handle_request(request, storage_root_dir=tmp_path, client=_perfect_client('DS3-01'))

    def ds2(request, *, live):
        calls.append('ds2')
        # Injected schema-valid fixture, explicitly simulated for this test only.
        mocked = ds2_handle({**request, 'sector': 'btp'}, live=False)
        mocked['mode'] = 'live'
        mocked['computed_by'] = 'legal_retrieval.search.live'
        return mocked

    flow = CaseIntegrationWorkflow(ds3=ds3, ds2=ds2, audit=AuditTrail())
    common = dict(actor=actor, context=context, repository=MockCardRepository.from_payload([card]))
    return flow, scenario, common, calls


def prepare(setup_flow):
    flow, scenario, common, calls = setup_flow
    result = flow.prepare(**common, subject_id=scenario['subject_id'], evidence_id=scenario['evidence_id'],
                          legal_request=scenario['legal_request'], language='fr')
    return result


def test_no_retrieval_or_ds4_before_confirmation(setup_flow):
    result = prepare(setup_flow)
    assert result['status'] == 'pending_confirmation'
    assert setup_flow[3] == ['ds3']
    assert all(f['user_confirmed'] is False for f in result['facts'])
    assert all(f['citation']['document_id'] == result['document_id'] for f in result['facts'])


def test_full_flow_transmits_only_selected_confirmed_facts_and_is_idempotent(setup_flow):
    flow, _, common, calls = setup_flow
    prepared = prepare(setup_flow)
    fact_id = next(f['fact_id'] for f in prepared['facts'] if f['selectable'])
    kwargs = dict(**common, review_id=prepared['review_id'], confirmed_fact_ids=[fact_id], confirm_document_link=True)
    result = flow.complete(**kwargs)
    assert result['status'] == 'completed'
    assert len(result['confirmed_facts']) == 1
    assert result['confirmed_facts'][0]['user_confirmed'] is True
    assert result['analysis']['legal_conclusion'] is None
    diagnostics = result['analysis']['uncertain_information']
    assert diagnostics  # Missing legal-source metadata must reach the E2E UI.
    pairs = [(item['reference_id'], item['reason']) for item in diagnostics]
    assert len(pairs) == len(set(pairs))
    assert all(isinstance(ref, str) and isinstance(reason, str) for ref, reason in pairs)
    assert result['legal_sources']
    assert flow.complete(**kwargs) == result
    assert calls == ['ds3', 'ds2']
    assert [e.details['agent'] for e in flow.audit.events()] == ['document_intelligence', 'legal_retrieval', 'track_a_legal']
    assert all('value' not in e.details and 'query' not in e.details for e in flow.audit.events())


@pytest.mark.parametrize('selection,link', [([], True), (['invented'], True), (None, True), ([], False)])
def test_invalid_or_missing_confirmation_never_calls_ds2(setup_flow, selection, link):
    flow, _, common, calls = setup_flow
    prepared = prepare(setup_flow)
    with pytest.raises(CaseWorkflowError, match='CONFIRMATION'):
        flow.complete(**common, review_id=prepared['review_id'], confirmed_fact_ids=selection, confirm_document_link=link)
    assert calls == ['ds3']


def test_foreign_user_cannot_confirm_review(setup_flow):
    flow, _, common, _ = setup_flow
    prepared = prepare(setup_flow)
    actor = UserIdentity('org-demo', 'other-user', 'lawyer', common['actor'].authorized_card_ids)
    with pytest.raises(CaseWorkflowError, match='CONTEXT_MISMATCH'):
        flow.complete(**{**common, 'actor': actor}, review_id=prepared['review_id'],
                      confirmed_fact_ids=[prepared['facts'][0]['fact_id']], confirm_document_link=True)


def test_mock_ds2_is_blocked_and_can_be_retried(setup_flow):
    flow, _, common, _ = setup_flow
    prepared = prepare(setup_flow)
    real_handler = flow.ds2
    flow.ds2 = lambda request, **_: {'mode': 'mock', 'request_id': request['request_id']}
    kwargs = dict(**common, review_id=prepared['review_id'],
                  confirmed_fact_ids=[prepared['facts'][0]['fact_id']], confirm_document_link=True)
    with pytest.raises(CaseWorkflowError, match='DS2_LIVE'):
        flow.complete(**kwargs)
    flow.ds2 = real_handler
    assert flow.complete(**kwargs)['status'] == 'completed'


def test_response_from_another_document_is_rejected(setup_flow):
    flow, _, _, _ = setup_flow
    original = flow.ds3
    def foreign(request):
        result = original(request)
        result['document_id'] = 'other-document'
        return result
    flow.ds3 = foreign
    with pytest.raises(CaseWorkflowError, match='PROVENANCE'):
        prepare(setup_flow)


@pytest.mark.parametrize('confidence', [0.5, 0.896, 0.89999])
def test_low_confidence_field_cannot_be_confirmed(setup_flow, confidence):
    flow, _, common, calls = setup_flow
    original = flow.ds3
    def weak(request):
        result = original(request)
        result['result']['fields']['base_salary']['confidence'] = confidence
        return result
    flow.ds3 = weak
    prepared = prepare(setup_flow)
    fact = next(f for f in prepared['facts'] if f['field_name'] == 'base_salary')
    assert fact['selectable'] is False
    with pytest.raises(CaseWorkflowError, match='CONFIRMATION'):
        flow.complete(**common, review_id=prepared['review_id'], confirmed_fact_ids=[fact['fact_id']], confirm_document_link=True)
    assert calls == ['ds3']


def test_fictitious_case_matches_official_card_schema(setup_flow):
    from jsonschema import Draft202012Validator, FormatChecker
    schema = json.loads((ROOT / 'data/mock_cards/schemas/orchestrator_case_card.v0.schema.json').read_text(encoding='utf-8'))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(setup_flow[1]['card'])


@pytest.mark.parametrize('code,retryable', [('TIMEOUT', True), ('INTERNAL_ERROR', True), ('INTERNAL_ERROR', False)])
def test_ds3_error_messages_and_retry_reach_web_api(setup_flow, monkeypatch, code, retryable):
    from src.orchestrator import web_app
    flow, _, _, calls = setup_flow
    original = flow.ds3

    def unavailable(request):
        response = original(request)
        response.update(status='erreur', result=None, citations=[], refus=None,
                        ds3_code=code, retryable=retryable,
                        erreur={'type': code, 'message_fr': 'Lecture en cours. Réessayez.',
                                'message_ar': 'القراءة جارية. أعد المحاولة.'})
        return response

    flow.ds3 = unavailable
    monkeypatch.setattr(web_app, '_CASE_WORKFLOW', flow)
    for attempt in range(2):
        result = web_app.case_integration_action({'language': 'ar'})
        assert result['status'] == ('retry_later' if retryable else 'blocked')
        assert result['retryable'] is retryable
        assert result['code'] == f'DS3_{code}'
        assert result['message_fr'] == 'Lecture en cours. Réessayez.'
        assert result['message_ar'] == 'القراءة جارية. أعد المحاولة.'
        assert calls == ['ds3'] * (attempt + 1)
        assert not flow._sessions
        assert 'facts' not in result and 'review_id' not in result
    flow.ds3 = original
    prepared = web_app.case_integration_action({'language': 'ar'})
    assert prepared['status'] == 'pending_confirmation'
    assert calls == ['ds3'] * 3
    assert all(not f['user_confirmed'] for f in prepared['facts'])
    completed = web_app.case_integration_action({
        'review_id': prepared['review_id'],
        'confirmed_fact_ids': [next(f['fact_id'] for f in prepared['facts'] if f['selectable'])],
        'confirm_document_link': True,
    }, complete=True)
    assert completed['status'] == 'completed'
    assert calls == ['ds3'] * 3 + ['ds2']
    assert completed['analysis']['legal_conclusion'] is None


def test_ds3_refusal_preserves_messages_without_retry(setup_flow, monkeypatch):
    from src.orchestrator import web_app
    flow, _, _, calls = setup_flow
    original = flow.ds3

    def refused(request):
        response = original(request)
        response.update(status='refus', result=None, citations=[], ds3_code='UNSUPPORTED_FORMAT',
                        refus={'code': 'HORS_SCOPE', 'message_fr': 'OCR non installé.',
                               'message_ar': 'خدمة OCR غير مثبتة.'})
        return response

    flow.ds3 = refused
    monkeypatch.setattr(web_app, '_CASE_WORKFLOW', flow)
    result = web_app.case_integration_action({})
    assert result['status'] == 'blocked'
    assert result['retryable'] is False
    assert result['message_fr'] == 'OCR non installé.'
    assert result['message_ar'] == 'خدمة OCR غير مثبتة.'
    assert calls == ['ds3']
    assert not flow._sessions


def test_retryable_error_from_other_document_is_rejected(setup_flow):
    flow, _, _, _ = setup_flow
    original = flow.ds3

    def foreign(request):
        response = original(request)
        response.update(status='erreur', result=None, citations=[], refus=None,
                        document_id='foreign-document', ds3_code='TIMEOUT', retryable=True,
                        erreur={'type': 'TIMEOUT', 'message_fr': 'Attendez.', 'message_ar': 'انتظر.'})
        return response

    flow.ds3 = foreign
    with pytest.raises(CaseWorkflowError, match='PROVENANCE') as error:
        prepare(setup_flow)
    assert error.value.retryable is False


def test_unexpected_error_is_logged_without_document_or_exception_content(monkeypatch, caplog):
    from src.orchestrator import web_app

    def fail(**kwargs):
        raise ValueError('PRIVATE_DOCUMENT_TEXT_AND_TOKEN')

    monkeypatch.setattr(web_app._CASE_WORKFLOW, 'prepare', fail)
    response = web_app.case_integration_action({})
    assert response['code'] == 'INTEGRATION_ERROR'
    assert 'Case integration failed (ValueError)' in caplog.text
    assert 'PRIVATE_DOCUMENT_TEXT_AND_TOKEN' not in caplog.text


@pytest.mark.parametrize('contents', [None, '{invalid json', '{}', 'empty_documents'])
def test_unavailable_or_invalid_scenario_returns_a_safe_error(tmp_path, monkeypatch, caplog, contents):
    from src.orchestrator import web_app

    scenario = tmp_path / 'private_scenario.json'
    if contents == 'empty_documents':
        data = json.loads(web_app._E2E_SCENARIO.read_text(encoding='utf-8'))
        data['card']['data']['documents'] = []
        contents = json.dumps(data)
    if contents is not None:
        scenario.write_text(contents, encoding='utf-8')
    monkeypatch.setattr(web_app, '_E2E_SCENARIO', scenario)
    calls = []
    monkeypatch.setattr(web_app._CASE_WORKFLOW, 'prepare', lambda **kwargs: calls.append(kwargs))
    response = web_app.case_integration_action({})
    assert response['status'] == 'blocked'
    assert response['code'] == 'INTEGRATION_ERROR'
    assert response['message_fr'] and response['message_ar']
    assert not calls
    assert str(scenario) not in caplog.text
    assert str(scenario) not in json.dumps(response)


@pytest.mark.parametrize('language', [None, [], {}, 42, 'en'])
def test_invalid_language_is_refused_without_reading_the_scenario(tmp_path, monkeypatch, language):
    from src.orchestrator import web_app

    monkeypatch.setattr(web_app, '_E2E_SCENARIO', tmp_path / 'absent.json')
    response = web_app.case_integration_action({'language': language})
    assert response == {'status': 'blocked', 'code': 'INVALID_LANGUAGE'}
