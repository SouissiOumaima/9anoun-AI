"""Salaire de base conventionnel : grille sectorielle × population × catégorie × degré d'ancienneté × date
(D4, D6, D9), et règle de l'article 13 au-delà du dernier degré (D10)."""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Any

from .loaders import (
    GRILLES,
    bornes_degre,
    charger_grille,
    decision_ref,
    designations_degres,
    exiger_tables_transcrites,
    population_de_table,
)
from .models import Citation, Refus, Result, arrondi_millime, parse_date, plus_recent_avant


def _annees(anciennete) -> Decimal:
    if isinstance(anciennete, bool) or not isinstance(anciennete, (int, float, Decimal)):
        raise Refus(
            Refus.PARAM_INVALIDE,
            f"Ancienneté invalide : {anciennete!r} (nombre d'années attendu).",
            f"أقدمية غير صالحة: {anciennete!r} (المطلوب عدد السنوات).",
        )
    a = anciennete if isinstance(anciennete, Decimal) else Decimal(str(anciennete))
    if not a.is_finite() or a < 0:
        raise Refus(
            Refus.PARAM_INVALIDE,
            f"Ancienneté invalide : {anciennete!r} (doit être un nombre ≥ 0).",
            f"أقدمية غير صالحة: {anciennete!r} (يجب أن تكون عددًا موجبًا أو صفرًا).",
        )
    return a


def _intervalles(degres: list[dict]) -> list[tuple[int, int, int | None]]:
    """(degre, borne_basse, borne_haute|None) lus dans les libellés d'une liste de degrés."""
    out = []
    for d in degres:
        label = d["anciennete_label"]
        bornes = bornes_degre(label)
        if bornes is None:
            raise Refus(
                Refus.SOURCE_MANQUANTE,
                f"Libellé de degré illisible : {label!r}.",
                f"تسمية الدرجة غير مقروءة: {label!r}.",
            )
        out.append((d["degre"], *bornes))
    return out


def _population(grille: dict, population) -> str:
    """Population couverte par la grille ; population déclarée non couverte → refus lu dans le JSON (D9).
    Secteur à une seule population : la population peut être omise (D29) ; donnée, elle doit être celle-là."""
    if isinstance(population, str) and population in grille.get("populations_non_couvertes", {}):
        bloc = grille["populations_non_couvertes"][population]
        raise Refus(Refus.SOURCE_MANQUANTE, bloc["message_fr"], bloc["message_ar"])
    cats = grille["categories"]
    if population is None and len(cats) == 1:
        return next(iter(cats))
    if population is None:
        secteur = grille["_meta"]["secteur_code"]
        raise Refus(
            Refus.PARAM_INVALIDE,
            f"Population obligatoire pour le secteur {secteur} (disponibles : {', '.join(cats)}).",
            f"يجب تحديد فئة الأعوان للقطاع {secteur} (المتوفر: {', '.join(cats)}).",
        )
    if not isinstance(population, str) or population not in cats:
        raise Refus(
            Refus.PARAM_INVALIDE,
            f"Population inconnue : {population!r} (attendu : {', '.join(cats)}).",
            f"فئة أعوان غير معروفة: {population!r} (المتوفر: {', '.join(cats)}).",
        )
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
            raise Refus(
                Refus.PARAM_INVALIDE,
                f"La catégorie {cat} ({population}) comporte des sous-catégories : sous_categorie "
                f"obligatoire (valeurs possibles : {valeurs}).",
                f"الصنف {cat} ({population}) يتضمن أصنافًا فرعية: يجب تحديد sous_categorie (القيم الممكنة: {valeurs}).",
            )
        if not isinstance(sous_categorie, str) or sous_categorie not in sous[cat]:
            raise Refus(
                Refus.PARAM_INVALIDE,
                f"Sous-catégorie inconnue : {sous_categorie!r} pour la catégorie {cat} ({population}) "
                f"(valeurs possibles : {valeurs}).",
                f"صنف فرعي غير معروف: {sous_categorie!r} للصنف {cat} ({population}) (القيم الممكنة: {valeurs}).",
            )
        s = sous[cat][sous_categorie]
        return (
            cat,
            s["cle"],
            {"sous_categorie": sous_categorie, "libelle_fr": s["libelle_fr"], "libelle_ar": s["libelle_ar"]},
        )
    demandables = _categories_demandables(grille, population)
    alias = grille.get("alias_categories", {}).get(population, {})
    info_alias = {}
    if isinstance(cat, str) and cat not in demandables and cat in alias:
        # Alias déclaré dans le JSON (ex. numérotation de l'annexe → clé imprimée dans la grille).
        cat, info_alias = alias[cat], {"categorie_demandee": cat}
    if not isinstance(cat, str) or cat not in demandables:
        attendu = ", ".join(demandables) + (f" ; alias : {', '.join(alias)}" if alias else "")
        raise Refus(
            Refus.PARAM_INVALIDE,
            f"Catégorie inconnue : {categorie!r} pour {population} (attendu : {attendu}).",
            f"صنف غير معروف: {categorie!r} لفئة {population}.",
        )
    if sous_categorie is not None:
        raise Refus(
            Refus.PARAM_INVALIDE,
            f"Sous-catégorie {sous_categorie!r} non prévue : la catégorie {cat} ({population}) "
            "n'a pas de sous-catégorie.",
            f"الصنف الفرعي {sous_categorie!r} غير متوقع: الصنف {cat} ({population}) لا يتضمن أصنافًا فرعية.",
        )
    return cat, cat, info_alias


