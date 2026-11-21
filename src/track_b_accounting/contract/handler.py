"""Interface JSON du module comptable : requête dict → réponse dict (D7 ; contrat v1 à côté de v0, D75).

Aucune logique de calcul ici : validation de la requête (JSON Schema), appel de calc/,
conversion Result/Refus en réponse. Toute exception inattendue → status "erreur", sans montant.

Versions : une requête dont contract_version vaut exactement "track_b.v1" est traitée en v1 (schémas v1, demande
par degré, primes servies exactes) et reçoit une réponse v1 ; toute autre requête suit le chemin v0, inchangé.
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
CONTRACT_VERSION_V1 = "track_b.v1"
CONTRACT_VERSIONS = (CONTRACT_VERSION, CONTRACT_VERSION_V1)
SCHEMAS_DIR = Path(__file__).resolve().parents[3] / "data" / "mock_cards" / "schemas"
OPERATIONS: dict[str, Callable[..., Result]] = {
    "salaire_base": calc.salaire_base,
    "prime": calc.prime,
    "smig": calc.smig,
}
# Contrat v1 : mêmes opérations ; la prime sert aussi les montants imprimés exacts (D76). Le choix est fait ici,
# selon contract_version, jamais par un paramètre de la requête.
OPERATIONS_V1: dict[str, Callable[..., Result]] = {
    "salaire_base": calc.salaire_base,
    "prime": calc.prime_v1,
    "smig": calc.smig,
}
# Opérations valides au schéma de requête, mais toujours refusées (HORS_SCOPE) : aucune source vérifiée.
OPERATIONS_HORS_PERIMETRE = frozenset({"cotisation_cnss"})
COMPUTED_BY_CONTRACT = "track_b_accounting.contract"


class _RefusContrat(Refus):
    """Refus émis par la couche contrat, sans appel à calc/ (requête non conforme ou opération hors périmètre)."""


@lru_cache(maxsize=None)
def validator(nom: str, version: str = CONTRACT_VERSION) -> Draft202012Validator:
    """nom = "request" ou "response", version = "track_b.v0" ou "track_b.v1" (schémas de data/mock_cards/schemas/)."""
    suffixe = version.split(".")[1]
    schema = json.loads((SCHEMAS_DIR / f"track_b_{nom}.{suffixe}.schema.json").read_text(encoding="utf-8"))
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


def _version(request) -> str:
    """track_b.v1 seulement si la requête le demande exactement ; sinon v0 (y compris pour une requête invalide)."""
    if isinstance(request, dict) and request.get("contract_version") == CONTRACT_VERSION_V1:
        return CONTRACT_VERSION_V1
    return CONTRACT_VERSION


def _request_id(request) -> str | None:
    rid = request.get("request_id") if isinstance(request, dict) else None
    return rid if isinstance(rid, str) else None


def _traiter(request) -> dict:
    rid = _request_id(request)
    version = _version(request)
    if not isinstance(request, dict):
        raise _RefusContrat(Refus.PARAM_INVALIDE, "La requête doit être un objet JSON.", "يجب أن يكون الطلب كائن JSON.")

    # 1. Refus de contrat : requête mal formée (bug de l'appelant).
    erreur = best_match(validator("request", version).iter_errors(request))
    if erreur is not None:
        chemin = "/".join(str(p) for p in erreur.absolute_path) or "(racine)"
        raise _RefusContrat(
            Refus.PARAM_INVALIDE,
            f"Requête non conforme au contrat {version} ({chemin}) : {erreur.message}",
            f"الطلب غير مطابق للعقد {version} ({chemin}): {erreur.message}",
        )

    # 2. Refus métier : requête valide, opération connue du contrat mais hors périmètre Track B.
    op = request["operation"]
    if op in OPERATIONS_HORS_PERIMETRE:
        raise _RefusContrat(
            Refus.HORS_SCOPE,
            f"Opération {op!r} hors du périmètre Track B {version.split('.')[1]} (disponibles : {', '.join(OPERATIONS)}). "
            "CNSS, IRPP, salaire net et conversions ne sont pas couverts par une source vérifiée.",
            f"العملية {op!r} خارج نطاق المسار B (المتوفر: {', '.join(OPERATIONS)}). "
            "الضمان الاجتماعي والضريبة على الدخل والأجر الصافي غير مشمولة بمصدر مُتحقَّق منه.",
        )

    # 3. Calcul (refus éventuels émis par calc/).
    r = (OPERATIONS_V1 if version == CONTRACT_VERSION_V1 else OPERATIONS)[op](**request["params"])
    return reponse_ok(rid, r, f"track_b_accounting.calc.{op}")


def handle(request: object) -> dict:
    """Point d'entrée unique. Renvoie toujours une réponse conforme au schéma de réponse de la version traitée."""
    rid = _request_id(request)
    version = _version(request)
    op = request.get("operation") if isinstance(request, dict) else None
    try:
        rep = _traiter(request)
    except Refus as e:
        qui = COMPUTED_BY_CONTRACT if isinstance(e, _RefusContrat) else f"track_b_accounting.calc.{op}"
        rep = reponse_refus(rid, e, qui)
    except Exception as exc:  # noqa: BLE001 — contrat : jamais d'exception vers l'appelant
        rep = reponse_erreur(rid, exc)
    if version != CONTRACT_VERSION and isinstance(rep, dict):
        rep["contract_version"] = version
    if not validator("response", version).is_valid(rep):
        rep = reponse_erreur(rid, ValueError(f"réponse non conforme au schéma {version}"))
        rep["contract_version"] = version
    return rep
