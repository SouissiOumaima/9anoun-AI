"""Régénère les schémas JSON et le fichier d'exemples DS3 v2 à partir du contrat et du mock.

Lancer depuis la racine du dépôt :
    python -m src.document_intelligence.contract.v2.generate_examples
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.document_intelligence.contract.v2.mock import handle_request, list_operations
from src.document_intelligence.contract.v2.models import DS3Request, DS3Response

REPO = Path(__file__).resolve().parents[4]
MOCK_CARDS = REPO / "data" / "mock_cards"
SCHEMAS = MOCK_CARDS / "schemas"
DEMO_FILE = MOCK_CARDS / "document_intelligence_requests_demo.v2.json"


def _ctx(card: str = "company_042", card_type: str = "company") -> dict[str, Any]:
    return {"organization_id": "org_demo", "user_id": "user_comptable_01", "role": "accountant",
            "card_id": card, "card_type": card_type}


def _doc(doc_id: str, name: str, mime: str, card: str = "company_042") -> dict[str, Any]:
    return {"document_id": doc_id, "card_id": card, "file_name": name, "mime_type": mime,
            "storage_ref": f"tradrly://cards/{card}/documents/{doc_id}"}


def _req(request_id: str, document: dict[str, Any], operation: str = "analyze_document", lang: str = "fr",
         **extra: Any) -> dict[str, Any]:
    return {"contract_version": "ds3.v2", "request_id": request_id, "lang": lang, "operation": operation,
            "context": extra.pop("context", _ctx()), "document": document, **extra}


PDF = "application/pdf"
REQUESTS: dict[str, dict[str, Any]] = {
    "01_ok_fiche_paie": _req(
        "req-101", _doc("doc_7f3a", "paie_mars_2026.pdf", PDF),
        options={"language_hint": ["fr", "ar"], "expected_type": "fiche_de_paie", "min_confidence": 0.9},
    ),
    "02_ok_partiel_fiche_paie_illisible": _req(
        "req-102", _doc("doc_8b21", "paie_mars_2026_scan_illisible.jpg", "image/jpeg"),
    ),
    "03_ok_fiche_paie_arabe": _req(
        "req-103", _doc("doc_5c90", "paie_mars_2026_arabe.pdf", PDF), lang="ar",
    ),
    "04_ok_fiche_paie_dossier": _req(
        "req-104", _doc("doc_3d44", "paie_mars_2026.pdf", PDF, card="case_015"),
        case_id="case_015", context=_ctx("case_015", "case"),
    ),
    "05_ok_grille_salaires": _req(
        "req-105", _doc("conv_gardiennage", "convention_gardiennage.pdf", PDF),
        operation="extract_wage_grid", options={"pages": [21]},
    ),
    "06_refus_acces_autre_carte": _req(
        "req-106", _doc("doc_9999", "paie_autre_client.pdf", PDF, card="company_077"),
    ),
    "07_refus_format": _req("req-107", _doc("doc_1111", "archive.zip", "application/zip")),
    "08_refus_fichier_corrompu": _req("req-108", _doc("doc_0000", "facture_corrompu.pdf", PDF)),
    "09_refus_document_blanc": _req("req-109", _doc("doc_2222", "scan_blanc.jpg", "image/jpeg")),
    "10_refus_requete_invalide": {
        "contract_version": "ds3.v2", "request_id": "req-110", "operation": "analyze_document",
        "context": _ctx(), "document": _doc("doc_7f3a", "paie_mars_2026.pdf", PDF),
    },
    "11_erreur_timeout": _req("req-111", _doc("doc_3333", "paie_timeout.pdf", PDF)),
}


def _write(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_demo() -> list[dict[str, Any]]:
    """Les requêtes d'exemple et la réponse que le mock donne à chacune."""
    return [{"name": name, "request": req, "response": handle_request(req)} for name, req in REQUESTS.items()]


def main() -> None:
    SCHEMAS.mkdir(parents=True, exist_ok=True)
    _write(SCHEMAS / "document_intelligence_request.v2.schema.json", DS3Request.model_json_schema())
    _write(SCHEMAS / "document_intelligence_response.v2.schema.json",
           DS3Response.model_json_schema(mode="serialization"))
    _write(SCHEMAS / "document_intelligence_operations.v2.json", list_operations())
    _write(DEMO_FILE, build_demo())
    print(f"{len(REQUESTS)} exemples générés dans {DEMO_FILE.relative_to(REPO)}")


if __name__ == "__main__":
    main()
