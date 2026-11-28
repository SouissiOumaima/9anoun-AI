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
# Opérations valides au schéma de requête, mais toujours refusées (HORS_SCOPE), avec leur motif FR et AR (D110).
# Liste fermée, identique à l'enum « operation » des schémas v0 et v1 ; une opération absente de l'enum reste un
# refus de contrat (PARAM_INVALIDE). Motif None : message historique de cotisation_cnss, inchangé.
_MOTIF_CNSS = (
    "Aucun texte ni barème de la CNSS n'est fourni dans les sources vérifiées : cotisation non calculée.",
    "لا يوجد أي نص أو جدول للصندوق الوطني للضمان الاجتماعي في المصادر المُتحقَّق منها: لا تُحتسب المساهمة.",
)
_MOTIF_HORS_CDC = (
    "{sujet} : absent du cahier des charges de Track B, aucun calcul n'est fait.",
    "{sujet_ar}: غير وارد في كراس الشروط الخاص بالمسار B، لا يقع أي احتساب.",
)
OPERATIONS_HORS_PERIMETRE: dict[str, tuple[str, str] | None] = {
    "cotisation_cnss": None,
    "cnss": _MOTIF_CNSS,
    "irpp": (
        "Aucun barème de l'IRPP n'est fourni dans les sources vérifiées : impôt non calculé.",
        "لا يوجد أي جدول للضريبة على دخل الأشخاص الطبيعيين في المصادر المُتحقَّق منها: لا تُحتسب الضريبة.",
    ),
    "facture": (
        "Aucune facture ni donnée comptable n'est fournie à Track B : il ne lit ni ne contrôle les factures.",
        "لا تُقدَّم أي فاتورة أو معطيات محاسبية للمسار B: لا يقرأ الفواتير ولا يراقبها.",
    ),
    "depense": (
        "Aucune dépense ni donnée comptable n'est fournie à Track B : il ne classe ni ne contrôle les dépenses.",
        "لا تُقدَّم أي نفقة أو معطيات محاسبية للمسار B: لا يصنّف النفقات ولا يراقبها.",
    ),
    "ratio": (
        "Aucun état financier n'est fourni à Track B : aucun ratio financier n'est calculé.",
        "لا تُقدَّم أي قوائم مالية للمسار B: لا تُحتسب أي نسبة مالية.",
    ),
    "heures_supplementaires": (
        _MOTIF_HORS_CDC[0].format(sujet="Heures supplémentaires"),
        _MOTIF_HORS_CDC[1].format(sujet_ar="الساعات الإضافية"),
    ),
    "conges": (
        _MOTIF_HORS_CDC[0].format(sujet="Congés payés"),
        _MOTIF_HORS_CDC[1].format(sujet_ar="الرخص خالصة الأجر"),
    ),
    "indemnite_licenciement": (
        _MOTIF_HORS_CDC[0].format(sujet="Indemnité de licenciement"),
        _MOTIF_HORS_CDC[1].format(sujet_ar="غرامة الفصل عن العمل"),
    ),
    "salaire_net": (
        "Le net à payer demande les retenues CNSS et IRPP, dont aucun texte ni barème n'est fourni : non calculé.",
        "يتطلب الأجر الصافي اقتطاعات الضمان الاجتماعي والضريبة على الدخل، ولا يوجد لها أي نص أو جدول: لا يُحتسب.",
    ),
    "conversion_unite": (
        "La conversion d'une unité à l'autre (horaire, journalière, mensuelle) n'est écrite dans aucune source "
        "vérifiée (nombre d'heures par mois non fixé) : seul le montant imprimé, dans son unité, est servi.",
        "التحويل من وحدة إلى أخرى (بالساعة، باليوم، بالشهر) غير منصوص عليه في أي مصدر مُتحقَّق منه: "
        "يُقدَّم المبلغ المطبوع بوحدته فقط.",
    ),
    "simulation_hausse": (
        "Track B ne sert que les montants imprimés dans les grilles en vigueur : une hausse hypothétique n'est "
        "écrite dans aucune source.",
        "لا يقدّم المسار B إلا المبالغ المطبوعة في الجداول السارية: الزيادة الافتراضية غير منصوص عليها في أي مصدر.",
    ),
}
# Conventions-cadres reçues comme secteur : textes vérifiés sans grille de salaires (D110) → HORS_SCOPE qui les nomme.
_CADRE_GENERALE = (
    "La convention collective cadre (الاتفاقية المشتركة الإطارية, 1973, mise à jour 2022) ne fixe pas de grille de "
    "salaires : son article 50 renvoie les grilles aux conventions sectorielles. Indiquez la convention sectorielle "
    "de l'entreprise.",
    "الاتفاقية المشتركة الإطارية (1973، محيّنة 2022) لا تضبط جدول أجور: يحيل فصلها 50 جداول الأجور إلى "
    "الاتفاقيات المشتركة القطاعية. يُرجى تحديد الاتفاقية القطاعية للمؤسسة.",
)
CONVENTIONS_CADRES: dict[str, tuple[str, str]] = {
    "CONVENTION_CADRE_GENERALE": _CADRE_GENERALE,
    "CC-CADRE": _CADRE_GENERALE,
    "CONVENTION_CADRE_AGRICOLE": (
        "La convention collective cadre du secteur agricole (الاتفاقية المشتركة الإطارية في القطاع الفلاحي, 2015) "
        "ne fixe pas de grille de salaires : son article 14 renvoie aux grilles des conventions sectorielles. "
        "Le SMAG figure dans le référentiel SMIG/SMAG (décret n° 768 de 2022), mais l'opération smig ne sert "
        "aujourd'hui que le SMIG non agricole.",
        "الاتفاقية المشتركة الإطارية في القطاع الفلاحي (2015) لا تضبط جدول أجور: يحيل فصلها 14 إلى جداول الأجور "
        "في الاتفاقيات المشتركة القطاعية. الأجر الأدنى الفلاحي المضمون وارد في مرجع الأجر الأدنى (الأمر عدد 768 "
        "لسنة 2022)، لكن العملية smig لا تقدّم حاليا إلا الأجر الأدنى في القطاعات غير الفلاحية.",
    ),
}
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
        motif = OPERATIONS_HORS_PERIMETRE[op] or (
            "CNSS, IRPP, salaire net et conversions ne sont pas couverts par une source vérifiée.",
            "الضمان الاجتماعي والضريبة على الدخل والأجر الصافي غير مشمولة بمصدر مُتحقَّق منه.",
        )
        raise _RefusContrat(
            Refus.HORS_SCOPE,
            f"Opération {op!r} hors du périmètre Track B {version.split('.')[1]} (disponibles : {', '.join(OPERATIONS)}). "
            + motif[0],
            f"العملية {op!r} خارج نطاق المسار B (المتوفر: {', '.join(OPERATIONS)}). " + motif[1],
        )
    secteur = request["params"].get("secteur")
    if isinstance(secteur, str) and secteur in CONVENTIONS_CADRES:
        raise _RefusContrat(Refus.HORS_SCOPE, *CONVENTIONS_CADRES[secteur])

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
