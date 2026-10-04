# DS1 — Orchestration & Context (`src/orchestrator/`)

- **Owner** : Achraf Chaabane
- **Catégorie** : Backbone
- **Branche** : `DS1_Orchestration_Track`

## Responsabilité

Orchestrator, planner, state machine, context/card resolver, intent & entity understanding.

## Structure

| Dossier | Contenu |
|---|---|
| `tools/` | Outils et scripts du rôle. |
| `tests/` | Tests automatiques du rôle (`python -m pytest -q src/orchestrator/tests`). |
| `evaluation/` | Golden sets et métriques propres à ce rôle (voir `evaluation/README.md`). |

Aucun code n'est encore présent : l'organisation interne de ce dossier est
laissée à son owner.

## Conventions communes (voir le README racine)

- Données de test dans `data/mock_cards/`, avec le préfixe `orchestrator_`.
- Messages échangés avec les autres rôles : JSON Schema versionnés (`src/shared/schemas/`).
- Dépendances : section **DS1** du `requirements.txt` racine.
- Règle « Citation ou Silence » : toute réponse factuelle est sourcée, sinon refus explicite.
