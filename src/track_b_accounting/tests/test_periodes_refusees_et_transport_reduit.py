"""Deux champs optionnels des grilles (D80), testés sur des grilles fictives tirées de METALLURGIE_BATIMENT.

1. periodes_refusees d'une table : une période de la table contredite par une autre source (ex. date d'un avenant
   contraire au titre du tableau) est refusée avec le message lu dans le JSON ; avant et après, la table est servie.
2. montant_reduit_si_transport_assure sur une prime datée, avec ou sans groupe : transport_assure obligatoire,
   montant réduit servi quand il vaut True. Le chemin du montant unique (prime_panier_qefa) est inchangé.
Les deux champs passent par les contrats v0 et v1 sans changement des schémas de requête.
"""

import copy
from decimal import Decimal

import pytest
from conftest import lire_json

from track_b_accounting.calc import Refus, loaders, prime, salaire_base
from track_b_accounting.contract.handler import handle

S = "METALLURGIE_BATIMENT"
BM = lire_json("data/processed/salary_grids/metallurgie_batiment.json")
PERIODE = {
    "du": "2021-12-01",
    "au": "2022-11-30",
    "source_pdf_page": 3,
    "source_article": "ملحق تعديلي عدد 16",
    "message_fr": "FR-TEST période contredite",
    "message_ar": "AR-TEST فترة",
}
T21, T23 = "BM_E_2021-12-01", "BM_E_2023-01-01"


def _table(g: dict, tid: str) -> dict:
    return next(t for t in g["grilles"] if t["table_id"] == tid)


def grille_fictive(periodes=None, reduit=Decimal("0.000"), groupes=True) -> dict:
    g = copy.deepcopy(BM)
    if periodes is not None:
        _table(g, T21)["periodes_refusees"] = periodes
    p = next(p for p in g["primes"] if p["code"] == "prime_transport")
    if reduit is not None:
        p["montant_reduit_si_transport_assure"] = reduit
    if not groupes:
        p["montants"] = [{"effective_date": m["effective_date"], "montant": m["cadres"]} for m in p["montants"]]
        p.pop("libelles_groupes", None)
    return g


@pytest.fixture
def fictif(monkeypatch):
    def installer(g: dict) -> dict:
        g = loaders.valider_grille(g, "fictif.json")
        monkeypatch.setattr("track_b_accounting.calc.salary.charger_grille", lambda s: g)
        monkeypatch.setattr("track_b_accounting.calc.primes.charger_grille", lambda s: g)
        return g

    return installer


# --- 1. periodes_refusees ------------------------------------------------------------------------------------------


def test_periode_acceptee_par_le_validateur():
    g = loaders.valider_grille(grille_fictive([dict(PERIODE)]), "fictif.json")
    assert _table(g, T21)["periodes_refusees"] == [PERIODE]


@pytest.mark.parametrize("jour", ["2021-12-01", "2022-06-15", "2022-11-30"])
def test_jour_dans_la_periode_refuse_avec_le_message_du_json(fictif, jour):
    fictif(grille_fictive([dict(PERIODE)]))
    with pytest.raises(Refus) as e:
        salaire_base(S, "execution", "1", 5, jour)
    assert (e.value.code, e.value.message_fr, e.value.message_ar) == (
        Refus.SOURCE_MANQUANTE,
        "FR-TEST période contredite",
        "AR-TEST فترة",
    )


@pytest.mark.parametrize("jour, tid", [("2022-12-01", T21), ("2022-12-31", T21), ("2023-06-01", T23)])
def test_hors_periode_la_table_est_servie(fictif, jour, tid):
    fictif(grille_fictive([dict(PERIODE)]))
    assert salaire_base(S, "execution", "1", 5, jour).montant == _table(BM, tid)["valeurs"]["1"][2]


def test_autre_population_et_primes_non_touchees(fictif):
    fictif(grille_fictive([dict(PERIODE)]))
    t = _table(BM, "BM_T_2021-12-01")
    assert salaire_base(S, "admin_tech", "4", 15, "2022-06-01").montant == t["valeurs"]["4"][7]
    assert prime(S, "prime_transport", "2022-06-01", groupe="cadres", transport_assure=False).montant == Decimal(
        "88.221"
    )


def test_par_le_degre_aussi_refuse(fictif):
    fictif(grille_fictive([dict(PERIODE)]))
    with pytest.raises(Refus) as e:
        salaire_base(S, "execution", "1", None, "2022-06-01", degre=3)
    assert e.value.message_fr == "FR-TEST période contredite"


def test_deux_periodes_disjointes(fictif):
    a = dict(PERIODE, du="2021-12-01", au="2022-01-31")
    b = dict(PERIODE, du="2022-06-01", au="2022-06-30", message_fr="FR-TEST b")
    fictif(grille_fictive([b, a]))
    assert salaire_base(S, "execution", "1", 5, "2022-03-01").montant == _table(BM, T21)["valeurs"]["1"][2]
    with pytest.raises(Refus) as e:
        salaire_base(S, "execution", "1", 5, "2022-06-10")
    assert e.value.message_fr == "FR-TEST b"


