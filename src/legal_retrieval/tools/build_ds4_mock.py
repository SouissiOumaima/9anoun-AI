"""Build the realistic mock for DS4 (Lawyer Track): REAL articles, chosen cases.

Each case = a get_article request + the response DS2 really gives on the
ingested corpus (mode "live"), + what it lets DS4 test (temporal reasoning:
repealed, modified without old version, bis/ter/sub-article, motivated gap,
annex). Avenant dates of the sources involved are added for dated reasoning.

Run on a machine where the corpus was ingested (it refuses to build from the
mock, so DS4 never receives invented articles):
    python -m src.legal_retrieval.tools.build_ds4_mock
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from src.legal_retrieval.contract.get_article import get_article
from src.legal_retrieval.corpus.store import corpus_dir, load_store

OUTPUT = Path("data/mock_cards/legal_retrieval_ds4_cases.v0.json")
V0 = "legal_retrieval.v0"

# (case id, what DS4 can test, request, expected status, expected article status or None)
CASES: list[tuple[str, str, dict[str, Any], str, str | None]] = [
    ("abroge-avec-avenant-date",
     ("Article abrogé : annoncer l'abrogation et l'avenant n° 5 (signé 24/09/1996, approuvé "
     "16/10/1996) ; avant cette date l'article existait, mais son texte n'est pas dans le corpus."),
     {"article_id": "CCS-BTP-ART-39"}, "ok", "abroge"),
    ("abroge-avenant-inconnu",
     ("Article abrogé dont l'OCR a perdu le numéro d'avenant (« عدد؟ ») : amended_by = null, "
     "à dire tel quel, sans deviner."),
     {"article_id": "CCS-CONSTRUCTION-METALLIQUE-ART-55"}, "ok", "abroge"),
    ("abroge-autre-convention",
     ("Abrogation dans une autre convention (Assurance, avenant n° 4) : la numérotation des "
     "avenants est propre à chaque convention."),
     {"source_id": "CCS-ASSURANCE", "article": "6"}, "ok", "abroge"),
    ("modifie-ancienne-version-absente",
     ("Article « (جديد) » récupéré en milieu de ligne : texte actuel seulement, "
     "previous_version_available = false à annoncer."),
     {"article_id": "CCS-BTP-ART-51"}, "ok", "en_vigueur"),
    ("modifie-jadid",
     "Autre article modifié par un avenant non identifié dans le digest (amended_by = null).",
     {"article_id": "CCS-BTP-ART-46"}, "ok", "en_vigueur"),
    ("en-vigueur-non-modifie",
     "Article jamais modifié : cas de référence, previous_version_available = true.",
     {"source_id": "CCS-BANQUES", "article": "2"}, "ok", "en_vigueur"),
    ("article-bis",
     "Article « مكرر » (bis) : distinct de l'article 1, identifiant 1BIS.",
     {"source_id": "CCS-BANQUES", "article": "1BIS"}, "ok", "en_vigueur"),
    ("article-ter",
     "Article « مثلث » (ter) : identifiant 54TER.",
     {"source_id": "CCS-ENSEIGNEMENT-PRIVE", "article": "54TER"}, "ok", None),
    ("sous-article",
     "Sous-article « الفصل 46 - 3 » : identifiant 46-3.",
     {"source_id": "CCS-GARDIENNAGE", "article": "46-3"}, "ok", None),
    ("annexe",
     ("Annexe placée après le dernier article (liste des sanctions, renvoie au fasl 36) : "
     "à citer comme annexe, jamais comme l'article 58."),
     {"article_id": "CCS-CONSTRUCTION-METALLIQUE-ANNEXE-1"}, "ok", "inconnu"),
    ("trou-motive",
     ("Article présent dans le PDF mais absent du corpus : refus SOURCE_MANQUANTE avec la "
     "raison, à afficher tel quel (Citation ou Silence)."),
     {"source_id": "CC-CADRE", "article": "5"}, "refus", None),
    ("article-inexistant",
     "Référence qui n'existe pas : refus SOURCE_MANQUANTE simple.",
     {"source_id": "CCS-BTP", "article": "99"}, "refus", None),
]


# Extra checks on the first result: the case must really show what its purpose says.
EXPECT_MODIFIED = {"modifie-ancienne-version-absente": True, "modifie-jadid": True,
                   "en-vigueur-non-modifie": False}


def build() -> dict[str, Any]:
    """Run every case on the live corpus and check what DS2 answers."""
    if load_store() is None:
        raise SystemExit("Corpus absent : lancer d'abord python -m "
                         "src.legal_retrieval.corpus.ingest_sections")
    cases: list[dict[str, Any]] = []
    for case_id, purpose, reference, expected, article_status in CASES:
        request = {"contract_version": V0, "request_id": f"ds4-{case_id}", **reference}
        response = get_article(request)
        problems = []
        if response["mode"] != "live":
            problems.append("mode != live")
        if response["status"] != expected:
            problems.append(f"status {response['status']} != {expected}")
        if article_status and response["results"] and \
                response["results"][0]["status"] != article_status:
            problems.append(f"article {response['results'][0]['status']} != {article_status}")
        if case_id in EXPECT_MODIFIED and response["results"] and \
                response["results"][0]["modified"] is not EXPECT_MODIFIED[case_id]:
            problems.append(f"modified != {EXPECT_MODIFIED[case_id]}")
        if problems:  # never ship a case that does not show what it claims
            raise SystemExit(f"Cas {case_id} : {'; '.join(problems)}")
        cases.append({"id": case_id, "purpose_fr": purpose, "request": request,
                      "expected_response": response})
    sources = {r["source_id"] for c in cases for r in c["expected_response"]["results"]}
    avenants_file = corpus_dir() / "avenants.json"
    avenants = [a for a in json.loads(avenants_file.read_text(encoding="utf-8"))
                if a["source_id"] in sources] if avenants_file.exists() else []
    return {
        "mock_version": "legal_retrieval.ds4_cases.v0",
        "contract_version": V0,
        "decision_ref": "D22",
        "generated_on": date.today().isoformat(),
        "_doc": ("Articles RÉELS du corpus DS2 (mode live), choisis pour tester le "
                 "raisonnement juridique temporel de DS4. Chaque cas : la requête "
                 "get_article et la réponse exacte de DS2. Régénérer avec "
                 "python -m src.legal_retrieval.tools.build_ds4_mock."),
        "operation": {"python": "src.legal_retrieval.contract.get_article.get_article",
                      "http": "POST /legal/article"},
        "cases": cases,
        "avenants": avenants,
    }


def main() -> None:
    data = build()
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    for case in data["cases"]:
        response = case["expected_response"]
        ids = [r["article_id"] for r in response["results"]] or response["refus"]["code"]
        print(f"OK  {case['id']:<34} {response['status']:<6} {ids}")
    print(f"{len(data['cases'])} cas, {len(data['avenants'])} sources datées -> {OUTPUT}")


if __name__ == "__main__":
    main()
