"""Strict DS1 -> DS3 request construction.

Document metadata comes only from the active card context supplied by the
backend.  It is never inferred from the user's prompt.
"""

from __future__ import annotations

from typing import Any, Mapping

from .models import ActiveContext, UserIdentity


class DocumentRequestError(ValueError):
    """The active card does not provide the document required by DS3."""


_ROLE_MAP = {
    "admin": "admin", "accountant": "accountant", "comptable": "accountant",
    "lawyer": "lawyer", "avocat": "lawyer",
}
_DOCUMENT_KEYS = ("document_id", "document_file_name", "document_mime_type", "document_storage_ref")


def build_document_intelligence_request(
    *, request_id: str, actor: UserIdentity, context: ActiveContext, language: str,
    operation: str = "analyze_document", contract_version: str = "ds3.v2",
) -> dict[str, Any]:
    """Build a DS3 request from an authorized active-card document.

    ``entity_ids`` is backend-owned context.  It must carry document metadata
    when a document is selected; missing metadata produces clarification rather
    than a fabricated file reference.
    """
    if context.card_id is None or context.card_type is None:
        raise DocumentRequestError("DS3 requires an active authorized card")
    if operation not in {"analyze_document", "extract_wage_grid"}:
        raise DocumentRequestError("DS3 operation is not supported")
    if contract_version not in {"ds3.v1", "ds3.v2"}:
        raise DocumentRequestError("DS3 contract version is not supported")
    missing = [key for key in _DOCUMENT_KEYS if not context.entity_ids.get(key)]
    if missing:
        raise DocumentRequestError("DS3 requires selected document metadata: " + ", ".join(missing))
    role = _ROLE_MAP.get(actor.role.lower())
    if role is None:
        raise DocumentRequestError("DS3 requires a mapped authenticated role")
    document = {
        "document_id": context.entity_ids["document_id"],
        "card_id": context.card_id,
        "file_name": context.entity_ids["document_file_name"],
        "mime_type": context.entity_ids["document_mime_type"],
        "storage_ref": context.entity_ids["document_storage_ref"],
    }
    request = {
        "contract_version": contract_version, "request_id": request_id, "operation": operation,
        "context": {
            "organization_id": context.organization_id, "user_id": actor.user_id, "role": role,
            "card_id": context.card_id, "card_type": context.card_type.value,
        },
        "document": document,
        "options": {"language_hint": [language]},
    }
    if contract_version == "ds3.v2":
        request["lang"] = language
    return request
