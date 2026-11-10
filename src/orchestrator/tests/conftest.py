"""Keep orchestration tests deterministic even on a live-configured host."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _force_ds3_mock_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests opt into live mode explicitly when they need to exercise that seam."""

    monkeypatch.setenv("DS3_HANDLER_MODE", "mock")
