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
