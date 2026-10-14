"""Salaire de base conventionnel : grille sectorielle × population × catégorie × degré d'ancienneté × date
(D4, D6, D9), et règle de l'article 13 au-delà du dernier degré (D10)."""
from __future__ import annotations

import math
from decimal import Decimal

from .loaders import (GRILLES, bornes_degre, charger_grille, decision_ref, exiger_tables_transcrites,
                      population_de_table)
from .models import Citation, Refus, Result, arrondi_millime, parse_date, plus_recent_avant


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
        bornes = bornes_degre(label)
        if bornes is None:
            raise Refus(Refus.SOURCE_MANQUANTE, f"Libellé de degré illisible : {label!r}.",
                        f"تسمية الدرجة غير مقروءة: {label!r}.")
        out.append((d["degre"], *bornes))
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
    alias = grille.get("alias_categories", {}).get(population, {})
    info_alias = {}
    if isinstance(cat, str) and cat not in demandables and cat in alias:
        # Alias déclaré dans le JSON (ex. numérotation de l'annexe → clé imprimée dans la grille).
        cat, info_alias = alias[cat], {"categorie_demandee": cat}
    if not isinstance(cat, str) or cat not in demandables:
        attendu = ", ".join(demandables) + (f" ; alias : {', '.join(alias)}" if alias else "")
        raise Refus(Refus.PARAM_INVALIDE,
                    f"Catégorie inconnue : {categorie!r} pour {population} (attendu : {attendu}).",
                    f"صنف غير معروف: {categorie!r} لفئة {population}.")
    if sous_categorie is not None:
        raise Refus(Refus.PARAM_INVALIDE,
                    f"Sous-catégorie {sous_categorie!r} non prévue : la catégorie {cat} ({population}) "
                    "n'a pas de sous-catégorie.",
                    f"الصنف الفرعي {sous_categorie!r} غير متوقع: الصنف {cat} ({population}) لا يتضمن أصنافًا فرعية.")
    return cat, cat, info_alias


