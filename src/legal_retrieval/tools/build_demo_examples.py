"""Build data/mock_cards/legal_retrieval_requests_demo.json for DS1 (and DS4/DS5).

Every expected_response is PRODUCED by the real handler, so the examples can
never drift from the code (a test checks it). Re-run after any contract change:
    python -m src.legal_retrieval.tools.build_demo_examples
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.legal_retrieval.contract.handler import CONTRACT_VERSION, handle

OUT = Path("data/mock_cards/legal_retrieval_requests_demo.json")

# (id, what it shows, request) — requests DS1 can send as-is
EXAMPLES: list[tuple[str, str, dict[str, Any]]] = [
    ("ok-toutes-versions",
     "Succès : 1 article demandé (top_k=1) → ses 2 versions (nouvelle + ancienne), règle D17.",
     {"contract_version": CONTRACT_VERSION, "request_id": "ds2-demo-01",
      "query": "ما هي منحة النقل في قطاع البناء؟", "reference_date": "2024-01-15",
      "sector": "btp", "lang": "ar", "top_k": 1}),
    ("ok-abrogation-et-ancienne-version-absente",
     ("Succès : plusieurs articles, dont un modifié sans ancienne version dans le corpus "
      "(previous_version_available=false) et un article abrogé (status=abroge)."),
     {"contract_version": CONTRACT_VERSION, "request_id": "ds2-demo-02",
      "query": "Prime de transport et articles abrogés, secteur BTP",
      "sector": "btp", "lang": "fr"}),
    ("refus-source-manquante",
     "Refus « Citation ou Silence » : aucun article pertinent pour ce secteur → SOURCE_MANQUANTE (HTTP 200).",
     {"contract_version": CONTRACT_VERSION, "request_id": "ds2-demo-03",
      "query": "مدة التجربة في قطاع البنوك", "sector": "banques", "lang": "ar"}),
    ("refus-param-invalide-date",
     "Refus de contrat : date au mauvais format → PARAM_INVALIDE (HTTP 422).",
     {"contract_version": CONTRACT_VERSION, "request_id": "ds2-demo-04",
      "query": "préavis de licenciement", "reference_date": "15/01/2024"}),
    ("refus-param-invalide-champ-manquant",
     "Refus de contrat : champ obligatoire `query` absent → PARAM_INVALIDE (HTTP 422).",
     {"contract_version": CONTRACT_VERSION, "request_id": "ds2-demo-05"}),
]

# status "erreur" cannot be triggered by a request: documented, schema-valid example
ERREUR_EXAMPLE: dict[str, Any] = {
    "contract_version": CONTRACT_VERSION, "request_id": "ds2-demo-06", "status": "erreur",
    "citations": [], "refus": None, "computed_by": "legal_retrieval.contract",
    "mode": "mock", "results": [],
    "erreur": {"type": "INTERNE",
               "message_fr": "Incident technique dans le service de recherche juridique.",
               "message_ar": "خلل تقني في خدمة البحث القانوني."},
}


def build() -> dict[str, Any]:
    """Run every example through the handler."""
    return {
        "_comment": ("Exemples DS2 pour l'intégration (DS1). Chaque expected_response est produite "
                     "par le vrai handler (tools/build_demo_examples.py) et vérifiée par un test. "
                     "Textes juridiques FAUX, marqués [MOCK]."),
        "contract_version": CONTRACT_VERSION,
        "operations": [{"name": "search", "python": "src.legal_retrieval.contract.handler.handle",
                        "http": "POST /legal/search", "cli": "python -m src.legal_retrieval.contract.cli <fichier.json>"}],
        "examples": [{"id": i, "description": d, "request": r, "expected_response": handle(r)}
                     for i, d, r in EXAMPLES],
        "erreur_example": {"description": ("status = erreur : incident technique inattendu, non "
                                           "déclenchable par une requête. HTTP 500, aucun détail interne."),
                           "response": ERREUR_EXAMPLE},
    }


def main() -> None:
    """Write the examples file (UTF-8, Arabic kept readable)."""
    OUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{OUT} : {len(EXAMPLES)} exemples + 1 exemple d'erreur")


if __name__ == "__main__":
    main()
