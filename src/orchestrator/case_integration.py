"""DS1-controlled, two-step DS3 live / human review / DS2 live / DS4 workflow."""

from copy import deepcopy
from datetime import date, datetime, timezone
from threading import Lock
from time import monotonic, perf_counter
from typing import Any
from uuid import uuid4

from src.document_intelligence.contract.v2.models import DS3Response
from src.document_intelligence.service import handle_request
from src.legal_retrieval.contract.handler import handle as search_legal
from src.track_a_legal.tools.ds2_v1_legal_sources import map_ds2_to_v1_legal_sources
from src.track_a_legal.tools.ds3_v1_document_facts import convert_ds3_facts_to_v1
from src.track_a_legal.v1_document_fact_validation import assess_document_fact

from .card_repository import MockCardRepository
from .audit import AuditEvent
from .document_intelligence_adapter import DocumentIntelligenceAdapter
from .document_intelligence_requests import build_document_intelligence_request
from .models import ActiveContext, UserIdentity
from .tool_contracts import build_tool_call
from .track_a_adapter import TrackAAdapter
from .track_a_requests import build_track_a_request_from_case_card


class CaseWorkflowError(ValueError):
    def __init__(self, code: str, *, retryable: bool = False,
                 message_fr: str | None = None, message_ar: str | None = None):
        self.code = code
        self.retryable = retryable
        self.message_fr, self.message_ar = message_fr, message_ar
        super().__init__(code)


