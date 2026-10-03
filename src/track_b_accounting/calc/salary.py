"""Salaire de base conventionnel : grille sectorielle × catégorie × degré d'ancienneté × date (D4, D6)."""
from __future__ import annotations

import re
from decimal import Decimal

from .loaders import GRILLES, charger_grille
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


def _intervalles(grille: dict) -> list[tuple[int, int, int | None]]:
    """(degre, borne_basse, borne_haute|None) lus dans les libellés de la liste "degres"."""
    out = []
    for d in grille["degres"]:
        label = d["anciennete_label"]
        if m := _BORNES.match(label):
            out.append((d["degre"], int(m[1]), int(m[2])))
        elif m := _OUVERT.match(label):
            out.append((d["degre"], int(m[1]), None))
        else:
            raise Refus(Refus.SOURCE_MANQUANTE, f"Libellé de degré illisible : {label!r}.",
                        f"تسمية الدرجة غير مقروءة: {label!r}.")
    return out


def degre_from_anciennete(annees, secteur: str = "METALLURGIE_BATIMENT") -> int:
    """Degré dont l'intervalle contient strictement l'ancienneté.

    Les libellés du PDF (« 2/0 », « 4/2 », …, « 20+ ») font apparaître chaque borne intérieure
    (2, 4, …, 20) dans deux degrés sans dire lequel s'applique : ces valeurs exactes → Refus
    PARAM_INVALIDE (D6), plutôt que de choisir. 0 n'appartient qu'au degré 1.
    """
    a = _annees(annees)
    intervalles = _intervalles(charger_grille(secteur))
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
    cats = grille["categories"]
    if population not in cats:
        raise Refus(Refus.PARAM_INVALIDE,
                    f"Population inconnue : {population!r} (attendu : {', '.join(cats)}).",
                    f"فئة أعوان غير معروفة: {population!r} (المتوفر: {', '.join(cats)}).")
    attendues = set(cats[population])
    return [t for t in grille["grilles"] if set(t["valeurs"]) == attendues]


def table_applicable(secteur: str, population: str, date) -> dict:
    """Table de la population dont effective_date est la plus récente ≤ date."""
    jour = parse_date(date)
    tables = _tables_population(charger_grille(secteur), population)
    table = plus_recent_avant(tables, jour)
    if table is None:
        premiere = min((t["effective_date"] for t in tables), default="—")
        raise Refus(Refus.SOURCE_MANQUANTE,
                    f"Aucune grille {secteur}/{population} en vigueur au {jour.isoformat()} "
                    f"(première date d'effet disponible : {premiere}).",
                    f"لا يوجد جدول أجور {secteur}/{population} ساري المفعول بتاريخ {jour.isoformat()} "
                    f"(أول تاريخ نفاذ متوفر: {premiere}).")
    return table


def salaire_base(secteur: str, population: str, categorie, anciennete_annees, date,
                 unite_souhaitee: str | None = None) -> Result:
    """Salaire de base dans l'unité de la table (TND/mois ou TND/heure), sans aucune conversion."""
    grille = charger_grille(secteur)
    table = table_applicable(secteur, population, date)
    cat = str(categorie) if isinstance(categorie, int) and not isinstance(categorie, bool) else categorie
    if not isinstance(cat, str) or cat not in table["valeurs"]:
        raise Refus(Refus.PARAM_INVALIDE,
                    f"Catégorie inconnue : {categorie!r} pour {population} "
                    f"(attendu : {', '.join(grille['categories'][population])}).",
                    f"صنف غير معروف: {categorie!r} لفئة {population}.")
    if unite_souhaitee is not None and unite_souhaitee != table["unite"]:
        raise Refus(Refus.HORS_SCOPE,
                    f"La grille donne un montant en {table['unite']} ; la conversion en {unite_souhaitee} "
                    "n'est écrite dans aucune source vérifiée (nombre d'heures par mois non fixé).",
                    f"يعطي الجدول المبلغ بوحدة {table['unite']}؛ التحويل إلى {unite_souhaitee} "
                    "غير منصوص عليه في أي مصدر مُتحقَّق منه.")
    degre = degre_from_anciennete(anciennete_annees, secteur)
    montant = arrondi_millime(table["valeurs"][cat][degre - 1])
    return Result(
        montant=montant,
        unite=table["unite"],
        detail={
            "secteur": secteur,
            "population": population,
            "categorie": cat,
            "degre": degre,
            "anciennete_annees": _annees(anciennete_annees),
            "table_id": table["table_id"],
            "effective_date": table["effective_date"],
            "date_calcul": parse_date(date).isoformat(),
            "regime_hebdomadaire_heures": table.get("regime_hebdomadaire_heures"),
            "regles": "D6",
        },
        citations=[Citation(
            source_file=grille["_meta"]["source_file"],
            page=table["source_pdf_page"],
            article=None,
            data_file=GRILLES[secteur],
            decision_ref="D4",
        )],
    )
