"""Seul module qui lit des fichiers : JSON vérifiés de data/processed/ (jamais data/raw/).

Les nombres décimaux sont lus en Decimal (parse_float=Decimal) : aucun float n'entre dans les calculs.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

from .models import Refus

# calc -> track_b_accounting -> src -> <racine du dépôt>
REPO_ROOT = Path(__file__).resolve().parents[3]

SALARY_GRIDS_DIR = REPO_ROOT / "data" / "processed" / "salary_grids"
SMIG_FILE = "data/processed/smig_smag/smig_smag.json"
_DECISION_REF = re.compile(r"D([0-9]+)")


def decouvrir_grilles(dossier: Path = SALARY_GRIDS_DIR) -> dict[str, str]:
    """Registre des secteurs : {secteur_code: chemin du fichier}, découvert dans dossier/*.json.

    Un fichier est retenu s'il porte un _meta.secteur_code non vide et un _meta.decision_ref valide
    (« D » suivi d'un nombre) ; sinon il est ignoré et le secteur répond comme un secteur inconnu
    (SOURCE_MANQUANTE). Un code porté par plusieurs fichiers est ignoré (ambigu). Ordre : numéro de
    la décision, puis code, pour que la liste des secteurs disponibles ne dépende pas des noms de fichiers.
    Chemins relatifs à la racine du dépôt (cités dans data_file), absolus pour un dossier hors du dépôt.
    """
    trouves: dict[str, list[tuple[int, str]]] = {}
    for f in sorted(Path(dossier).glob("*.json")):
        try:
            meta = json.loads(f.read_text(encoding="utf-8")).get("_meta", {})
            code, ref = meta.get("secteur_code"), meta.get("decision_ref")
        except (OSError, json.JSONDecodeError, AttributeError):
            continue
        if not (_texte(code) and isinstance(ref, str) and (m := _DECISION_REF.fullmatch(ref))):
            continue
        try:
            chemin = f.resolve().relative_to(REPO_ROOT).as_posix()
        except ValueError:
            chemin = f.resolve().as_posix()
        trouves.setdefault(code, []).append((int(m[1]), chemin))
    uniques = {code: v[0] for code, v in trouves.items() if len(v) == 1}
    return {code: chemin for code, (_, chemin) in sorted(uniques.items(), key=lambda kv: (kv[1][0], kv[0]))}


def _invalide(chemin: str, raison: str) -> Refus:
    return Refus(
        Refus.SOURCE_MANQUANTE,
        f"Fichier de données {chemin} absent ou invalide : {raison}.",
        f"ملف البيانات {chemin} غير موجود أو غير صالح: {raison}.",
    )


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


# Registre découvert une fois au chargement du module (même objet partagé avec salary.py et primes.py).
GRILLES = decouvrir_grilles()


def _exiger_refus_declare(bloc: dict, objet: str, avec_anciennete: bool = False) -> None:
    """Refus déclaré dans les données (D8, D9) : source citée + messages FR/AR complets."""
    _exiger(
        _entier_positif(bloc["source_pdf_page"]) and _texte(bloc["source_article"]),
        f"{objet} : source_pdf_page et source_article attendus",
    )
    _exiger(_texte(bloc["message_fr"]) and _texte(bloc["message_ar"]), f"{objet} : message_fr et message_ar attendus")
    if avec_anciennete:
        _exiger(
            "{a}" in bloc["message_fr"] and "{a}" in bloc["message_ar"], f"{objet} : {{a}} attendu dans les messages"
        )


_BORNES = re.compile(r"^\s*(\d+)\s*-\s*(\d+)")
_OUVERT = re.compile(r"^\s*(\d+)\s*\+\s*$")


def bornes_degre(label: str) -> tuple[int, int | None] | None:
    """(borne basse, borne haute | None si tranche ouverte) lues dans un libellé de degré ; None si illisible."""
    if m := _BORNES.match(label):
        return int(m[1]), int(m[2])
    if m := _OUVERT.match(label):
        return int(m[1]), None
    return None


def _liste_textes(v) -> bool:
    return isinstance(v, list) and bool(v) and all(_texte(x) for x in v)


def _valider_art13_commun(bloc: dict, objet: str) -> None:
    """Règle au-delà du dernier degré implémentée (D10) : source, référence, hypothèses FR/AR, message de borne."""
    _exiger(
        _entier_positif(bloc["source_pdf_page"]) and _texte(bloc["source_article"]) and _texte(bloc["texte_source_ar"]),
        f"{objet} : source_pdf_page, source_article et texte_source_ar attendus",
    )
    _exiger(
        isinstance(bloc["decision_ref"], str) and re.fullmatch(r"D[0-9]+", bloc["decision_ref"]),
        f"{objet} : decision_ref attendue",
    )
    _exiger(
        _liste_textes(bloc["hypotheses_fr"])
        and _liste_textes(bloc["hypotheses_ar"])
        and len(bloc["hypotheses_fr"]) == len(bloc["hypotheses_ar"]),
        f"{objet} : hypotheses_fr/ar attendues",
    )
    _exiger(
        all(_texte(bloc[k]) and "{a}" in bloc[k] for k in ("message_borne_fr", "message_borne_ar")),
        f"{objet} : message_borne_fr/ar avec {{a}} attendus",
    )
    _exiger(
        _entier_positif(bloc["dernier_degre_atteint_a_annees"]), f"{objet} : dernier_degre_atteint_a_annees attendu"
    )


def _valider_au_dela(bloc: dict, pop: str, degres: list, cats: list) -> None:
    """Bloc au_dela_dernier_degre d'une population : refus déclaré (D8), dernier degré ouvert (D29)
    ou règle implémentée (D10)."""
    objet = f"au_dela_dernier_degre[{pop}]"
    regle = bloc.get("regle", "refus")
    if regle == "refus":
        _exiger(
            _entier_positif(bloc["anciennete_max_couverte_annees"]),
            f"{objet} : anciennete_max_couverte_annees entier > 0 attendu",
        )
        _exiger_refus_declare(bloc, objet, avec_anciennete=True)
        return
    if regle == "ouvert":
        # Dernier degré ouvert (« 30+ ») servi tel quel : ni plafond ni extrapolation, texte de la source cité.
        _exiger(
            _entier_positif(bloc["source_pdf_page"])
            and _texte(bloc["source_article"])
            and _texte(bloc["texte_source_ar"]),
            f"{objet} : source_pdf_page, source_article et texte_source_ar attendus",
        )
        lues = [bornes_degre(d["anciennete_label"]) for d in degres]
        bornes = [b for b in lues if b is not None]
        _exiger(
            bool(degres) and all(lues) and bornes[-1][1] is None, f"{objet} : dernier degré ouvert (« n+ ») attendu"
        )
        return
    _exiger(regle in ("ecart_cumule_biennal", "table_correspondance"), f"{objet} : règle inconnue {regle!r}")
    _valider_art13_commun(bloc, objet)
    lues = [bornes_degre(d["anciennete_label"]) for d in degres]
    bornes = [b for b in lues if b is not None]
    _exiger(
        len(degres) >= 2
        and all(lues)
        and bornes[-1][1] is None
        and bornes[-1][0] == bloc["dernier_degre_atteint_a_annees"],
        f"{objet} : dernier degré ouvert atteint à {bloc['dernier_degre_atteint_a_annees']} ans attendu",
    )
    if regle == "ecart_cumule_biennal":
        _exiger(_entier_positif(bloc["periode_annees"]), f"{objet} : periode_annees attendu")
        return
    # table_correspondance : chaque catégorie renvoie à une case de la grille, ou est refusée avec son texte.
    _exiger(_entier_positif(bloc["duree_au_dernier_degre_annees"]), f"{objet} : duree_au_dernier_degre_annees attendu")
    _exiger(
        all(
            _texte(bloc[k]) and "{a}" in bloc[k] and "{fin}" in bloc[k]
            for k in ("message_hors_fenetre_fr", "message_hors_fenetre_ar")
        ),
        f"{objet} : message_hors_fenetre_fr/ar avec {{a}} et {{fin}} attendus",
    )
    table, refusees = bloc["table_correspondance"], bloc["categories_refusees"]
    _exiger(
        not set(table) & set(refusees) and set(table) | set(refusees) == set(cats),
        f"{objet} : chaque catégorie doit avoir une case cible ou un refus",
    )
    for cat, e in table.items():
        _exiger(
            isinstance(e["degre"], int)
            and 1 <= e["degre"] <= len(degres)
            and e["categorie"] in cats
            and e["case_imprimee"] == f"{e['degre']}/{e['categorie']}",
            f"{objet}[{cat}] : case cible invalide",
        )
        bas, haut = bornes[e["degre"] - 1]
        duree = bloc["duree_au_dernier_degre_annees"] if haut is None else haut - bas
        _exiger(
            e["fenetre_annees"] == duree,
            f"{objet}[{cat}] : fenêtre {e['fenetre_annees']} ≠ tranche du degré cible ({duree})",
        )
    for cat, r in refusees.items():
        _exiger(
            _texte(r["message_fr"]) and _texte(r["message_ar"]), f"{objet} : refus de la catégorie {cat} sans texte"
        )


def population_de_table(data: dict, table: dict) -> str | None:
    """Population d'une table : son champ « population » s'il est présent (catégories identiques exigées),
    sinon la seule population dont les catégories sont exactement celles de la table. Plusieurs populations
    avec les mêmes catégories sans champ « population » : ambigu → None (table refusée par valider_grille)."""
    cles = set(table["valeurs"])
    if "population" in table:
        pop = table["population"]
        return pop if isinstance(pop, str) and set(data["categories"].get(pop, ())) == cles else None
    candidates = [pop for pop, cats in data["categories"].items() if set(cats) == cles]
    return candidates[0] if len(candidates) == 1 else None


def _valider_alias_et_hypotheses(data: dict, cats: dict) -> None:
    """alias_categories (ex. numérotation de l'annexe → clé imprimée dans la grille) et hypotheses_grille."""
    for pop, alias in data.get("alias_categories", {}).items():
        _exiger(pop in cats and isinstance(alias, dict), f"alias_categories[{pop}] : population inconnue")
        parents = set(data.get("sous_categories", {}).get(pop, {}).get("par_categorie", {}))
        for a, cle in alias.items():
            _exiger(
                _texte(a) and a not in cats[pop] and a not in parents,
                f"alias_categories[{pop}][{a!r}] : alias vide ou déjà utilisé comme catégorie",
            )
            _exiger(cle in cats[pop], f"alias_categories[{pop}][{a!r}] : catégorie cible {cle!r} inconnue")

    def _hyp(h, objet):
        _exiger(
            _liste_textes(h["fr"]) and _liste_textes(h["ar"]) and len(h["fr"]) == len(h["ar"]),
            f"{objet} : listes fr et ar non vides et de même longueur attendues",
        )

    for pop, h in data.get("hypotheses_grille", {}).items():
        _exiger(pop in cats, f"hypotheses_grille[{pop}] : population inconnue")
        _hyp(h, f"hypotheses_grille[{pop}]")
    # Hypothèses propres à une ligne de grille (ex. ligne combinée « III+II »), ajoutées seulement pour cette clé.
    for pop, par_cle in data.get("hypotheses_categories", {}).items():
        _exiger(pop in cats and isinstance(par_cle, dict), f"hypotheses_categories[{pop}] : population inconnue")
        for cle, h in par_cle.items():
            _exiger(cle in cats[pop], f"hypotheses_categories[{pop}][{cle!r}] : catégorie inconnue")
            _hyp(h, f"hypotheses_categories[{pop}][{cle!r}]")


def _valider_textes_prime(p: dict) -> None:
    """Textes affichés d'une prime : note_ar, hypotheses (FR/AR), libelles_groupes (un par colonne de montants)."""
    objet = f"prime {p['code']}"
    if "note_ar" in p:
        _exiger(_texte(p["note_ar"]), f"{objet} : note_ar non vide attendue")
    if "hypotheses" in p:
        h = p["hypotheses"]
        _exiger(
            _liste_textes(h["fr"]) and _liste_textes(h["ar"]) and len(h["fr"]) == len(h["ar"]),
            f"{objet} : hypotheses fr et ar non vides et de même longueur attendues",
        )
    if "libelles_groupes" in p:
        libelles = p["libelles_groupes"]
        _exiger(
            isinstance(libelles, dict) and all(_texte(lib["fr"]) and _texte(lib["ar"]) for lib in libelles.values()),
            f"{objet} : libelles_groupes fr et ar attendus",
        )
        for ligne in p.get("montants", []):
            _exiger(
                set(libelles) == set(ligne) - {"effective_date", "au_titre_de"},
                f"{objet} : libelles_groupes différents des colonnes de montants ({ligne['effective_date']})",
            )
        _exiger(bool(p.get("montants")), f"{objet} : libelles_groupes sans montants datés")


def _cellules_manquantes(table: dict, n_degres: int) -> set[tuple[str, int]]:
    """Cases illisibles d'une table (champ optionnel cellules_source_manquante) : {(catégorie, degré)}.
    Chaque case : catégorie de la table, degré existant, page, article, raison et messages FR/AR ; pas de doublon."""
    cases = table.get("cellules_source_manquante", [])
    _exiger(isinstance(cases, list), f"{table['table_id']} : cellules_source_manquante doit être une liste")
    out = set()
    for c in cases:
        objet = f"{table['table_id']}.cellules_source_manquante"
        _exiger(
            n_degres > 0
            and c["categorie"] in table["valeurs"]
            and isinstance(c["degre"], int)
            and not isinstance(c["degre"], bool)
            and 1 <= c["degre"] <= n_degres,
            f"{objet} : case inconnue",
        )
        _exiger(_texte(c["raison"]), f"{objet} : raison attendue")
        _exiger_refus_declare(c, objet)
        _exiger((c["categorie"], c["degre"]) not in out, f"{objet} : case en double")
        out.add((c["categorie"], c["degre"]))
    return out


def _entier_positif_ou_nul(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def _valider_anciennetes_refusees(data: dict, degres: dict) -> None:
    """Champ optionnel anciennetes_refusees : {population à degrés: [{au_dela_de, jusqu_a_inclus, refus déclaré}]}."""
    for pop, liste in data.get("anciennetes_refusees", {}).items():
        objet = f"anciennetes_refusees[{pop}]"
        _exiger(bool(degres.get(pop)) and isinstance(liste, list) and liste, f"{objet} : population à degrés attendue")
        for r in liste:
            _exiger(
                _entier_positif_ou_nul(r["au_dela_de"])
                and _entier_positif_ou_nul(r["jusqu_a_inclus"])
                and r["au_dela_de"] < r["jusqu_a_inclus"],
                f"{objet} : bornes entières croissantes attendues",
            )
            _exiger_refus_declare(r, objet, avec_anciennete=True)


def _valider_cases_refusees(data: dict, au_dela: dict) -> None:
    """Champ optionnel cases_refusees d'un bloc ecart_cumule_biennal : [{table_id, categorie, refus déclaré}]."""
    for pop, bloc in au_dela.items():
        if "cases_refusees" not in bloc:
            continue
        objet = f"au_dela_dernier_degre[{pop}].cases_refusees"
        _exiger(
            bloc.get("regle") == "ecart_cumule_biennal"
            and isinstance(bloc["cases_refusees"], list)
            and bloc["cases_refusees"],
            f"{objet} : liste non vide, règle ecart_cumule_biennal attendue",
        )
        tables = {t["table_id"] for t in data["grilles"] if population_de_table(data, t) == pop}
        for r in bloc["cases_refusees"]:
            _exiger(r["table_id"] in tables and r["categorie"] in data["categories"][pop], f"{objet} : case inconnue")
            _exiger_refus_declare(r, objet)


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
            _exiger(
                isinstance(liste, list) and all("degre" in d and "anciennete_label" in d for d in liste),
                f"degres[{pop}] : liste de degrés attendue",
            )
        # Ce que dit la source au-delà du dernier degré (D8, D10) : obligatoire pour toute population à degrés.
        au_dela = data["au_dela_dernier_degre"]
        _exiger(
            isinstance(au_dela, dict) and set(au_dela) == {p for p, liste in degres.items() if liste},
            "au_dela_dernier_degre : un bloc par population à degrés attendu",
        )
        for pop, bloc in au_dela.items():
            _valider_au_dela(bloc, pop, degres[pop], cats[pop])
        for pop, sc in data.get("sous_categories", {}).items():
            _exiger(pop in cats and _entier_positif(sc["source_pdf_page"]), f"sous_categories[{pop}] invalide")
            for cat, sous in sc["par_categorie"].items():
                _exiger(cat not in cats[pop] and sous, f"sous_categories[{pop}][{cat}] invalide")
                for s in sous.values():
                    _exiger(
                        s["cle"] in cats[pop] and _texte(s["libelle_fr"]) and _texte(s["libelle_ar"]),
                        f"sous_categories[{pop}][{cat}] : cle, libelle_fr et libelle_ar attendus",
                    )
        _valider_alias_et_hypotheses(data, cats)
        for pop, bloc in data.get("populations_non_couvertes", {}).items():
            _exiger(pop not in cats, f"population {pop} à la fois couverte et non couverte")
            _exiger_refus_declare(bloc, f"populations_non_couvertes[{pop}]")
        # Secteur dont les tables ne sont pas encore transcrites : déclaré explicitement, aucune table.
        transcrites = data["_meta"].get("tables_transcrites", True)
        _exiger(bool(data["grilles"]) == (transcrites is True), "grilles : tables_transcrites incohérent")
        for t in data["grilles"]:
            for k in ("table_id", "effective_date", "source_pdf_page", "unite", "valeurs"):
                _exiger(k in t, f"{t.get('table_id', '?')} : clé {k} manquante")
            if "valide_jusqu_au" in t:
                # Dernier jour de validité de la table (ex. grille révisée par un avenant absent des sources).
                fin = t["valide_jusqu_au"]
                _exiger(
                    isinstance(fin, dict)
                    and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(fin.get("date", "")))
                    and fin["date"] >= t["effective_date"],
                    f"{t['table_id']} : valide_jusqu_au.date invalide",
                )
                _exiger_refus_declare(fin, f"{t['table_id']}.valide_jusqu_au")
            pop = population_de_table(data, t)
            _exiger(
                pop is not None,
                f"{t['table_id']} : population absente, inconnue ou ambiguë "
                "(champ population obligatoire si plusieurs populations ont ces catégories)",
            )
            manquantes = _cellules_manquantes(t, len(degres[pop]))
            for cat, vals in t["valeurs"].items():
                if degres[pop]:
                    _exiger(
                        isinstance(vals, list) and len(vals) == len(degres[pop]),
                        f"{t['table_id']} cat. {cat} : {len(vals)} degrés",
                    )
                    # null seulement pour une case déclarée illisible, et toute case déclarée vaut null.
                    _exiger(
                        all(
                            isinstance(v, Decimal) if (cat, i) not in manquantes else v is None
                            for i, v in enumerate(vals, 1)
                        ),
                        f"{t['table_id']} cat. {cat} : montant non décimal",
                    )
                else:
                    _exiger(isinstance(vals, Decimal), f"{t['table_id']} cat. {cat} : montant unique décimal attendu")
        _valider_anciennetes_refusees(data, degres)
        _valider_cases_refusees(data, au_dela)
        for p in data.get("primes", []):
            for k in ("code", "source_article", "source_pdf_page", "unite"):
                _exiger(k in p, f"prime {p.get('code', '?')} : clé {k} manquante")
            _valider_textes_prime(p)
        for code, bloc in data.get("primes_non_couvertes", {}).items():
            _exiger(
                code not in {p["code"] for p in data.get("primes", [])}, f"prime {code} à la fois servie et refusée"
            )
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
        raise Refus(
            Refus.SOURCE_MANQUANTE,
            f"Référence de vérification ({champ}) absente ou invalide pour {objet} ({ref!r}) : montant non citable.",
            f"مرجع التحقق ({champ}) غير موجود أو غير صالح لـ {objet}: لا يمكن الاستشهاد بالمبلغ.",
        )
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


def charger_grille(secteur: Any) -> dict:
    """Grille vérifiée du secteur. Secteur absent → PARAM_INVALIDE ; inconnu → SOURCE_MANQUANTE."""
    if not _texte(secteur):
        dispo = ", ".join(secteurs_disponibles())
        raise Refus(
            Refus.PARAM_INVALIDE,
            f"Secteur absent ou invalide : {secteur!r} (disponibles : {dispo}).",
            f"القطاع غير موجود أو غير صالح: {secteur!r} (المتوفر: {dispo}).",
        )
    if secteur not in GRILLES:
        raise _refus_sans_grille(secteur)
    return _charger_grille(secteur)


def _refus_sans_grille(secteur: str) -> Refus:
    dispo = ", ".join(secteurs_disponibles())
    return Refus(
        Refus.SOURCE_MANQUANTE,
        f"Aucune grille vérifiée pour le secteur {secteur!r} (disponibles : {dispo}).",
        f"لا يوجد جدول أجور مُتحقَّق منه للقطاع {secteur!r} (المتوفر: {dispo}).",
    )


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
