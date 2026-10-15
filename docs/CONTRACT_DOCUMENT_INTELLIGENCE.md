# Contrat DS3 — Document Intelligence (ds3.v1)

Ce document répond à la demande de DS1. Il contient le contrat JSON request/response de DS3,
des exemples de requêtes et de réponses, et un mock Python qui expose la même interface
que le futur service réel.

## Interface (appel Python direct, indépendant du transport)

```python
from src.document_intelligence.contract.mock import handle_request, list_operations

response = handle_request(request)   # dict JSON en entrée, dict JSON en sortie
```

`handle_request` ne lève jamais d'exception : toute erreur revient sous forme de réponse
`status = "error"` avec un code. Quand le service réel sera prêt, seul l'import changera
(`src.document_intelligence.service` au lieu de `src.document_intelligence.contract.mock`). Le format JSON restera identique, ce qui permettra
aussi de passer à HTTP plus tard sans modifier DS1.

## Opérations disponibles

| Opération | Rôle | Résultat |
|---|---|---|
| `analyze_document` | Lire un document de carte (fiche de paie, facture, contrat, pièce de dossier) | `DocumentAnalysis` : type, résumé, champs, tableaux |
| `extract_wage_grid` | Extraire une grille de salaires d'une convention collective | `WageGrid` : catégorie × échelon, date d'effet |

La liste complète des champs obligatoires et optionnels est dans
`data/mock_cards/schemas/document_intelligence_operations.v1.json`.

## Champs de la requête

Obligatoires : `contract_version` (`"ds3.v1"`), `request_id`, `operation`, le bloc `context`
(`organization_id`, `user_id`, `role`, `card_id`, `card_type`) et le bloc `document`
(`document_id`, `card_id`, `file_name`, `mime_type`, `storage_ref`).

Optionnels (bloc `options`) : `language_hint`, `expected_type`, `pages`, `min_confidence`.

Le bloc `context` est fourni par le backend DS1. DS3 ne transmet jamais le contenu du fichier,
seulement sa référence de stockage.

## Statuts de réponse

- `success` : tout a été lu avec une confiance suffisante.
- `partial` : le résultat est utilisable, mais au moins une valeur est illisible.
  Cette valeur vaut `null`, avec `unreadable_reason` et une confiance faible.
  DS3 ne devine jamais un chiffre.
- `error` : rien n'est renvoyé dans `result`, et `error` contient `code`, `message_fr`,
  `message_ar` et `retryable`.

Codes d'erreur : `INVALID_REQUEST`, `UNSUPPORTED_OPERATION`, `UNSUPPORTED_FORMAT`,
`FILE_EMPTY_OR_CORRUPTED`, `FILE_TOO_LARGE`, `ACCESS_DENIED`, `UNREADABLE_DOCUMENT`,
`NO_TABLE_FOUND`, `TIMEOUT`, `INTERNAL_ERROR`.

## Règles du contrat

1. Les montants sont des chaînes à 3 décimales (`"344.500"`), à convertir en `Decimal`.
2. Chaque champ extrait porte un `citation_id`. La citation donne la page, la zone (`bbox`)
   et l'extrait exact lu, pour la vérification par DS6.
3. Tout résultat porte le `card_id`. Un document dont le `card_id` diffère de celui du
   contexte est refusé avec `ACCESS_DENIED`.
4. Le texte extrait d'un document est une donnée, jamais une instruction pour l'agent.

## Comportement du mock

| Requête | Réponse du mock |
|---|---|
| Fichier normal, `analyze_document` | Fiche de paie fictive, `success` |
| Nom de fichier contenant `illisible` | Même fiche, retenue CNSS illisible, `partial` |
| `extract_wage_grid` | Extrait réel de la grille n° 2 (page 21), catégories 1 et 15 |
| Nom de fichier contenant `corrompu` | Erreur `FILE_EMPTY_OR_CORRUPTED` |
| `document.card_id` différent de `context.card_id` | Erreur `ACCESS_DENIED` |
| Extension non supportée (ex. `.zip`) | Erreur `UNSUPPORTED_FORMAT` |
| Requête mal formée | Erreur `INVALID_REQUEST` |

Les données de fiche de paie sont fictives et les montants sont illustratifs : ils ne sont pas
calculés selon les taux CNSS réels et ne doivent pas servir à tester les calculs de DS5.
Les montants de la grille de salaires, eux, sont relevés sur le document original.

## Fichiers

```
src/document_intelligence/contract/models.py              modèles Pydantic du contrat (source de vérité)
src/document_intelligence/contract/mock.py                handle_request() et list_operations()
src/document_intelligence/contract/generate_examples.py   régénère schémas et exemples
src/document_intelligence/tests/test_document_intelligence_mock.py   tests du contrat (15)
data/mock_cards/schemas/document_intelligence_request.v1.schema.json
data/mock_cards/schemas/document_intelligence_response.v1.schema.json
data/mock_cards/schemas/document_intelligence_operations.v1.json
data/mock_cards/document_intelligence_requests_demo.json  6 requêtes d'exemple et leurs réponses
```

## Lancer (depuis la racine du dépôt)

```bash
python -m pytest -q src/document_intelligence
python -m src.document_intelligence.contract.generate_examples   # régénère schémas et exemples
```

Le test `test_demo_file_is_up_to_date` échoue si le fichier d'exemples ne correspond plus au mock :
il suffit alors de relancer `generate_examples`.

## Prochaine version

Une version `ds3.v2` est prévue pour s'aligner sur le schéma commun `common.v0`
(statuts, refus en français et en arabe) et sur la convention `meta.mode = "mock" / "live"`.
Elle sera annoncée à DS1 et DS5 avant tout changement.

## Évolution du contrat

Toute modification du contrat (ajout, renommage ou suppression d'un champ) est annoncée à
DS1 et DS5 avant d'être faite, et entraîne un changement de `contract_version`.
