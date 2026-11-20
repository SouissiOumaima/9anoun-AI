"""Routage explicite des contrats Track A v0 et v1."""

from typing import Any, Callable, Mapping

from src.track_a_legal.tools.ds1_v1_adapter import (
    DS1TrackAV1Adapter,
    DS1V1ContractError,
)


class DS1TrackAVersionRouter:
    """Sélectionner un adaptateur Track A selon la version demandée."""

    def __init__(
        self,
        *,
        v0_adapter: Callable[[Mapping[str, Any]], Mapping[str, Any]],
        v1_adapter: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    ) -> None:
        # L'adaptateur v0 officiel sera injecté par DS1.
        # Ne pas importer src.orchestrator dans la branche DS4.
        self._v0_adapter = v0_adapter
        self._v1_adapter = v1_adapter or DS1TrackAV1Adapter()

    def __call__(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """Acheminer une requête vers la version exacte du contrat."""

        if not isinstance(payload, Mapping):
            raise DS1V1ContractError("Invalid DS1 payload.")

        # N'accepter que l'opération Track A prévue.
        if (
            payload.get("agent") != "track_a_legal"
            or payload.get("operation") != "analyze_case"
        ):
            raise DS1V1ContractError("Unsupported Track A operation.")

        params = payload.get("params")

        if not isinstance(params, Mapping):
            raise DS1V1ContractError("Invalid DS1 parameters.")

        request = params.get("track_a_request")

        if not isinstance(request, Mapping):
            raise DS1V1ContractError("Missing Track A request.")

        version = request.get("contract_version")

        # Préserver strictement la compatibilité v0.
        if version == "track_a.v0":
            return self._v0_adapter(payload)

        # Utiliser l'adaptateur sécurisé DS4 v1.
        if version == "track_a.v1":
            return self._v1_adapter(payload)

        # Refuser toute version inconnue.
        raise DS1V1ContractError("Unsupported Track A contract version.")