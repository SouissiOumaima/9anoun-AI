"""Safe, bilingual user-facing responses for DS1 flow outcomes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class UserResponseCode(str, Enum):
    SUCCESS = "SUCCESS"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    ACCESS_DENIED = "ACCESS_DENIED"
    CONTEXT_REQUIRED = "CONTEXT_REQUIRED"
    INVALID_PARAMETERS = "INVALID_PARAMETERS"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    DOCUMENT_UNREADABLE = "DOCUMENT_UNREADABLE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    SOURCE_MISSING = "SOURCE_MISSING"
    TOOL_TIMEOUT = "TOOL_TIMEOUT"
    TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"
    INVALID_TOOL_RESPONSE = "INVALID_TOOL_RESPONSE"
    EXECUTION_LIMIT = "EXECUTION_LIMIT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


@dataclass(frozen=True, slots=True)
class UserResponse:
    """Stable API-safe response; internal reasons are deliberately excluded."""

    status: str
    code: UserResponseCode
    message_fr: str
    message_ar: str
    next_action: str
    request_id: str
    specialist_code: str | None = None

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["code"] = self.code.value
        return payload


_MESSAGES: dict[UserResponseCode, tuple[str, str, str]] = {
    UserResponseCode.SUCCESS: (
        "Votre demande a été traitée.", "تمت معالجة طلبك.", "review_result"
    ),
    UserResponseCode.CLARIFICATION_REQUIRED: (
        "Des précisions sont nécessaires avant de poursuivre.", "نحتاج إلى توضيحات قبل المتابعة.", "provide_missing_information"
    ),
    UserResponseCode.ACCESS_DENIED: (
        "Vous n'êtes pas autorisé à accéder à ce contexte.", "ليس لديك صلاحية للوصول إلى هذا السياق.", "select_an_authorized_card"
    ),
    UserResponseCode.CONTEXT_REQUIRED: (
        "Une carte active autorisée est nécessaire pour cette demande.", "تتطلب هذه العملية بطاقة نشطة ومصرحًا بها.", "select_an_active_card"
    ),
    UserResponseCode.INVALID_PARAMETERS: (
        "Les paramètres fournis ne sont pas valides.", "المعطيات المقدمة غير صالحة.", "correct_parameters"
    ),
    UserResponseCode.UNSUPPORTED_FORMAT: (
        "Ce format de fichier n'est pas pris en charge.", "صيغة الملف غير مدعومة.", "choose_supported_file"
    ),
    UserResponseCode.DOCUMENT_UNREADABLE: (
        "Le document est vide, endommagé ou illisible.", "الوثيقة فارغة أو تالفة أو غير قابلة للقراءة.", "upload_a_readable_document"
    ),
    UserResponseCode.OUT_OF_SCOPE: (
        "Cette demande est hors du périmètre actuellement pris en charge.", "هذا الطلب خارج النطاق المدعوم حاليًا.", "change_request"
    ),
    UserResponseCode.SOURCE_MISSING: (
        "Aucune source vérifiée ne permet de répondre à cette demande.", "لا يوجد مصدر موثوق يسمح بالإجابة عن هذا الطلب.", "provide_a_verified_source_or_change_request"
    ),
    UserResponseCode.TOOL_TIMEOUT: (
        "Le service a mis trop de temps à répondre. Veuillez réessayer.", "استغرق النظام وقتًا طويلاً للرد. يرجى إعادة المحاولة.", "retry_later"
    ),
    UserResponseCode.TOOL_UNAVAILABLE: (
        "Le service spécialisé est indisponible pour le moment.", "الخدمة المتخصصة غير متاحة حاليًا.", "retry_later"
    ),
    UserResponseCode.INVALID_TOOL_RESPONSE: (
        "Le service a renvoyé une réponse non valide. Aucun résultat n'est affiché.", "أرجعت الخدمة استجابة غير صالحة. لم يتم عرض أي نتيجة.", "retry_or_contact_support"
    ),
    UserResponseCode.EXECUTION_LIMIT: (
        "La demande dépasse la limite d'exécution autorisée.", "تجاوز الطلب حد التنفيذ المسموح به.", "simplify_request"
    ),
    UserResponseCode.INTERNAL_ERROR: (
        "Une erreur technique est survenue. Aucun résultat n'est affiché.", "حدث خطأ تقني. لم يتم عرض أي نتيجة.", "retry_or_contact_support"
    ),
}


def format_flow_result(result: Any) -> UserResponse:
    """Map a state-machine result to a bilingual, non-sensitive API response."""

    state = getattr(result.state, "value", result.state)
    if state == "completed":
        tool_status = (result.tool_response or {}).get("status")
        if tool_status == "refused":
            refusal = (result.tool_response or {}).get("error")
            code = _refusal_code(refusal)
            if getattr(getattr(result, "tool_call", None), "agent", None) == "track_b_accounting":
                return _ds5_refusal_response(refusal, code, result.request_id)
            return _response("refused", code, result.request_id)
        return _response("success", UserResponseCode.SUCCESS, result.request_id)
    if state == "clarification_required":
        return _response("clarification_required", UserResponseCode.CLARIFICATION_REQUIRED, result.request_id)
    tool_error = (result.tool_response or {}).get("error") if isinstance(getattr(result, "tool_response", None), dict) else None
    if isinstance(tool_error, dict):
        code = _specialist_error_code(_error_identifier(tool_error))
        if code is not None:
            return _response("error", code, result.request_id)
    return _response("error", _failure_code(result.reason or ""), result.request_id)


def _specialist_error_code(code: Any) -> UserResponseCode | None:
    """Normalize public specialist codes without exposing their raw payload."""
    return {
        "ACCESS_DENIED": UserResponseCode.ACCESS_DENIED,
        "ACCES_REFUSE": UserResponseCode.ACCESS_DENIED,
        "UNSUPPORTED_FORMAT": UserResponseCode.UNSUPPORTED_FORMAT,
        "FILE_EMPTY_OR_CORRUPTED": UserResponseCode.DOCUMENT_UNREADABLE,
        "UNREADABLE_DOCUMENT": UserResponseCode.DOCUMENT_UNREADABLE,
        "NO_TABLE_FOUND": UserResponseCode.SOURCE_MISSING,
        "SOURCE_MANQUANTE": UserResponseCode.SOURCE_MISSING,
        "TIMEOUT": UserResponseCode.TOOL_TIMEOUT,
        "TOOL_TIMEOUT": UserResponseCode.TOOL_TIMEOUT,
        "INVALID_REQUEST": UserResponseCode.INVALID_PARAMETERS,
        "PARAM_INVALIDE": UserResponseCode.INVALID_PARAMETERS,
        "FILE_TOO_LARGE": UserResponseCode.INVALID_PARAMETERS,
        "UNSUPPORTED_OPERATION": UserResponseCode.OUT_OF_SCOPE,
        "HORS_SCOPE": UserResponseCode.OUT_OF_SCOPE,
    }.get(code, UserResponseCode.INTERNAL_ERROR if code in {"INTERNAL_ERROR", "INTERNE"} else None)


def _refusal_code(error: Any) -> UserResponseCode:
    """Map every public specialist refusal (DS2–DS5) to one UI vocabulary."""

    return _specialist_error_code(_error_identifier(error)) or UserResponseCode.INVALID_TOOL_RESPONSE


def _ds5_refusal_response(error: Any, code: UserResponseCode, request_id: str) -> UserResponse:
    """Preserve DS5's bilingual, source-aware refusal for the user."""

    if isinstance(error, dict) and all(isinstance(error.get(key), str) and error[key] for key in ("code", "message_fr", "message_ar")):
        _, _, next_action = _MESSAGES[code]
        return UserResponse("refused", code, error["message_fr"], error["message_ar"], next_action, request_id, error["code"])
    return _response("refused", code, request_id)


