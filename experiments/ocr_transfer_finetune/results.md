# Résultats : Transfer Learning vs Fine-Tuning (arabic_PP-OCRv5_mobile_rec)

Fichier généré automatiquement par `run_experiment.py` : uniquement des chiffres mesurés.

- Données FICTIVES : train 1200, val 200, test 400, generic (hors domaine) 150 lignes ; graine 42.
- Machine : Intel64 Family 6 Model 183 Stepping 1, GenuineIntel (20 threads), CPU seulement ; durée totale 363.8 min (reprises après plantage comprises).
- **Variante de Fine-Tuning qui a produit le chiffre : `bn_frozen`** — tout dégelé sauf BatchNorm (paramètres et statistiques gelés). Voir ANALYSE.md (plantage natif de Paddle pendant le Fine-Tuning complet).

## Jeu de test (domaine : fiches de paie et conventions, FR + AR)

| Méthode | CER | WER | Lignes exactes | CER FR | CER AR | CER mixte | Paramètres entraînés | Époques (meilleure) | Durée |
|---|---|---|---|---|---|---|---|---|---|
| Baseline (pré-entraîné, sans entraînement) | 13.68 % | 24.74 % | 47.00 % | 0.57 % | 24.93 % | 46.97 % | 0 | — | — |
| Transfer Learning (encodeur gelé, tête entraînée) | 3.24 % | 19.38 % | 58.50 % | 0.13 % | 5.92 % | 11.04 % | 90 629 | 15 (8) | 17.1 min |
| Fine-Tuning, variante `bn_frozen` (LR faible) | 1.20 % | 7.06 % | 79.50 % | 0.13 % | 1.91 % | 6.28 % | 5 478 185 | 4 (3) | 153.9 min |

## Oubli : jeu « generic » (phrases hors domaine, jamais vues à l'entraînement)

| Méthode | CER generic | WER generic |
|---|---|---|
| Baseline (pré-entraîné, sans entraînement) | 0.65 % | 3.59 % |
| Transfer Learning (encodeur gelé, tête entraînée) | 0.43 % | 2.53 % |
| Fine-Tuning, variante `bn_frozen` (LR faible) | 0.35 % | 2.00 % |

## Exemples (test)

| Référence | Baseline | Transfer | Fine-Tuning |
|---|---|---|---|
| Catégorie 4 Échelon 5 | Catégorie 4 Echelon 5 | Catégorie 4 Échelon 5 | Catégorie 4 Échelon 5 |
| Date d'embauche : 21/06/2015 | Date d'embauche : 21/06/2015 | Date d'embauche : 21/06/2015 | Date d'embauche : 21/06/2015 |
| الضريبة على الدخل : 2613.193 د | الضريبة علىالدخل | الضريبة علىالدخل 2613.193د | الضريبة على الدخل : 2613.193د |
| Convention collective du commerce | Convention collective du commerce | Convention collective du commerce | Convention collective du commerce |
| Date d'embauche : 11/01/2022 | Date d'embauche : 11/01/2022 | Date d'embauche : 11/01/2022 | Date d'embauche : 11/01/2022 |
| Qualification : Agent de maîtrise | Qualification : Agent de maïtrise | Qualification : Agent de maitrise | Qualification : Agent de maïtrise |
| Catégorie 12 sous-catégorie I | Catégorie 12 sous-catégorie I | Catégorie 12 sous-catégorie I | Catégorie 12 sous-catégorie I |
| Avance sur salaire 26 1296.688 | Avance sur salaire 26 1296.688 | Avance sur salaire 26 1296.688 | Avance sur salaire 26 1296.688 |

Courbes : `loss_curves.png`. Détails complets : `results.json`.
