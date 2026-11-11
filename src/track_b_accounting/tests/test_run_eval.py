"""Banc d'évaluation (evaluation/metrics_harness/run_eval.py) : verdicts, métriques, comparaison à la baseline,
codes de sortie, et relance complète déterministe identique à la baseline versionnée."""
from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path
from types import ModuleType

import pytest

RUN_EVAL = Path(__file__).resolve().parents[1] / "evaluation" / "metrics_harness" / "run_eval.py"


def _charger() -> ModuleType:
    spec = importlib.util.spec_from_file_location("run_eval_track_b", RUN_EVAL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RE = _charger()


def _ok(montant: str = "100.000", unite: str = "TND/mois") -> dict:
    return {"status": "ok", "result": {"montant": montant, "unite": unite}, "refus": None, "citations": []}


def _refus(code: str = "SOURCE_MANQUANTE", fr: str = "fr", ar: str = "ar") -> dict:
    return {"status": "refus", "result": None, "refus": {"code": code, "message_fr": fr, "message_ar": ar},
            "citations": []}


# --- Verdicts ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("attendu, rep, verdict", [
    ({"status": "ok", "montant": "100.000", "unite": "TND/mois"}, _ok(), "correct"),
    ({"status": "ok", "montant": "100.000", "unite": "TND/mois"}, _ok("100.001"), "faux_montant"),
    ({"status": "ok", "montant": "100.000", "unite": "TND/mois"}, _ok(unite="TND/heure"), "faux_montant"),
    ({"status": "ok", "montant": "100.000", "unite": "TND/mois"}, _refus(), "silence_excessif"),
    ({"status": "refus", "code": "SOURCE_MANQUANTE"}, _ok(), "montant_au_lieu_de_refus"),
    ({"status": "refus", "code": "SOURCE_MANQUANTE"}, _refus("PARAM_INVALIDE"), "code_refus_incorrect"),
    ({"status": "refus", "code": "SOURCE_MANQUANTE", "message_fr": "attendu"}, _refus(fr="autre"),
     "message_refus_incorrect"),
    ({"status": "refus", "code": "SOURCE_MANQUANTE", "message_ar": "ar"}, _refus(), "correct"),
    ({"status": "ok", "montant": "1", "unite": "TND/mois"}, {"status": "erreur"}, "statut_erreur"),
])
def test_verdict(attendu: dict, rep: dict, verdict: str) -> None:
    assert RE._verdict(attendu, rep) == verdict


def test_citations_valides_signale_chaque_ecart() -> None:
    attendu = {"citations": [{"pdf": "a.pdf", "page": 3}]}
    rep = {"citations": [{"source_file": "data/raw/pdf/b.pdf", "page": 4, "data_file": "absent.json",
                          "decision_ref": "D999"}, {"source_file": "x", "page": 1}]}
    problemes = RE._citations_valides(attendu, rep, {"D1"})
    assert problemes[0] == "2 citation(s) au lieu de 1"
    assert any("PDF cité 'b.pdf'" in p for p in problemes)
    assert any("page citée 4" in p for p in problemes)
    assert any("source_file introuvable" in p for p in problemes)
    assert any("data_file introuvable" in p for p in problemes)
    assert any("decision_ref D999" in p for p in problemes)


def test_exception_du_handler_enregistree_sans_arreter_l_evaluation(monkeypatch: pytest.MonkeyPatch) -> None:
    def leve(_: dict) -> dict:
        raise RuntimeError("panne")
    monkeypatch.setattr(RE, "handle", leve)
    cas = {"id": "X-1", "categorie": "ok", "certitude": "L", "decision": None, "verification_humaine": True,
           "attendu": {"status": "ok", "montant": "1.000", "unite": "TND/mois"}, "requete": {}}
    r = RE.evaluer_cas(cas, set(), None, None)
    assert r["verdict"] == "exception_inattendue"
    assert r["obtenu"] == {"exception": "RuntimeError", "message": "panne"}


# --- Métriques et comparaison --------------------------------------------------------------------------------

def _res(verdict: str, attendu: str = "ok", citations_ok: bool | None = True) -> dict:
    return {"verdict": verdict, "attendu": {"status": attendu}, "citations_ok": citations_ok,
            "conforme_schema_track_b": True, "conforme_schema_commun": True}


def test_metriques_comptent_chaque_verdict() -> None:
    m = RE.metriques([_res("correct"), _res("faux_montant"), _res("correct", "refus", None),
                      _res("montant_au_lieu_de_refus", "refus", None)])
    assert m["cas"] == 4
    assert m["exactitude_montants"] == {"n": 1, "sur": 2, "taux": 0.5}
    assert m["faux_montants"]["n"] == 1 and m["montants_au_lieu_de_refus"]["n"] == 1
    assert m["faux_montants_total"] == 2
    assert m["refus_corrects"] == {"n": 1, "sur": 2, "taux": 0.5}
    assert RE.metriques([])["exactitude_montants"] == {"n": 0, "sur": 0, "taux": None}


def _ensemble(**modifs: object) -> dict:
    m: dict = {nom: {"n": 0, "sur": 10, "taux": 1.0 if sens > 0 else 0.0} for nom, sens in RE.SENS_METRIQUES.items()}
    m.update(statut_erreur=0, exceptions_inattendues=0, faux_montants_total=0, cas=10)
    m.update(modifs)
    return m


def test_comparaison_stable() -> None:
    ecarts = RE.comparer(_ensemble(), _ensemble())
    assert [e["metrique"] for e in ecarts] == list(RE.SENS_METRIQUES)
    assert {e["statut"] for e in ecarts} == {"stable"}
    assert RE.code_sortie(_ensemble(), ecarts) == 0


