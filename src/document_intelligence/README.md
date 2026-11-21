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
| `tests/` | Tests automatiques du rôle (`python -m pytest -q src/document_intelligence/tests`). |
| `evaluation/` | Golden sets et métriques propres à ce rôle (voir `evaluation/README.md`). |

Aucun code n'est encore présent : l'organisation interne de ce dossier est
laissée à ses co-owners.

## Conventions communes (voir le README racine)

- Données de test dans `data/mock_cards/`, avec le préfixe `document_intelligence_`.
- Messages échangés avec les autres rôles : JSON Schema versionnés (`src/shared/schemas/`).
- Dépendances : section **DS3** du `requirements.txt` racine.
- Règle « Citation ou Silence » : toute réponse factuelle est sourcée, sinon refus explicite.
# Performance des analyses PDF live

Les extractions Gemini réussies sont conservées en mémoire du processus pendant
5 minutes, avec un maximum de 32 entrées. Une analyse identique évite un nouvel
appel réseau ; les appels identiques simultanés partagent le même travail.
Le cache est isolé par organisation, utilisateur, rôle, carte, document et
référence de stockage, et dépend du texte complet envoyé, du modèle et de la clé
configurée. Les erreurs ne sont jamais conservées. La lecture du PDF et les
vérifications des citations sont exécutées à chaque demande ; les confirmations
utilisateur et résultats DS5 ne sont pas mis en cache.

Définir `DS3_EXTRACTION_CACHE=0` pour forcer les appels Gemini pendant une
évaluation. Le premier appel reste dépendant de la latence du service distant.
Les journaux INFO de la pipeline indiquent les durées de lecture et d'extraction
sans enregistrer le contenu des documents.