def degre_from_anciennete(annees: Any, secteur: Any = None, population: Any = None) -> int:
    """Degré de la grille dont l'intervalle contient strictement l'ancienneté (degrés propres à chaque population).

    Les libellés du PDF (« 2/0 », « 4/2 », …, « 20+ ») font apparaître chaque borne intérieure
    (2, 4, …, 20) dans deux degrés sans dire lequel s'applique : ces valeurs exactes → Refus
    PARAM_INVALIDE (D6), plutôt que de choisir. 0 n'appartient qu'au degré 1.
    Le dernier degré est ouvert (« 20+ ») : ce qui s'applique au-delà (article 13) est traité par
    regle_au_dela_dernier_degre (D10). Si la population déclare seulement un refus (regle « refus »),
    toute ancienneté ≥ anciennete_max_couverte_annees est refusée ici (SOURCE_MANQUANTE, D8). Règle « ouvert » :
    le dernier degré est servi quelle que soit l'ancienneté au-delà de sa borne basse (D29).
    Aucun secteur par défaut : secteur absent → Refus PARAM_INVALIDE.
    """
    grille = charger_grille(secteur)
    pop = _population(grille, population)
    degres = grille["degres"][pop]
    if not degres:
        raise Refus(
            Refus.PARAM_INVALIDE,
            f"La grille {secteur}/{pop} n'a pas de degré d'ancienneté.",
            f"جدول الأجور {secteur}/{pop} لا يتضمن درجات أقدمية.",
        )
    a = _annees(annees)
    # Anciennetés refusées au milieu de la grille (texte de la convention contraire à l'en-tête) : refus lu dans le JSON.
    for r in grille.get("anciennetes_refusees", {}).get(pop, []):
        if r["au_dela_de"] < a <= r["jusqu_a_inclus"]:
            raise Refus(
                Refus.SOURCE_MANQUANTE, r["message_fr"].replace("{a}", str(a)), r["message_ar"].replace("{a}", str(a))
            )
    au_dela = grille["au_dela_dernier_degre"][pop]
    if au_dela.get("regle", "refus") == "refus" and a >= au_dela["anciennete_max_couverte_annees"]:
        raise Refus(
            Refus.SOURCE_MANQUANTE,
            au_dela["message_fr"].replace("{a}", str(a)),
            au_dela["message_ar"].replace("{a}", str(a)),
        )
    intervalles = _intervalles(degres)
    contenants = [deg for deg, bas, haut in intervalles if bas <= a and (haut is None or a <= haut)]
    if len(contenants) == 1:
        return contenants[0]
    if len(contenants) > 1:
        raise Refus(
            Refus.PARAM_INVALIDE,
            f"Ancienneté de {a} ans = borne commune aux degrés {contenants} : la grille ne précise "
            "pas lequel s'applique. Indiquer l'ancienneté exacte (ex. 2 ans et 1 jour).",
            f"أقدمية {a} سنة تقع على الحد المشترك بين الدرجات {contenants} ولا يحدد الجدول أيّها "
            "ينطبق. يرجى تحديد الأقدمية بدقة.",
        )
    raise Refus(
        Refus.SOURCE_MANQUANTE, f"Aucun degré de la grille ne couvre {a} ans.", f"لا توجد درجة في الجدول تغطي {a} سنة."
    )


