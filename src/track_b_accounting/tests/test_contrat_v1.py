"""Contrat track_b.v1 à côté de v0 (D75, D76) : demande par degré déclaré, montants imprimés exacts.

La preuve « v0 inchangé » : fichiers v0 identiques (empreintes), et chaque démo v0 rejouée en v1 donne la même
réponse (hors contract_version), sauf les écarts listés. Lancer depuis la racine du dépôt.
"""

import copy
import datetime
import hashlib
import io
import json
import re
from decimal import Decimal as D

import pytest
from conftest import REPO_ROOT, lire_json
from jsonschema import Draft202012Validator
from mocks import DEMO_FILE, DEMO_FILE_V1

from track_b_accounting.calc import Refus, prime, prime_v1, salaire_base
from track_b_accounting.calc import loaders
from track_b_accounting.contract import cli, handle
from track_b_accounting.contract import handler as H

SCHEMAS = REPO_ROOT / "data" / "mock_cards" / "schemas"


def _schema(nom: str) -> dict:
    return json.loads((SCHEMAS / nom).read_text(encoding="utf-8"))


REQ_V0, REP_V0 = _schema("track_b_request.v0.schema.json"), _schema("track_b_response.v0.schema.json")
REQ_V1, REP_V1 = _schema("track_b_request.v1.schema.json"), _schema("track_b_response.v1.schema.json")
COMMUN = Draft202012Validator(
    json.loads((REPO_ROOT / "src/shared/schemas/common.v0.schema.json").read_text(encoding="utf-8"))
)
REQ1_V, REP1_V = Draft202012Validator(REQ_V1), Draft202012Validator(REP_V1)
REP0_V = Draft202012Validator(REP_V0)
DEMO = json.loads(DEMO_FILE.read_text(encoding="utf-8"))
DEMO_V1 = json.loads(DEMO_FILE_V1.read_text(encoding="utf-8"))
V1 = "track_b.v1"


def valide_v1(rep: dict) -> dict:
    erreurs = sorted(REP1_V.iter_errors(rep), key=str)
    assert not erreurs, [e.message for e in erreurs]
    assert COMMUN.is_valid(rep)
    return rep


def req_v1(operation: str, **params) -> dict:
    return {"contract_version": V1, "request_id": "t-v1", "operation": operation, "params": params, "lang": "fr"}


def refus(exc: pytest.ExceptionInfo) -> tuple[str, str]:
    return exc.value.code, exc.value.message_fr


# --- v0 inchangé ----------------------------------------------------------------------------------------------------


