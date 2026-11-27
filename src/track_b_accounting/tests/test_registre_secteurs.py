"""Registre des secteurs découvert dans data/processed/salary_grids/ (calc/loaders.py, decouvrir_grilles).
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_registre_secteurs.py
"""

import json
from decimal import Decimal

import pytest
from conftest import REPO_ROOT

from track_b_accounting.calc import Refus, salaire_base
from track_b_accounting.calc import loaders

BM_FILE = REPO_ROOT / "data/processed/salary_grids/metallurgie_batiment.json"


def _ecrire(dossier, nom, code, ref="D4"):
    """Copie de la grille métallurgie sous un autre code de secteur (et une autre référence)."""
    g = json.loads(BM_FILE.read_text(encoding="utf-8"))
    g["_meta"]["secteur_code"] = code
    if ref is None:
        g["_meta"].pop("decision_ref")
    else:
        g["_meta"]["decision_ref"] = ref
    (dossier / nom).write_text(json.dumps(g, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def registre_temporaire(monkeypatch):
    """Ajoute des secteurs au registre partagé le temps d'un test, caches vidés avant et après."""
    loaders._charger_grille.cache_clear()
    yield lambda code, chemin: monkeypatch.setitem(loaders.GRILLES, code, chemin)
    loaders._charger_grille.cache_clear()


def test_registre_actuel_identique():
    assert loaders.GRILLES == {
        "METALLURGIE_BATIMENT": "data/processed/salary_grids/metallurgie_batiment.json",
        "BATIMENT_TRAVAUX_PUBLICS": "data/processed/salary_grids/batiment_travaux_publics.json",
        "ASSOCIATIONS_PERSONNES_HANDICAPEES": "data/processed/salary_grids/associations_personnes_handicapees.json",
        "ASSURANCE": "data/processed/salary_grids/assurance.json",
        "ENSEIGNEMENT_PRIVE": "data/processed/salary_grids/enseignement_prive.json",
        "BANQUES": "data/processed/salary_grids/banques.json",
        "GARDIENNAGE_SECURITE_TRANSPORT_FONDS": "data/processed/salary_grids/gardiennage.json",
        "TORREFACTION_CAFE": "data/processed/salary_grids/torrefaction_cafe.json",
        "AGENCES_VOYAGES": "data/processed/salary_grids/agences_voyages.json",
        "HOTELS_TOURISTIQUES": "data/processed/salary_grids/hotels_touristiques.json",
        "CONFISERIE_BISCUITERIE_CHOCOLATERIE": "data/processed/salary_grids/confiserie_biscuiterie.json",
        "PATES_ALIMENTAIRES_COUSCOUS": "data/processed/salary_grids/pates_alimentaires.json",
        "COSMETIQUES_PARFUMS": "data/processed/salary_grids/cosmetiques_parfums.json",
        "SAVONNERIE_RAFFINAGE_GRIGNONS": "data/processed/salary_grids/savonnerie_raffinage.json",
        "COMMERCE_DISTRIBUTION_PETROLE": "data/processed/salary_grids/distribution_petrole.json",
        "PLASTURGIE": "data/processed/salary_grids/plasturgie.json",
        "MINOTERIES": "data/processed/salary_grids/minoteries.json",
        "TEINTURERIES_PRESSINGS": "data/processed/salary_grids/teintureries_pressings.json",
        "BOISSONS_GAZEUSES": "data/processed/salary_grids/boissons_gazeuses.json",
        "MECANIQUE_STATIONS_SERVICE": "data/processed/salary_grids/mecanique_stations_service.json",
        "BOISSONS_ALCOOLISEES": "data/processed/salary_grids/boissons_alcoolisees.json",
        "BOIS_AMEUBLEMENT_LIEGE": "data/processed/salary_grids/bois_ameublement_liege.json",
        "GESTION_DECHETS": "data/processed/salary_grids/gestion_dechets.json",
        "HABILLEMENT": "data/processed/salary_grids/habillement.json",
        "COMMERCE_GROS_DETAIL": "data/processed/salary_grids/commerce_gros_detail.json",
        "IMPRIMERIE_EDITION_CARTONNAGE": "data/processed/salary_grids/imprimerie_edition.json",
        "VERRE_MIROIRS": "data/processed/salary_grids/verre_miroirs.json",
        "CONCESSIONNAIRES_MATERIEL_AGRICOLE": "data/processed/salary_grids/materiel_agricole.json",
        "BOULANGERIES": "data/processed/salary_grids/boulangeries.json",
        "TEXTILE": "data/processed/salary_grids/textile.json",
        "FONDERIE_METALLURGIE_MECANIQUE": "data/processed/salary_grids/fonderies_mecanique.json",
        "PRODUITS_ENTRETIEN_INSECTICIDES": "data/processed/salary_grids/produits_entretien.json",
        "CONSTRUCTEURS_CONCESSIONNAIRES_AUTOMOBILES": "data/processed/salary_grids/constructeurs_automobiles.json",
        "MATERIAUX_CONSTRUCTION": "data/processed/salary_grids/materiaux_construction.json",
        "PEINTURES": "data/processed/salary_grids/peintures.json",
        "CHAUSSURE": "data/processed/salary_grids/chaussure.json",
        "CUIRS_TANNERIE": "data/processed/salary_grids/cuirs_tannerie.json",
        "CLERCS_AVOCATS": "data/processed/salary_grids/clercs_avocats.json",
        "PERSONNEL_PHARMACIES": "data/processed/salary_grids/pharmacies.json",
        "CONSERVERIES_CONDITIONNEMENT_HUILES": "data/processed/salary_grids/conserveries_huiles.json",
        "GROSSISTES_REPARTITEURS_MEDICAMENTS": "data/processed/salary_grids/grossistes_medicaments.json",
        "SALLES_CINEMA": "data/processed/salary_grids/salles_cinema.json",
        "TRANSPORT_ROUTIER_MARCHANDISES": "data/processed/salary_grids/transport_routier_marchandises.json",
        "JARDINS_ENFANTS_CRECHES": "data/processed/salary_grids/jardins_enfants_creches.json",
        "CLINIQUES_PRIVEES": "data/processed/salary_grids/cliniques_privees.json",
        "LOCATION_VOITURES": "data/processed/salary_grids/location_voitures.json",
        "COMMERCE_MATERIAUX_BOIS_ACIER": "data/processed/salary_grids/commerce_materiaux_bois_acier.json",
        "CAFES_RESTAURANTS_BARS": "data/processed/salary_grids/cafes_restaurants_bars.json",
        "PORTS_CHARGEMENT_DECHARGEMENT": "data/processed/salary_grids/ports_chargement_dechargement.json",
    }
    assert (
        list(loaders.GRILLES) == loaders.secteurs_disponibles()
    )  # ordre D4, puis D9, D23, D29, D38, D46, D47, D49 à D54, D55 à D60, D61 à D66, D67 à D72, D78 à D83, D84 à D89, D91 à D96
    assert loaders.decouvrir_grilles() == loaders.GRILLES


def test_nouveau_fichier_valide_charge(tmp_path, registre_temporaire):
    _ecrire(tmp_path, "secteur_test.json", "SECTEUR_TEST", ref="D99")
    reg = loaders.decouvrir_grilles(tmp_path)
    assert list(reg) == ["SECTEUR_TEST"] and reg["SECTEUR_TEST"].endswith("/secteur_test.json")
    registre_temporaire("SECTEUR_TEST", reg["SECTEUR_TEST"])
    # Fichier hors de data/processed/ (dossier temporaire) : on ne passe pas par la fixture ok.
    r = salaire_base("SECTEUR_TEST", "admin_tech", "4", 15, "2022-06-01")
    assert r.montant == Decimal("593.873") and r.citations[0].decision_ref == "D99"
    assert r.citations[0].data_file == reg["SECTEUR_TEST"]


@pytest.mark.parametrize("ref", [None, "", "4", "D", "D-4", "d4", "D4a", 4])
def test_fichier_sans_decision_ref_valide_ignore(tmp_path, ref):
    _ecrire(tmp_path, "sans_ref.json", "SANS_REF", ref=ref)
    assert loaders.decouvrir_grilles(tmp_path) == {}


def test_fichier_ignore_refuse_comme_secteur_inconnu():
    """Un code absent du registre (fichier ignoré ou inexistant) : SOURCE_MANQUANTE, liste des secteurs disponibles."""
    with pytest.raises(Refus) as e:
        salaire_base("SANS_REF", "admin_tech", "4", 15, "2022-06-01")
    assert e.value.code == Refus.SOURCE_MANQUANTE
    assert e.value.message_fr == (
        "Aucune grille vérifiée pour le secteur 'SANS_REF' "
        "(disponibles : METALLURGIE_BATIMENT, BATIMENT_TRAVAUX_PUBLICS, ASSOCIATIONS_PERSONNES_HANDICAPEES, ASSURANCE, ENSEIGNEMENT_PRIVE, BANQUES, GARDIENNAGE_SECURITE_TRANSPORT_FONDS, "
        "TORREFACTION_CAFE, AGENCES_VOYAGES, HOTELS_TOURISTIQUES, CONFISERIE_BISCUITERIE_CHOCOLATERIE, PATES_ALIMENTAIRES_COUSCOUS, COSMETIQUES_PARFUMS, "
        "SAVONNERIE_RAFFINAGE_GRIGNONS, COMMERCE_DISTRIBUTION_PETROLE, PLASTURGIE, MINOTERIES, TEINTURERIES_PRESSINGS, BOISSONS_GAZEUSES, "
        "MECANIQUE_STATIONS_SERVICE, BOISSONS_ALCOOLISEES, BOIS_AMEUBLEMENT_LIEGE, GESTION_DECHETS, HABILLEMENT, COMMERCE_GROS_DETAIL, "
        "IMPRIMERIE_EDITION_CARTONNAGE, VERRE_MIROIRS, CONCESSIONNAIRES_MATERIEL_AGRICOLE, BOULANGERIES, TEXTILE, FONDERIE_METALLURGIE_MECANIQUE, "
        "PRODUITS_ENTRETIEN_INSECTICIDES, CONSTRUCTEURS_CONCESSIONNAIRES_AUTOMOBILES, MATERIAUX_CONSTRUCTION, PEINTURES, CHAUSSURE, CUIRS_TANNERIE, "
        "CLERCS_AVOCATS, PERSONNEL_PHARMACIES, CONSERVERIES_CONDITIONNEMENT_HUILES, GROSSISTES_REPARTITEURS_MEDICAMENTS, SALLES_CINEMA, TRANSPORT_ROUTIER_MARCHANDISES, "
        "JARDINS_ENFANTS_CRECHES, CLINIQUES_PRIVEES, LOCATION_VOITURES, COMMERCE_MATERIAUX_BOIS_ACIER, CAFES_RESTAURANTS_BARS, PORTS_CHARGEMENT_DECHARGEMENT)."
    )


def test_fichiers_invalides_ou_ambigus_ignores(tmp_path):
    (tmp_path / "mal_forme.json").write_text("{", encoding="utf-8")
    (tmp_path / "liste.json").write_text("[]", encoding="utf-8")
    (tmp_path / "sans_code.json").write_text(json.dumps({"_meta": {"decision_ref": "D4"}}), encoding="utf-8")
    _ecrire(tmp_path, "a.json", "DOUBLON", ref="D4")
    _ecrire(tmp_path, "b.json", "DOUBLON", ref="D5")  # même code dans deux fichiers : ambigu
    _ecrire(tmp_path, "c.json", "UNIQUE", ref="D7")
    assert loaders.decouvrir_grilles(tmp_path) == {"UNIQUE": (tmp_path / "c.json").resolve().as_posix()}


def test_ordre_par_numero_de_decision(tmp_path):
    _ecrire(tmp_path, "a.json", "ZETA", ref="D2")
    _ecrire(tmp_path, "b.json", "ALPHA", ref="D10")
    _ecrire(tmp_path, "c.json", "BETA", ref="D10")
    assert list(loaders.decouvrir_grilles(tmp_path)) == ["ZETA", "ALPHA", "BETA"]