def test_comparaison_sens_des_metriques() -> None:
    ecarts = {e["metrique"]: e for e in RE.comparer(
        _ensemble(), _ensemble(exactitude_montants={"n": 9, "sur": 10, "taux": 0.9},
                               silence_excessif={"n": 1, "sur": 10, "taux": 0.1},
                               refus_corrects={"n": 10, "sur": 10, "taux": 1.0},
                               statut_erreur=0))}
    assert ecarts["exactitude_montants"] == {"metrique": "exactitude_montants", "baseline": 1.0, "actuel": 0.9,
                                             "ecart": -0.1, "statut": "baisse"}
    assert ecarts["silence_excessif"]["statut"] == "baisse" and ecarts["silence_excessif"]["ecart"] == 0.1
    base = _ensemble(refus_corrects={"n": 8, "sur": 10, "taux": 0.8}, statut_erreur=2)
    amel = {e["metrique"]: e["statut"] for e in RE.comparer(base, _ensemble())}
    assert amel["refus_corrects"] == "amélioration" and amel["statut_erreur"] == "amélioration"


def test_une_seule_baisse_ne_bloque_pas() -> None:
    ecarts = RE.comparer(_ensemble(), _ensemble(citations_valides={"n": 9, "sur": 10, "taux": 0.9}))
    assert RE.baisses(ecarts) == ["citations_valides"]
    assert RE.code_sortie(_ensemble(), ecarts) == 0


def test_deux_baisses_bloquent() -> None:
    ecarts = RE.comparer(_ensemble(), _ensemble(citations_valides={"n": 9, "sur": 10, "taux": 0.9},
                                                statut_erreur=1))
    assert RE.baisses(ecarts) == ["citations_valides", "statut_erreur"]
    assert RE.code_sortie(_ensemble(), ecarts) == RE.CODE_REGRESSION == 2


def test_faux_montant_ou_exception_prioritaires() -> None:
    assert RE.code_sortie(_ensemble(faux_montants_total=1), None) == RE.CODE_CRITIQUE == 1
    assert RE.code_sortie(_ensemble(exceptions_inattendues=1), RE.comparer(_ensemble(), _ensemble())) == 1


def test_metrique_absente_ou_sans_taux_non_comparable() -> None:
    base = _ensemble()
    del base["citations_valides"]
    ecarts = {e["metrique"]: e for e in RE.comparer(base, _ensemble(refus_corrects={"n": 0, "sur": 0, "taux": None}))}
    assert ecarts["citations_valides"]["statut"] == "non comparable" and ecarts["citations_valides"]["ecart"] is None
    assert ecarts["refus_corrects"]["statut"] == "non comparable"
    assert RE._valeur(True) is None


def test_texte_comparaison() -> None:
    ecarts = RE.comparer(_ensemble(), _ensemble(statut_erreur=1))
    texte = RE.texte_comparaison(ecarts, 10, 10)
    assert texte.splitlines()[0] == "Comparaison à la baseline (10 cas -> 10 cas) :"
    assert "statut_erreur" in texte and "baisse" in texte
    assert texte.splitlines()[-1].startswith("Métriques en baisse : 1 (statut_erreur)")


# --- Relance complète ------------------------------------------------------------------------------------------

@pytest.fixture
def resultats(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Dossier de résultats temporaire contenant une copie de la baseline versionnée."""
    shutil.copyfile(RE.BASELINE, tmp_path / "baseline.json")
    monkeypatch.setattr(RE, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(RE, "BASELINE", tmp_path / "baseline.json")
    return tmp_path


def _sans_fins_de_ligne(p: Path) -> bytes:
    return p.read_bytes().replace(b"\r\n", b"\n")


def test_relance_identique_a_la_baseline_versionnee(resultats: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base = json.loads(RE.BASELINE.read_text(encoding="utf-8"))
    assert RE.main(["--date", base["date"]]) == 0
    sortie = resultats / f"eval_{base['date']}.json"
    assert _sans_fins_de_ligne(sortie) == _sans_fins_de_ligne(RE.BASELINE)
    comparaison = json.loads((resultats / f"eval_{base['date']}_comparaison.json").read_text(encoding="utf-8"))
    assert comparaison["baisses"] == [] and {e["statut"] for e in comparaison["ecarts"]} == {"stable"}
    assert "Métriques en baisse : 0 (aucune)" in capsys.readouterr().out


def test_relance_bloquee_par_deux_baisses(resultats: Path) -> None:
    base = json.loads(RE.BASELINE.read_text(encoding="utf-8"))
    m = base["metriques"]["ensemble"]
    m["statut_erreur"] = -1           # baseline artificiellement meilleure sur deux compteurs
    m["exceptions_inattendues"] = -1
    (resultats / "baseline.json").write_text(json.dumps(base), encoding="utf-8")
    assert RE.main(["--date", base["date"]]) == 2


def test_relance_sans_baseline(resultats: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (resultats / "baseline.json").unlink()
    assert RE.main(["--date", "2026-01-01"]) == 0
    assert "comparaison impossible" in capsys.readouterr().out
    assert not (resultats / "eval_2026-01-01_comparaison.json").exists()


def test_mode_baseline_ecrit_sans_comparer(resultats: Path) -> None:
    (resultats / "baseline.json").unlink()
    assert RE.main(["--date", "2026-01-01", "--baseline"]) == 0
    assert (resultats / "baseline.json").is_file() and (resultats / "baseline.md").is_file()
    assert not list(resultats.glob("*_comparaison.json"))
