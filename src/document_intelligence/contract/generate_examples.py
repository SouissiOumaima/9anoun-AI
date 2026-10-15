"""Régénère les schémas JSON et le fichier d'exemples DS3 à partir du contrat et du mock.

Lancer depuis la racine du dépôt :
    python -m src.document_intelligence.contract.generate_examples
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.document_intelligence.contract.mock import handle_request, list_operations
from src.document_intelligence.contract.models import DS3Request, DS3Response

REPO = Path(__file__).resolve().parents[3]
MOCK_CARDS = REPO / "data" / "mock_cards"
SCHEMAS = MOCK_CARDS / "schemas"
DEMO_FILE = MOCK_CARDS / "document_intelligence_requests_demo.json"


def _ctx(card: str = "company_042") -> dict[str, Any]:
    return {"organization_id": "org_demo", "user_id": "user_comptable_01", "role": "accountant",
            "card_id": card, "card_type": "company"}


def _doc(doc_id: str, name: str, mime: str, card: str = "company_042") -> dict[str, Any]:
    return {"document_id": doc_id, "card_id": card, "file_name": name, "mime_type": mime,
            "storage_ref": f"tradrly://cards/{card}/documents/{doc_id}"}


REQUESTS: dict[str, dict[str, Any]] = {
    "01_analyze_fiche_paie": {
        "contract_version": "ds3.v1", "request_id": "req-001", "operation": "analyze_document",
        "context": _ctx(), "document": _doc("doc_7f3a", "paie_mars_2026.pdf", "application/pdf"),
        "options": {"language_hint": ["fr", "ar"], "expected_type": "fiche_de_paie", "min_confidence": 0.8},
    },
    "02_analyze_fiche_paie_illisible": {
        "contract_version": "ds3.v1", "request_id": "req-002", "operation": "analyze_document",
        "context": _ctx(), "document": _doc("doc_8b21", "paie_mars_2026_scan_illisible.jpg", "image/jpeg"),
    },
    "03_extract_wage_grid": {
        "contract_version": "ds3.v1", "request_id": "req-003", "operation": "extract_wage_grid",
        "context": _ctx(),
        "document": _doc("conv_gardiennage", "convention_gardiennage.pdf", "application/pdf"),
        "options": {"pages": [21]},
    },
    "04_erreur_fichier_corrompu": {
        "contract_version": "ds3.v1", "request_id": "req-004", "operation": "analyze_document",
        "context": _ctx(), "document": _doc("doc_0000", "facture_corrompu.pdf", "application/pdf"),
    },
    "05_erreur_acces_autre_carte": {
        "contract_version": "ds3.v1", "request_id": "req-005", "operation": "analyze_document",
        "context": _ctx("company_042"),
        "document": _doc("doc_9999", "paie_autre_client.pdf", "application/pdf", card="company_077"),
    },
    "06_erreur_format": {
        "contract_version": "ds3.v1", "request_id": "req-006", "operation": "analyze_document",
        "context": _ctx(), "document": _doc("doc_1111", "archive.zip", "application/zip"),
    },
}


def _write(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_demo() -> list[dict[str, Any]]:
    """Les requêtes d'exemple et la réponse que le mock donne à chacune."""
    return [{"name": name, "request": req, "response": handle_request(req)} for name, req in REQUESTS.items()]


def main() -> None:
    SCHEMAS.mkdir(parents=True, exist_ok=True)
    _write(SCHEMAS / "document_intelligence_request.v1.schema.json", DS3Request.model_json_schema())
    _write(SCHEMAS / "document_intelligence_response.v1.schema.json", DS3Response.model_json_schema())
    _write(SCHEMAS / "document_intelligence_operations.v1.json", list_operations())
    _write(DEMO_FILE, build_demo())
    print(f"{len(REQUESTS)} exemples générés dans {DEMO_FILE.relative_to(REPO)}")


if __name__ == "__main__":
    main()
