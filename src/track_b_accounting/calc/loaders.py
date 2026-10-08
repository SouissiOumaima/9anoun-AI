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
    "BATIMENT_TRAVAUX_PUBLICS": "data/processed/salary_grids/batiment_travaux_publics.json",
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


def _entier_positif(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v > 0


def _texte(v) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _exiger_refus_declare(bloc: dict, objet: str, avec_anciennete: bool = False) -> None:
    """Refus déclaré dans les données (D8, D9) : source citée + messages FR/AR complets."""
    _exiger(_entier_positif(bloc["source_pdf_page"]) and _texte(bloc["source_article"]),
            f"{objet} : source_pdf_page et source_article attendus")
    _exiger(_texte(bloc["message_fr"]) and _texte(bloc["message_ar"]), f"{objet} : message_fr et message_ar attendus")
    if avec_anciennete:
        _exiger("{a}" in bloc["message_fr"] and "{a}" in bloc["message_ar"], f"{objet} : {{a}} attendu dans les messages")


def population_de_table(data: dict, table: dict) -> str | None:
    """Population dont les catégories sont exactement celles de la table."""
    cles = set(table["valeurs"])
    return next((pop for pop, cats in data["categories"].items() if set(cats) == cles), None)


def valider_grille(data: dict, chemin: str) -> dict:
    """Validation minimale du schéma d'une grille sectorielle (degrés et refus déclarés par population)."""
    try:
        _exiger(data["_meta"]["source_file"] and data["_meta"]["secteur_code"])
        cats = data["categories"]
        _exiger(cats and all(isinstance(v, list) and v for v in cats.values()))
        # Degrés par population ; liste vide = population sans degré d'ancienneté.
        degres = data["degres"]
        _exiger(isinstance(degres, dict) and set(degres) == set(cats), "degres : une liste par population attendue")
        for pop, liste in degres.items():
            _exiger(isinstance(liste, list) and all("degre" in d and "anciennete_label" in d for d in liste),
                    f"degres[{pop}] : liste de degrés attendue")
        # Ce que dit la source au-delà du dernier degré (D8) : obligatoire pour toute population à degrés.
        au_dela = data["au_dela_dernier_degre"]
        _exiger(isinstance(au_dela, dict) and set(au_dela) == {p for p, l in degres.items() if l},
                "au_dela_dernier_degre : un bloc par population à degrés attendu")
        for pop, bloc in au_dela.items():
            _exiger(_entier_positif(bloc["anciennete_max_couverte_annees"]),
                    f"au_dela_dernier_degre[{pop}] : anciennete_max_couverte_annees entier > 0 attendu")
            _exiger_refus_declare(bloc, f"au_dela_dernier_degre[{pop}]", avec_anciennete=True)
        for pop, sc in data.get("sous_categories", {}).items():
            _exiger(pop in cats and _entier_positif(sc["source_pdf_page"]), f"sous_categories[{pop}] invalide")
            for cat, sous in sc["par_categorie"].items():
                _exiger(cat not in cats[pop] and sous, f"sous_categories[{pop}][{cat}] invalide")
                for s in sous.values():
                    _exiger(s["cle"] in cats[pop] and _texte(s["libelle_fr"]) and _texte(s["libelle_ar"]),
                            f"sous_categories[{pop}][{cat}] : cle, libelle_fr et libelle_ar attendus")
        for pop, bloc in data.get("populations_non_couvertes", {}).items():
            _exiger(pop not in cats, f"population {pop} à la fois couverte et non couverte")
            _exiger_refus_declare(bloc, f"populations_non_couvertes[{pop}]")
        # Secteur dont les tables ne sont pas encore transcrites : déclaré explicitement, aucune table.
        transcrites = data["_meta"].get("tables_transcrites", True)
        _exiger(bool(data["grilles"]) == (transcrites is True), "grilles : tables_transcrites incohérent")
        for t in data["grilles"]:
            for k in ("table_id", "effective_date", "source_pdf_page", "unite", "valeurs"):
                _exiger(k in t, f"{t.get('table_id', '?')} : clé {k} manquante")
            pop = population_de_table(data, t)
            _exiger(pop is not None, f"{t['table_id']} : catégories sans population")
            for cat, vals in t["valeurs"].items():
                if degres[pop]:
                    _exiger(isinstance(vals, list) and len(vals) == len(degres[pop]),
                            f"{t['table_id']} cat. {cat} : {len(vals)} degrés")
                    _exiger(all(isinstance(v, Decimal) for v in vals), f"{t['table_id']} cat. {cat} : montant non décimal")
                else:
                    _exiger(isinstance(vals, Decimal), f"{t['table_id']} cat. {cat} : montant unique décimal attendu")
        for p in data.get("primes", []):
            for k in ("code", "source_article", "source_pdf_page", "unite"):
                _exiger(k in p, f"prime {p.get('code', '?')} : clé {k} manquante")
        for code, bloc in data.get("primes_non_couvertes", {}).items():
            _exiger(code not in {p["code"] for p in data.get("primes", [])}, f"prime {code} à la fois servie et refusée")
            _exiger_refus_declare(bloc, f"primes_non_couvertes[{code}]")
    except (_SchemaInvalide, KeyError, TypeError, AttributeError) as e:
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


def secteurs_disponibles() -> list[str]:
    """Secteurs dont les tables sont transcrites et vérifiées (un secteur enregistré sans table n'en fait pas partie)."""
    out = []
    for s in GRILLES:
        try:
            if _charger_grille(s)["_meta"].get("tables_transcrites", True) is True:
                out.append(s)
        except Refus:
            pass
    return out


def charger_grille(secteur) -> dict:
    """Grille vérifiée du secteur. Secteur absent → PARAM_INVALIDE ; inconnu → SOURCE_MANQUANTE."""
    if not _texte(secteur):
        dispo = ", ".join(secteurs_disponibles())
        raise Refus(Refus.PARAM_INVALIDE,
                    f"Secteur absent ou invalide : {secteur!r} (disponibles : {dispo}).",
                    f"القطاع غير موجود أو غير صالح: {secteur!r} (المتوفر: {dispo}).")
    if secteur not in GRILLES:
        raise _refus_sans_grille(secteur)
    return _charger_grille(secteur)


def _refus_sans_grille(secteur: str) -> Refus:
    dispo = ", ".join(secteurs_disponibles())
    return Refus(Refus.SOURCE_MANQUANTE,
                 f"Aucune grille vérifiée pour le secteur {secteur!r} (disponibles : {dispo}).",
                 f"لا يوجد جدول أجور مُتحقَّق منه للقطاع {secteur!r} (المتوفر: {dispo}).")


def exiger_tables_transcrites(grille: dict, secteur: str) -> None:
    """Secteur enregistré dont les tables ne sont pas encore transcrites : même refus qu'un secteur inconnu."""
    if grille["_meta"].get("tables_transcrites", True) is not True:
        raise _refus_sans_grille(secteur)


@lru_cache(maxsize=None)
def _charger_grille(secteur: str) -> dict:
    return valider_grille(_lire(GRILLES[secteur]), GRILLES[secteur])


@lru_cache(maxsize=None)
def charger_smig() -> dict:
    return valider_smig(_lire(SMIG_FILE), SMIG_FILE)
