"""Contrôle de lecture permanent : hausse entre deux dates voisines, cellule par cellule, sur toutes les grilles.

Pour chaque population qui a au moins deux tables datées de même forme, chaque ligne de catégorie et chaque paire de
dates voisines, la hausse de la ligne est modélisée de deux façons :
- montant fixe : la hausse la plus fréquente de la ligne (au moins deux cellules) ;
- pourcentage fixe : rapport médian nouvelle / ancienne de la ligne, montant attendu arrondi au millime.
Le modèle qui explique le plus de cellules à 1 millime près est retenu (montant fixe à égalité). Le test échoue si une
cellule servie s'écarte de plus de 1 millime de ce modèle. Les cellules déclarées en source manquante (D48, valeur
null) sont exclues, ainsi que les lignes d'une seule cellule (aucune hausse de référence).

Une cellule signalée n'est jamais corrigée par ce test : elle est relue sur l'image (rendu à 400 dpi), puis déclarée
en source manquante si un chiffre est abîmé, ou inscrite dans ANOMALIES_IMPRIMEES si l'image imprime bien la valeur.
Limites : une erreur reproduite à l'identique aux deux dates, ou d'environ 1 millime, n'est pas détectée ; les
grilles à une seule table ne sont pas couvertes (GRILLES_UNE_SEULE_TABLE).
"""

from __future__ import annotations

import collections
import copy
import statistics
from decimal import ROUND_HALF_UP, Decimal

import pytest

from track_b_accounting.calc import loaders

MILLIME = Decimal("0.001")

# Cellules imprimées telles quelles, relues sur l'image, dont la hausse s'écarte de celle de leur ligne :
# (secteur, table_id, catégorie, degré) -> justification.
ANOMALIES_IMPRIMEES = {
    ("CONFISERIE_BISCUITERIE_CHOCOLATERIE", "CONF_MENSUELS_2021-12-01", "2", 15): (
        "590.535 imprimé net (p.21, ligne 2, degré 15), plus bas que le degré 14 ; anomalies_imprimees de la table (D52)"
    ),
}

# Grilles dont aucune population n'a deux tables datées : contrôle impossible.
GRILLES_UNE_SEULE_TABLE = {
    "ENSEIGNEMENT_PRIVE",
    "GARDIENNAGE_SECURITE_TRANSPORT_FONDS",
    "CLERCS_AVOCATS",
    "CONSERVERIES_CONDITIONNEMENT_HUILES",
    "GROSSISTES_REPARTITEURS_MEDICAMENTS",
    "SALLES_CINEMA",
    "TRANSPORT_ROUTIER_MARCHANDISES",
    "JARDINS_ENFANTS_CRECHES",
    "CLINIQUES_PRIVEES",
    "LOCATION_VOITURES",
    "CAFES_RESTAURANTS_BARS",
    "PORTS_CHARGEMENT_DECHARGEMENT",
}


def _arrondi(x: Decimal) -> Decimal:
    return x.quantize(MILLIME, rounding=ROUND_HALF_UP)


def _tables_par_population(grille: dict) -> dict[str, list[dict]]:
    pops: dict[str, list[dict]] = collections.defaultdict(list)
    for t in grille["grilles"]:
        pop = loaders.population_de_table(grille, t)
        assert pop is not None, t["table_id"]
        pops[pop].append(t)
    return {pop: sorted(ts, key=lambda t: t["effective_date"]) for pop, ts in pops.items()}


def _ligne(v: object) -> list:
    return v if isinstance(v, list) else [v]


def ecarts_de_hausse(secteur: str, grille: dict) -> tuple[int, list[dict]]:
    """(nombre de cellules comparées, cellules qui s'écartent de plus de 1 millime du modèle de leur ligne)."""
    comparees, signalees = 0, []
    for ts in _tables_par_population(grille).values():
        for a, b in zip(ts, ts[1:]):
            manquantes = {
                (t["table_id"], c["categorie"], c["degre"])
                for t in (a, b)
                for c in t.get("cellules_source_manquante", [])
            }
            for cat, va in a["valeurs"].items():
                la, lb = _ligne(va), _ligne(b["valeurs"][cat])
                assert len(la) == len(lb), (a["table_id"], b["table_id"], cat)
                cellules = [
                    (degre, x, y)
                    for degre, (x, y) in enumerate(zip(la, lb), 1)
                    if x is not None
                    and y is not None
                    and (a["table_id"], cat, degre) not in manquantes
                    and (b["table_id"], cat, degre) not in manquantes
                ]
                if len(cellules) < 2:
                    continue
                comparees += len(cellules)
                mode, n_mode = collections.Counter(y - x for _, x, y in cellules).most_common(1)[0]
                rapport = statistics.median(y / x for _, x, y in cellules)
                fixe = [abs(y - x - mode) <= MILLIME for _, x, y in cellules]
                pct = [abs(y - _arrondi(x * rapport)) <= MILLIME for _, x, y in cellules]
                montant_fixe = n_mode >= 2 and sum(fixe) >= sum(pct)
                for (degre, x, y), ok_fixe, ok_pct in zip(cellules, fixe, pct):
                    if ok_fixe if montant_fixe else ok_pct:
                        continue
                    attendu = x + mode if montant_fixe else _arrondi(x * rapport)
                    signalees.append(
                        {
                            "secteur": secteur,
                            "categorie": cat,
                            "degre": degre,
                            "tables": (a["table_id"], b["table_id"]),
                            "valeurs": (x, y),
                            "attendu": attendu,
                            "modele": "montant fixe" if montant_fixe else "pourcentage",
                        }
                    )
    return comparees, signalees


