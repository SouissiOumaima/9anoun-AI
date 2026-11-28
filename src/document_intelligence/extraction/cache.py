"""Cache mémoire borné à durée limitée ; les appels identiques simultanés partagent le calcul."""

from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import Future
from copy import deepcopy
from threading import Lock
from time import monotonic
from typing import Any


class ExtractionCache:
    def __init__(self, ttl: float = 300, capacity: int = 32) -> None:
        self.ttl, self.capacity = ttl, capacity
        self._lock = Lock()
        self._values: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._pending: dict[str, Future[Any]] = {}

    def get_or_compute(self, key: str, compute: Callable[[], Any]) -> Any:
        with self._lock:
            now = monotonic()
            for stale in [k for k, (expires, _) in self._values.items() if expires <= now]:
                del self._values[stale]
            if key in self._values:
                self._values.move_to_end(key)
                return deepcopy(self._values[key][1])
            pending = self._pending.get(key)
            owner = pending is None
            future: Future[Any] = pending if pending is not None else Future()
            if owner:
                self._pending[key] = future
        if not owner:
            return deepcopy(future.result())
        try:
            value = compute()
        except BaseException as exc:
            with self._lock:
                self._pending.pop(key)
                future.set_exception(exc)
            raise
        with self._lock:
            self._values[key] = (monotonic() + self.ttl, deepcopy(value))
            while len(self._values) > self.capacity:
                self._values.popitem(last=False)
            self._pending.pop(key)
            future.set_result(value)
        return deepcopy(value)
