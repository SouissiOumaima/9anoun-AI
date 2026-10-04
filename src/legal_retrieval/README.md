# DS2 — Legal Knowledge & Retrieval (`src/legal_retrieval/`)

- **Owner** : Abd Mouhib Souri
- **Catégorie** : Foundation
- **Branche** : `DS2_Legal_Retrieval_Track`

## Responsabilité

Legal knowledge graph, legal metadata, hybrid retrieval, reranking, legal research agent.

## Structure

| Dossier | Contenu |
|---|---|
| `tools/` | Outils et scripts du rôle. |
| `tests/` | Tests automatiques du rôle (`python -m pytest -q src/legal_retrieval/tests`). |
| `evaluation/` | Golden sets et métriques propres à ce rôle (voir `evaluation/README.md`). |

Aucun code n'est encore présent : l'organisation interne de ce dossier est
laissée à son owner.

## Conventions communes (voir le README racine)

- Données de test dans `data/mock_cards/`, avec le préfixe `legal_retrieval_`.
- Messages échangés avec les autres rôles : JSON Schema versionnés (`src/shared/schemas/`).
- Dépendances : section **DS2** du `requirements.txt` racine.
- Règle « Citation ou Silence » : toute réponse factuelle est sourcée, sinon refus explicite.
