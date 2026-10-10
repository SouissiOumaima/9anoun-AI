# DS2 — Legal Knowledge & Retrieval (`src/legal_retrieval/`)

- **Owner** : Abd Mouhib Souri
- **Catégorie** : Foundation
- **Branche** : `DS2_Legal_Retrieval_Track`

## Responsabilité

Legal knowledge graph, legal metadata, hybrid retrieval, reranking, legal research agent.

## Structure

| Dossier | Contenu |
|---|---|
| `corpus/` | Ingestion hybride : texte de l'OCR (`data/raw/txt`), chiffres vérifiés sur le PDF (`data/raw/pdf`) → articles. |
| `contract/` | Contrat avec les autres rôles : `handler` (validation JSON Schema), `cli`, `api` (HTTP). |
| `tools/` | `diagnose_text_layer` (forme des en-têtes), `diagnose_pua` (glyphes Private Use, comparaison PDF/OCR). |
| `tests/` | Tests automatiques (`python -m pytest -q src/legal_retrieval/tests`). |
| `evaluation/` | Golden sets et métriques (voir `evaluation/README.md`). |
| `SPRINTS.md` | Plan de travail DS2 sur 10 semaines. |

## Lancer depuis zéro (depuis la racine du dépôt)

```bash
python -m pip install -r src/legal_retrieval/requirements.txt
python -m pytest -q src/legal_retrieval/tests                   # tests
python -m src.legal_retrieval.corpus.ingest                     # data/raw/txt (+ data/raw/pdf) -> data/processed/legal_corpus
python -m src.legal_retrieval.contract.cli --demo               # contrat en ligne de commande
uvicorn src.legal_retrieval.contract.api:app --port 8002        # contrat en HTTP (POST /legal/search)
```

## Sorties de l'ingestion (`data/processed/legal_corpus/`)

| Fichier | Contenu |
|---|---|
| `legal_articles.jsonl` | un article par ligne = une unité de recherche (chunk) ; `numbers_unverified` liste les chiffres de l'OCR absents du PDF |
| `legal_sources.json` | une source par PDF (dates et références JORT : Sprint 2) |
| `ingestion_report.json` | qualité par fichier : articles, numéros manquants, pages vides, texte inversé |

## Contrat (statut : v0 — proposition, à valider)

- Schémas : `data/mock_cards/schemas/legal_retrieval_search_{request,response}.v0.schema.json`
- Exemple requête/réponse : `data/mock_cards/legal_retrieval_search_demo.json`
- Documentation : `docs/CONTRACT_LEGAL_RETRIEVAL.md`

## Conventions communes (voir le README racine)

- Données de test dans `data/mock_cards/`, avec le préfixe `legal_retrieval_`.
- Messages échangés avec les autres rôles : JSON Schema versionnés (`src/shared/schemas/`).
- Dépendances : section **DS2** du `requirements.txt` racine → `src/legal_retrieval/requirements.txt`.
- Règle « Citation ou Silence » : toute réponse factuelle est sourcée, sinon refus explicite
  (`status: "refus"`, code `SOURCE_MANQUANTE`, message FR + AR — enveloppe `common.v0`, D19).
