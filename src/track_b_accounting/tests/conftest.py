"""Rend le package track_b_accounting importable (src/ dans sys.path) et fournit les contrôles communs."""
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2]
REPO_ROOT = SRC.parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from track_b_accounting.calc.models import Citation, Result  # noqa: E402


def lire_json(chemin: str) -> dict:
    """Lecture indépendante du loader, pour comparer les résultats au JSON."""
    return json.loads((REPO_ROOT / chemin).read_text(encoding="utf-8"), parse_float=Decimal)


def _sans_float(x) -> bool:
    if isinstance(x, float):
        return False
    if isinstance(x, dict):
        return all(_sans_float(v) for v in x.values())
    if isinstance(x, (list, tuple)):
        return all(_sans_float(v) for v in x)
    return True


def verifier_result(r: Result) -> Result:
    """Invariants de tout Result « ok » : Decimal au millime, aucune float, ≥ 1 Citation complète."""
    assert isinstance(r, Result)
    assert type(r.montant) is Decimal and r.montant == r.montant.quantize(Decimal("0.001"))
    assert r.montant.as_tuple().exponent == -3
    assert _sans_float(r.detail)
    assert r.citations and all(isinstance(c, Citation) for c in r.citations)
    for c in r.citations:
        assert c.source_file.startswith("data/raw/pdf/") and c.source_file.endswith(".pdf")
        assert c.data_file.startswith("data/processed/") and (REPO_ROOT / c.data_file).is_file()
        assert c.decision_ref.startswith("D") and isinstance(c.page, int)
    assert r.unite.startswith("TND/")
    return r


@pytest.fixture
def ok():
    return verifier_result