def _texte_art13(gabarit: str, **valeurs) -> str:
    """Seuls {a}, {categorie}, {case} et {fin} sont remplacés dans les textes lus dans le JSON (D10)."""
    for k, v in valeurs.items():
        gabarit = gabarit.replace("{" + k + "}", str(v))
    return gabarit


def regle_au_dela_dernier_degre(grille: dict, population: str, cle: str, annees: Any) -> dict | None:
    """Règle de l'article 13 au-delà du dernier degré, ou None si elle ne s'applique pas (D10).

    - « ecart_cumule_biennal » (métallurgie, p.9) : n = ⌊(a − âge du dernier degré) / période⌋ paliers ;
      n = 0 → None (dernier degré simple). Palier exact (22, 24, 26… ans) → PARAM_INVALIDE, comme les bornes de D6.
    - « table_correspondance » (BTP, p.8) : après dernier degré + durée (27 ans), case cible de la table
      pendant sa fenêtre (2 ou 3 ans). 27 ans pile → PARAM_INVALIDE ; fin de fenêtre et au-delà, ou catégorie
      refusée (19) → SOURCE_MANQUANTE. Textes FR/AR lus dans le JSON.
    - « refus » (D8) et « ouvert » (D29) → None : aucune règle à appliquer ici.
    """
    bloc = grille["au_dela_dernier_degre"][population]
    regle = bloc.get("regle", "refus")
    if regle == "refus":
        return None  # plafond déjà appliqué par degre_from_anciennete (D8)
    if regle == "ouvert":
        return None  # dernier degré ouvert servi tel quel, sans plafond (D29)
    a = _annees(annees)
    debut = bloc["dernier_degre_atteint_a_annees"]
    if regle == "ecart_cumule_biennal":
        periode = bloc["periode_annees"]
        if a > debut and (a - debut) % periode == 0:
            raise Refus(
                Refus.PARAM_INVALIDE,
                _texte_art13(bloc["message_borne_fr"], a=a),
                _texte_art13(bloc["message_borne_ar"], a=a),
            )
        n = math.floor((a - debut) / periode)
        return {"regle": regle, "bloc": bloc, "n": n} if n >= 1 else None
    seuil = debut + bloc["duree_au_dernier_degre_annees"]
    if a < seuil:
        return None
    if a == seuil:
        raise Refus(
            Refus.PARAM_INVALIDE,
            _texte_art13(bloc["message_borne_fr"], a=a),
            _texte_art13(bloc["message_borne_ar"], a=a),
        )
    if cle in bloc["categories_refusees"]:
        r = bloc["categories_refusees"][cle]
        raise Refus(Refus.SOURCE_MANQUANTE, r["message_fr"], r["message_ar"])
    cible = bloc["table_correspondance"][cle]
    fin = seuil + cible["fenetre_annees"]
    if a >= fin:
        valeurs = {"a": a, "categorie": cle, "case": cible["case_imprimee"], "fin": fin}
        raise Refus(
            Refus.SOURCE_MANQUANTE,
            _texte_art13(bloc["message_hors_fenetre_fr"], **valeurs),
            _texte_art13(bloc["message_hors_fenetre_ar"], **valeurs),
        )
    return {"regle": regle, "bloc": bloc, "cible": cible, "debut": seuil, "fin": fin}


def _tables_population(grille: dict, population: str) -> list[dict]:
    """Tables de la population (champ « population » de la table, sinon ses catégories)."""
    return [t for t in grille["grilles"] if population_de_table(grille, t) == population]


def table_applicable(secteur: Any, population: Any, date: object) -> dict:
    """Table de la population dont effective_date est la plus récente ≤ date ; au-delà de valide_jusqu_au.date,
    refus lu dans le JSON."""
    jour = parse_date(date)
    grille = charger_grille(secteur)
    pop = _population(grille, population)
    exiger_tables_transcrites(grille, secteur)
    tables = _tables_population(grille, pop)
    table = plus_recent_avant(tables, jour)
    if table is None:
        premiere = min((t["effective_date"] for t in tables), default="—")
        raise Refus(
            Refus.SOURCE_MANQUANTE,
            f"Aucune grille {secteur}/{pop} en vigueur au {jour.isoformat()} "
            f"(première date d'effet disponible : {premiere}).",
            f"لا يوجد جدول أجور {secteur}/{pop} ساري المفعول بتاريخ {jour.isoformat()} "
            f"(أول تاريخ نفاذ متوفر: {premiere}).",
        )
    fin = table.get("valide_jusqu_au")
    if fin is not None and jour.isoformat() > fin["date"]:
        # Table remplacée par une grille absente des sources : refus lu dans le JSON (Citation ou Silence).
        raise Refus(Refus.SOURCE_MANQUANTE, fin["message_fr"], fin["message_ar"])
    for periode in table.get("periodes_refusees", []):
        # Période de la table contredite par une autre source (ex. date d'avenant) : refus lu dans le JSON (D80).
        if periode["du"] <= jour.isoformat() <= periode["au"]:
            raise Refus(Refus.SOURCE_MANQUANTE, periode["message_fr"], periode["message_ar"])
    return table


