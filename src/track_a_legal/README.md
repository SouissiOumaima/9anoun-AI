# DS4 — Lawyer Track (Track A) (`src/track_a_legal/`)

- **Owner** : Ghofran Maaoui
- **Catégorie** : Vertical
- **Branche** : `DS4_Lawyer_Track`

## Responsabilité

Case-analysis agent, evidence mapping, legal drafting, domain validation for legal answers.

## Structure

| Dossier | Contenu |
|---|---|
| `tools/` | Outils et scripts du rôle. |
| `tests/` | Tests automatiques du rôle (`python -m pytest -q src/track_a_legal/tests`). |
| `evaluation/` | Golden sets et métriques propres à ce rôle (voir `evaluation/README.md`). |

Aucun code n'est encore présent : l'organisation interne de ce dossier est
laissée à son owner.

## Conventions communes (voir le README racine)

- Données de test dans `data/mock_cards/`, avec le préfixe `track_a_`.
- Messages échangés avec les autres rôles : JSON Schema versionnés (`src/shared/schemas/`).
- Dépendances : section **DS4** du `requirements.txt` racine.
- Règle « Citation ou Silence » : toute réponse factuelle est sourcée, sinon refus explicite.
