"""Salaire de base conventionnel : grille sectorielle × population × catégorie × degré d'ancienneté × date (D4, D6, D9)."""
from __future__ import annotations

import re
from decimal import Decimal

from .loaders import GRILLES, charger_grille, decision_ref, exiger_tables_transcrites
from .models import Citation, Refus, Result, arrondi_millime, parse_date, plus_recent_avant

_BORNES = re.compile(r"^\s*(\d+)\s*-\s*(\d+)")
_OUVERT = re.compile(r"^\s*(\d+)\s*\+\s*$")


def _annees(anciennete) -> Decimal:
    if isinstance(anciennete, bool) or not isinstance(anciennete, (int, float, Decimal)):
        raise Refus(Refus.PARAM_INVALIDE, f"Ancienneté invalide : {anciennete!r} (nombre d'années attendu).",
                    f"أقدمية غير صالحة: {anciennete!r} (المطلوب عدد السنوات).")
    a = anciennete if isinstance(anciennete, Decimal) else Decimal(str(anciennete))
    if not a.is_finite() or a < 0:
        raise Refus(Refus.PARAM_INVALIDE, f"Ancienneté invalide : {anciennete!r} (doit être un nombre ≥ 0).",
                    f"أقدمية غير صالحة: {anciennete!r} (يجب أن تكون عددًا موجبًا أو صفرًا).")
    return a


def _intervalles(degres: list[dict]) -> list[tuple[int, int, int | None]]:
    """(degre, borne_basse, borne_haute|None) lus dans les libellés d'une liste de degrés."""
    out = []
    for d in degres:
        label = d["anciennete_label"]
        if m := _BORNES.match(label):
            out.append((d["degre"], int(m[1]), int(m[2])))
        elif m := _OUVERT.match(label):
            out.append((d["degre"], int(m[1]), None))
        else:
            raise Refus(Refus.SOURCE_MANQUANTE, f"Libellé de degré illisible : {label!r}.",
                        f"تسمية الدرجة غير مقروءة: {label!r}.")
    return out


def _population(grille: dict, population) -> str:
    """Population couverte par la grille ; population déclarée non couverte → refus lu dans le JSON (D9)."""
    if isinstance(population, str) and population in grille.get("populations_non_couvertes", {}):
        bloc = grille["populations_non_couvertes"][population]
        raise Refus(Refus.SOURCE_MANQUANTE, bloc["message_fr"], bloc["message_ar"])
    cats = grille["categories"]
    if not isinstance(population, str) or population not in cats:
        raise Refus(Refus.PARAM_INVALIDE,
                    f"Population inconnue : {population!r} (attendu : {', '.join(cats)}).",
                    f"فئة أعوان غير معروفة: {population!r} (المتوفر: {', '.join(cats)}).")
    return population


def _sous_categories(grille: dict, population: str) -> dict:
    return grille.get("sous_categories", {}).get(population, {}).get("par_categorie", {})


def _categories_demandables(grille: dict, population: str) -> list[str]:
    """Catégories telles que la requête les nomme : une catégorie à sous-catégories n'apparaît qu'une fois."""
    parent = {s["cle"]: cat for cat, sous in _sous_categories(grille, population).items() for s in sous.values()}
    out = []
    for c in grille["categories"][population]:
        c = parent.get(c, c)
        if c not in out:
            out.append(c)
    return out