def _hors_anomalies(secteur: str, signalees: list[dict]) -> list[dict]:
    return [
        s
        for s in signalees
        if not any((secteur, t, s["categorie"], s["degre"]) in ANOMALIES_IMPRIMEES for t in s["tables"])
    ]


SECTEURS = sorted(loaders.GRILLES)


@pytest.mark.parametrize("secteur", SECTEURS)
def test_hausse_entre_dates_conforme(secteur: str) -> None:
    comparees, signalees = ecarts_de_hausse(secteur, loaders.charger_grille(secteur))
    if secteur in GRILLES_UNE_SEULE_TABLE:
        assert comparees == 0
        return
    assert comparees > 0, f"{secteur} : aucune cellule comparée"
    assert _hors_anomalies(secteur, signalees) == []


def test_liste_des_grilles_a_une_seule_table() -> None:
    sans_paire = {s for s in SECTEURS if ecarts_de_hausse(s, loaders.charger_grille(s))[0] == 0}
    assert sans_paire == GRILLES_UNE_SEULE_TABLE


@pytest.mark.parametrize("cle", sorted(ANOMALIES_IMPRIMEES))
def test_chaque_anomalie_connue_est_encore_signalee(cle: tuple[str, str, str, int]) -> None:
    """Une anomalie qui ne s'écarte plus de la hausse doit être retirée de la liste (pas d'exception inutile)."""
    secteur, table_id, cat, degre = cle
    _, signalees = ecarts_de_hausse(secteur, loaders.charger_grille(secteur))
    assert any(table_id in s["tables"] and (s["categorie"], s["degre"]) == (cat, degre) for s in signalees)


def test_anomalie_confiserie_declaree_dans_la_grille() -> None:
    grille = loaders.charger_grille("CONFISERIE_BISCUITERIE_CHOCOLATERIE")
    table = next(t for t in grille["grilles"] if t["table_id"] == "CONF_MENSUELS_2021-12-01")
    assert [(a["categorie"], a["degre"]) for a in table["anomalies_imprimees"]] == [("2", 15)]
    assert table["valeurs"]["2"][14] == Decimal("590.535")


@pytest.mark.parametrize(
    "secteur, table_id, cat, degre, delta",
    [
        ("METALLURGIE_BATIMENT", None, None, 5, Decimal("0.002")),  # montant fixe
        ("AGENCES_VOYAGES", "VOY_TOUS_AGENTS_2023-05-01", "3", 4, Decimal("-0.010")),  # pourcentage
        ("BANQUES", None, None, 2, Decimal("1.000")),
    ],
)
def test_une_cellule_mal_lue_est_detectee(
    secteur: str, table_id: str | None, cat: str | None, degre: int, delta: Decimal
) -> None:
    """Sensibilité : une seule cellule modifiée dans une copie de la grille est signalée."""
    grille = copy.deepcopy(loaders.charger_grille(secteur))
    table = next(t for t in grille["grilles"] if table_id is None or t["table_id"] == table_id)
    cat = cat or next(iter(table["valeurs"]))
    table["valeurs"][cat][degre - 1] += delta
    _, signalees = ecarts_de_hausse(secteur, grille)
    assert any(table["table_id"] in s["tables"] and (s["categorie"], s["degre"]) == (cat, degre) for s in signalees)


def test_les_cellules_abimees_sont_en_source_manquante() -> None:
    """Cellules relues à 400 dpi après le contrôle de hausse (dernier chiffre abîmé, 3 ou 8) : null et déclarées."""
    attendues = {
        ("AGENCES_VOYAGES", "VOY_TOUS_AGENTS_2022-05-01", "3", 7, 18),
        ("AGENCES_VOYAGES", "VOY_TOUS_AGENTS_2022-05-01", "8", 7, 18),
        ("CONFISERIE_BISCUITERIE_CHOCOLATERIE", "CONF_MENSUELS_2021-12-01", "1", 8, 21),
        ("CONFISERIE_BISCUITERIE_CHOCOLATERIE", "CONF_MENSUELS_2021-12-01", "6", 8, 21),
    }
    for secteur, table_id, cat, degre, page in attendues:
        table = next(t for t in loaders.charger_grille(secteur)["grilles"] if t["table_id"] == table_id)
        assert table["valeurs"][cat][degre - 1] is None
        c = next(c for c in table["cellules_source_manquante"] if (c["categorie"], c["degre"]) == (cat, degre))
        assert c["source_pdf_page"] == page
        assert c["raison"] == "dernier chiffre abîmé à l'impression (3 ou 8)"


def test_colonne_7_des_voyages_2022_cellules_lues_conservees() -> None:
    """Dernier chiffre partiellement effacé mais lu sur l'image à 400 dpi (décision DS5, D50) : valeurs conservées."""
    table = loaders.charger_grille("AGENCES_VOYAGES")["grilles"][0]
    assert table["table_id"] == "VOY_TOUS_AGENTS_2022-05-01"
    assert [table["valeurs"][c][6] for c in ("1", "6", "7")] == [
        Decimal("579.775"),
        Decimal("868.902"),
        Decimal("915.568"),
    ]


def test_les_cellules_null_sont_ignorees_par_le_controle() -> None:
    """Les cellules en source manquante ne sont ni comparées ni signalées : 2 cellules de moins chez les voyages."""
    grille = loaders.charger_grille("AGENCES_VOYAGES")
    comparees, signalees = ecarts_de_hausse("AGENCES_VOYAGES", grille)
    total = sum(len(v) for v in grille["grilles"][0]["valeurs"].values())
    assert comparees == total - 2
    assert not [s for s in signalees if s["degre"] == 7 and s["categorie"] in ("3", "8")]
