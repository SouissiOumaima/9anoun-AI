from types import SimpleNamespace

from src.orchestrator.response_formatter import UserResponseCode, format_flow_result


def result(state, *, response=None, reason=None):
    return SimpleNamespace(request_id="request-1", state=state, tool_response=response, reason=reason)


def test_success_response_is_bilingual_and_safe() -> None:
    formatted = format_flow_result(result("completed", response={"status": "success"}))
    assert formatted.status == "success"
    assert formatted.code is UserResponseCode.SUCCESS
    assert formatted.message_fr and formatted.message_ar


def test_track_b_refusal_codes_get_user_safe_messages() -> None:
    formatted = format_flow_result(result("completed", response={"status": "refused", "error": {"code": "SOURCE_MANQUANTE"}}))
    assert formatted.status == "refused"
    assert formatted.code is UserResponseCode.SOURCE_MISSING
    assert formatted.next_action == "provide_a_verified_source_or_change_request"


def test_access_reason_never_leaks_raw_detail() -> None:
    formatted = format_flow_result(result("failed", reason="card is not authorized for this user: secret-card"))
    payload = formatted.to_payload()
    assert formatted.code is UserResponseCode.ACCESS_DENIED
    assert "secret-card" not in str(payload)
    assert "not authorized" not in str(payload)


def test_timeout_and_execution_limit_are_distinguished() -> None:
    timeout = format_flow_result(result("failed", reason="TimeoutError"))
    limit = format_flow_result(result("failed", reason="maximum state-machine steps reached"))
    assert timeout.code is UserResponseCode.TOOL_TIMEOUT
    assert limit.code is UserResponseCode.EXECUTION_LIMIT


def test_clarification_response_has_next_step() -> None:
    formatted = format_flow_result(result("clarification_required"))
    assert formatted.code is UserResponseCode.CLARIFICATION_REQUIRED
    assert formatted.next_action == "provide_missing_information"


def test_ds3_errors_are_mapped_to_safe_specific_user_messages() -> None:
    cases = {
        "ACCESS_DENIED": UserResponseCode.ACCESS_DENIED,
        "UNSUPPORTED_FORMAT": UserResponseCode.UNSUPPORTED_FORMAT,
        "FILE_EMPTY_OR_CORRUPTED": UserResponseCode.DOCUMENT_UNREADABLE,
        "TIMEOUT": UserResponseCode.TOOL_TIMEOUT,
    }
    for error_code, expected in cases.items():
        formatted = format_flow_result(result("failed", response={
            "status": "error", "error": {"code": error_code, "message_fr": "internal secret"},
        }))
        assert formatted.status == "error"
        assert formatted.code is expected
        assert "internal secret" not in str(formatted.to_payload())
