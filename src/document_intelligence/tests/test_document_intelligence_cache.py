from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from src.document_intelligence.extraction.cache import ExtractionCache


def test_cache_reuses_success_but_returns_independent_values():
    cache = ExtractionCache()
    value = cache.get_or_compute('user-card-prompt', lambda: {'fields': [1]})
    value['fields'].append(2)
    assert cache.get_or_compute('user-card-prompt', lambda: pytest.fail('cache miss')) == {'fields': [1]}
    assert cache.get_or_compute('other-user-card', lambda: {'fields': [3]}) == {'fields': [3]}


def test_errors_are_not_cached():
    cache = ExtractionCache()
    with pytest.raises(ValueError):
        cache.get_or_compute('key', lambda: int('invalid'))
    assert cache.get_or_compute('key', lambda: 42) == 42


def test_expiration_and_capacity():
    cache = ExtractionCache(ttl=0)
    assert cache.get_or_compute('key', lambda: 1) == 1
    assert cache.get_or_compute('key', lambda: 2) == 2
    cache = ExtractionCache(capacity=1)
    cache.get_or_compute('first', lambda: 1)
    cache.get_or_compute('second', lambda: 2)
    assert cache.get_or_compute('first', lambda: 3) == 3


def test_concurrent_duplicate_calls_share_one_computation():
    cache = ExtractionCache()
    entered, release = Event(), Event()
    calls = []

    def compute():
        calls.append(1)
        entered.set()
        assert release.wait(5)
        return 42

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(cache.get_or_compute, 'key', compute)
        assert entered.wait(5)
        second = pool.submit(cache.get_or_compute, 'key', compute)
        release.set()
        assert first.result() == second.result() == 42
    assert len(calls) == 1


@pytest.mark.parametrize("different_scope", [None, "user", "card"])
def test_pipeline_cache_reuses_only_same_actor_and_card(monkeypatch, different_scope):
    from src.document_intelligence.contract.v2.models import DS3Response
    from src.document_intelligence.evaluation.fictive_documents import DOCS_DIR
    from src.document_intelligence.evaluation.run_gemini_eval import request_for
    from src.document_intelligence.extraction import gemini
    from src.document_intelligence.extraction.pipeline import analyze_payslip_pdf
    from src.document_intelligence.tests.test_document_intelligence_gemini import (
        _perfect_client,
    )
    from src.document_intelligence.tests.test_document_intelligence_golden import CASES

    client = _perfect_client("DS3-01")
    monkeypatch.setattr(gemini, "_answers", ExtractionCache())
    monkeypatch.setattr(gemini, "_default_client", lambda: client)
    monkeypatch.setenv("DS3_EXTRACTION_CACHE", "1")
    case = CASES["DS3-01"]
    first = request_for(case)
    second = first.model_copy(deep=True)
    second.request_id = "second-request"
    if different_scope == "user":
        second.context.user_id = "another-user"
    elif different_scope == "card":
        second.context.card_id = second.document.card_id = "another-card"
    path = DOCS_DIR / case["requete"]["file_name"]
    one = analyze_payslip_pdf(path, first)
    two = analyze_payslip_pdf(path, second)
    DS3Response.model_validate(one)
    DS3Response.model_validate(two)
    assert one["status"] == two["status"] == "ok"
    assert len(client.calls) == (1 if different_scope is None else 2)
    assert two["request_id"] == "second-request"
    assert two["card_id"] == second.context.card_id
    assert two["citations"]