def salaire_base(
    secteur: Any = None,
    population: Any = None,
    categorie: Any = None,
    anciennete_annees: Any = None,
    date: object = None,
    unite_souhaitee: str | None = None,
    sous_categorie: str | None = None,
    degre: Any = None,
) -> Result:
    """Salaire de base dans l'unité de la table (TND/mois ou TND/heure), sans aucune conversion.

    anciennete_annees : obligatoire pour une population à degrés, refusée pour une population sans degré.
    sous_categorie : obligatoire pour une catégorie à sous-catégories, refusée sinon (D9).
    degre : désignation imprimée du degré, à la place de anciennete_annees (contrat v1, D75) ; None → chemin par
    l'ancienneté, strictement inchangé.
    """
    if degre is not None:
        return salaire_par_degre(
            secteur, population, categorie, anciennete_annees, date, unite_souhaitee, sous_categorie, degre
        )
    grille = charger_grille(secteur)
    pop = _population(grille, population)
    cat, cle, info_sous = _cle_categorie(grille, pop, categorie, sous_categorie)
    degre = art13 = None
    if grille["degres"][pop]:
        if anciennete_annees is None:
            raise Refus(
                Refus.PARAM_INVALIDE,
                f"anciennete_annees obligatoire pour {secteur}/{pop} (grille à degrés d'ancienneté).",
                f"anciennete_annees إلزامي لـ {secteur}/{pop} (جدول بدرجات أقدمية).",
            )
        degre = degre_from_anciennete(anciennete_annees, secteur, pop)
        if degre == len(grille["degres"][pop]):
            art13 = regle_au_dela_dernier_degre(grille, pop, cle, anciennete_annees)
    elif anciennete_annees is not None:
        raise Refus(
            Refus.PARAM_INVALIDE,
            f"anciennete_annees non prévue : la grille {secteur}/{pop} n'a pas de degré d'ancienneté.",
            f"anciennete_annees غير متوقع: جدول الأجور {secteur}/{pop} لا يتضمن درجات أقدمية.",
        )
    table = table_applicable(secteur, pop, date)
    if art13 is not None and art13["regle"] == "ecart_cumule_biennal":
        # Case exclue de l'écart cumulé (ex. écart imprimé négatif) : refus lu dans le JSON, case seule servie avant.
        for r in art13["bloc"].get("cases_refusees", []):
            if (r["table_id"], r["categorie"]) == (table["table_id"], cle):
                raise Refus(
                    Refus.SOURCE_MANQUANTE,
                    _texte_art13(r["message_fr"], a=_annees(anciennete_annees)),
                    _texte_art13(r["message_ar"], a=_annees(anciennete_annees)),
                )
    if unite_souhaitee is not None and unite_souhaitee != table["unite"]:
        raise Refus(
            Refus.HORS_SCOPE,
            f"La grille donne un montant en {table['unite']} ; la conversion en {unite_souhaitee} "
            "n'est écrite dans aucune source vérifiée (nombre d'heures par mois non fixé).",
            f"يعطي الجدول المبلغ بوحدة {table['unite']}؛ التحويل إلى {unite_souhaitee} "
            "غير منصوص عليه في أي مصدر مُتحقَّق منه.",
        )
    ref = decision_ref(grille, secteur)
    valeur = table["valeurs"][cle] if degre is None else montant_case(table, cle, degre)
    detail = {"secteur": secteur, "population": pop, "categorie": cat, **info_sous}
    if degre is not None:
        detail.update(degre=degre, anciennete_annees=_annees(anciennete_annees))
    citations = [
        Citation(
            source_file=grille["_meta"]["source_file"],
            page=table["source_pdf_page"],
            article=None,
            data_file=GRILLES[secteur],
            decision_ref=ref,
        )
    ]
    if art13 is not None:
        # Article 13 (D10) : montant recalculé, hypothèses dans detail, seconde citation (article et page).
        valeur, info_art13 = _appliquer_art13(art13, table, cle, valeur)
        detail.update(info_art13)
        bloc = art13["bloc"]
        citations.append(
            Citation(
                source_file=grille["_meta"]["source_file"],
                page=bloc["source_pdf_page"],
                article=bloc["source_article"],
                data_file=GRILLES[secteur],
                decision_ref=decision_ref({"_meta": bloc}, secteur),
            )
        )
    # Interprétations lues dans le JSON : grille de la population, puis ligne demandée, puis article 13.
    hyps = [
        h
        for h in (
            grille.get("hypotheses_grille", {}).get(pop),
            grille.get("hypotheses_categories", {}).get(pop, {}).get(cle),
        )
        if h
    ]
    if hyps:
        detail["hypotheses"] = [x for h in hyps for x in h["fr"]] + detail.get("hypotheses", [])
        detail["hypotheses_ar"] = [x for h in hyps for x in h["ar"]] + detail.get("hypotheses_ar", [])
    detail.update(
        {
            "table_id": table["table_id"],
            "effective_date": table["effective_date"],
            "date_calcul": parse_date(date).isoformat(),
            "regime_hebdomadaire_heures": table.get("regime_hebdomadaire_heures"),
            "regles": "D6",
        }
    )
    return Result(montant=arrondi_millime(valeur), unite=table["unite"], detail=detail, citations=citations)


