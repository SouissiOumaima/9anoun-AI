"""Hors périmètre de Track B (D110) : opérations de la liste fermée, conventions-cadres, cohérence schémas / handler.
Lancer depuis la racine du dépôt : pytest src/track_b_accounting/tests/test_hors_perimetre.py
"""

from __future__ import annotations

import json

import pytest
from conftest import REPO_ROOT
from jsonschema import Draft202012Validator

from track_b_accounting.contract import handle
from track_b_accounting.contract import handler as H

SCHEMAS = REPO_ROOT / "data" / "mock_cards" / "schemas"
VERSIONS = ("track_b.v0", "track_b.v1")


def _schema(nom: str, version: str) -> dict:
    suffixe = version.split(".")[1]
    return json.loads((SCHEMAS / f"track_b_{nom}.{suffixe}.schema.json").read_text(encoding="utf-8"))


def _req(version: str, operation: str, params: dict, lang: str = "fr") -> dict:
    return {"contract_version": version, "request_id": "hp", "operation": operation, "params": params, "lang": lang}


def _refus(rep: dict, version: str) -> dict:
    assert Draft202012Validator(_schema("response", version)).is_valid(rep)
    assert rep["contract_version"] == version
    assert rep["status"] == "refus" and rep["result"] is None and rep["citations"] == []
    assert rep["computed_by"] == "track_b_accounting.contract"
    return rep["refus"]


@pytest.mark.parametrize("version", VERSIONS)
def test_enum_des_schemas_egale_operations_servies_plus_liste_fermee(version: str) -> None:
    enum = _schema("request", version)["properties"]["operation"]["enum"]
    assert len(enum) == len(set(enum))
    assert set(enum) == set(H.OPERATIONS) | set(H.OPERATIONS_HORS_PERIMETRE)
    assert not set(H.OPERATIONS) & set(H.OPERATIONS_HORS_PERIMETRE)


@pytest.mark.parametrize("version", VERSIONS)
@pytest.mark.parametrize("operation", sorted(op for op, m in H.OPERATIONS_HORS_PERIMETRE.items() if m is not None))
def test_operation_hors_perimetre_refus_hors_scope_avec_son_motif(version: str, operation: str) -> None:
    req = _req(version, operation, {"secteur": "METALLURGIE_BATIMENT", "date": "2024-01-01"})
    assert Draft202012Validator(_schema("request", version)).is_valid(req)
    refus = _refus(handle(req), version)
    motif_fr, motif_ar = H.OPERATIONS_HORS_PERIMETRE[operation]  # type: ignore[misc]
    assert refus["code"] == "HORS_SCOPE"
    assert refus["message_fr"].startswith(f"Opération {operation!r} hors du périmètre Track B {version[-2:]}")
    assert refus["message_fr"].endswith(motif_fr) and refus["message_ar"].endswith(motif_ar)


def test_motifs_distincts_par_theme() -> None:
    motifs = [m for m in H.OPERATIONS_HORS_PERIMETRE.values() if m is not None]
    # cnss partage le motif CNSS ; toutes les autres opérations ont leur propre motif.
    assert len({m[0] for m in motifs}) == len(motifs)
    assert all(m[0] and m[1] for m in motifs)


@pytest.mark.parametrize("version", VERSIONS)
@pytest.mark.parametrize("operation", ["calcul_irpp", "cnss_salariale", "Salaire_Net", "facturation", ""])
def test_operation_vraiment_inconnue_reste_param_invalide(version: str, operation: str) -> None:
    refus = _refus(handle(_req(version, operation, {})), version)
    assert refus["code"] == "PARAM_INVALIDE" and "non conforme" in refus["message_fr"]


@pytest.mark.parametrize("version", VERSIONS)
def test_operation_hors_perimetre_mal_formee_reste_param_invalide(version: str) -> None:
    req = _req(version, "irpp", {})
    del req["lang"]
    assert _refus(handle(req), version)["code"] == "PARAM_INVALIDE"


@pytest.mark.parametrize("version", VERSIONS)
@pytest.mark.parametrize("secteur", sorted(H.CONVENTIONS_CADRES))
@pytest.mark.parametrize(
    "operation, params",
    [
        ("salaire_base", {"categorie": 1, "anciennete_annees": 3, "date": "2024-01-01"}),
        ("prime", {"code": "prime_transport", "date": "2024-01-01"}),
    ],
)
def test_convention_cadre_refus_hors_scope_qui_la_nomme(
    version: str, secteur: str, operation: str, params: dict
) -> None:
    refus = _refus(handle(_req(version, operation, {"secteur": secteur, **params})), version)
    assert refus["code"] == "HORS_SCOPE"
    assert (
        "convention collective cadre" in refus["message_fr"]
        and "ne fixe pas de grille de salaires" in refus["message_fr"]
    )
    assert "الاتفاقية المشتركة الإطارية" in refus["message_ar"] and "لا تضبط جدول أجور" in refus["message_ar"]


def test_convention_cadre_agricole_nommee_et_smag_signale() -> None:
    fr = H.CONVENTIONS_CADRES["CONVENTION_CADRE_AGRICOLE"][0]
    assert "secteur agricole" in fr and "SMAG" in fr
    assert H.CONVENTIONS_CADRES["CC-CADRE"] == H.CONVENTIONS_CADRES["CONVENTION_CADRE_GENERALE"]


@pytest.mark.parametrize("version", VERSIONS)
def test_secteur_inconnu_et_population_inexistante_inchanges(version: str) -> None:
    p = {"categorie": 1, "anciennete_annees": 3, "date": "2024-01-01"}
    refus = _refus_calc(handle(_req(version, "salaire_base", {"secteur": "CONVENTION_CADRE", **p})))
    assert refus["code"] == "SOURCE_MANQUANTE" and "Aucune grille vérifiée" in refus["message_fr"]
    refus = _refus_calc(
        handle(_req(version, "salaire_base", {"secteur": "BATIMENT_TRAVAUX_PUBLICS", "population": "x", **p}))
    )
    assert refus["code"] == "PARAM_INVALIDE" and "Population inconnue" in refus["message_fr"]


def _refus_calc(rep: dict) -> dict:
    assert rep["status"] == "refus" and rep["computed_by"] == "track_b_accounting.calc.salaire_base"
    return rep["refus"]
