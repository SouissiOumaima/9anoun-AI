# DS3 — Document Intelligence (`src/document_intelligence/`)

- **Co-owners** : Hadil Lajili et Wiem Saafi. Le rôle et la branche sont partagés ; la répartition interne du travail sera décidée par l'équipe DS3 et documentée ici.
- **Catégorie** : Foundation
- **Branche** : `DS3_Document_Intelligence_Track`

## Responsabilité

File processing, OCR, table & clause extraction, confidence scoring, document-analysis agent.

## Structure

| Dossier | Contenu |
|---|---|
| `tools/` | Outils et scripts du rôle. |
| `tests/` | Tests automatiques du rôle (`python -m pytest -q src/document_intelligence/tests`). Par défaut, `tests/conftest.py` fait comme si PaddleOCR n'était ni installé ni activé : les résultats sont les mêmes sur tous les postes. Un test qui veut l'OCR passe un faux moteur (`ocr_engine=...`) ; le vrai PaddleOCR est testé dans `test_document_intelligence_ocr.py` (ignoré s'il n'est pas installé). |
| `evaluation/` | Golden sets et métriques propres à ce rôle (voir `evaluation/README.md`). |

Aucun code n'est encore présent : l'organisation interne de ce dossier est
laissée à ses co-owners.

## Conventions communes (voir le README racine)

- Données de test dans `data/mock_cards/`, avec le préfixe `document_intelligence_`.
- Messages échangés avec les autres rôles : JSON Schema versionnés (`src/shared/schemas/`).
- Dépendances : section **DS3** du `requirements.txt` racine.
- Règle « Citation ou Silence » : toute réponse factuelle est sourcée, sinon refus explicite.