def montant_case(table: dict, cle: str, degre: int) -> Decimal:
    """Montant imprimé d'une case ; case illisible déclarée dans cellules_source_manquante (valeur null) → refus
    SOURCE_MANQUANTE lu dans le JSON (page et raison)."""
    valeur = table["valeurs"][cle][degre - 1]
    if valeur is None:
        r = next(c for c in table["cellules_source_manquante"] if (c["categorie"], c["degre"]) == (cle, degre))
        raise Refus(Refus.SOURCE_MANQUANTE, r["message_fr"], r["message_ar"])
    return valeur


def _appliquer_art13(art13: dict, table: dict, cle: str, valeur_dernier_degre: Decimal) -> tuple[Decimal, dict]:
    """Montant et détail de la règle de l'article 13 (D10). Les hypothèses sont renvoyées pour être affichées."""
    bloc = art13["bloc"]
    info = {"regle_art13": art13["regle"]}
    if art13["regle"] == "ecart_cumule_biennal":
        n_degres = len(table["valeurs"][cle])
        d10, d11 = montant_case(table, cle, n_degres - 1), montant_case(table, cle, n_degres)
        ecart = d11 - d10
        valeur = d11 + art13["n"] * ecart
        info.update(n_paliers=art13["n"], ecart=ecart, montant_dernier_degre=d11)
    else:
        cible = art13["cible"]
        valeur = montant_case(table, cible["categorie"], cible["degre"])
        info.update(
            case_cible=cible["case_imprimee"],
            degre_cible=cible["degre"],
            categorie_cible=cible["categorie"],
            montant_dernier_degre=valeur_dernier_degre,
            ecart=valeur - valeur_dernier_degre,
            fenetre_debut_annees=art13["debut"],
            fenetre_fin_annees=art13["fin"],
        )
    info.update(hypotheses=list(bloc["hypotheses_fr"]), hypotheses_ar=list(bloc["hypotheses_ar"]))
    return valeur, info


# --- Demande par degré déclaré (contrat v1, D75) ----------------------------------------------------------------


def _ans(n: int) -> str:
    return f"{n} an" if n == 1 else f"{n} ans"


def _colonnes_par_degre(grille: dict, population: str, table: dict) -> list[dict]:
    """Colonnes atteignables par le degré déclaré, dans l'ordre de la grille : les degrés (désignation imprimée,
    alias éventuel), puis les colonnes gardées hors de valeurs que la table déclare servies par degré."""
    degres = grille["degres"][population]
    out = [
        {
            "designation": nom,
            "alias": d.get("alias_designation"),
            "degre": d["degre"],
            "anciennete_imprimee": d.get("anciennete_imprimee"),
            "libelle": d["anciennete_label"] if bornes_degre(d["anciennete_label"]) else None,
            "hors_valeurs": None,
        }
        for d, nom in zip(degres, designations_degres(degres))
    ]
    ns = table.get("colonnes_non_servies")
    if ns is not None and ns.get("servies_par_degre") is True:
        for i, (nom, anc) in enumerate(zip(ns["colonnes_imprimees"], ns["anciennete_imprimee"])):
            out.append(
                {
                    "designation": nom,
                    "alias": None,
                    "degre": len(degres) + i + 1,
                    "anciennete_imprimee": anc,
                    "libelle": None,
                    "hors_valeurs": i,
                }
            )
    return out


