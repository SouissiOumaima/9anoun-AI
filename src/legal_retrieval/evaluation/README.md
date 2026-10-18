# Évaluation — DS2 Legal Knowledge & Retrieval

Ce dossier contient les **golden sets et les métriques propres à DS2**.
L'évaluation n'est pas un rôle séparé : chaque rôle évalue son propre domaine.

## Organisation prévue

| Élément | Sprint | Contenu |
|---|---|---|
| `golden_set_retrieval.v0.json` ✅ (D27) | S4 | questions (AR/FR) → `article_id` attendus + date de référence + source qui justifie |
| `metrics.py` ✅ + `find_candidates.py` ✅ | S4 | Recall@10, précision temporelle, taux d'abstention correcte |
| `results/AAAA-MM-JJ.json` | S4+ | résultats datés, comparés au dernier baseline |

## Métriques cibles (spec Tradrly §8.4)

| Métrique | Définition | Cible |
|---|---|---|
| Recall@10 | l'article attendu est dans les 10 premiers résultats | ≥ 88 % |
| Temporal accuracy | la version renvoyée était en vigueur à `reference_date` | ≥ 90 % |
| Abstention | hors périmètre → `no_decisive_source` | ≥ 85 % |

Les données de test partagées avec d'autres rôles vont dans `data/mock_cards/`
(préfixe `legal_retrieval_`).

## Utilisation (D27)

```powershell
# 1. trouver l'article attendu d'une question (recherche par mot, indépendante du moteur)
python -m src.legal_retrieval.evaluation.find_candidates "عطلة" --sector banques
# 2. le noter dans golden_set_retrieval.v0.json : "expected": ["CCS-BANQUES-ART-21"], "status": "complet"
# 3. mesurer (sauvegarde results/<date>.json)
python -m src.legal_retrieval.evaluation.metrics
```
Seuls les identifiants, rangs et scores sont affichés : jamais le texte d'un article (NDA).
