
"""Adaptateur autonome entre l'enveloppe DS1 et DS4 Track A v1."""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Mapping

from jsonschema import Draft202012Validator, FormatChecker

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

        # Déterminer la racine du dépôt.
        self._root = Path(__file__).resolve().parents[3]

        # Charger les deux schémas officiels DS4 v1.
        self._request_validator = self._load_validator(
            "track_a_request.v1.schema.json"
        )

        self._response_validator = self._load_validator(
            "track_a_response.v1.schema.json"
        )

    def _load_validator(self, filename: str) -> Draft202012Validator:
        """Charger un schéma JSON officiel et initialiser son validateur."""

        schema_path = (
            self._root
            / "data"
            / "mock_cards"
            / "schemas"
            / filename
        )

        # Vérifier l'existence du schéma officiel.
        if not schema_path.is_file():
            raise DS1V1ContractError(
                f"Official schema not found: {filename}"
            )

        # Lire le schéma en prenant en charge le BOM UTF-8.
        schema = json.loads(
            schema_path.read_text(encoding="utf-8-sig")
        )

        return Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        )

    def __call__(
        self,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Exécuter une requête DS4 v1 dans un contexte DS1 validé."""

        # Étape 1 : vérifier l'enveloppe DS1.
        if not isinstance(payload, Mapping):
            raise DS1V1ContractError("Invalid DS1 payload.")

        # Autoriser uniquement l'opération juridique prévue.
        if (
            payload.get("agent") != "track_a_legal"
            or payload.get("operation") != "analyze_case"
        ):
            raise DS1V1ContractError(
                "Unsupported agent operation."
            )

        # Exiger une opération en lecture seule.
        if payload.get("read_only") is not True:
            raise DS1V1ContractError(
                "Read-only operation required."
            )

        context = payload.get("context")
        params = payload.get("params")

        if not isinstance(context, Mapping):
            raise DS1V1ContractError("Invalid DS1 context.")

        if not isinstance(params, Mapping):
            raise DS1V1ContractError("Invalid DS1 parameters.")

        if context.get("card_type") != "case":
            raise DS1V1ContractError("Case Card required.")

        # Étape 2 : récupérer la requête Track A.
        request = params.get("track_a_request")

        if not isinstance(request, dict):
            raise DS1V1ContractError(
                "Invalid Track A request."
            )

        if request.get("contract_version") != "track_a.v1":
            raise DS1V1ContractError(
                "Track A v1 required."
            )

        # Étape 3 : valider intégralement le contrat d'entrée.
        # Cette validation intervient AVANT tout appel au handler.
        if not self._request_validator.is_valid(request):
            raise DS1V1ContractError(
                "Invalid Track A v1 request schema."
            )

        # Étape 4 : vérifier la cohérence des identifiants.
        if (
            not isinstance(payload.get("request_id"), str)
            or not payload["request_id"]
            or request.get("request_id") != payload["request_id"]
            or not isinstance(context.get("card_id"), str)
            or not context["card_id"]
            or request.get("case_id") != context["card_id"]
        ):
            raise DS1V1ContractError(
                "Request or Case Card mismatch."
            )

        # Étape 5 : transmettre une copie indépendante au handler.
        # Les données originales fournies par DS1 restent intactes.
        response = self._handler(deepcopy(request))

        if not isinstance(response, dict):
            raise DS1V1ContractError(
                "Invalid DS4 response."
            )

        # Étape 6 : vérifier la version et l'identifiant de réponse.
        if response.get("contract_version") != "track_a.v1":
            raise DS1V1ContractError(
                "Invalid DS4 response version."
            )

        if response.get("request_id") != payload["request_id"]:
            raise DS1V1ContractError(
                "DS4 response request_id mismatch."
            )

        # Étape 7 : valider la réponse avec le schéma officiel.
        if not self._response_validator.is_valid(response):
            raise DS1V1ContractError(
                "Invalid DS4 response schema."
            )

        status = response.get("status")

        # Étape 8 : normaliser une réponse réussie.
        if status == "ok":
            result = response.get("result")

            if not isinstance(result, dict):
                raise DS1V1ContractError(
                    "Missing DS4 result."
                )

            if result.get("case_id") != context["card_id"]:
                raise DS1V1ContractError(
                    "DS4 result case_id mismatch."
                )

            if not isinstance(response.get("citations"), list):
                raise DS1V1ContractError(
                    "Invalid DS4 citations."
                )

            # Interdire toute conclusion juridique automatique.
            if result.get("legal_conclusion") is not None:
                raise DS1V1ContractError(
                    "Legal conclusion not authorized."
                )

            return {
                "status": "success",
                "data": {
                    "result": deepcopy(result),
                    "computed_by": response.get("computed_by"),
                },
                "citations": deepcopy(response["citations"]),
                "error": None,
            }

        # Étape 9 : normaliser un refus DS4.
        if status == "refus":
            if response.get("result") is not None:
                raise DS1V1ContractError(
                    "Invalid refusal result."
                )

            return {
                "status": "refused",
                "data": None,
                "citations": [],
                "error": deepcopy(response.get("refus")),
            }

        # Étape 10 : normaliser une erreur DS4.
        if status == "erreur":
            if response.get("result") is not None:
                raise DS1V1ContractError(
                    "Invalid error result."
                )

            return {
                "status": "error",
                "data": None,
                "citations": [],
                "error": deepcopy(response.get("erreur")),
            }

        # Refuser tout statut inconnu.
        raise DS1V1ContractError(
            "Invalid DS4 response status."
        )