def _valeur_par_degre(table: dict, cle: str, col: dict) -> tuple[Decimal, bool]:
    """(montant imprimé, colonne atteinte seulement par le degré). Case illisible → refus lu dans le JSON ; case
    déclarée servie_par_degre → valeur_imprimee."""
    if col["hors_valeurs"] is not None:
        return table["colonnes_non_servies"]["valeurs"][cle][col["hors_valeurs"]], True
    valeur = table["valeurs"][cle][col["degre"] - 1]
    if valeur is not None:
        return valeur, False
    r = next(c for c in table["cellules_source_manquante"] if (c["categorie"], c["degre"]) == (cle, col["degre"]))
    if r.get("servie_par_degre") is True:
        return r["valeur_imprimee"], True
    raise Refus(Refus.SOURCE_MANQUANTE, r["message_fr"], r["message_ar"])


def _hypotheses_par_degre(
    grille: dict, pop: str, cle: str, table: dict, col: dict, dernier: bool, sans_anciennete: bool
) -> tuple[list[str], list[str], str | None]:
    """Hypothèses FR/AR du degré déclaré, et règle au-delà du dernier degré non appliquée (ou None)."""
    page = table["source_pdf_page"]
    fr = ["Degré déclaré par l'utilisateur, non vérifié : aucune ancienneté n'a été contrôlée."]
    ar = ["الدرجة مصرَّح بها من المستخدم ولم يُتحقَّق منها: لم تُراقَب أي أقدمية."]
    if col["anciennete_imprimee"] is not None:
        x = col["anciennete_imprimee"]
        fr.append(f"Ancienneté imprimée pour ce degré dans la grille (page {page}) : « {x} ».")
        ar.append(f"الأقدمية المطبوعة لهذه الدرجة في الجدول (الصفحة {page}): «{x}».")
    bloc = grille["au_dela_dernier_degre"][pop]
    regle = bloc.get("regle", "refus")
    art, p = bloc.get("source_article"), bloc.get("source_pdf_page")
    seuil_nul = regle == "refus" and bloc["anciennete_max_couverte_annees"] == 0
    if seuil_nul:
        fr.append(
            f"La grille n'imprime aucune durée de degré (article {art}, page {p}) : le degré déclaré n'est rattaché "
            "à aucune ancienneté."
        )
        ar.append(f"لا يذكر الجدول مدة أي درجة (الفصل {art}، الصفحة {p}): لا ترتبط الدرجة المصرَّح بها بأي أقدمية.")
    if sans_anciennete:
        fr.append(
            f"Cette colonne n'est atteinte par aucune ancienneté, faute de durée imprimée (page {page}) : elle n'est "
            "servie que par le degré déclaré."
        )
        ar.append(f"لا تُبلَغ هذه الخانة بأي أقدمية لعدم ذكر مدتها (الصفحة {page}): لا تُعتمد إلا بالدرجة المصرَّح بها.")
    bornes = bornes_degre(col["libelle"]) if col["libelle"] else None
    for r in grille.get("anciennetes_refusees", {}).get(pop, []):
        x, y = r["au_dela_de"], r["jusqu_a_inclus"]
        if bornes is not None and bornes[0] < y and (bornes[1] is None or bornes[1] >= x):
            ra, rp = r["source_article"], r["source_pdf_page"]
            fr.append(
                f"L'article {ra} (page {rp}) et l'en-tête de la grille se contredisent pour une ancienneté de plus de "
                f"{_ans(x)} jusqu'à {_ans(y)} inclus, intervalle qui touche ce degré : par l'ancienneté, il est "
                "refusé ; le montant servi est celui imprimé pour le degré déclaré."
            )
            ar.append(
                f"يتعارض الفصل {ra} (الصفحة {rp}) مع رأس الجدول بالنسبة إلى أقدمية تفوق {x} سنة إلى {y} سنة، وهي "
                "فترة تمسّ هذه الدرجة: تُرفض بحساب الأقدمية؛ والمبلغ المُرجَع هو المطبوع للدرجة المصرَّح بها."
            )
    if not dernier or regle == "ouvert":
        return fr, ar, None
    if regle == "ecart_cumule_biennal":
        s = bloc["dernier_degre_atteint_a_annees"] + bloc["periode_annees"]
        fr.append(
            f"Dernier degré : l'écart cumulé de l'article {art} (page {p}) s'ajoute au-delà de {_ans(s)} "
            "d'ancienneté ; il dépend de l'ancienneté, non fournie, et n'est pas appliqué. Pour un salarié de plus "
            f"de {_ans(s)}, demander par l'ancienneté."
        )
        ar.append(
            f"آخر درجة: يُضاف الفارق المتراكم المنصوص عليه بالفصل {art} (الصفحة {p}) بعد {s} سنة من الأقدمية؛ "
            "وهو مرتبط بالأقدمية غير المُقدَّمة ولا يُطبَّق. بالنسبة إلى عامل تفوق أقدميته "
            f"{s} سنة، يُطلب الأجر بحساب الأقدمية."
        )
        for r in bloc.get("cases_refusees", []):
            if (r["table_id"], r["categorie"]) == (table["table_id"], cle):
                ra, rp = r["source_article"], r["source_pdf_page"]
                fr.append(
                    f"Cette case est exclue de l'écart cumulé (article {ra}, page {rp}) ; le montant servi est "
                    "celui imprimé."
                )
                ar.append(
                    f"هذه الخانة مستثناة من الفارق المتراكم (الفصل {ra}، الصفحة {rp})؛ والمبلغ المُرجَع هو المطبوع."
                )
    elif regle == "table_correspondance":
        s = bloc["dernier_degre_atteint_a_annees"] + bloc["duree_au_dernier_degre_annees"]
        fr.append(
            f"Dernier degré : la table de correspondance de l'article {art} (page {p}) s'applique au-delà de "
            f"{_ans(s)} d'ancienneté ; elle dépend de l'ancienneté, non fournie, et n'est pas appliquée. Pour un "
            f"salarié de plus de {_ans(s)}, demander par l'ancienneté."
        )
        ar.append(
            f"آخر درجة: يُطبَّق جدول التناظر المنصوص عليه بالفصل {art} (الصفحة {p}) بعد {s} سنة من الأقدمية؛ "
            "وهو مرتبط بالأقدمية غير المُقدَّمة ولا يُطبَّق. بالنسبة إلى عامل تفوق أقدميته "
            f"{s} سنة، يُطلب الأجر بحساب الأقدمية."
        )
    elif not seuil_nul:
        n = bloc["anciennete_max_couverte_annees"]
        fr.append(
            f"Dernier degré : par l'ancienneté, la grille n'est servie que jusqu'à moins de {_ans(n)} ; au-delà, la "
            f"convention ne fixe pas le montant (article {art}, page {p}). Cette règle n'est pas appliquée : le "
            "montant servi est celui imprimé pour le degré déclaré."
        )
        ar.append(
            f"آخر درجة: بحساب الأقدمية لا يُعتمد الجدول إلا لأقدمية تقل عن {n} سنة، وبعدها لا تضبط الاتفاقية "
            f"المبلغ (الفصل {art}، الصفحة {p}). لا تُطبَّق هذه القاعدة: المبلغ المُرجَع هو المطبوع للدرجة "
            "المصرَّح بها."
        )
    return fr, ar, f"article {art}, page {p}"