@pytest.mark.parametrize(
    "periodes",
    [
        [],
        {},
        [dict(PERIODE, du="2021-11-30")],  # avant la date d'effet de la table
        [dict(PERIODE, au="2021-11-30", du="2021-12-01")],  # au < du
        [dict(PERIODE, du="2021-12-1")],
        [dict(PERIODE, du=None)],
        [dict(PERIODE, message_ar="")],
        [dict(PERIODE, source_pdf_page=0)],
        [dict(PERIODE), dict(PERIODE, du="2022-11-30", au="2022-12-15")],  # chevauchement
        [{k: v for k, v in PERIODE.items() if k != "au"}],
    ],
)
def test_periode_invalide_refusee_par_le_validateur(periodes):
    with pytest.raises(Refus) as e:
        loaders.valider_grille(grille_fictive(periodes), "fictif.json")
    assert e.value.code == Refus.SOURCE_MANQUANTE


def test_periode_au_dela_de_valide_jusqu_au_refusee():
    g = grille_fictive([dict(PERIODE, au="2022-12-31")])
    _table(g, T21)["valide_jusqu_au"] = dict(
        date="2022-11-30", source_pdf_page=3, source_article="x", message_fr="fin", message_ar="fin"
    )
    with pytest.raises(Refus):
        loaders.valider_grille(g, "fictif.json")


# --- 2. montant_reduit_si_transport_assure sur une prime datée -----------------------------------------------------


@pytest.mark.parametrize(
    "jour, cadres", [("2022-06-01", "88.221"), ("2023-06-01", "94.176"), ("2024-06-01", "100.533")]
)
def test_prime_datee_a_groupes_reduite_si_transport_assure(fictif, jour, cadres):
    fictif(grille_fictive())
    plein = prime(S, "prime_transport", jour, groupe="cadres", transport_assure=False)
    reduit = prime(S, "prime_transport", jour, groupe="cadres", transport_assure=True)
    assert plein.montant == Decimal(cadres) and plein.detail["transport_assure"] is False
    assert reduit.montant == Decimal("0.000") and reduit.detail["transport_assure"] is True
    assert reduit.detail["groupe"] == "cadres" and reduit.detail["effective_date"] == plein.detail["effective_date"]


def test_prime_datee_sans_groupe_reduite(fictif):
    fictif(grille_fictive(reduit=Decimal("1.500"), groupes=False))
    assert prime(S, "prime_transport", "2024-06-01", transport_assure=True).montant == Decimal("1.500")
    assert prime(S, "prime_transport", "2024-06-01", transport_assure=False).montant == Decimal("100.533")


@pytest.mark.parametrize("val", [None, "oui", 1])
def test_transport_assure_obligatoire_sur_la_prime_datee(fictif, val):
    fictif(grille_fictive())
    kwargs = {} if val is None else {"transport_assure": val}
    with pytest.raises(Refus) as e:
        prime(S, "prime_transport", "2024-06-01", groupe="cadres", **kwargs)
    assert e.value.code == Refus.PARAM_INVALIDE


@pytest.mark.parametrize("reduit", [Decimal("-0.001"), "0", True, None])
def test_montant_reduit_invalide_refuse(reduit):
    g = grille_fictive(reduit=None)
    next(p for p in g["primes"] if p["code"] == "prime_transport")["montant_reduit_si_transport_assure"] = reduit
    with pytest.raises(Refus):
        loaders.valider_grille(g, "fictif.json")


def test_prime_a_montant_unique_inchangee():
    """prime_panier_qefa (seule prime réelle qui porte ce champ) : mêmes montants et mêmes clés de détail."""
    for transport, montant in ((False, None), (True, Decimal("0.160"))):
        r = prime(S, "prime_panier_qefa", "2024-06-01", transport_assure=transport)
        attendu = montant or next(p for p in BM["primes"] if p["code"] == "prime_panier_qefa")["montant"]
        assert r.montant == attendu and r.detail["transport_assure"] is transport


# --- contrats v0 et v1 : aucun changement des schémas de requête ---------------------------------------------------


@pytest.mark.parametrize("version", ["track_b.v0", "track_b.v1"])
def test_les_deux_champs_passent_par_les_contrats(fictif, version):
    fictif(grille_fictive([dict(PERIODE)]))
    base = {"contract_version": version, "lang": "fr"}
    rep = handle(
        dict(
            base,
            request_id="t-transport",
            operation="prime",
            params={
                "secteur": S,
                "code": "prime_transport",
                "date": "2024-06-01",
                "groupe": "cadres",
                "transport_assure": True,
            },
        )
    )
    assert rep["status"] == "ok" and Decimal(rep["result"]["montant"]) == Decimal("0")
    rep = handle(
        dict(
            base,
            request_id="t-periode",
            operation="salaire_base",
            params={
                "secteur": S,
                "population": "execution",
                "categorie": "1",
                "anciennete_annees": 5,
                "date": "2022-06-01",
            },
        )
    )
    assert rep["status"] == "refus" and rep["refus"]["message_fr"] == "FR-TEST période contredite"
