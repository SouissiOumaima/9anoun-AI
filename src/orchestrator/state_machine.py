"""Bounded, auditable DS1 request flow.

The engine only executes allow-listed read-only calls from ``tool_contracts``.
It is intentionally adapter-neutral: DS2-DS5 integrations provide the
``ToolExecutor`` callable once their contracts are accepted.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Mapping
from uuid import uuid4

from .context import ContextResolutionError, resolve_context
from .intent import parse_message
from .legal_retrieval_prompt import extract_legal_prompt
from .models import CardType, Intent, ParsedRequest, RequestEnvelope
from .tool_contracts import ToolCall, ToolContractError, build_tool_call
from .track_b_requests import build_track_b_request
from .track_a_requests import build_track_a_request_from_case_card
from .track_b_prompt import extract_track_b_prompt
from .sector_mapping import sector_clarification_labels
from .document_intelligence_requests import DocumentRequestError, build_document_intelligence_request


class FlowState(str, Enum):
    RECEIVED = "received"
    CONTEXT_VALIDATED = "context_validated"
    UNDERSTOOD = "understood"
    PLANNED = "planned"
    EXECUTING = "executing"
    COMPLETED = "completed"
    CLARIFICATION_REQUIRED = "clarification_required"
    FAILED = "failed"


class PlanningError(ValueError):
    """The request cannot safely be converted into an allow-listed tool call."""


class ClarificationNeeded(PlanningError):
    """A safe route exists but mandatory structured fields are missing."""

    def __init__(self, reason: str, *, message_fr: str | None = None, message_ar: str | None = None) -> None:
        super().__init__(reason)
        self.message_fr = message_fr
        self.message_ar = message_ar


ToolExecutor = Callable[[Mapping[str, Any]], Mapping[str, Any]]
AuditHook = Callable[[RequestEnvelope, "FlowResult"], None]
CaseCardProvider = Callable[[RequestEnvelope], Mapping[str, Any]]


@dataclass(frozen=True, slots=True)
class ExecutionLimits:
    max_steps: int = 8
    tool_timeout_seconds: float = 10.0
    max_retries: int = 1

    def __post_init__(self) -> None:
        if self.max_steps < 1 or self.tool_timeout_seconds <= 0 or self.max_retries < 0:
            raise ValueError("execution limits must be positive (retries may be zero)")


@dataclass(frozen=True, slots=True)
class FlowResult:
    request_id: str
    state: FlowState
    states: tuple[FlowState, ...]
    parsed: ParsedRequest | None = None
    tool_call: ToolCall | None = None
    tool_response: Mapping[str, Any] | None = None
    reason: str | None = None
    attempts: int = 0
    clarification_message_fr: str | None = None
    clarification_message_ar: str | None = None


class Planner:
    """Maps an understood request to exactly one v0 read-only agent call."""

    _ROUTES: dict[Intent, tuple[str, str]] = {
        Intent.LEGAL_RESEARCH: ("legal_retrieval", "search"),
        Intent.DOCUMENT_ANALYSIS: ("document_intelligence", "analyze_document"),
        Intent.CASE_ANALYSIS: ("track_a_legal", "analyze_case"),
        Intent.PAYROLL_CALCULATION: ("track_b_accounting", "compute"),
    }

    def __init__(self, *, case_card_provider: CaseCardProvider | None = None) -> None:
        self._case_card_provider = case_card_provider

    def plan(self, envelope: RequestEnvelope, parsed: ParsedRequest) -> ToolCall:
        if parsed.needs_clarification or parsed.intent not in self._ROUTES:
            raise PlanningError("the request needs clarification before planning")

        agent, operation = self._ROUTES[parsed.intent]
        params: Mapping[str, Any]
        if parsed.intent is Intent.PAYROLL_CALCULATION:
            params = self._track_b_params(envelope, parsed)
        elif parsed.intent is Intent.LEGAL_RESEARCH:
            operation, params = self._legal_retrieval_params(envelope, parsed)
        elif parsed.intent is Intent.CASE_ANALYSIS:
            params = self._track_a_params(envelope, parsed)
        elif parsed.intent is Intent.DOCUMENT_ANALYSIS:
            operation = "extract_wage_grid" if any(word in envelope.message.lower() for word in ("grille", "tableau des salaires", "جدول الأجور")) else operation
            params = self._document_intelligence_params(envelope, parsed, operation)
        else:
            params = {
                "message": envelope.message,
                "language": parsed.language,
                "entities": {key: list(values) for key, values in parsed.entities.items()},
            }
        return build_tool_call(
            tool_call_id=f"tool-{uuid4()}",
            request_id=envelope.request_id,
            actor=envelope.actor,
            context=envelope.context,
            agent=agent,
            operation=operation,
            params=params,
        )

    @staticmethod
    def _track_b_params(envelope: RequestEnvelope, parsed: ParsedRequest) -> Mapping[str, Any]:
        """Build a schema-valid Track B request from explicit prompt wording.

        The extractor standardizes known labels only.  Missing values result in
        clarification rather than guessed payroll data; the JSON schema remains
        the final boundary before a DS5 call.
        """

        extracted = extract_track_b_prompt(envelope.message)
        if extracted.operation is None:
            raise ClarificationNeeded("Track B requires the exact operation: SMIG, salaire de base, or prime")
        if extracted.sector_clarification:
            choices_fr, choices_ar = sector_clarification_labels(envelope.message)
            raise ClarificationNeeded(
                "payroll sector clarification is required",
                message_fr=f"Plusieurs secteurs sont indiqués : {' ou '.join(choices_fr)} ?",
                message_ar=f"تم ذكر أكثر من قطاع: {' أم '.join(choices_ar)}؟",
            )
        if extracted.missing:
            fields = ", ".join(extracted.missing)
            label = "SMIG" if extracted.operation == "smig" else extracted.operation
            raise ClarificationNeeded(f"{label} requires explicit fields: {fields}")
        request = build_track_b_request(
            request_id=envelope.request_id,
            language=parsed.language,
            operation=extracted.operation,
            params=extracted.params,
        )
        return {"track_b_request": request}

    @staticmethod
    def _legal_retrieval_params(envelope: RequestEnvelope, parsed: ParsedRequest) -> tuple[str, Mapping[str, Any]]:
        """Build the DS1 → DS2 legal_retrieval.v0 request from explicit text."""

        extracted = extract_legal_prompt(envelope.message)
        if extracted.sector_ambiguous:
            raise ClarificationNeeded("Le terme construction est ambigu : précisez BTP ou construction métallique")
        dates = parsed.entities.get("dates", ())
        reference_date = next((value for value in dates if len(value) == 10), None)
        if extracted.article is not None and extracted.source_id is None and extracted.article_id is None:
            raise ClarificationNeeded("La référence d'article exige le secteur ou la source, par exemple BTP ou CCS-BTP")
        request: dict[str, Any] = {
            "contract_version": "legal_retrieval.v0", "request_id": envelope.request_id, "lang": parsed.language,
        }
        if reference_date is not None:
            request["reference_date"] = reference_date
        if extracted.article_id is not None:
            request["article_id"] = extracted.article_id
            return "get_article", {"legal_retrieval_request": request}
        if extracted.article is not None:
            request.update({"source_id": extracted.source_id, "article": extracted.article})
            return "get_article", {"legal_retrieval_request": request}
        request.update({"query": envelope.message, "top_k": 5})
        if extracted.sector is not None:
            request["sector"] = extracted.sector
        if extracted.worker_category is not None:
            request["worker_category"] = extracted.worker_category
        return "search", {"legal_retrieval_request": request}

    def _track_a_params(self, envelope: RequestEnvelope, parsed: ParsedRequest) -> Mapping[str, Any]:
        """Build DS1 → DS4 facts only from the validated active Case Card."""

        if envelope.context.card_id is None:
            raise ClarificationNeeded("Track A requires an active Case Card")
        if envelope.context.card_type is not CardType.CASE:
            raise PlanningError("track_a_legal.analyze_case requires one of: case")
        if self._case_card_provider is None:
            raise ClarificationNeeded("Track A requires a structured Case Card provider")
        try:
            case_card = self._case_card_provider(envelope)
            request = build_track_a_request_from_case_card(
                request_id=envelope.request_id, case_id=envelope.context.card_id,
                language=parsed.language, case_card=case_card,
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ClarificationNeeded("The active Case Card is incomplete or inconsistent") from error
        return {"track_a_request": request}

    @staticmethod
    def _document_intelligence_params(
        envelope: RequestEnvelope, parsed: ParsedRequest, operation: str,
    ) -> Mapping[str, Any]:
        try:
            request = build_document_intelligence_request(
                request_id=envelope.request_id, actor=envelope.actor, context=envelope.context,
                language=parsed.language, operation=operation,
            )
        except DocumentRequestError as error:
            raise ClarificationNeeded(str(error)) from error
        return {"ds3_request": request}


class StructuredTrackBPlanner(Planner):
    """Planner for a validated UI/card form supplying a Track B operation."""

    def __init__(self, *, operation: str, params: Mapping[str, Any]) -> None:
        self._operation = operation
        self._params = dict(params)

    def plan(self, envelope: RequestEnvelope, parsed: ParsedRequest) -> ToolCall:
        if parsed.intent is not Intent.PAYROLL_CALCULATION:
            raise ClarificationNeeded("the message does not describe a payroll calculation")
        request = build_track_b_request(
            request_id=envelope.request_id,
            language=parsed.language,
            operation=self._operation,
            params=self._params,
        )
        return build_tool_call(
            tool_call_id=f"tool-{uuid4()}",
            request_id=envelope.request_id,
            actor=envelope.actor,
            context=envelope.context,
            agent="track_b_accounting",
            operation="compute",
            params={"track_b_request": request},
        )


class StateMachine:
    """Runs one request through a bounded state sequence and optional retry."""

    def __init__(self, executor: ToolExecutor, *, limits: ExecutionLimits | None = None,
                 planner: Planner | None = None, audit_hook: AuditHook | None = None) -> None:
        self._executor = executor
        self._limits = limits or ExecutionLimits()
        self._planner = planner or Planner()
        self._audit_hook = audit_hook

    def run(self, envelope: RequestEnvelope) -> FlowResult:
        states: list[FlowState] = []

        def advance(state: FlowState) -> None:
            if len(states) >= self._limits.max_steps:
                raise PlanningError("maximum state-machine steps reached")
            states.append(state)

        advance(FlowState.RECEIVED)
        try:
            resolve_context(actor=envelope.actor, context=envelope.context)
            advance(FlowState.CONTEXT_VALIDATED)
            parsed = parse_message(envelope.message)
            advance(FlowState.UNDERSTOOD)
            if parsed.needs_clarification:
                advance(FlowState.CLARIFICATION_REQUIRED)
                return self._finish(envelope, FlowResult(envelope.request_id, states[-1], tuple(states), parsed=parsed,
                                    reason="intent is ambiguous or unsupported"))

            tool_call = self._planner.plan(envelope, parsed)
            advance(FlowState.PLANNED)
        except ClarificationNeeded as error:
            advance(FlowState.CLARIFICATION_REQUIRED)
            return self._finish(envelope, FlowResult(envelope.request_id, states[-1], tuple(states), parsed=parsed,
                                reason=str(error), clarification_message_fr=error.message_fr,
                                clarification_message_ar=error.message_ar))
        except (ContextResolutionError, ToolContractError, PlanningError, ValueError) as error:
            return self._finish(envelope, self._failed(envelope.request_id, states, str(error)))

        attempts = 0
        last_error: str | None = None
        last_response: Mapping[str, Any] | None = None
        while attempts <= self._limits.max_retries:
            try:
                advance(FlowState.EXECUTING)
                attempts += 1
                response = self._execute(tool_call)
                if response.get("status") not in {"success", "partial", "refused", "error"}:
                    raise ToolContractError("tool response has an invalid status")
                if response["status"] == "error":
                    last_response = response
                    error = response.get("error")
                    error_code = error.get("code") if isinstance(error, Mapping) else None
                    last_error = f"tool error: {error_code or 'unknown'}"
                    retryable = error.get("retryable", True) if isinstance(error, Mapping) else True
                    if retryable and attempts <= self._limits.max_retries:
                        continue
                    return self._finish(envelope, self._failed(
                        envelope.request_id, states, last_error, parsed, tool_call, attempts, last_response,
                    ))
                advance(FlowState.COMPLETED)
                return self._finish(envelope, FlowResult(envelope.request_id, states[-1], tuple(states), parsed, tool_call, response, attempts=attempts))
            except (FutureTimeoutError, ToolContractError, ValueError) as error:
                last_error = str(error) or type(error).__name__

        return self._finish(envelope, self._failed(
            envelope.request_id, states, last_error or "tool execution failed", parsed, tool_call, attempts, last_response,
        ))

    def _finish(self, envelope: RequestEnvelope, result: FlowResult) -> FlowResult:
        if self._audit_hook is not None:
            self._audit_hook(envelope, result)
        return result

    def _execute(self, tool_call: ToolCall) -> Mapping[str, Any]:
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(self._executor, tool_call.to_payload())
        try:
            return future.result(timeout=self._limits.tool_timeout_seconds)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    @staticmethod
    def _failed(
        request_id: str,
        states: list[FlowState],
        reason: str,
        parsed: ParsedRequest | None = None,
        tool_call: ToolCall | None = None,
        attempts: int = 0,
        tool_response: Mapping[str, Any] | None = None,
    ) -> FlowResult:
        if not states or states[-1] is not FlowState.FAILED:
            states.append(FlowState.FAILED)
        return FlowResult(
            request_id, FlowState.FAILED, tuple(states), parsed, tool_call,
            tool_response=tool_response, reason=reason, attempts=attempts,
        )
