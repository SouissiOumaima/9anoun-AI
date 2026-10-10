# DS2 — Legal Search & Graph Service : plan de sprints (10 × 1 semaine)

Règle : chaque sprint livre une tranche verticale qui tourne. CORE d'abord, ENHANCEMENT ensuite.
Definition of Done : tests pytest verts, ruff et mypy propres, README à jour, PR revue, démo.

| Sprint | CORE (obligatoire) | ENHANCEMENT (si le CORE est fini) | Livrable démontrable |
|---|---|---|---|
| S1 | Contrat `legal_retrieval.v0` (JSON Schema), mock, ingestion data/raw/pdf → articles JSONL, rapport qualité | CLI + API HTTP `/legal/search` pour DS1 | `ingestion_report.json` + `curl` sur l’API |
| S2 | Schéma métadonnées : référence JORT, date de publication **≠ date d'effet**, statut, secteur, langue (rempli pour les 9 sources) | Mini golden set de recherche (30 questions → article_id attendus) | `legal_sources.json` complet + golden set v0 |
| S3 | Graphe : nœuds Source/Article/Version/Secteur ; arêtes APPLIQUE, MODIFIE, ABROGE, S_APPLIQUE_AU_SECTEUR, CITE | Liens convention sectorielle ↔ convention cadre ↔ SMIG | Requête : « tous les textes applicables au secteur banques » |
| S4 | BM25 (texte normalisé, n° d'article exact) + dense (embeddings validés par Tradrly) + fusion RRF | Requête par numéro d'article (« الفصل 14 ») | 1ʳᵉ mesure Recall@10 |
| S5 | Filtre temporel : `effective_from ≤ reference_date < effective_to` | Avertissement si `reference_date` absente | Tests de précision temporelle |
| S6 | Vraie API `/legal/search` + `GET /legal/article/{id}` (pour la vérification des citations) branchée à DS1 | Expansion par le graphe (`related`) | Appel de bout en bout depuis l'orchestrateur |
| S7 | Reranking (cross-encoder ou petit tier Gemini 3) | Reformulation de requête (darija/FR → AR) si la latence le permet | Comparaison Recall avant/après |
| S8 | Recall@10 ≥ 88 % sur le golden set | Seuil d'abstention `no_decisive_source` | Rapport de métriques |
| S9 | Gel des index + procédure de mise à jour du corpus | Latence recherche < 3 s (P95) | Index versionné |
| S10 | Documentation + transfert | Démo recette | Handover |

## Points bloquants à remonter à Tradrly (S1)
1. Le Code du travail et les décrets d’application ne sont pas dans `data/raw/` : seuls 9 textes y sont (7 conventions sectorielles, la convention cadre, la grille SMIG).
2. Choix du modèle d'embeddings (Gemini ou modèle local) : validation écrite nécessaire.
3. Dates d'effet et références JORT de chaque convention et de ses avenants.