def _empreinte(chemin: str) -> str:
    return hashlib.sha256((REPO_ROOT / chemin).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


@pytest.mark.parametrize(
    "chemin,empreinte",
    [
        (
            "data/mock_cards/schemas/track_b_request.v0.schema.json",
            "28a0543a4d8edf4111e638117d0684bb2e659a6d845658e13afb07460d1dcc05",
        ),
        (
            "data/mock_cards/schemas/track_b_response.v0.schema.json",
            "3dacaa34622da5b814d13dcd1864bea96cd324e2f6db718bc076a1ab6e9fe285",
        ),
    ],
)
def test_fichiers_v0_identiques_a_l_octet(chemin, empreinte):
    """Schémas v0 : contenu inchangé (fins de ligne normalisées)."""
    assert _empreinte(chemin) == empreinte


# 211 démos v0 figées au contrat v1 (D75) : requêtes et réponses de référence, valables quand des démos ou des secteurs
# s'ajoutent. Empreinte = SHA-256 du JSON canonique (clés triées, UTF-8) ; seule demo-10 change avec les secteurs.
N_DEMOS_FIGEES = 211
D10 = "demo-10-refus-secteur-non-couvert"
EMPREINTE_REQUETES_FIGEES = "a0fc6e2fdbe123062bab4e9c3cd0184eade26f2deb0313c390dfe0ed929579d0"
EMPREINTE_REPONSES_FIGEES_HORS_D10 = "e2431c7a2b4de0ce0e22cfedebd15be2a9e8120f3dcd63fb1f450901f61dee98"
EMPREINTE_D10_SANS_LISTE = "e65e5b6f451f6abea5aeced35cffd04722188b05ad846a0203af9ac1a5bef0c2"
SECTEURS_D10_FIGES = (
    "METALLURGIE_BATIMENT, BATIMENT_TRAVAUX_PUBLICS, ASSOCIATIONS_PERSONNES_HANDICAPEES, ASSURANCE, ENSEIGNEMENT_PRIVE, "
    "BANQUES, GARDIENNAGE_SECURITE_TRANSPORT_FONDS, TORREFACTION_CAFE, AGENCES_VOYAGES, HOTELS_TOURISTIQUES, "
    "CONFISERIE_BISCUITERIE_CHOCOLATERIE, PATES_ALIMENTAIRES_COUSCOUS, COSMETIQUES_PARFUMS, SAVONNERIE_RAFFINAGE_GRIGNONS, "
    "COMMERCE_DISTRIBUTION_PETROLE, PLASTURGIE, MINOTERIES, TEINTURERIES_PRESSINGS, BOISSONS_GAZEUSES, "
    "MECANIQUE_STATIONS_SERVICE, BOISSONS_ALCOOLISEES, BOIS_AMEUBLEMENT_LIEGE, GESTION_DECHETS, HABILLEMENT, "
    "COMMERCE_GROS_DETAIL, IMPRIMERIE_EDITION_CARTONNAGE, VERRE_MIROIRS, CONCESSIONNAIRES_MATERIEL_AGRICOLE, BOULANGERIES, "
    "TEXTILE, FONDERIE_METALLURGIE_MECANIQUE"
).split(", ")
LISTE_SECTEURS = re.compile(r"\((disponibles : |المتوفر: )([A-Z_, ]+)\)\.$")
REPONSES_REF = json.loads(
    (REPO_ROOT / "src/track_b_accounting/tests/references/track_b_responses_demo.json").read_text(encoding="utf-8")
)


def _empreinte_json(objet) -> str:
    return hashlib.sha256(json.dumps(objet, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def test_211_premieres_demos_v0_inchangees():
    assert len(DEMO) >= N_DEMOS_FIGEES and len(REPONSES_REF) == len(DEMO)
    assert _empreinte_json(DEMO[:N_DEMOS_FIGEES]) == EMPREINTE_REQUETES_FIGEES
    figees = [r for r in REPONSES_REF[:N_DEMOS_FIGEES] if r["request_id"] != D10]
    assert len(figees) == N_DEMOS_FIGEES - 1
    assert _empreinte_json(figees) == EMPREINTE_REPONSES_FIGEES_HORS_D10


def test_demo_10_ne_differe_que_par_la_liste_des_secteurs():
    """Réponse de demo-10 = réponse figée, liste des secteurs disponibles mise à part ; chaque secteur figé y est encore,
    dans les deux langues, avec la même liste en FR et en AR."""
    rep = copy.deepcopy(next(r for r in REPONSES_REF[:N_DEMOS_FIGEES] if r["request_id"] == D10))
    listes = []
    for k in ("message_fr", "message_ar"):
        m = LISTE_SECTEURS.search(rep["refus"][k])
        assert m, k
        listes.append(m[2].split(", "))
        rep["refus"][k] = LISTE_SECTEURS.sub(r"(\1…).", rep["refus"][k])
    assert _empreinte_json(rep) == EMPREINTE_D10_SANS_LISTE
    assert listes[0] == listes[1] and len(set(listes[0])) == len(listes[0])
    assert set(SECTEURS_D10_FIGES) <= set(listes[0])


# Démos v0 rejouées en v1 : seules différences admises (D76) ; la CNSS nomme la version dans son message.
ECARTS_V1 = {
    "demo-134-refus-alcool-prime-panier": ("refus", "PARAM_INVALIDE"),  # servie en v1, condition_remplie exigée
    "demo-142-refus-bois-aide-deces": ("refus", "PARAM_INVALIDE"),  # idem
    "demo-209-refus-fonderie-prime-panier": ("ok", None),  # servie en v1 : 706.666 millimes/jour
}


@pytest.mark.parametrize("req", DEMO, ids=lambda r: r["request_id"])
def test_demo_v0_rejouee_en_v1_meme_reponse(req):
    rep0 = handle(req)
    rep1 = valide_v1(handle(dict(copy.deepcopy(req), contract_version=V1)))
    rid = req["request_id"]
    if rid in ECARTS_V1:
        assert rep0["status"] == "refus" and rep0["refus"]["code"] == "SOURCE_MANQUANTE"
        statut, code = ECARTS_V1[rid]
        assert rep1["status"] == statut and (rep1["refus"] or {}).get("code") == code
        return
    attendu = dict(rep0, contract_version=V1)
    if rid == "demo-07-refus-cnss":
        for k in ("message_fr", "message_ar"):
            attendu["refus"][k] = rep0["refus"][k].replace("Track B v0", "Track B v1").replace("المسار B", "المسار B")
    assert rep1 == attendu


def test_requete_v1_sans_degre_identique_a_v0():
    req = next(r for r in DEMO_V1 if r["request_id"] == "demo-v1-18-sans-degre-identique-a-v0")
    rep0 = handle(dict(req, contract_version="track_b.v0"))
    assert handle(req) == dict(rep0, contract_version=V1)
    assert rep0["result"]["montant"] == "593.873"


# --- schémas v1 -----------------------------------------------------------------------------------------------------


def test_schemas_v1_bien_formes_et_ecarts_avec_v0():
    for s in (REQ_V1, REP_V1):
        Draft202012Validator.check_schema(s)
        assert "v1 — proposition Track B, à valider avec l'équipe" in s["description"]
    assert REQ_V1["properties"]["contract_version"] == {"const": V1}
    p0, p1 = REQ_V0["$defs"]["params_salaire_base"], REQ_V1["$defs"]["params_salaire_base"]
    assert set(p1["properties"]) == set(p0["properties"]) | {"degre"}
    assert p1["properties"]["degre"]["type"] == ["integer", "string"]
    assert {k: v for k, v in REQ_V1["$defs"].items() if k != "params_salaire_base"} == {
        k: v for k, v in REQ_V0["$defs"].items() if k != "params_salaire_base"
    }
    r0, r1 = REP_V0["properties"]["result"]["oneOf"][1], REP_V1["properties"]["result"]["oneOf"][1]
    assert r1["properties"]["montant"]["pattern"] == "^-?[0-9]+\\.[0-9]{3,}$"
    assert r1["properties"]["unite"]["pattern"] == "^(TND|millimes)/"
    assert r1["properties"]["detail"] == r0["properties"]["detail"]
    assert REP_V1["allOf"] == REP_V0["allOf"] and REP_V1["$defs"] == REP_V0["$defs"]


@pytest.mark.parametrize(
    "degre,valide",
    [(5, True), ("stage", True), ("unique", True), (5.0, True), ("", False), (5.5, False), (True, False)],
)
def test_schema_v1_type_du_degre(degre, valide):
    """5.0 est un entier au sens de JSON Schema : le schéma l'accepte, calc/ le refuse (test_degre_invalide_…)."""
    req = req_v1(
        "salaire_base", secteur="VERRE_MIROIRS", population="horaires", categorie="3", degre=degre, date="2024-06-01"
    )
    assert REQ1_V.is_valid(req) is valide


def test_schema_v0_refuse_toujours_degre():
    req = dict(
        req_v1(
            "salaire_base", secteur="VERRE_MIROIRS", population="horaires", categorie="3", degre=5, date="2024-06-01"
        ),
        contract_version="track_b.v0",
    )
    rep = handle(req)
    assert REP0_V.is_valid(rep) and rep["contract_version"] == "track_b.v0"
    assert rep["refus"]["code"] == "PARAM_INVALIDE" and rep["computed_by"] == "track_b_accounting.contract"
    assert rep["refus"]["message_fr"].startswith("Requête non conforme au contrat track_b.v0 (params)")


def test_schema_v1_montant_a_plus_de_3_decimales_et_millimes():
    rep = handle(
        req_v1("prime", secteur="BOIS_AMEUBLEMENT_LIEGE", code="aide_deces", date="2024-06-01", condition_remplie=True)
    )
    assert valide_v1(rep)["result"]["montant"] == "466.6666"
    assert not REP0_V.is_valid(dict(rep, contract_version="track_b.v0"))
    rep2 = copy.deepcopy(rep)
    rep2["result"]["montant"] = "466.66"
    assert not REP1_V.is_valid(rep2)
    rep2["result"].update(montant="466.666", unite="EUR/versement")
    assert not REP1_V.is_valid(rep2)


# --- handler : choix de la version ---------------------------------------------------------------------------------


@pytest.mark.parametrize("version", ["track_b.v9", "track_b.v1 ", "TRACK_B.V1", None])
def test_version_inconnue_traitee_en_v0(version):
    req = dict(copy.deepcopy(DEMO[0]), contract_version=version)
    rep = handle(req)
    assert REP0_V.is_valid(rep) and rep["contract_version"] == "track_b.v0"
    assert rep["refus"]["message_fr"].startswith("Requête non conforme au contrat track_b.v0 (contract_version)")


def test_refus_de_contrat_v1_nomme_la_version_v1():
    rep = valide_v1(
        handle(dict(req_v1("salaire_base", secteur="VERRE_MIROIRS", categorie="3", degre=5.5, date="2024-06-01")))
    )
    assert rep["refus"]["code"] == "PARAM_INVALIDE"
    assert rep["refus"]["message_fr"].startswith("Requête non conforme au contrat track_b.v1 (params/degre)")
    assert "track_b.v1" in rep["refus"]["message_ar"]


def test_erreur_interne_en_v1_reste_une_reponse_v1(monkeypatch):
    def boom(**_):
        raise RuntimeError("panne")

    monkeypatch.setitem(H.OPERATIONS_V1, "smig", boom)
    req = dict(copy.deepcopy(DEMO[4]), contract_version=V1)
    rep = valide_v1(handle(req))
    assert rep["status"] == "erreur" and rep["contract_version"] == V1 and "panne" not in json.dumps(rep)


def test_contrat_n_est_pas_un_parametre_de_la_requete():
    """En v0, un paramètre « contrat » n'ouvre pas le service v1 des primes : refus v0 inchangé."""
    req = dict(
        copy.deepcopy(DEMO[0]),
        operation="prime",
        params={
            "secteur": "FONDERIE_METALLURGIE_MECANIQUE",
            "code": "prime_panier",
            "date": "2024-06-01",
            "contrat": "v1",
        },
    )
    rep = handle(req)
    assert rep["contract_version"] == "track_b.v0" and rep["refus"]["code"] == "SOURCE_MANQUANTE"
    with pytest.raises(Refus) as e:
        prime_v1("VERRE_MIROIRS", "prime_caisse", "2024-06-01", condition_remplie=True, contrat="v1")
    assert e.value.code == Refus.PARAM_INVALIDE and "contrat" in e.value.message_fr


# --- démos v1 -------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("req", DEMO_V1, ids=lambda r: r["request_id"])
def test_demo_v1_requete_et_reponse_conformes(req):
    assert REQ1_V.is_valid(req) and req["contract_version"] == V1
    rep = valide_v1(handle(req))
    assert rep["request_id"] == req["request_id"] and rep["contract_version"] == V1
    if rep["status"] == "ok":
        assert rep["citations"] and re.fullmatch(r"\d+\.\d{3,}", rep["result"]["montant"])
    else:
        assert rep["status"] == "refus" and rep["result"] is None and rep["citations"] == []


def test_bilan_demo_v1():
    reps = {r["request_id"]: handle(r) for r in DEMO_V1}
    montants = {k: (r["result"]["montant"], r["result"]["unite"]) for k, r in reps.items() if r["status"] == "ok"}
    assert montants == {
        "demo-v1-01-verre-horaires-degre-5": ("4.055", "TND/heure"),
        "demo-v1-02-verre-mensuels-dernier-degre": ("648.760", "TND/mois"),
        "demo-v1-03-textile-colonne-stage": ("559.062", "TND/mois"),
        "demo-v1-04-textile-colonne-0": ("2.829", "TND/heure"),
        "demo-v1-05-textile-colonne-19": ("1273.662", "TND/mois"),
        "demo-v1-06-textile-colonne-20": ("2.604", "TND/heure"),
        "demo-v1-07-banques-colonne-stage": ("1687.106", "TND/mois"),
        "demo-v1-13-metallurgie-dernier-degre": ("680.334", "TND/mois"),
        "demo-v1-14-cosmetiques-degre-unique": ("575.741", "TND/mois"),
        "demo-v1-15-alcool-prime-panier-millimes": ("416.666", "millimes/jour"),
        "demo-v1-16-bois-aide-deces-4-decimales": ("466.6666", "TND/versement"),
        "demo-v1-17-fonderie-prime-panier-millimes": ("706.666", "millimes/jour"),
        "demo-v1-18-sans-degre-identique-a-v0": ("593.873", "TND/mois"),
        "demo-v1-19-peintures-execution-horaires-degre-13": ("5.668", "TND/heure"),
        "demo-v1-20-peintures-administratifs-degre-1": ("1428.536", "TND/mois"),
        "demo-v1-21-peintures-execution-mensuels-degre-7": ("540.294", "TND/mois"),
        "demo-v1-22-chaussure-horaires-degre-30": ("3.881", "TND/heure"),
        "demo-v1-23-chaussure-mensuels-1b-degre-1": ("579.170", "TND/mois"),
        "demo-v1-24-chaussure-mensuels-anomalie-degre-24": ("707.557", "TND/mois"),
        "demo-v1-26-cinema-projectionniste-degre-13": ("410.151", "TND/mois"),
        "demo-v1-27-transport-categorie-15-degre-13": ("748.830", "TND/mois"),
        "demo-v1-28-clercs-anomalie-degre-5": ("348.380", "TND/mois"),
        "demo-v1-29-grossistes-ii-a-degre-15": ("465.220", "TND/mois"),
        "demo-v1-30-cafes-grands-colonne-recrutement": ("423.227", "TND/mois"),
        "demo-v1-31-cafes-categorie-1-degre-12": ("388.635", "TND/mois"),
        "demo-v1-32-ports-titularises-19-degre-20": ("1076.610", "TND/mois"),
        "demo-v1-34-jardins-creches-4-degre-16": ("467.429", "TND/mois"),
        "demo-v1-35-materiaux-horaires-2-degre-12": ("3.209", "TND/heure"),
        "demo-v1-36-location-17-degre-18": ("1761.853", "TND/mois"),
        "demo-v1-37-electricite-execution-48h-e11-degre-15": ("1320.776", "TND/mois"),
        "demo-v1-39-presse-mensuels-83-degre-28": ("2126.557", "TND/mois"),
        "demo-v1-40-lait-administratifs-x-b-degre-14": ("1793.245", "TND/mois"),
    }
    codes = {k: r["refus"]["code"] for k, r in reps.items() if r["status"] == "refus"}
    assert codes == {
        "demo-v1-08-refus-banques-colonne-1": "PARAM_INVALIDE",
        "demo-v1-09-refus-degre-absent": "PARAM_INVALIDE",
        "demo-v1-10-refus-degre-et-anciennete": "PARAM_INVALIDE",
        "demo-v1-11-refus-ni-degre-ni-anciennete": "PARAM_INVALIDE",
        "demo-v1-12-refus-confiserie-cellule-illisible": "SOURCE_MANQUANTE",
        "demo-v1-25-refus-peintures-degre-absent": "PARAM_INVALIDE",
        "demo-v1-33-ports-manutention-cellule-non-tranchee": "SOURCE_MANQUANTE",
        "demo-v1-38-electricite-degre-7-trait-blanc": "SOURCE_MANQUANTE",
        "demo-v1-41-explosifs-cellule-nette-non-servie": "SOURCE_MANQUANTE",
    }


def test_demos_v1_identiques_a_la_reference_a_l_octet():
    sortie = io.StringIO()
    assert cli.main([str(DEMO_FILE_V1)], stdout=sortie) == 0
    reference = (REPO_ROOT / "src/track_b_accounting/tests/references/track_b_responses_demo.v1.json").read_text(
        encoding="utf-8"
    )
    assert sortie.getvalue() == reference


def test_demo_affiche_la_serie_v1_apres_la_serie_v0():
    from track_b_accounting.demo import main

    out = io.StringIO()
    assert main(out=out) == 0
    texte = out.getvalue()
    assert texte.count("=== Contrat v1, démo ") == len(DEMO_V1) == 41
    assert texte.index("Bilan : 225 ok, 169 refus, 0 erreur(s).") < texte.index("=== Contrat v1, démo 1/41")
    assert texte.rstrip().endswith("Bilan v1 : 32 ok, 9 refus, 0 erreur(s).")


# --- demande par degré : chaque cellule imprimée ----------------------------------------------------------------------


def _requete_categorie(grille: dict, pop: str, cle: str) -> tuple[str, str | None]:
    for cat, sous in grille.get("sous_categories", {}).get(pop, {}).get("par_categorie", {}).items():
        for nom, s in sous.items():
            if s["cle"] == cle:
                return cat, nom
    return cle, None


def test_chaque_cellule_atteinte_par_son_degre_imprime():
    """Toute cellule de valeurs, de colonnes_non_servies (servies_par_degre) et de case « stage » servie par degré
    est servie telle qu'imprimée par sa désignation ; une case illisible non servie reste refusée avec son message."""
    vus = servis = refuses = 0
    for secteur, chemin in loaders.GRILLES.items():
        g = lire_json(chemin)
        if g["_meta"].get("tables_transcrites", True) is not True:
            continue
        for t in g["grilles"]:
            pop = loaders.population_de_table(g, t)
            degres = g["degres"][pop]
            if not degres:
                continue
            noms = loaders.designations_degres(degres)
            manquantes = {(c["categorie"], c["degre"]): c for c in t.get("cellules_source_manquante", [])}
            jour = t["effective_date"]
            for p in t.get("periodes_refusees", []):  # date d'effet refusée (D80) : lendemain de la période
                if p["du"] <= jour <= p["au"]:
                    jour = (datetime.date.fromisoformat(p["au"]) + datetime.timedelta(days=1)).isoformat()
            ns = t.get("colonnes_non_servies") if t.get("colonnes_non_servies", {}).get("servies_par_degre") else None
            for cle, vals in t["valeurs"].items():
                cat, sous = _requete_categorie(g, pop, cle)
                cases = list(zip(noms, vals, range(1, len(vals) + 1)))
                if ns:
                    cases += [(n, v, None) for n, v in zip(ns["colonnes_imprimees"], ns["valeurs"][cle])]
                for nom, v, deg in cases:
                    vus += 1
                    try:
                        r = salaire_base(secteur, pop, cat, None, jour, None, sous, degre=nom)
                    except Refus as e:
                        c = manquantes.get((cle, deg))
                        assert v is None and c is not None and not c.get("servie_par_degre"), (secteur, cle, nom)
                        assert (e.code, e.message_fr) == (Refus.SOURCE_MANQUANTE, c["message_fr"])
                        refuses += 1
                        continue
                    if r.detail["table_id"] != t["table_id"]:
                        continue  # deux tables de même date pour la population : déjà refusé par les tests v0
                    attendu = manquantes[(cle, deg)]["valeur_imprimee"] if v is None else v
                    assert r.montant == attendu.quantize(D("0.001")), (secteur, t["table_id"], cle, nom)
                    assert r.detail["degre_imprime"] == nom and r.detail["degre_declare"] is True
                    assert "anciennete_annees" not in r.detail and r.detail["regles"] == "D75"
                    assert r.citations[0].page == t["source_pdf_page"]
                    servis += 1
    assert vus > 15000 and refuses > 0 and servis + refuses <= vus


def test_textile_stage_servi_par_degre_refuse_par_l_anciennete():
    g = lire_json(loaders.GRILLES["TEXTILE"])
    n = 0
    for t in (t for t in g["grilles"] if t["population"] == "mensuels"):
        for c in t["cellules_source_manquante"]:
            assert c["servie_par_degre"] is True
            cat, sous = _requete_categorie(g, "mensuels", c["categorie"])
            r = salaire_base("TEXTILE", "mensuels", cat, None, t["effective_date"], None, sous, degre="stage")
            assert r.montant == c["valeur_imprimee"] and r.detail["anciennete_imprimee"] == "période de stage"
            with pytest.raises(Refus) as e:
                salaire_base("TEXTILE", "mensuels", cat, D("0.5"), t["effective_date"], None, sous)
            assert refus(e) == (Refus.SOURCE_MANQUANTE, c["message_fr"])
            n += 1
    assert n == 36


@pytest.mark.parametrize("pop,seuil", [("horaires", 35), ("mensuels", 36)])
def test_textile_colonnes_19_et_20_par_degre_seulement(pop, seuil):
    g = lire_json(loaders.GRILLES["TEXTILE"])
    for t in (t for t in g["grilles"] if t["population"] == pop):
        ns = t["colonnes_non_servies"]
        assert ns["servies_par_degre"] is True
        cle, (v19, v20) = next(iter(ns["valeurs"].items()))
        cat, sous = _requete_categorie(g, pop, cle)
        r19 = salaire_base("TEXTILE", pop, cat, None, t["effective_date"], None, sous, degre=19)
        r20 = salaire_base("TEXTILE", pop, cat, None, t["effective_date"], None, sous, degre="20")
        assert (r19.montant, r20.montant) == (v19, v20)
        assert r19.detail["anciennete_imprimee"] == str(seuil) and "anciennete_imprimee" not in r20.detail
        assert "regle_au_dela_non_appliquee" not in r19.detail
        assert r20.detail["regle_au_dela_non_appliquee"] == "article 12 (جديد), page 8"
        with pytest.raises(Refus) as e:
            salaire_base("TEXTILE", pop, cat, seuil, t["effective_date"], None, sous)
        assert e.value.code == Refus.SOURCE_MANQUANTE


# --- demande par degré : refus ---------------------------------------------------------------------------------------


VERRE = {"secteur": "VERRE_MIROIRS", "population": "horaires", "categorie": "3", "date": "2024-06-01"}


def test_degre_et_anciennete_ensemble_refuses():
    with pytest.raises(Refus) as e:
        salaire_base(**VERRE, anciennete_annees=4, degre=5)
    assert refus(e) == (
        Refus.PARAM_INVALIDE,
        "anciennete_annees et degre ne peuvent pas être donnés ensemble : donner l'un ou l'autre.",
    )


def test_ni_degre_ni_anciennete_meme_refus_qu_en_v0():
    with pytest.raises(Refus) as e:
        salaire_base(**VERRE)
    assert refus(e) == (
        Refus.PARAM_INVALIDE,
        "anciennete_annees obligatoire pour VERRE_MIROIRS/horaires (grille à degrés d'ancienneté).",
    )


@pytest.mark.parametrize(
    "params,debut",
    [
        (
            dict(VERRE, degre=14),
            "Degré 14 absent de la grille VERRE_MIROIRS/horaires (table VERRE_HORAIRES_2024-01-01)",
        ),
        (dict(VERRE, degre="05"), "Degré '05' absent"),
        (dict(secteur="BANQUES", categorie="agent_services_3", degre=1, date="2021-06-01"), "Degré 1 absent"),
        (dict(secteur="TEXTILE", population="mensuels", categorie="17", degre=0, date="2022-06-01"), "Degré 0 absent"),
        (
            dict(secteur="TEXTILE", population="horaires", categorie="I", degre="stage", date="2022-06-01"),
            "Degré 'stage' absent",
        ),
        (dict(VERRE, degre=True), "Degré invalide : True"),
        (dict(VERRE, degre=5.0), "Degré invalide : 5.0"),
        (
            dict(
                secteur="BATIMENT_TRAVAUX_PUBLICS",
                population="ouvriers_occasionnels",
                categorie="6",
                sous_categorie="I",
                degre=1,
                date="2024-06-01",
            ),
            "degre non prévu",
        ),
    ],
)
def test_degre_invalide_param_invalide(params, debut):
    with pytest.raises(Refus) as e:
        salaire_base(**params)
    assert e.value.code == Refus.PARAM_INVALIDE and e.value.message_fr.startswith(debut), e.value.message_fr
    assert e.value.message_ar


def test_degre_absent_liste_les_designations_imprimees():
    with pytest.raises(Refus) as e:
        salaire_base(secteur="BANQUES", categorie="agent_services_3", degre=1, date="2021-06-01")
    assert e.value.message_fr.endswith(
        "désignations imprimées acceptées : stage, " + ", ".join(map(str, range(2, 20))) + "."
    )
    with pytest.raises(Refus) as e:
        salaire_base(
            secteur="COSMETIQUES_PARFUMS",
            population="production_categorie_1",
            categorie="1",
            degre=2,
            date="2024-06-01",
        )
    assert e.value.message_fr.endswith("acceptées : درجة وحيدة ; alias : unique.")


def test_degre_refus_communs_au_v0():
    with pytest.raises(Refus) as e:
        salaire_base(**dict(VERRE, date="2020-01-01"), degre=5)
    assert e.value.code == Refus.SOURCE_MANQUANTE
    with pytest.raises(Refus) as e:
        salaire_base(**VERRE, degre=5, unite_souhaitee="TND/mois")
    assert e.value.code == Refus.HORS_SCOPE


def test_cellule_illisible_refusee_aussi_par_le_degre():
    with pytest.raises(Refus) as e:
        salaire_base("CONFISERIE_BISCUITERIE_CHOCOLATERIE", "mensuels", "1", None, "2022-06-01", degre=8)
    assert e.value.code == Refus.SOURCE_MANQUANTE and "abîmé" in e.value.message_fr


# --- demande par degré : détail et hypothèses ----------------------------------------------------------------------


def test_designation_entiere_ou_texte_et_alias():
    assert salaire_base(**VERRE, degre=5) == salaire_base(**VERRE, degre="5")
    a = salaire_base("COSMETIQUES_PARFUMS", "production_categorie_1", "1", None, "2024-06-01", degre="unique")
    b = salaire_base("COSMETIQUES_PARFUMS", "production_categorie_1", "1", None, "2024-06-01", degre="درجة وحيدة")
    assert a.montant == b.montant == D("575.741")
    assert a.detail["alias_designation"] == "unique" and "alias_designation" not in b.detail
    assert a.detail["degre_imprime"] == b.detail["degre_imprime"] == "درجة وحيدة"


def test_detail_degre_declare():
    r = salaire_base("TEXTILE", "mensuels", "1", None, "2022-06-01", None, "a", degre="stage")
    d = r.detail
    assert (d["degre"], d["degre_imprime"], d["degre_declare"], d["libelle_degre"]) == (1, "stage", True, "0-1")
    h = lire_json(loaders.GRILLES["TEXTILE"])["hypotheses_grille"]["mensuels"]
    n = len(h["fr"]) - len(h["chemin_anciennete_seulement"])
    assert d["hypotheses"][n:] == [
        "Degré déclaré par l'utilisateur, non vérifié : aucune ancienneté n'a été contrôlée.",
        "Ancienneté imprimée pour ce degré dans la grille (page 32) : « période de stage ».",
        "Cette colonne n'est atteinte par aucune ancienneté, faute de durée imprimée (page 32) : elle n'est servie "
        "que par le degré déclaré.",
    ]
    assert len(d["hypotheses"]) == len(d["hypotheses_ar"]) and all(d["hypotheses_ar"])
    assert "anciennete_annees" not in d and "regle_au_dela_non_appliquee" not in d
    assert [(c.page, c.decision_ref) for c in r.citations] == [(32, "D71")]


@pytest.mark.parametrize(
    "args,champ,extrait",
    [
        (
            ("METALLURGIE_BATIMENT", "admin_tech", "4", None, "2024-06-01"),
            "article 13 (جديد) ب, page 9",
            "l'écart cumulé de l'article 13 (جديد) ب (page 9) s'ajoute au-delà de 22 ans",
        ),
        (
            ("BATIMENT_TRAVAUX_PUBLICS", "admin_tech", "4", None, "2024-06-01"),
            "article 13 (جديد) ب, page 8",
            "la table de correspondance de l'article 13 (جديد) ب (page 8) s'applique au-delà de 27 ans",
        ),
        (
            ("IMPRIMERIE_EDITION_CARTONNAGE", "administratifs_mensuels", "5", None, "2024-06-01"),
            "article 11 (جديد), page 8",
            "n'est servie que jusqu'à moins de 31 ans ; au-delà, la convention ne fixe pas le montant",
        ),
        (
            ("COSMETIQUES_PARFUMS", "production_categorie_1", "1", None, "2024-06-01"),
            "article 49, page 15",
            "jusqu'à moins de 1 an ;",
        ),
    ],
)
def test_dernier_degre_regle_au_dela_non_appliquee(args, champ, extrait):
    grille = lire_json(loaders.GRILLES[args[0]])
    dernier = loaders.designations_degres(grille["degres"][args[1]])[-1]
    r = salaire_base(*args, degre=dernier)
    assert r.detail["regle_au_dela_non_appliquee"] == champ
    assert any(extrait in h for h in r.detail["hypotheses"]), r.detail["hypotheses"]
    assert len(r.citations) == 1 and "regle_art13" not in r.detail
    avant = salaire_base(*args, degre=loaders.designations_degres(grille["degres"][args[1]])[0])
    assert "regle_au_dela_non_appliquee" not in avant.detail or len(grille["degres"][args[1]]) == 1


def test_dernier_degre_ouvert_sans_regle_non_appliquee():
    r = salaire_base("AGENCES_VOYAGES", None, "1", None, "2024-06-01", degre=13)
    assert "regle_au_dela_non_appliquee" not in r.detail
    assert not any(h.startswith("Dernier degré") for h in r.detail["hypotheses"])


def test_verre_seuil_nul_hypothese_sur_chaque_degre():
    for deg in range(1, 14):
        r = salaire_base(**VERRE, degre=deg)
        h = r.detail["hypotheses"]
        assert sum("La grille n'imprime aucune durée de degré (article 12 (جديد) و 53, page 7)" in x for x in h) == 1
        assert not any(x.startswith("Dernier degré") for x in h)
        assert ("regle_au_dela_non_appliquee" in r.detail) is (deg == 13)


@pytest.mark.parametrize("deg,touche", [(2, False), (3, True), (4, True), (5, False)])
def test_confiserie_hypothese_des_degres_voisins_de_l_intervalle_refuse(deg, touche):
    r = salaire_base("CONFISERIE_BISCUITERIE_CHOCOLATERIE", "mensuels", "4", None, "2024-06-01", degre=deg)
    assert any(h.startswith("L'article 53 (page 14) et l'en-tête") for h in r.detail["hypotheses"]) is touche


def test_confiserie_case_exclue_de_l_ecart_servie_telle_qu_imprimee():
    r = salaire_base("CONFISERIE_BISCUITERIE_CHOCOLATERIE", "mensuels", "2", None, "2022-06-01", degre=15)
    assert r.montant == D("590.535")
    assert any(h.startswith("Cette case est exclue de l'écart cumulé") for h in r.detail["hypotheses"])
    autre = salaire_base("CONFISERIE_BISCUITERIE_CHOCOLATERIE", "mensuels", "3", None, "2022-06-01", degre=15)
    assert not any(h.startswith("Cette case est exclue") for h in autre.detail["hypotheses"])


ANCIENNETE_RECUE_FR = "ancienneté reçue"
ANCIENNETE_RECUE_AR = "الأقدمية المعتمدة هي أقدمية التدرج"


def _populations_a_degres():
    for secteur, chemin in loaders.GRILLES.items():
        g = lire_json(chemin)
        if g["_meta"].get("tables_transcrites", True) is not True:
            continue
        for pop, degres in g["degres"].items():
            if not degres:
                continue
            t = max(
                (t for t in g["grilles"] if loaders.population_de_table(g, t) == pop), key=lambda t: t["effective_date"]
            )
            cle = next(iter(t["valeurs"]))
            yield secteur, g, pop, t, cle, loaders.designations_degres(degres)


def test_aucune_reponse_par_degre_ne_parle_d_une_anciennete_recue():
    """Par le degré, aucune hypothèse ne parle d'une ancienneté reçue (FR ou AR) : toutes les populations à degrés,
    premier et dernier degré de la première ligne de la table la plus récente, et les 18 démos v1."""
    reponses = []
    for secteur, g, pop, t, cle, noms in _populations_a_degres():
        cat, sous = _requete_categorie(g, pop, cle)
        for nom in (noms[0], noms[-1]):
            try:
                reponses.append(
                    salaire_base(secteur, pop, cat, None, t["effective_date"], None, sous, degre=nom).detail
                )
            except Refus:
                pass  # case illisible : aucune hypothèse affichée
    reponses += [r["result"]["detail"] for r in (handle(q) for q in DEMO_V1) if r["status"] == "ok"]
    assert len(reponses) > 100
    for d in reponses:
        for h in d.get("hypotheses", []):
            assert ANCIENNETE_RECUE_FR not in h.lower(), h
        for h in d.get("hypotheses_ar", []):
            assert ANCIENNETE_RECUE_AR not in h, h
        assert len(d.get("hypotheses", [])) == len(d.get("hypotheses_ar", []))


def test_chemin_par_l_anciennete_affiche_toujours_ces_hypotheses():
    r = salaire_base("TEXTILE", "mensuels", "2", 11, "2022-06-01")
    assert sum(h.startswith("L'ancienneté reçue") for h in r.detail["hypotheses"]) == 1
    assert sum(h.startswith(ANCIENNETE_RECUE_AR) for h in r.detail["hypotheses_ar"]) == 1


def test_indicateur_sur_les_seules_phrases_d_anciennete_recue():
    """chemin_anciennete_seulement désigne exactement les hypothèses de grille « L'ancienneté reçue… » (98 phrases,
    48 fichiers), avec leur traduction arabe au même rang."""
    fichiers = phrases = 0
    for chemin in loaders.GRILLES.values():
        g = lire_json(chemin)
        vu = False
        for h in g.get("hypotheses_grille", {}).values():
            rangs = h.get("chemin_anciennete_seulement", [])
            assert rangs == [i for i, x in enumerate(h["fr"]) if x.startswith("L'ancienneté reçue")]
            assert all(h["ar"][i].startswith(ANCIENNETE_RECUE_AR) for i in rangs)
            phrases += len(rangs)
            vu = vu or bool(rangs)
        fichiers += vu
    assert (fichiers, phrases) == (48, 98)


@pytest.mark.parametrize("rangs", [[], [5], [0, 0], ["1"], [True], "1"])
def test_indicateur_invalide(rangs):
    g = _grille("VERRE_MIROIRS")
    g["hypotheses_grille"]["horaires"]["chemin_anciennete_seulement"] = rangs
    _invalide(g)


def test_chemin_par_l_anciennete_inchange_en_v1():
    req = dict(copy.deepcopy(DEMO[13]), contract_version=V1)
    assert handle(req) == dict(handle(DEMO[13]), contract_version=V1)
    assert handle(req)["result"]["montant"] == "684.630"


# --- primes servies exactes (D76) ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "secteur,code,params,montant,unite,equivalent",
    [
        ("BOISSONS_ALCOOLISEES", "prime_panier", {"condition_remplie": True}, "416.666", "millimes/jour", "0.416666"),
        ("BOIS_AMEUBLEMENT_LIEGE", "aide_deces", {"condition_remplie": True}, "466.6666", "TND/versement", None),
        ("FONDERIE_METALLURGIE_MECANIQUE", "prime_panier", {}, "706.666", "millimes/jour", "0.706666"),
    ],
)
def test_prime_exacte_en_v1_refusee_en_v0(secteur, code, params, montant, unite, equivalent):
    bloc = lire_json(loaders.GRILLES[secteur])["primes_non_couvertes"][code]
    with pytest.raises(Refus) as e:
        prime(secteur, code, "2024-06-01", **params)
    assert refus(e) == (Refus.SOURCE_MANQUANTE, bloc["message_fr"])
    r = prime_v1(secteur, code, "2024-06-01", **params)
    assert (str(r.montant), r.unite) == (montant, unite)
    assert r.detail["montant_tel_qu_imprime"] is True and r.detail["regles"] == "D76"
    assert r.detail.get("montant_equivalent_tnd") == equivalent
    assert r.detail["effective_date"] is None
    assert r.detail["hypotheses"][-1].startswith("Montant servi tel qu'imprimé, sans arrondi au millime")
    assert len(r.detail["hypotheses"]) == len(r.detail["hypotheses_ar"])
    s = bloc["service_contrat_v1"]
    assert [(c.page, c.article) for c in r.citations] == [(s["source_pdf_page"], s["source_article"])]
    rep = valide_v1(handle(req_v1("prime", secteur=secteur, code=code, date="2024-06-01", **params)))
    assert rep["result"]["montant"] == montant and rep["result"]["detail"].get("montant_equivalent_tnd") == equivalent


def test_equivalent_en_dinars_sans_arrondi():
    r = prime_v1("BOISSONS_ALCOOLISEES", "prime_panier", "2024-06-01", condition_remplie=True)
    assert D(r.detail["montant_equivalent_tnd"]) * 1000 == r.montant
    assert r.detail["hypotheses"][-1].endswith(": 416,666 millimes, soit 0,416666 dinar.")


@pytest.mark.parametrize(
    "secteur,code", [("BOISSONS_ALCOOLISEES", "prime_panier"), ("BOIS_AMEUBLEMENT_LIEGE", "aide_deces")]
)
def test_prime_exacte_condition(secteur, code):
    with pytest.raises(Refus) as e:
        prime_v1(secteur, code, "2024-06-01")
    assert e.value.code == Refus.PARAM_INVALIDE
    with pytest.raises(Refus) as e:
        prime_v1(secteur, code, "2024-06-01", condition_remplie=False)
    assert e.value.code == Refus.HORS_SCOPE


def test_autres_primes_non_couvertes_refusees_aussi_en_v1():
    with pytest.raises(Refus) as e:
        prime_v1("VERRE_MIROIRS", "prime_globale", "2024-06-01")
    assert e.value.code == Refus.SOURCE_MANQUANTE


def test_seules_trois_primes_ont_un_service_v1():
    blocs = {
        (s, code)
        for s, chemin in loaders.GRILLES.items()
        for code, b in lire_json(chemin).get("primes_non_couvertes", {}).items()
        if "service_contrat_v1" in b
    }
    assert blocs == {
        ("BOISSONS_ALCOOLISEES", "prime_panier"),
        ("BOIS_AMEUBLEMENT_LIEGE", "aide_deces"),
        ("FONDERIE_METALLURGIE_MECANIQUE", "prime_panier"),
    }


# --- validation des nouveaux champs ----------------------------------------------------------------------------------


def _grille(secteur: str) -> dict:
    return copy.deepcopy(loaders._lire(loaders.GRILLES[secteur]))


def _invalide(data: dict) -> None:
    with pytest.raises(Refus) as e:
        loaders.valider_grille(data, "x.json")
    assert e.value.code == Refus.SOURCE_MANQUANTE


def test_grilles_modifiees_valides():
    for s in (
        "TEXTILE",
        "COSMETIQUES_PARFUMS",
        "BOISSONS_ALCOOLISEES",
        "BOIS_AMEUBLEMENT_LIEGE",
        "FONDERIE_METALLURGIE_MECANIQUE",
    ):
        loaders.valider_grille(_grille(s), "x.json")


@pytest.mark.parametrize(
    "alteration",
    [
        lambda g: g["degres"]["production_categorie_1"][0].__setitem__("alias_designation", ""),
        lambda g: g["degres"]["production_categorie_1"][0].__setitem__("alias_designation", "درجة وحيدة"),
        lambda g: g["degres"]["administratifs"][0].__setitem__("alias_designation", "2"),
    ],
)
def test_alias_designation_invalide(alteration):
    g = _grille("COSMETIQUES_PARFUMS")
    alteration(g)
    _invalide(g)


def _table(g: dict, pop: str) -> dict:
    return next(t for t in g["grilles"] if t["population"] == pop)


@pytest.mark.parametrize(
    "alteration",
    [
        lambda g: _table(g, "mensuels")["cellules_source_manquante"][0].__setitem__("servie_par_degre", False),
        lambda g: _table(g, "mensuels")["cellules_source_manquante"][0].__setitem__("valeur_imprimee", "522.488"),
        lambda g: _table(g, "horaires")["colonnes_non_servies"].__setitem__("servies_par_degre", "oui"),
        lambda g: _table(g, "horaires")["colonnes_non_servies"].__setitem__("colonnes_imprimees", ["18", "20"]),
        lambda g: _table(g, "horaires")["colonnes_non_servies"].__setitem__("colonnes_imprimees", ["19", "19"]),
        lambda g: _table(g, "horaires")["colonnes_non_servies"].__setitem__("anciennete_imprimee", ["35"]),
        lambda g: _table(g, "horaires")["colonnes_non_servies"]["valeurs"]["I"].pop(),
        lambda g: _table(g, "horaires")["colonnes_non_servies"]["valeurs"].pop("I"),
    ],
)
def test_drapeaux_textile_invalides(alteration):
    g = _grille("TEXTILE")
    alteration(g)
    _invalide(g)


@pytest.mark.parametrize(
    "alteration",
    [
        lambda s: s.__setitem__("code", "autre"),
        lambda s: s.__setitem__("unite", "EUR/jour"),
        lambda s: s.pop("montant_exact"),
        lambda s: s.__setitem__("montant", "706.666"),
        lambda s: s.pop("montant_imprime"),
        lambda s: s.__setitem__("montants", []),
        lambda s: s["hypotheses"]["ar"].pop(),
    ],
)
def test_service_contrat_v1_invalide(alteration):
    g = _grille("FONDERIE_METALLURGIE_MECANIQUE")
    alteration(g["primes_non_couvertes"]["prime_panier"]["service_contrat_v1"])
    _invalide(g)


# --- banc d'évaluation -----------------------------------------------------------------------------------------------


def test_jeu_de_reference_cas_v1():
    golden = json.loads(
        (REPO_ROOT / "src/track_b_accounting/evaluation/golden_sets/track_b_golden.v0.json").read_text(encoding="utf-8")
    )
    v1 = [c for c in golden["cases"] if c["requete"].get("contract_version") == V1]
    ids = [c["id"] for c in v1]
    assert len(ids) == len(set(ids)) and len({c["id"] for c in golden["cases"]}) == len(golden["cases"])
    # Cas du contrat v1 (D75 à D77) : présents et VÉRIFIÉS par DS5, 2026-11-21.
    premiers = {c["id"]: c for c in v1 if c["id"] in {f"TB-{i}" for i in range(291, 309)}}
    assert sorted(premiers, key=lambda x: int(x[3:])) == [f"TB-{i}" for i in range(291, 309)]
    assert all(c["verification_humaine"] for c in premiers.values())
    assert all(c["justification"]["pdf"] and c["justification"]["page"] for c in premiers.values())
    # Cas v1 ajoutés ensuite (vagues de grilles) : page, ligne, colonne et rendu ; vérification libre (false ou true).
    for c in v1:
        if c["id"] in premiers:
            continue
        j = c["justification"]
        assert (
            j["pdf"] and j["page"] and j["ligne"] not in (None, "") and j["colonne"] not in (None, "") and j["rendu"]
        ), c["id"]
        assert isinstance(c["verification_humaine"], bool)
    assert not any("contract_version" in c["requete"] for c in golden["cases"] if c not in v1)


def test_evaluation_valide_un_cas_v1_avec_le_schema_v1():
    import importlib.util

    chemin = REPO_ROOT / "src/track_b_accounting/evaluation/metrics_harness/run_eval.py"
    spec = importlib.util.spec_from_file_location("run_eval_track_b_v1", chemin)
    assert spec is not None and spec.loader is not None
    RE = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(RE)

    cas = {
        "id": "X-1",
        "categorie": "ok",
        "certitude": "L",
        "decision": None,
        "verification_humaine": False,
        "requete": {
            "contract_version": V1,
            "operation": "prime",
            "params": {
                "secteur": "BOIS_AMEUBLEMENT_LIEGE",
                "code": "aide_deces",
                "date": "2024-06-01",
                "condition_remplie": True,
            },
            "lang": "fr",
        },
        "attendu": {
            "status": "ok",
            "montant": "466.6666",
            "unite": "TND/versement",
            "citations": [{"pdf": "صناعة الخشب والموبيليا والخفاف.pdf", "page": 18}],
        },
    }
    v0, v1, commun = (RE._validateur(p) for p in (RE.SCHEMA_TB, RE.SCHEMA_TB_V1, RE.SCHEMA_COMMUN))
    refs = {"D63"}
    r = RE.evaluer_cas(cas, refs, v0, commun, v1)
    assert (r["verdict"], r["conforme_schema_track_b"], r["citations_ok"]) == (RE.CORRECT, True, True)
    assert RE.evaluer_cas(cas, refs, v0, commun)["conforme_schema_track_b"] is False
