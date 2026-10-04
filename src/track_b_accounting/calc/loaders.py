"""Seul module qui lit des fichiers : JSON vérifiés de data/processed/ (jamais data/raw/).

Les nombres décimaux sont lus en Decimal (parse_float=Decimal) : aucun float n'entre dans les calculs.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from .models import Refus

# calc -> track_b_accounting -> src -> <racine du dépôt>
REPO_ROOT = Path(__file__).resolve().parents[3]

GRILLES = {
    "METALLURGIE_BATIMENT": "data/processed/salary_grids/metallurgie_batiment.json",
}
SMIG_FILE = "data/processed/smig_smag/smig_smag.json"


def _invalide(chemin: str, raison: str) -> Refus:
    return Refus(Refus.SOURCE_MANQUANTE,
                 f"Fichier de données {chemin} absent ou invalide : {raison}.",
                 f"ملف البيانات {chemin} غير موجود أو غير صالح: {raison}.")


def _lire(chemin: str) -> dict:
    try:
        texte = (REPO_ROOT / chemin).read_text(encoding="utf-8")
    except OSError as e:
        raise _invalide(chemin, f"lecture impossible ({e.__class__.__name__})") from e
    try:
        return json.loads(texte, parse_float=Decimal)
    except json.JSONDecodeError as e:
        raise _invalide(chemin, "JSON mal formé") from e


class _SchemaInvalide(Exception):
    pass


def _exiger(condition, message: str = "schéma inattendu") -> None:
    if not condition:
        raise _SchemaInvalide(message)


def valider_grille(data: dict, chemin: str) -> dict:
    """Validation minimale du schéma d'une grille sectorielle."""
    try:
        _exiger(data["_meta"]["source_file"] and data["_meta"]["secteur_code"])
        degres = data["degres"]
        _exiger(degres and all("degre" in d and "anciennete_label" in d for d in degres))
        cats = data["categories"]
        _exiger(cats and all(isinstance(v, list) and v for v in cats.values()))
        _exiger(data["grilles"])
        for t in data["grilles"]:
            for k in ("table_id", "effective_date", "source_pdf_page", "unite", "valeurs"):
                _exiger(k in t, f"{t.get('table_id', '?')} : clé {k} manquante")
            for cat, vals in t["valeurs"].items():
                _exiger(len(vals) == len(degres), f"{t['table_id']} cat. {cat} : {len(vals)} degrés")
                _exiger(all(isinstance(v, Decimal) for v in vals), f"{t['table_id']} cat. {cat} : montant non décimal")
        for p in data.get("primes", []):
            for k in ("code", "source_article", "source_pdf_page", "unite"):
                _exiger(k in p, f"prime {p.get('code', '?')} : clé {k} manquante")
    except (_SchemaInvalide, KeyError, TypeError) as e:
        raise _invalide(chemin, str(e) or "schéma inattendu") from e
    return data


def valider_smig(data: dict, chemin: str) -> dict:
    try:
        _exiger(data["_meta"]["source_file"])
        bloc = data["smig_non_agricole"]
        _exiger(bloc["decree"]["effective_date"] and bloc["decree"]["number"])
        _exiger(bloc["bareme"])
        for ligne in bloc["bareme"]:
            _exiger({"mode_remuneration", "regime_hebdomadaire_heures", "montant"} <= set(ligne))
            _exiger(isinstance(ligne["montant"], Decimal), "montant non décimal")
    except (_SchemaInvalide, KeyError, TypeError) as e:
        raise _invalide(chemin, str(e) or "schéma inattendu") from e
    return data


def _exiger_ref(ref, champ: str, objet: str) -> str:
    """Référence docs/DECISIONS.md (« Dn ») lue dans les données.

    Absente ou mal formée → Refus SOURCE_MANQUANTE : jamais de citation avec une référence inventée.
    """
    if not isinstance(ref, str) or not re.fullmatch(r"D[0-9]+", ref):
        raise Refus(Refus.SOURCE_MANQUANTE,
                    f"Référence de vérification ({champ}) absente ou invalide pour {objet} ({ref!r}) : "
                    "montant non citable.",
                    f"مرجع التحقق ({champ}) غير موجود أو غير صالح لـ {objet}: لا يمكن الاستشهاد بالمبلغ.")
    return ref


def decision_ref(grille: dict, secteur: str) -> str:
    """Référence de vérification d'une grille sectorielle : _meta.decision_ref."""
    return _exiger_ref(grille.get("_meta", {}).get("decision_ref"), "_meta.decision_ref", f"le secteur {secteur!r}")


def decision_ref_smig(bloc: dict) -> str:
    """Référence de vérification du barème SMIG : smig_non_agricole.decision_ref (par section, cf. D6)."""
    return _exiger_ref(bloc.get("decision_ref"), "smig_non_agricole.decision_ref", "le barème SMIG")


@lru_cache(maxsize=None)
def charger_grille(secteur: str) -> dict:
    if secteur not in GRILLES:
        raise Refus(Refus.SOURCE_MANQUANTE,
                    f"Aucune grille vérifiée pour le secteur {secteur!r} (disponibles : {', '.join(GRILLES)}).",
                    f"لا يوجد جدول أجور مُتحقَّق منه للقطاع {secteur!r} (المتوفر: {', '.join(GRILLES)}).")
    return valider_grille(_lire(GRILLES[secteur]), GRILLES[secteur])


@lru_cache(maxsize=None)
def charger_smig() -> dict:
    return valider_smig(_lire(SMIG_FILE), SMIG_FILE)
