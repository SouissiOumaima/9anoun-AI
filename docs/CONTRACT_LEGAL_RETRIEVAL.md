# Contrat DS2 — Legal Retrieval (`legal_retrieval.v0`)

> **Statut : v0 — proposition, à valider** par DS1 (appelant principal), DS4 et DS5.
> Owner : Abd Mouhib Souri (DS2).

## À quoi sert ce service

Il reçoit une question juridique et renvoie les **articles de loi applicables**
(conventions sectorielles, convention cadre, SMIG…), avec tout ce qu'il faut pour
les **citer** : identifiant stable, texte exact, page du PDF, dates de vigueur.
Il **n'interprète pas** le droit : l'interprétation revient à DS4/DS5.

## Comment l'appeler

| Mode | Commande |
|---|---|
| Python | `from src.legal_retrieval.contract.handler import handle` puis `handle(request_dict)` |
| CLI | `python -m src.legal_retrieval.contract.cli request.json` (ou `--demo`) |
| HTTP | `POST /legal/search` (lancer `uvicorn src.legal_retrieval.contract.api:app --port 8002`) |

## Requête — `legal_retrieval_search_request.v0.schema.json`

| Champ | Type | Obligatoire | Rôle |
|---|---|---|---|
| `contract_version` | `"legal_retrieval.v0"` | oui | version du contrat |
| `query` | string non vide | oui | question (AR ou FR) |
| `request_id` | string | non | traçabilité (audit trail) |
| `reference_date` | `YYYY-MM-DD` ou null | non | la loi doit être en vigueur à cette date ; null = aujourd'hui |
| `sector` | string ou null | non | ex. `banques`, `btp`, `assurance` |
| `worker_category` | string ou null | non | ex. `ouvrier`, `cadre` |
| `language` | `ar` / `fr` | non (`ar`) | langue de la question |
| `top_k` | 1–50 | non (10) | nombre de résultats |

Aucun champ supplémentaire n'est accepté (`additionalProperties: false`).

## Réponse — `legal_retrieval_search_response.v0.schema.json`

| Champ | Valeurs | Sens |
|---|---|---|
| `status` | `success` | des articles pertinents sont renvoyés |
| | `no_decisive_source` | **Citation ou Silence** : rien d'assez pertinent, l'appelant doit s'abstenir |
| | `error` | requête invalide ; le détail est dans `error` (HTTP 422) |
| `mode` | `mock` / `live` | `mock` tant que la recherche hybride n'est pas branchée (Sprint 4) |
| `results[]` | liste | voir ci-dessous |

Chaque résultat contient : `article_id` (ex. `CCS-BANQUES-ART-14-v1`), `source_id`,
`source_title`, `article_number`, `hierarchy_path`, `text` (**texte exact, jamais
normalisé**), `page`, `effective_from`, `effective_to` (null = en vigueur),
`status` (`en_vigueur` / `modifie` / `abroge` / `inconnu`), `sector` (null = tous
secteurs), `related` (voisins dans le graphe), `score` (0–1).

## Règle « toutes les versions » (D-DS2-7)

Quand un avocat, un client ou un comptable pose une question, **toutes les versions
connues** de chaque article pertinent sont renvoyées : la version en vigueur, les
anciennes versions modifiées, et les articles abrogés. L'agent qui rédige la réponse
(DS4/DS5) doit **annoncer les deux** : « voici la règle actuelle, et voici ce qu'elle
était avant l'avenant n° X ».

| Champ | Sens |
|---|---|
| `version_group` | identifiant commun à toutes les versions d'un article (ex. `CCS-BTP-ART-50`) |
| `version` | 1 = plus ancienne version connue |
| `applicable_at_reference_date` | `true` sur **au plus une** version par article : celle en vigueur à `reference_date` |
| `modified` | `true` si l'article porte « (جديد) » |
| `amended_by` | avenant qui a modifié ou abrogé cette version |
| `previous_version_available` | `false` = l'article a été modifié, mais le texte précédent n'est pas dans le corpus (texte consolidé) : **l'appelant doit l'annoncer** |

`top_k` compte des **articles**, jamais des versions : `top_k=1` peut renvoyer
plusieurs lignes (toutes les versions d'un même article).

### Ce que l'appelant doit afficher

| Cas | Message attendu |
|---|---|
| 2 versions disponibles | règle actuelle **et** ancienne règle, avec l'avenant et les dates |
| `previous_version_available = false` | règle actuelle **+** « cet article a été modifié par un avenant ; l'ancienne version n'est pas disponible dans le corpus » |
| `status = abroge` | « cet article a été abrogé par l'avenant n° X » (jamais « introuvable ») |

## Exemple

Voir `data/mock_cards/legal_retrieval_search_demo.json`. En mode `mock`, les textes
sont **faux** et marqués `[MOCK]`. Il contient les trois cas : un article en 2 versions,
un article modifié sans ancienne version disponible, et un article abrogé.

## Points à valider en équipe

1. DS1 : `reference_date` et `sector` sont-ils extraits par votre parser d'entités ?
1b. DS4/DS5 : vos agents savent-ils afficher plusieurs versions d'un même article (règle D-DS2-7) ?
2. DS5 : les barèmes SMIG doivent-ils venir de DS2 (une seule source versionnée) ou rester dans `data/processed/smig_smag/` ?
3. Emplacement définitif des schémas : `src/shared/schemas/` ou `data/mock_cards/schemas/` ?
