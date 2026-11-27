"""DS1 readiness checks; the 56-sector vocabulary below is synthetic, not a delivery."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from src.legal_retrieval.contract.vocabulary import load_vocabulary
from src.legal_retrieval.corpus.ingest_sections import run
from src.orchestrator import legal_retrieval_prompt as prompt
from src.orchestrator.legal_retrieval_adapter import LegalRetrievalAdapter
from src.orchestrator.models import ActiveContext, RequestEnvelope, UserIdentity
from src.orchestrator.sector_mapping import resolve_active_ds5_sector
from src.orchestrator.state_machine import FlowState, StateMachine
from src.orchestrator.sector_vocabulary_audit import audit_vocabulary


def vocabulary56():
    data = deepcopy(load_vocabulary())
    data['sectors'] = [
        dict(code='commerce_gros', source_id='TEST-GROS', label_fr='Commerce de gros', label_ar='تجارة الجملة', aliases=['commerce', 'commerce de gros']),
        dict(code='commerce_materiaux', source_id='TEST-MATERIAUX', label_fr='Commerce des matériaux de construction', label_ar='تجارة مواد البناء', aliases=['commerce des matériaux', 'commerce des matériaux de construction']),
        dict(code='boissons_gazeuses', source_id='TEST-GAZEUSES', label_fr='Boissons gazeuses', label_ar='المشروبات الغازية', aliases=['boissons']),
        dict(code='boissons_alcoolisees', source_id='TEST-ALCOOL', label_fr='Boissons alcoolisées', label_ar='المشروبات الكحولية', aliases=['boissons']),
    ]
    data['sector_ambiguities'] = []
    while len(data['sectors']) < 56:
        i = len(data['sectors'])
        suffix = chr(97+i//26) + chr(97+i%26)
        data['sectors'].append(dict(code=f'synthetic_{suffix}', source_id=f'TEST-{suffix.upper()}',
                                    label_fr=f'Secteur fictif {suffix}', label_ar=f'قطاع تجريبي {suffix}', aliases=[]))
    return data


@pytest.mark.parametrize('message', [
    'sécurité sociale', 'agent de sécurité sociale', 'sécurité-sociale', 'assurance sociale',
    'assurance-maladie', 'assurance santé', 'التأمين الاجتماعي', 'التأمين على المرض', 'التأمين الصحي',
])
def test_social_protection_never_forces_a_sector(message):
    result = prompt.extract_legal_prompt(message)
    assert result.sector is None
    assert result.sector_ambiguous is False


@pytest.mark.parametrize('message,expected', [
    ('construction metallique', 'construction_metallique'),
    ('école privée', 'enseignement_prive'), ('البنوك', 'banques'),
    ('CCS-BTP', 'btp'), ('enseignement_prive', 'enseignement_prive'),
    ('préavis de gardiennage et sécurité sociale', 'gardiennage_securite_transport_fonds'),
])
def test_explicit_current_designations_remain_recognized(message, expected):
    assert prompt.extract_legal_prompt(message).sector == expected


@pytest.mark.parametrize('message', ['construction', 'bâtiment', 'métallurgie', 'المعادن', 'البناء', 'banque et assurance'])
def test_ambiguities_have_no_selected_sector(message):
    result = prompt.extract_legal_prompt(message)
    assert result.sector is None and result.sector_ambiguous
    assert result.sector_choices_fr and result.sector_choices_ar


@pytest.mark.parametrize('message', ['rassurance', 'bancairement', 'قطاع غير معروف'])
def test_substrings_and_unknown_sectors_are_not_guessed(message):
    assert prompt.extract_legal_prompt(message).sector is None


@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('message,expected,ambiguous', [
    ('commerce de gros', 'commerce_gros', False),
    ('commerce des matériaux de construction', 'commerce_materiaux', False),
    ('تجارة مواد البناء', 'commerce_materiaux', False),
    ('boissons gazeuses', 'boissons_gazeuses', False),
    ('boissons alcoolisées', 'boissons_alcoolisees', False),
    ('boissons', None, True),
    ('commerce de gros et commerce des matériaux', None, True),
    ('المشروبات الغازية أو المشروبات الكحولية', None, True),
])
def test_56_synthetic_sectors_are_independent_of_vocabulary_order(monkeypatch, reverse, message, expected, ambiguous):
    data = vocabulary56()
    assert len(data['sectors']) == 56
    if reverse:
        data['sectors'].reverse()
    monkeypatch.setattr(prompt, 'load_vocabulary', lambda: data)
    result = prompt.extract_legal_prompt(message)
    assert result.sector == expected
    assert result.sector_ambiguous is ambiguous


def envelope(message):
    return RequestEnvelope('migration-test', message, 'ar' if 'قانون' in message else 'fr',
                           UserIdentity('org-demo', 'user-1', 'lawyer', frozenset()), ActiveContext('org-demo'))


def test_new_ambiguity_stops_before_any_ds2_call_with_real_choices(monkeypatch):
    monkeypatch.setattr(prompt, 'load_vocabulary', vocabulary56)
    calls = []
    result = StateMachine(lambda p: calls.append(p)).run(envelope('Quel préavis pour les boissons ?'))
    assert result.state is FlowState.CLARIFICATION_REQUIRED
    assert calls == []
    assert 'gazeuses' in result.clarification_message_fr
    assert 'الكحولية' in result.clarification_message_ar
    assert 'construction' not in result.clarification_message_fr


def test_known_ds2_sector_does_not_enable_a_missing_ds5_grid(monkeypatch):
    monkeypatch.setattr(prompt, 'load_vocabulary', vocabulary56)
    assert prompt.extract_legal_prompt('commerce de gros').sector == 'commerce_gros'
    assert resolve_active_ds5_sector('commerce de gros') is None


def test_acceptance_audit_reports_alias_collisions_without_rejecting_56_sectors():
    result = audit_vocabulary(vocabulary56(), expected_sectors=56)
    assert result['passed']
    assert any(item['alias'] == 'boissons' for item in result['shared_aliases_require_clarification'])


@pytest.mark.parametrize('data,count', [(None, 0), ({}, 0), ({'sectors': [{}]}, 1)])
def test_invalid_vocabulary_keeps_a_complete_failed_audit_report(data, count):
    report = audit_vocabulary(data)
    assert report['passed'] is False
    assert report['errors']
    assert report['sector_count'] == count
    assert report['shared_aliases_require_clarification'] == []
    assert 'not assessed' in report['note']


def test_acceptance_audit_rejects_missing_sectors_duplicates_and_dangling_ambiguities():
    data = vocabulary56()
    data['sectors'][-1]['code'] = data['sectors'][0]['code']
    data['sector_ambiguities'].append({'alias': 'inconnu', 'codes': ['unknown']})
    result = audit_vocabulary(data, expected_sectors=55)
    assert not result['passed']
    assert len(result['errors']) == 3


def test_official_ds1_ds2_search_keeps_general_sources_and_excludes_other_sectors(tmp_path, monkeypatch):
    # Use the real ingester and handler with three synthetic, equally relevant articles.
    raw = tmp_path / 'raw'
    raw.mkdir()
    for name in ['الاتفاقية المشتركة القطاعية للبناء والأشغال العامة.json',
                 'الاتفاقية المشتركة القطاعية لقطاع البنوك.json', 'الاتفاقية المشتركة الاطارية.json']:
        text = 'نص تجريبي عن القانون حول مدة التجربة في البنوك.'
        (raw / name).write_text(json.dumps({'sections': [{
            'source_article': '2', 'source_heading': 'الفصل 2', 'title': 'الفصل 2',
            'content_type': None, 'content': text, 'paragraphs': [text],
        }]}, ensure_ascii=False), encoding='utf-8')
    output = tmp_path / 'corpus'
    run(raw, output)
    monkeypatch.setenv('DS2_CORPUS_DIR', str(output))
    captured = []
    def execute(payload):
        captured.append(payload)
        return LegalRetrievalAdapter()(payload)
    result = StateMachine(execute).run(envelope('ما هو القانون حول مدة التجربة في البنوك؟'))
    assert result.state is FlowState.COMPLETED
    request = captured[0]['params']['legal_retrieval_request']
    assert request['sector'] == 'banques'
    assert 'source_id' not in request
    sources = {r['source_id'] for r in result.tool_response['data']['results']}
    assert sources == {'CCS-BANQUES', 'CC-CADRE'}
    assert result.tool_response['data']['mode'] == 'live'