class CaseIntegrationWorkflow:
    """Sessions are actor-scoped, bounded, short-lived and kept only in memory."""

    def __init__(self, *, ds3=handle_request, ds2=search_legal, ds4=None, audit=None):
        self.ds3, self.ds2 = ds3, ds2
        self.ds4 = ds4 or TrackAAdapter()
        self.audit = audit
        self._lock = Lock()
        self._sessions: dict[str, dict] = {}

    def _record(self, actor, context, request_id, agent, operation, state):
        if self.audit is not None:
            self.audit.record(AuditEvent(
                event_type='case_integration_stage', occurred_at=datetime.now(timezone.utc).isoformat(),
                request_id=request_id, organization_id=actor.organization_id, user_id=actor.user_id,
                card_id=context.card_id,
                details={'agent': agent, 'operation': operation, 'final_state': state, 'attempts': 1},
            ))

    @staticmethod
    def _call(actor, context, request_id, agent, operation, params):
        return build_tool_call(
            tool_call_id=f'tool-{uuid4()}', request_id=request_id,
            actor=actor, context=context, agent=agent, operation=operation, params=params,
        ).to_payload()

    def prepare(self, *, actor: UserIdentity, context: ActiveContext, repository: MockCardRepository,
                subject_id: str, evidence_id: str, legal_request: dict, language: str) -> dict:
        started = perf_counter()
        card = repository.read_active_case_card(actor=actor, context=context)
        document_id = context.entity_ids.get('document_id')
        document = next((d for d in card['data']['documents'] if d['document_id'] == document_id), None)
        evidence = next((e for e in card['data']['evidence'] if e['evidence_id'] == evidence_id), None)
        if not document or not evidence or evidence['document_id'] != document_id:
            raise CaseWorkflowError('DOCUMENT_EVIDENCE_MISMATCH')
        if subject_id not in {p['party_id'] for p in card['data']['parties']}:
            raise CaseWorkflowError('UNKNOWN_SUBJECT')
        # Do not accept a caller-supplied path instead of the authorized card metadata.
        for key, field in [('document_file_name', 'file_name'), ('document_mime_type', 'mime_type'),
                           ('document_storage_ref', 'storage_ref')]:
            if context.entity_ids.get(key) != document[field]:
                raise CaseWorkflowError('DOCUMENT_CONTEXT_MISMATCH')
        reference_date = legal_request.get('reference_date')
        if not isinstance(reference_date, str) or date.fromisoformat(reference_date).isoformat() != reference_date:
            raise CaseWorkflowError('REFERENCE_DATE_REQUIRED')
        request_id = f'case-e2e-{uuid4()}'
        request = build_track_a_request_from_case_card(
            request_id=request_id, case_id=context.card_id, language=language,
            case_card=card, contract_version='track_a.v1',
        )
        if request.get('document_facts') or request.get('legal_sources'):
            raise CaseWorkflowError('PREEXISTING_SOURCES')
        request['reference_date'] = reference_date
        ds3_request = build_document_intelligence_request(
            request_id=request_id, actor=actor, context=context, language=language,
        )
        ds3_request['options']['expected_type'] = 'fiche_de_paie'
        captured = {}

        def extract(req):
            response = self.ds3(deepcopy(req))
            captured.update(deepcopy(response))
            return response

        normalized = DocumentIntelligenceAdapter(extract, handler_mode='live')(self._call(
            actor, context, request_id, 'document_intelligence', 'analyze_document', {'ds3_request': ds3_request},
        ))
        DS3Response.model_validate(captured)
        if (captured.get('mode') != 'live' or captured.get('request_id') != request_id
                or captured.get('card_id') != context.card_id or captured.get('document_id') != document_id):
            raise CaseWorkflowError('DS3_PROVENANCE_MISMATCH')
        if normalized['status'] not in {'success', 'partial'}:
            detail = captured.get('erreur') or captured.get('refus') or {}
            retryable = captured.get('status') == 'erreur' and captured.get('retryable') is True
            self._record(actor, context, request_id, 'document_intelligence', 'analyze_document',
                         'retry_later' if retryable else 'blocked')
            raise CaseWorkflowError(
                f"DS3_{captured.get('ds3_code') or detail.get('code') or detail.get('type') or 'ERROR'}",
                retryable=retryable, message_fr=detail.get('message_fr'), message_ar=detail.get('message_ar'),
            )
        facts = convert_ds3_facts_to_v1(captured, subject_id, request['evidence'], {document_id: evidence_id})
        if not facts:
            raise CaseWorkflowError('NO_DOCUMENT_FACTS')
        selectable = {f['fact_id'] for f in facts if assess_document_fact({**f, 'user_confirmed': True})['eligible_for_established_fact']}
        if not selectable:
            raise CaseWorkflowError('NO_REVIEWABLE_FACTS')
        ds2_request = deepcopy(legal_request)
        ds2_request.update(contract_version='legal_retrieval.v0', request_id=request_id, lang=language)
        review_id = f'case-review-{uuid4()}'
        public = {
            'status': 'pending_confirmation', 'review_id': review_id, 'request_id': request_id,
            'case_id': context.card_id, 'document_id': document_id, 'subject_id': subject_id,
            'subject_name': next(p['name'] for p in request['parties'] if p['party_id'] == subject_id),
            'facts': [{**deepcopy(f), 'selectable': f['fact_id'] in selectable} for f in facts],
            'legal_request': ds2_request, 'ds3_mode': 'live',
            'timings_ms': {'ds3': round((perf_counter() - started) * 1000)},
        }
        with self._lock:
            now = monotonic()
            for key in [k for k, v in self._sessions.items() if now - v['created'] > 1800]:
                del self._sessions[key]
            if len(self._sessions) >= 32:
                raise CaseWorkflowError('TOO_MANY_REVIEWS')
            self._sessions[review_id] = dict(
                created=now, actor=(actor.organization_id, actor.user_id, actor.role), context=context,
                card=deepcopy(card), request=request, legal_request=ds2_request, facts=facts,
                selectable=selectable, public=deepcopy(public), state='pending',
            )
        self._record(actor, context, request_id, 'document_intelligence', 'analyze_document', 'pending_confirmation')
        return public

    def complete(self, *, actor: UserIdentity, context: ActiveContext, repository: MockCardRepository,
                 review_id: str, confirmed_fact_ids: list[str], confirm_document_link: bool) -> dict:
        card = repository.read_active_case_card(actor=actor, context=context)
        with self._lock:
            session = self._sessions.get(review_id)
            if not session or monotonic() - session['created'] > 1800:
                raise CaseWorkflowError('REVIEW_EXPIRED_OR_UNKNOWN')
            if (session['actor'] != (actor.organization_id, actor.user_id, actor.role)
                    or session['context'].card_id != context.card_id or session['card'] != card):
                raise CaseWorkflowError('REVIEW_CONTEXT_MISMATCH')
            if (confirm_document_link is not True or not isinstance(confirmed_fact_ids, list)
                    or not confirmed_fact_ids or not all(isinstance(i, str) for i in confirmed_fact_ids)
                    or len(set(confirmed_fact_ids)) != len(confirmed_fact_ids)
                    or not set(confirmed_fact_ids) <= session['selectable']):
                raise CaseWorkflowError('EXPLICIT_VALID_CONFIRMATION_REQUIRED')
            selection = frozenset(confirmed_fact_ids)
            if session['state'] == 'done':
                if selection != session['selection']:
                    raise CaseWorkflowError('REVIEW_ALREADY_COMPLETED')
                return deepcopy(session['result'])
            if session['state'] != 'pending':
                raise CaseWorkflowError('REVIEW_BUSY')
            session['state'] = 'running'
        try:
            started = perf_counter()
            ds2_response = self.ds2(deepcopy(session['legal_request']), live=True)
            if ds2_response.get('mode') != 'live' or ds2_response.get('request_id') != session['request']['request_id']:
                raise CaseWorkflowError('DS2_LIVE_RESPONSE_REQUIRED')
            if ds2_response.get('status') != 'ok':
                raise CaseWorkflowError(f"DS2_{(ds2_response.get('refus') or {}).get('code', 'ERROR')}")
            sources = map_ds2_to_v1_legal_sources(ds2_response)
            self._record(actor, context, session['request']['request_id'], 'legal_retrieval', 'search', 'completed')
            ds2_ms = round((perf_counter() - started) * 1000)
            request = deepcopy(session['request'])
            request['document_facts'] = []
            for fact in session['facts']:
                if fact['fact_id'] in selection:
                    confirmed = deepcopy(fact)
                    confirmed['user_confirmed'] = True
                    confirmed['warnings'] = [w for w in confirmed['warnings'] if w != 'USER_CONFIRMATION_REQUIRED']
                    request['document_facts'].append(confirmed)
            request['legal_sources'] = sources
            started = perf_counter()
            response = self.ds4(self._call(
                actor, context, request['request_id'], 'track_a_legal', 'analyze_case', {'track_a_request': request},
            ))
            if response.get('status') != 'success':
                raise CaseWorkflowError('DS4_ANALYSIS_FAILED')
            if response['data']['result'].get('legal_conclusion') is not None:
                raise CaseWorkflowError('LEGAL_CONCLUSION_FORBIDDEN')
            result = {
                'status': 'completed', 'request_id': request['request_id'],
                'case_id': context.card_id, 'ds3_mode': 'live', 'ds2_mode': 'live',
                'confirmed_facts': request['document_facts'], 'legal_sources': sources,
                'document_citations': [f['citation'] for f in request['document_facts']],
                'retrieval_citations': ds2_response['citations'],
                'final_citations': response['citations'], 'analysis': response['data']['result'],
                'review_required': ['HUMAN_LEGAL_REVIEW_REQUIRED'] + [
                    f"DS2_CITATION_PAGE_MISSING:{s['article_id']}" for s in sources
                    if not s.get('citation') or s['citation'].get('page') is None
                ] + [
                    f"DS2_EFFECTIVE_DATE_MISSING:{s['article_id']}" for s in sources
                    if s.get('effective_from') is None
                ],
                'timings_ms': {**session['public']['timings_ms'], 'ds2': ds2_ms,
                               'ds4': round((perf_counter() - started) * 1000)},
            }
        except BaseException:
            with self._lock:
                session['state'] = 'pending'
            raise
        with self._lock:
            session.update(state='done', selection=selection, result=deepcopy(result))
        self._record(actor, context, request['request_id'], 'track_a_legal', 'analyze_case', 'completed')
        return result