def _error_identifier(error: Any) -> Any:
    """Contracts use ``code`` for refusals and ``type``/``ds3_code`` for errors."""

    if not isinstance(error, dict):
        return None
    return error.get("code") or error.get("type") or error.get("ds3_code")


def _failure_code(reason: str) -> UserResponseCode:
    lowered = reason.lower()
    if "organization mismatch" in lowered or "not authorized" in lowered:
        return UserResponseCode.ACCESS_DENIED
    if "active card is required" in lowered or "requires one of" in lowered:
        return UserResponseCode.CONTEXT_REQUIRED
    if "timeout" in lowered:
        return UserResponseCode.TOOL_TIMEOUT
    if "dependencies are not installed" in lowered or "unavailable" in lowered:
        return UserResponseCode.TOOL_UNAVAILABLE
    if "invalid status" in lowered or "invalid response" in lowered or "requires result and citations" in lowered:
        return UserResponseCode.INVALID_TOOL_RESPONSE
    if "maximum state-machine steps" in lowered:
        return UserResponseCode.EXECUTION_LIMIT
    if "parameter" in lowered or "contract" in lowered or "request is invalid" in lowered:
        return UserResponseCode.INVALID_PARAMETERS
    return UserResponseCode.INTERNAL_ERROR


def _response(status: str, code: UserResponseCode, request_id: str) -> UserResponse:
    message_fr, message_ar, next_action = _MESSAGES[code]
    return UserResponse(status, code, message_fr, message_ar, next_action, request_id)
