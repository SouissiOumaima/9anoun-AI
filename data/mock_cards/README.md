# `data/mock_cards/` — données de test partagées

Chaque rôle peut déposer ici ses jeux de requêtes et de réponses de démo,
ainsi que ses fixtures et ses schémas, sans collision de noms avec les autres.

## Convention : un préfixe par rôle

Chaque fichier, y compris dans `schemas/`, commence par le préfixe du rôle
qui en est propriétaire :

| Rôle | Préfixe | Exemple |
|---|---|---|
| DS1 — Orchestration & Context | `orchestrator_` | `orchestrator_dialogues_demo.json` |
| DS2 — Legal Knowledge & Retrieval | `legal_retrieval_` | `legal_retrieval_queries_demo.json` |
| DS3 — Document Intelligence | `document_intelligence_` | `document_intelligence_samples_demo.json` |
| DS4 — Lawyer Track (Track A) | `track_a_` | `track_a_cases_demo.json` |
| DS5 — Comptable Track (Track B) | `track_b_` | `track_b_requests_demo.json` (existant) |

Les exemples des lignes DS1 à DS4 sont indicatifs : seul le préfixe est
imposé.

Règles :
- Un rôle ne modifie que **ses propres fichiers**. Pour faire évoluer le
  fichier d'un autre rôle, il passe par son owner ou par une pull request.
- Les fichiers existants ne sont pas déplacés : Track B lit les siens à ces
  chemins.
- `schemas/` suit la convention de [`src/shared/schemas/README.md`](../../src/shared/schemas/README.md)
  (`<rôle>_<objet>.v<N>.schema.json`).
- Aucune donnée personnelle réelle : uniquement des données fictives ou tirées
  du corpus public de `data/raw/`.

## Contenu actuel

- `track_b_requests_demo.json` : 10 requêtes de démo du contrat Track B v0.
- `schemas/track_b_request.v0.schema.json`, `schemas/track_b_response.v0.schema.json`.
- `track_b_requests_demo.v1.json` : 18 requêtes de démo du contrat Track B v1 (D75, D76), à part des démos v0.
- `schemas/track_b_request.v1.schema.json`, `schemas/track_b_response.v1.schema.json`.