def _cle_categorie(grille: dict, population: str, categorie, sous_categorie) -> tuple[str, str, dict]:
    """(catégorie demandée, clé de la grille ex. "4" ou "6_I", libellés de la sous-catégorie) (D9)."""
    cat = str(categorie) if isinstance(categorie, int) and not isinstance(categorie, bool) else categorie
    sous = _sous_categories(grille, population)
    if isinstance(cat, str) and cat in sous:
        valeurs = ", ".join(sous[cat])
        if sous_categorie is None:
            raise Refus(Refus.PARAM_INVALIDE,
                        f"La catégorie {cat} ({population}) comporte des sous-catégories : sous_categorie "
                        f"obligatoire (valeurs possibles : {valeurs}).",
                        f"الصنف {cat} ({population}) يتضمن أصنافًا فرعية: يجب تحديد sous_categorie "
                        f"(القيم الممكنة: {valeurs}).")
        if not isinstance(sous_categorie, str) or sous_categorie not in sous[cat]:
            raise Refus(Refus.PARAM_INVALIDE,
                        f"Sous-catégorie inconnue : {sous_categorie!r} pour la catégorie {cat} ({population}) "
                        f"(valeurs possibles : {valeurs}).",
                        f"صنف فرعي غير معروف: {sous_categorie!r} للصنف {cat} ({population}) "
                        f"(القيم الممكنة: {valeurs}).")
        s = sous[cat][sous_categorie]
        return cat, s["cle"], {"sous_categorie": sous_categorie,
                               "libelle_fr": s["libelle_fr"], "libelle_ar": s["libelle_ar"]}
    demandables = _categories_demandables(grille, population)
    if not isinstance(cat, str) or cat not in demandables:
        raise Refus(Refus.PARAM_INVALIDE,
                    f"Catégorie inconnue : {categorie!r} pour {population} (attendu : {', '.join(demandables)}).",
                    f"صنف غير معروف: {categorie!r} لفئة {population}.")
    if sous_categorie is not None:
        raise Refus(Refus.PARAM_INVALIDE,
                    f"Sous-catégorie {sous_categorie!r} non prévue : la catégorie {cat} ({population}) "
                    "n'a pas de sous-catégorie.",
                    f"الصنف الفرعي {sous_categorie!r} غير متوقع: الصنف {cat} ({population}) لا يتضمن أصنافًا فرعية.")
    return cat, cat, {}


def degre_from_anciennete(annees, secteur=None, population=None) -> int:
    """Degré dont l'intervalle contient strictement l'ancienneté (degrés propres à chaque population).

    Les libellés du PDF (« 2/0 », « 4/2 », …, « 20+ ») font apparaître chaque borne intérieure
    (2, 4, …, 20) dans deux degrés sans dire lequel s'applique : ces valeurs exactes → Refus
    PARAM_INVALIDE (D6), plutôt que de choisir. 0 n'appartient qu'au degré 1.
    Au-delà du dernier degré, la règle de la convention n'est pas implémentée : ancienneté ≥
    au_dela_dernier_degre[population].anciennete_max_couverte_annees → Refus SOURCE_MANQUANTE,
    messages FR/AR lus dans le JSON, où seul {a} est remplacé par l'ancienneté (D8, D9).
    Aucun secteur par défaut : secteur absent → Refus PARAM_INVALIDE.
    """
    grille = charger_grille(secteur)
    pop = _population(grille, population)
    degres = grille["degres"][pop]
    if not degres:
        raise Refus(Refus.PARAM_INVALIDE, f"La grille {secteur}/{pop} n'a pas de degré d'ancienneté.",
                    f"جدول الأجور {secteur}/{pop} لا يتضمن درجات أقدمية.")
    a = _annees(annees)
    au_dela = grille["au_dela_dernier_degre"][pop]
    if a >= au_dela["anciennete_max_couverte_annees"]:
        raise Refus(Refus.SOURCE_MANQUANTE, au_dela["message_fr"].replace("{a}", str(a)),
                    au_dela["message_ar"].replace("{a}", str(a)))
    intervalles = _intervalles(degres)
    contenants = [deg for deg, bas, haut in intervalles if bas <= a and (haut is None or a <= haut)]
    if len(contenants) == 1:
        return contenants[0]
    if len(contenants) > 1:
        raise Refus(Refus.PARAM_INVALIDE,
                    f"Ancienneté de {a} ans = borne commune aux degrés {contenants} : la grille ne précise "
                    "pas lequel s'applique. Indiquer l'ancienneté exacte (ex. 2 ans et 1 jour).",
                    f"أقدمية {a} سنة تقع على الحد المشترك بين الدرجات {contenants} ولا يحدد الجدول أيّها "
                    "ينطبق. يرجى تحديد الأقدمية بدقة.")
    raise Refus(Refus.SOURCE_MANQUANTE, f"Aucun degré de la grille ne couvre {a} ans.",
                f"لا توجد درجة في الجدول تغطي {a} سنة.")


