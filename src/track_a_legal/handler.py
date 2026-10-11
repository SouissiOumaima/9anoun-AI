
"""
Handler principal du Lawyer Track (DS4).

Point d'entrée destiné à l'orchestrateur DS1.

Version initiale :
- validation de la requête ;
- analyse préparatoire du dossier ;
- refus si aucune source juridique vérifiée ;
- gestion des erreurs techniques.

Aucune citation juridique n'est inventée.
"""

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from src.track_a_legal.tools.case_analysis import analyze_case


# Chemin vers la racine du projet
ROOT = Path(__file__).resolve().parents[2]

# Contrats JSON de DS4
SCHEMAS = ROOT / "data" / "mock_cards" / "schemas"

REQUEST_SCHEMA = SCHEMAS / "track_a_request.v0.schema.json"
RESPONSE_SCHEMA = SCHEMAS / "track_a_response.v0.schema.json"


def load_schema(path: Path) -> dict:
    """Charge un contrat JSON Schema."""
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def make_refus(request_id, case_id, code, message_fr, message_ar):
    """Construit une réponse de refus bilingue."""

    response = {
        "contract_version": "track_a.v0",
        "request_id": request_id,
        "status": "refus",
        "result": None,
        "citations": [],
        "refus": {
            "code": code,
            "message_fr": message_fr,
            "message_ar": message_ar
        },
        "computed_by": "track_a_legal.handler"
    }

    if case_id is not None:
        response["case_id"] = case_id

    return response


def handle(request: dict) -> dict:
    """
    Traite une requête DS4 et retourne une réponse JSON.

    Ne produit pas encore de conclusion juridique sourcée.
    """

    # 1. Charger les schémas
    request_schema = load_schema(REQUEST_SCHEMA)
    response_schema = load_schema(RESPONSE_SCHEMA)

    request_validator = Draft202012Validator(
        request_schema,
        format_checker=FormatChecker()
    )
    response_validator = Draft202012Validator(response_schema)

    # 2. Récupérer les identifiants lisibles
    request_id = None
    case_id = None

    if isinstance(request, dict):
        if isinstance(request.get("request_id"), str):
            request_id = request["request_id"]

        if isinstance(request.get("case_id"), str):
            case_id = request["case_id"]

    # 3. Valider la requête
    if not request_validator.is_valid(request):
        response = make_refus(
            request_id,
            case_id,
            "PARAM_INVALIDE",
            "La requête ne respecte pas le contrat Track A v0.",
            "الطلب لا يتوافق مع عقد Track A v0."
        )

    else:
        try:
            # 4. Exécuter l'analyse préparatoire
            analysis = analyze_case(request)

            # 5. Vérifier sa structure
            result_schema = response_schema["properties"]["result"]

            response_validator_result = Draft202012Validator(
                result_schema,
                format_checker=FormatChecker()
            )
            response_validator_result.validate(analysis)

            # 6. Pas encore de citations juridiques vérifiées
            response = make_refus(
                request_id,
                case_id,
                "SOURCE_MANQUANTE",
                "L'analyse préparatoire a été exécutée, mais aucune source juridique vérifiée ne permet encore de produire une conclusion.",
                "تم تنفيذ التحليل الأولي، لكن لا تتوفر بعد مصادر قانونية موثوقة لإصدار استنتاج قانوني."
            )

        except Exception:
            # Ne pas exposer les détails techniques internes
            response = {
                "contract_version": "track_a.v0",
                "request_id": request_id,
                "status": "erreur",
                "result": None,
                "citations": [],
                "refus": None,
                "erreur": {
                    "type": "INTERNAL_ERROR",
                    "message_fr": "Une erreur technique est survenue pendant le traitement.",
                    "message_ar": "حدث خطأ تقني أثناء معالجة الطلب."
                },
                "computed_by": "track_a_legal.handler"
            }

            if case_id is not None:
                response["case_id"] = case_id

    # 7. Vérifier la réponse avant de la retourner
    response_validator.validate(response)

    return response
