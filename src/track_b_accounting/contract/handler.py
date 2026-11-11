"""Interface JSON v0 du module comptable : requête dict → réponse dict (D7).

Aucune logique de calcul ici : validation de la requête (JSON Schema), appel de calc/,
conversion Result/Refus en réponse. Toute exception inattendue → status "erreur", sans montant.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import best_match

from .. import calc
from ..calc import Refus, Result

CONTRACT_VERSION = "track_b.v0"
SCHEMAS_DIR = Path(__file__).resolve().parents[3] / "data" / "mock_cards" / "schemas"
OPERATIONS: dict[str, Callable[..., Result]] = {
    "salaire_base": calc.salaire_base,
    "prime": calc.prime,
    "smig": calc.smig,
}
# Opérations valides au schéma de requête, mais toujours refusées (HORS_SCOPE) : aucune source vérifiée.
OPERATIONS_HORS_PERIMETRE = frozenset({"cotisation_cnss"})
COMPUTED_BY_CONTRACT = "track_b_accounting.contract"


class _RefusContrat(Refus):
    """Refus émis par la couche contrat, sans appel à calc/ (requête non conforme ou opération hors périmètre)."""


@lru_cache(maxsize=None)
def validator(nom: str) -> Draft202012Validator:
    """nom = "request" ou "response" (schémas de data/mock_cards/schemas/)."""
    schema = json.loads((SCHEMAS_DIR / f"track_b_{nom}.v0.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _jsonable(v):
    """Decimal → chaîne (jamais de float dans la réponse)."""
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    return v


def _base(request_id, status: str, computed_by: str) -> dict:
    return {
        "contract_version": CONTRACT_VERSION,
        "request_id": request_id,
        "status": status,
        "result": None,
        "citations": [],
        "refus": None,
        "computed_by": computed_by,
    }


def reponse_ok(request_id: str | None, r: Result, computed_by: str) -> dict:
    rep = _base(request_id, "ok", computed_by)
    rep["result"] = {"montant": str(r.montant), "unite": r.unite, "detail": _jsonable(r.detail)}
    rep["citations"] = [
        {
            "source_file": c.source_file,
            "page": c.page,
            "article": c.article,
            "data_file": c.data_file,
            "decision_ref": c.decision_ref,
        }
        for c in r.citations
    ]
    return rep


def reponse_refus(request_id: str | None, e: Refus, computed_by: str) -> dict:
    rep = _base(request_id, "refus", computed_by)
    rep["refus"] = {"code": e.code, "message_fr": e.message_fr, "message_ar": e.message_ar}
    return rep


def reponse_erreur(request_id: str | None, exc: BaseException) -> dict:
    rep = _base(request_id, "erreur", COMPUTED_BY_CONTRACT)
    rep["erreur"] = {
        "type": type(exc).__name__,
        "message_fr": "Erreur interne du module comptable : aucun montant n'est fourni.",
        "message_ar": "خطأ داخلي في وحدة المحاسبة: لم يتم تقديم أي مبلغ.",
    }
    return rep


def _request_id(request) -> str | None:
    rid = request.get("request_id") if isinstance(request, dict) else None
    return rid if isinstance(rid, str) else None


def _traiter(request) -> dict:
    rid = _request_id(request)
    if not isinstance(request, dict):
        raise _RefusContrat(Refus.PARAM_INVALIDE, "La requête doit être un objet JSON.", "يجب أن يكون الطلب كائن JSON.")

    # 1. Refus de contrat : requête mal formée (bug de l'appelant).
    erreur = best_match(validator("request").iter_errors(request))
    if erreur is not None:
        chemin = "/".join(str(p) for p in erreur.absolute_path) or "(racine)"
        raise _RefusContrat(
            Refus.PARAM_INVALIDE,
            f"Requête non conforme au contrat {CONTRACT_VERSION} ({chemin}) : {erreur.message}",
            f"الطلب غير مطابق للعقد {CONTRACT_VERSION} ({chemin}): {erreur.message}",
        )

    # 2. Refus métier : requête valide, opération connue du contrat mais hors périmètre Track B.
    op = request["operation"]
    if op in OPERATIONS_HORS_PERIMETRE:
        raise _RefusContrat(
            Refus.HORS_SCOPE,
            f"Opération {op!r} hors du périmètre Track B v0 (disponibles : {', '.join(OPERATIONS)}). "
            "CNSS, IRPP, salaire net et conversions ne sont pas couverts par une source vérifiée.",
            f"العملية {op!r} خارج نطاق المسار B (المتوفر: {', '.join(OPERATIONS)}). "
            "الضمان الاجتماعي والضريبة على الدخل والأجر الصافي غير مشمولة بمصدر مُتحقَّق منه.",
        )

    # 3. Calcul (refus éventuels émis par calc/).
    r = OPERATIONS[op](**request["params"])
    return reponse_ok(rid, r, f"track_b_accounting.calc.{op}")


def handle(request: object) -> dict:
    """Point d'entrée unique. Renvoie toujours une réponse conforme au schéma de réponse v0."""
    rid = _request_id(request)
    op = request.get("operation") if isinstance(request, dict) else None
    try:
        rep = _traiter(request)
    except Refus as e:
        qui = COMPUTED_BY_CONTRACT if isinstance(e, _RefusContrat) else f"track_b_accounting.calc.{op}"
        rep = reponse_refus(rid, e, qui)
    except Exception as exc:  # noqa: BLE001 — contrat : jamais d'exception vers l'appelant
        rep = reponse_erreur(rid, exc)
    if not validator("response").is_valid(rep):
        rep = reponse_erreur(rid, ValueError("réponse non conforme au schéma v0"))
    return rep
