"""coverage@k : la part des sources attendues réellement rendues.

Toutes les valeurs attendues de ce fichier sont calculées À LA MAIN, à partir de
quatre questions fabriquées ici. Aucun corpus n'est lu, aucune API n'est appelée :
le test mesure la formule, pas le moteur.

Les quatre questions, et ce que chacune attend :

  Q1  1 source  : CCS-BTP-ART-52                     rang 1
  Q2  2 sources : CCS-BTP-ART-10                     rang 1
                  CC-CADRE-ART-4                     rang 5
  Q3  4 sources : CC-CADRE-ART-7                     rang 2
                  CCS-BANQUES-ART-3                  absente
                  CCS-ASSURANCE-ART-9                absente
                  CCS-BTP-ART-20                     absente
  Q4  1 source  : CCS-GARDIENNAGE-ART-1              absente

Rappel, qui ne regarde que la PREMIÈRE source trouvée, donc min(rangs) = 1, 1, 2, None :

    recall@1  = 2/4 = 0,50       Q1 et Q2
    recall@5  = 3/4 = 0,75       + Q3
    recall@10 = 3/4 = 0,75

Couverture, moyenne par question de la part des sources rendues :

    coverage@1  = (1/1 + 1/2 + 0/4 + 0/1) / 4 = 1,5  / 4 = 0,375
    coverage@5  = (1/1 + 2/2 + 1/4 + 0/1) / 4 = 2,25 / 4 = 0,5625
    coverage@10 = idem                                     = 0,5625

Sur le sous-ensemble multi-sources, Q2 et Q3 :

    recall@10   = 2/2 = 1,00          les deux ont AU MOINS une source trouvée
    coverage@10 = (2/2 + 1/4) / 2 = 1,25 / 2 = 0,625

L'écart entre 1,00 et 0,625 est exactement ce que la mesure sert à montrer : le
rappel déclare ces deux questions parfaitement réussies alors que trois des six
sources applicables n'ont pas été rendues.
"""

from __future__ import annotations

import pytest

from src.legal_retrieval.evaluation.metrics import _coverage, _recall, _source_of, summarize


def _ligne(qid: str, rangs: dict[str, int | None]) -> dict:
    """Une ligne de résultat réduite à ce dont summarize() a besoin."""
    trouves = [r for r in rangs.values() if r]
    return {
        "id": qid,
        "kind": "sujet",                  # dans CORE_KINDS, donc compté dans "core"
        "mode": "live",
        "status": "ok",
        "rank": min(trouves) if trouves else None,
        "ranks": rangs,
        "top1": None,
        "raw_top": 12.0,                  # au-dessus du seuil : pas de refus
        "coverage": 0.9,
        "cosine": None,                   # None partout -> résumé en "BM25 seul"
        "article_number_asked": False,
        "expected": list(rangs),
    }


LIGNES = [
    _ligne("Q1", {"CCS-BTP-ART-52": 1}),
    _ligne("Q2", {"CCS-BTP-ART-10": 1, "CC-CADRE-ART-4": 5}),
    _ligne("Q3", {"CC-CADRE-ART-7": 2, "CCS-BANQUES-ART-3": None,
                  "CCS-ASSURANCE-ART-9": None, "CCS-BTP-ART-20": None}),
    _ligne("Q4", {"CCS-GARDIENNAGE-ART-1": None}),
]


# --------------------------------------------------------------- la source d'un groupe

@pytest.mark.parametrize(("groupe", "attendu"), [
    ("CCS-ASSURANCE-ART-12", "CCS-ASSURANCE"),
    ("CC-CADRE-ART-4", "CC-CADRE"),
    ("CCS-BTP-ART-10BIS", "CCS-BTP"),
    ("CCS-HOTELS-TOURISTIQUES-ANX-2", "CCS-HOTELS-TOURISTIQUES"),  # annexes, D32
    ("CCS-TEXTILE-SEC-1", "CCS-TEXTILE"),                          # sections, D32
])
def test_source_of_isole_le_texte(groupe: str, attendu: str) -> None:
    assert _source_of(groupe) == attendu


# ------------------------------------------------------------------- les deux mesures

@pytest.mark.parametrize(("k", "attendu"), [(1, 0.375), (5, 0.5625), (10, 0.5625)])
def test_coverage_vaut_la_valeur_calculee_a_la_main(k: int, attendu: float) -> None:
    assert _coverage(LIGNES, k) == pytest.approx(attendu)


@pytest.mark.parametrize(("k", "attendu"), [(1, 0.50), (5, 0.75), (10, 0.75)])
def test_recall_reste_inchange(k: int, attendu: float) -> None:
    """La couverture s'ajoute au rappel, elle ne le remplace pas."""
    assert _recall(LIGNES, k) == pytest.approx(attendu)


def test_coverage_egale_recall_quand_chaque_question_a_une_seule_source() -> None:
    """Propriété attendue : sur du mono-source, la nouvelle mesure ne change rien."""
    mono = [r for r in LIGNES if len(r["ranks"]) == 1]
    for k in (1, 5, 10):
        assert _coverage(mono, k) == pytest.approx(_recall(mono, k))


def test_coverage_ignore_les_lignes_sans_champ_ranks() -> None:
    """Les anciens fichiers de résultats n'ont pas "ranks" : ne pas les compter 0."""
    ancienne = {**LIGNES[0]}
    del ancienne["ranks"]
    assert _coverage([ancienne], 10) is None
    assert _coverage([*LIGNES, ancienne], 10) == pytest.approx(0.5625)


# ------------------------------------------------- le bloc multi-sources du résumé

def test_summarize_isole_les_questions_multi_sources() -> None:
    multi = summarize(LIGNES)["multi_source"]
    assert multi["n"] == 2
    assert multi["ids"] == ["Q2", "Q3"]


def test_summarize_montre_l_ecart_entre_rappel_et_couverture() -> None:
    """Le cœur de la mesure : R@10 déclare 100 %, la couverture dit 62,5 %."""
    multi = summarize(LIGNES)["multi_source"]
    assert multi["recall@10"] == pytest.approx(1.0)
    assert multi["coverage@10"] == pytest.approx(0.625)
    assert multi["coverage@10"] < multi["recall@10"]


def test_summarize_reporte_la_couverture_sur_le_perimetre_de_tete() -> None:
    core = summarize(LIGNES)["core"]
    assert core["n"] == 4
    assert core["recall@1"] == pytest.approx(0.50)
    assert core["coverage@1"] == pytest.approx(0.375)