def degre_from_anciennete(annees, secteur=None, population=None) -> int:
    """Degré de la grille dont l'intervalle contient strictement l'ancienneté (degrés propres à chaque population).

    Les libellés du PDF (« 2/0 », « 4/2 », …, « 20+ ») font apparaître chaque borne intérieure
    (2, 4, …, 20) dans deux degrés sans dire lequel s'applique : ces valeurs exactes → Refus
    PARAM_INVALIDE (D6), plutôt que de choisir. 0 n'appartient qu'au degré 1.
    Le dernier degré est ouvert (« 20+ ») : ce qui s'applique au-delà (article 13) est traité par
    regle_au_dela_dernier_degre (D10). Si la population déclare seulement un refus (regle « refus »),
    toute ancienneté ≥ anciennete_max_couverte_annees est refusée ici (SOURCE_MANQUANTE, D8).
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
    if au_dela.get("regle", "refus") == "refus" and a >= au_dela["anciennete_max_couverte_annees"]:
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


def _texte_art13(gabarit: str, **valeurs) -> str:
    """Seuls {a}, {categorie}, {case} et {fin} sont remplacés dans les textes lus dans le JSON (D10)."""
    for k, v in valeurs.items():
        gabarit = gabarit.replace("{" + k + "}", str(v))
    return gabarit


def regle_au_dela_dernier_degre(grille: dict, population: str, cle: str, annees) -> dict | None:
    """Règle de l'article 13 au-delà du dernier degré, ou None si elle ne s'applique pas (D10).

    - « ecart_cumule_biennal » (métallurgie, p.9) : n = ⌊(a − âge du dernier degré) / période⌋ paliers ;
      n = 0 → None (dernier degré simple). Palier exact (22, 24, 26… ans) → PARAM_INVALIDE, comme les bornes de D6.
    - « table_correspondance » (BTP, p.8) : après dernier degré + durée (27 ans), case cible de la table
      pendant sa fenêtre (2 ou 3 ans). 27 ans pile → PARAM_INVALIDE ; fin de fenêtre et au-delà, ou catégorie
      refusée (19) → SOURCE_MANQUANTE. Textes FR/AR lus dans le JSON.
    """
    bloc = grille["au_dela_dernier_degre"][population]
    regle = bloc.get("regle", "refus")
    if regle == "refus":
        return None                      # plafond déjà appliqué par degre_from_anciennete (D8)
    a = _annees(annees)
    debut = bloc["dernier_degre_atteint_a_annees"]
    if regle == "ecart_cumule_biennal":
        periode = bloc["periode_annees"]
        if a > debut and (a - debut) % periode == 0:
            raise Refus(Refus.PARAM_INVALIDE, _texte_art13(bloc["message_borne_fr"], a=a),
                        _texte_art13(bloc["message_borne_ar"], a=a))
        n = math.floor((a - debut) / periode)
        return {"regle": regle, "bloc": bloc, "n": n} if n >= 1 else None
    seuil = debut + bloc["duree_au_dernier_degre_annees"]
    if a < seuil:
        return None
    if a == seuil:
        raise Refus(Refus.PARAM_INVALIDE, _texte_art13(bloc["message_borne_fr"], a=a),
                    _texte_art13(bloc["message_borne_ar"], a=a))
    if cle in bloc["categories_refusees"]:
        r = bloc["categories_refusees"][cle]
        raise Refus(Refus.SOURCE_MANQUANTE, r["message_fr"], r["message_ar"])
    cible = bloc["table_correspondance"][cle]
    fin = seuil + cible["fenetre_annees"]
    if a >= fin:
        valeurs = {"a": a, "categorie": cle, "case": cible["case_imprimee"], "fin": fin}
        raise Refus(Refus.SOURCE_MANQUANTE, _texte_art13(bloc["message_hors_fenetre_fr"], **valeurs),
                    _texte_art13(bloc["message_hors_fenetre_ar"], **valeurs))
    return {"regle": regle, "bloc": bloc, "cible": cible, "debut": seuil, "fin": fin}


def _tables_population(grille: dict, population: str) -> list[dict]:
    """Tables de la population (champ « population » de la table, sinon ses catégories)."""
    return [t for t in grille["grilles"] if population_de_table(grille, t) == population]


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
    degre = art13 = None
    if grille["degres"][pop]:
        if anciennete_annees is None:
            raise Refus(Refus.PARAM_INVALIDE,
                        f"anciennete_annees obligatoire pour {secteur}/{pop} (grille à degrés d'ancienneté).",
                        f"anciennete_annees إلزامي لـ {secteur}/{pop} (جدول بدرجات أقدمية).")
        degre = degre_from_anciennete(anciennete_annees, secteur, pop)
        if degre == len(grille["degres"][pop]):
            art13 = regle_au_dela_dernier_degre(grille, pop, cle, anciennete_annees)
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
    citations = [Citation(source_file=grille["_meta"]["source_file"], page=table["source_pdf_page"], article=None,
                          data_file=GRILLES[secteur], decision_ref=ref)]
    if art13 is not None:
        # Article 13 (D10) : montant recalculé, hypothèses dans detail, seconde citation (article et page).
        valeur, info_art13 = _appliquer_art13(art13, table, cle, valeur)
        detail.update(info_art13)
        bloc = art13["bloc"]
        citations.append(Citation(source_file=grille["_meta"]["source_file"], page=bloc["source_pdf_page"],
                                  article=bloc["source_article"], data_file=GRILLES[secteur],
                                  decision_ref=decision_ref({"_meta": bloc}, secteur)))
    # Interprétations lues dans le JSON : grille de la population, puis ligne demandée, puis article 13.
    hyps = [h for h in (grille.get("hypotheses_grille", {}).get(pop),
                        grille.get("hypotheses_categories", {}).get(pop, {}).get(cle)) if h]
    if hyps:
        detail["hypotheses"] = [x for h in hyps for x in h["fr"]] + detail.get("hypotheses", [])
        detail["hypotheses_ar"] = [x for h in hyps for x in h["ar"]] + detail.get("hypotheses_ar", [])
    detail.update({
        "table_id": table["table_id"],
        "effective_date": table["effective_date"],
        "date_calcul": parse_date(date).isoformat(),
        "regime_hebdomadaire_heures": table.get("regime_hebdomadaire_heures"),
        "regles": "D6",
    })
    return Result(montant=arrondi_millime(valeur), unite=table["unite"], detail=detail, citations=citations)


def _appliquer_art13(art13: dict, table: dict, cle: str, valeur_dernier_degre: Decimal) -> tuple[Decimal, dict]:
    """Montant et détail de la règle de l'article 13 (D10). Les hypothèses sont renvoyées pour être affichées."""
    bloc = art13["bloc"]
    info = {"regle_art13": art13["regle"]}
    if art13["regle"] == "ecart_cumule_biennal":
        d10, d11 = table["valeurs"][cle][-2], table["valeurs"][cle][-1]
        ecart = d11 - d10
        valeur = d11 + art13["n"] * ecart
        info.update(n_paliers=art13["n"], ecart=ecart, montant_dernier_degre=d11)
    else:
        cible = art13["cible"]
        valeur = table["valeurs"][cible["categorie"]][cible["degre"] - 1]
        info.update(case_cible=cible["case_imprimee"], degre_cible=cible["degre"], categorie_cible=cible["categorie"],
                    montant_dernier_degre=valeur_dernier_degre, ecart=valeur - valeur_dernier_degre,
                    fenetre_debut_annees=art13["debut"], fenetre_fin_annees=art13["fin"])
    info.update(hypotheses=list(bloc["hypotheses_fr"]), hypotheses_ar=list(bloc["hypotheses_ar"]))
    return valeur, info
