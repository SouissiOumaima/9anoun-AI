# Évaluation — DS2 Legal Knowledge & Retrieval

Ce dossier contient les **golden sets et les métriques propres à DS2**.
L'évaluation n'est pas un rôle séparé : chaque rôle évalue son propre domaine.

## Organisation prévue

| Élément | Sprint | Contenu |
|---|---|---|
| `golden_set_retrieval.v0.json` | S2 | questions (AR/FR) → `article_id` attendus + date de référence + source qui justifie |
| `metrics.py` | S4 | Recall@10, précision temporelle, taux d'abstention correcte |
| `results/AAAA-MM-JJ.json` | S4+ | résultats datés, comparés au dernier baseline |

## Métriques cibles (spec Tradrly §8.4)

| Métrique | Définition | Cible |
|---|---|---|
| Recall@10 | l'article attendu est dans les 10 premiers résultats | ≥ 88 % |
| Temporal accuracy | la version renvoyée était en vigueur à `reference_date` | ≥ 90 % |
| Abstention | hors périmètre → `no_decisive_source` | ≥ 85 % |

Les données de test partagées avec d'autres rôles vont dans `data/mock_cards/`
(préfixe `legal_retrieval_`).