def _tables_population(grille: dict, population: str) -> list[dict]:
    attendues = set(grille["categories"][population])
    return [t for t in grille["grilles"] if set(t["valeurs"]) == attendues]


def table_applicable(secteur, population, date) -> dict:
    """Table de la population dont effective_date est la plus récente ≤ date."""
    jour = parse_date(date)
    grille = charger_grille(secteur)
    pop = _population(grille, population)
    exiger_tables_transcrites(grille, secteur)
    tables = _tables_population(grille, pop)
    table = plus_recent_avant(tables, jour)
    if table is None:
        premiere = min((t["effective_date"] for t in tables), default="—")
        raise Refus(Refus.SOURCE_MANQUANTE,
                    f"Aucune grille {secteur}/{population} en vigueur au {jour.isoformat()} "
                    f"(première date d'effet disponible : {premiere}).",
                    f"لا يوجد جدول أجور {secteur}/{population} ساري المفعول بتاريخ {jour.isoformat()} "
                    f"(أول تاريخ نفاذ متوفر: {premiere}).")
    return table


def salaire_base(secteur=None, population=None, categorie=None, anciennete_annees=None, date=None,
                 unite_souhaitee: str | None = None, sous_categorie: str | None = None) -> Result:
    """Salaire de base dans l'unité de la table (TND/mois ou TND/heure), sans aucune conversion.

    anciennete_annees : obligatoire pour une population à degrés, refusée pour une population sans degré.
    sous_categorie : obligatoire pour une catégorie à sous-catégories, refusée sinon (D9).
    """
    grille = charger_grille(secteur)
    pop = _population(grille, population)
    cat, cle, info_sous = _cle_categorie(grille, pop, categorie, sous_categorie)
    degre = None
    if grille["degres"][pop]:
        if anciennete_annees is None:
            raise Refus(Refus.PARAM_INVALIDE,
                        f"anciennete_annees obligatoire pour {secteur}/{pop} (grille à degrés d'ancienneté).",
                        f"anciennete_annees إلزامي لـ {secteur}/{pop} (جدول بدرجات أقدمية).")
        degre = degre_from_anciennete(anciennete_annees, secteur, pop)
    elif anciennete_annees is not None:
        raise Refus(Refus.PARAM_INVALIDE,
                    f"anciennete_annees non prévue : la grille {secteur}/{pop} n'a pas de degré d'ancienneté.",
                    f"anciennete_annees غير متوقع: جدول الأجور {secteur}/{pop} لا يتضمن درجات أقدمية.")
    table = table_applicable(secteur, pop, date)
    if unite_souhaitee is not None and unite_souhaitee != table["unite"]:
        raise Refus(Refus.HORS_SCOPE,
                    f"La grille donne un montant en {table['unite']} ; la conversion en {unite_souhaitee} "
                    "n'est écrite dans aucune source vérifiée (nombre d'heures par mois non fixé).",
                    f"يعطي الجدول المبلغ بوحدة {table['unite']}؛ التحويل إلى {unite_souhaitee} "
                    "غير منصوص عليه في أي مصدر مُتحقَّق منه.")
    ref = decision_ref(grille, secteur)
    valeur = table["valeurs"][cle] if degre is None else table["valeurs"][cle][degre - 1]
    detail = {"secteur": secteur, "population": pop, "categorie": cat, **info_sous}
    if degre is not None:
        detail.update(degre=degre, anciennete_annees=_annees(anciennete_annees))
    detail.update({
        "table_id": table["table_id"],
        "effective_date": table["effective_date"],
        "date_calcul": parse_date(date).isoformat(),
        "regime_hebdomadaire_heures": table.get("regime_hebdomadaire_heures"),
        "regles": "D6",
    })
    return Result(
        montant=arrondi_millime(valeur),
        unite=table["unite"],
        detail=detail,
        citations=[Citation(
            source_file=grille["_meta"]["source_file"],
            page=table["source_pdf_page"],
            article=None,
            data_file=GRILLES[secteur],
            decision_ref=ref,
        )],
    )