def salaire_par_degre(
    secteur: Any,
    population: Any,
    categorie: Any,
    anciennete_annees: Any,
    date: object,
    unite_souhaitee: str | None,
    sous_categorie: str | None,
    degre: Any,
) -> Result:
    """Salaire de base de la colonne désignée par degre, telle qu'imprimée (D75).

    degre : désignation imprimée (colonne_imprimee, sinon numéro du degré), entier ou chaîne, ou alias déclaré.
    Aucun refus lié à l'ancienneté ne s'applique ; aucune règle au-delà du dernier degré n'est appliquée (elle est
    nommée dans detail) ; une case illisible reste refusée, sauf case déclarée servie_par_degre.
    """
    if anciennete_annees is not None:
        raise Refus(
            Refus.PARAM_INVALIDE,
            "anciennete_annees et degre ne peuvent pas être donnés ensemble : donner l'un ou l'autre.",
            "لا يمكن تقديم anciennete_annees و degre معا: يُقدَّم أحدهما فقط.",
        )
    grille = charger_grille(secteur)
    pop = _population(grille, population)
    cat, cle, info_sous = _cle_categorie(grille, pop, categorie, sous_categorie)
    if not grille["degres"][pop]:
        raise Refus(
            Refus.PARAM_INVALIDE,
            f"degre non prévu : la grille {secteur}/{pop} n'a pas de degré d'ancienneté.",
            f"degre غير متوقع: جدول الأجور {secteur}/{pop} لا يتضمن درجات أقدمية.",
        )
    if isinstance(degre, bool) or not isinstance(degre, (int, str)):
        raise Refus(
            Refus.PARAM_INVALIDE,
            f"Degré invalide : {degre!r} (désignation imprimée attendue, nombre entier ou texte).",
            f"درجة غير صالحة: {degre!r} (المطلوب التسمية المطبوعة، عدد صحيح أو نص).",
        )
    table = table_applicable(secteur, pop, date)
    if unite_souhaitee is not None and unite_souhaitee != table["unite"]:
        raise Refus(
            Refus.HORS_SCOPE,
            f"La grille donne un montant en {table['unite']} ; la conversion en {unite_souhaitee} "
            "n'est écrite dans aucune source vérifiée (nombre d'heures par mois non fixé).",
            f"يعطي الجدول المبلغ بوحدة {table['unite']}؛ التحويل إلى {unite_souhaitee} "
            "غير منصوص عليه في أي مصدر مُتحقَّق منه.",
        )
    colonnes = _colonnes_par_degre(grille, pop, table)
    demande = str(degre)
    col = next((c for c in colonnes if demande in (c["designation"], c["alias"])), None)
    if col is None:
        noms = ", ".join(c["designation"] for c in colonnes)
        alias = [c["alias"] for c in colonnes if c["alias"]]
        noms += f" ; alias : {', '.join(alias)}" if alias else ""
        raise Refus(
            Refus.PARAM_INVALIDE,
            f"Degré {degre!r} absent de la grille {secteur}/{pop} (table {table['table_id']}) ; désignations "
            f"imprimées acceptées : {noms}.",
            f"الدرجة {degre!r} غير موجودة في جدول الأجور {secteur}/{pop} (الجدول {table['table_id']})؛ "
            f"التسميات المطبوعة المقبولة: {noms}.",
        )
    valeur, sans_anciennete = _valeur_par_degre(table, cle, col)
    fr, ar, regle_non_appliquee = _hypotheses_par_degre(
        grille, pop, cle, table, col, col is colonnes[-1], sans_anciennete
    )
    detail: dict[str, Any] = {"secteur": secteur, "population": pop, "categorie": cat, **info_sous}
    detail.update(degre=col["degre"], degre_imprime=col["designation"], degre_declare=True)
    if col["alias"] is not None and demande == col["alias"]:
        detail["alias_designation"] = col["alias"]
    if col["anciennete_imprimee"] is not None:
        detail["anciennete_imprimee"] = str(col["anciennete_imprimee"])
    if col["libelle"] is not None:
        detail["libelle_degre"] = col["libelle"]
    if regle_non_appliquee is not None:
        detail["regle_au_dela_non_appliquee"] = regle_non_appliquee
    hyps = [
        h
        for h in (
            grille.get("hypotheses_grille", {}).get(pop),
            grille.get("hypotheses_categories", {}).get(pop, {}).get(cle),
        )
        if h
    ]
    # Hypothèses écrites pour le chemin par l'ancienneté (« L'ancienneté reçue… ») : non affichées ici.
    detail["hypotheses"] = [
        x for h in hyps for i, x in enumerate(h["fr"]) if i not in h.get("chemin_anciennete_seulement", ())
    ] + fr
    detail["hypotheses_ar"] = [
        x for h in hyps for i, x in enumerate(h["ar"]) if i not in h.get("chemin_anciennete_seulement", ())
    ] + ar
    detail.update(
        {
            "table_id": table["table_id"],
            "effective_date": table["effective_date"],
            "date_calcul": parse_date(date).isoformat(),
            "regime_hebdomadaire_heures": table.get("regime_hebdomadaire_heures"),
            "regles": "D75",
        }
    )
    citations = [
        Citation(
            source_file=grille["_meta"]["source_file"],
            page=table["source_pdf_page"],
            article=None,
            data_file=GRILLES[secteur],
            decision_ref=decision_ref(grille, secteur),
        )
    ]
    return Result(montant=arrondi_millime(valeur), unite=table["unite"], detail=detail, citations=citations)
