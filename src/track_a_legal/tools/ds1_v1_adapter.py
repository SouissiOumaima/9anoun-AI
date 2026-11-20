"""Adaptateur autonome entre l'enveloppe DS1 et DS4 Track A v1."""

import json
from pathlib import Path
from copy import deepcopy
from jsonschema import Draft202012Validator, FormatChecker
from typing import Any, Callable, Mapping

from src.track_a_legal.v1_handler import handle_v1


class DS1V1ContractError(ValueError):
    """Erreur de contrat entre DS1 et DS4 v1."""


class DS1TrackAV1Adapter:
    """Valider une enveloppe DS1 et normaliser la réponse DS4 v1."""

    def __init__(
        self,
        handler: Callable[[dict[str, Any]], dict[str, Any]] = handle_v1,
    ) -> None:
        self._handler = handler

    def __call__(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Exécuter une requête DS4 v1 dans un contexte DS1 validé."""

        if not isinstance(payload, Mapping):
            raise DS1V1ContractError("Invalid DS1 payload.")

        # Autoriser uniquement l'opération juridique prévue.
        if (
            payload.get("agent") != "track_a_legal"
            or payload.get("operation") != "analyze_case"
        ):
            raise DS1V1ContractError("Unsupported agent operation.")

        # L'autorisation DS1 doit être vérifiée en amont.
        # Cet adaptateur ne remplace pas le contrôle des permissions.
        if payload.get("read_only") is not True:
            raise DS1V1ContractError("Read-only operation required.")

        context = payload.get("context")
        params = payload.get("params")

        if not isinstance(context, Mapping):
            raise DS1V1ContractError("Invalid DS1 context.")

        if not isinstance(params, Mapping):
            raise DS1V1ContractError("Invalid DS1 parameters.")

        if context.get("card_type") != "case":
            raise DS1V1ContractError("Case Card required.")

        request = params.get("track_a_request")

        if not isinstance(request, dict):
            raise DS1V1ContractError("Invalid Track A request.")

        if request.get("contract_version") != "track_a.v1":
            raise DS1V1ContractError("Track A v1 required.")

        # Empêcher le traitement d'une autre affaire.
        if (
            not isinstance(payload.get("request_id"), str)
            or not payload["request_id"]
            or request.get("request_id") != payload["request_id"]
            or not isinstance(context.get("card_id"), str)
            or not context["card_id"]
            or request.get("case_id") != context["card_id"]
        ):
            raise DS1V1ContractError("Request or Case Card mismatch.")

        # Ne jamais modifier les données fournies par DS1.
        response = self._handler(deepcopy(request))

        if not isinstance(response, dict):
            raise DS1V1ContractError("Invalid DS4 response.")

        if response.get("contract_version") != "track_a.v1":
            raise DS1V1ContractError("Invalid DS4 response version.")

        if response.get("request_id") != payload["request_id"]:
            raise DS1V1ContractError("DS4 response request_id mismatch.")


        # Valider la r?ponse compl?te avec le contrat officiel DS4 v1.
        schema_file = (
            Path(__file__).resolve().parents[3]
            / "data"
            / "mock_cards"
            / "schemas"
            / "track_a_response.v1.schema.json"
        )

        schema = json.loads(schema_file.read_text(encoding="utf-8-sig"))

        validator = Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        )

        errors = list(validator.iter_errors(response))

        if errors:
            raise DS1V1ContractError("Invalid DS4 response schema.")

        status = response.get("status")

        if status == "ok":
            result = response.get("result")

            if not isinstance(result, dict):
                raise DS1V1ContractError("Missing DS4 result.")

            if result.get("case_id") != context["card_id"]:
                raise DS1V1ContractError("DS4 result case_id mismatch.")

            if not isinstance(response.get("citations"), list):
                raise DS1V1ContractError("Invalid DS4 citations.")

            # Une analyse préliminaire peut avoir zéro citation.
            # Aucune conclusion juridique automatique n'est autorisée.
            if result.get("legal_conclusion") is not None:
                raise DS1V1ContractError("Legal conclusion not authorized.")

            return {
                "status": "success",
                "data": {
                    "result": deepcopy(result),
                    "computed_by": response.get("computed_by"),
                },
                "citations": deepcopy(response["citations"]),
                "error": None,
            }

        if status == "refus":
            if response.get("result") is not None:
                raise DS1V1ContractError("Invalid refusal result.")

            return {
                "status": "refused",
                "data": None,
                "citations": [],
                "error": deepcopy(response.get("refus")),
            }

        if status == "erreur":
            if response.get("result") is not None:
                raise DS1V1ContractError("Invalid error result.")

            return {
                "status": "error",
                "data": None,
                "citations": [],
                "error": deepcopy(response.get("erreur")),
            }

        raise DS1V1ContractError("Invalid DS4 response status.")