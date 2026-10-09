# Évaluation Track B — 2026-10-09

Jeu de référence : `src/track_b_accounting/evaluation/golden_sets/track_b_golden.v0.json` (track_b_golden.v0, 47 cas, sha256 `1f2ca0db95b2…`).
Cas vérifiés sur les PDF par DS5 : **0 / 47**.

**Faux montants : 0** (montant faux pour un ok attendu, ou montant renvoyé alors qu'un refus était attendu).

## Ensemble des cas (47 cas)

| Métrique | Nombre | Taux |
|---|---|---|
| Faux montants (ok attendu) | 0 / 31 | 0.0 % |
| Montant au lieu d'un refus | 0 / 16 | 0.0 % |
| Exactitude des montants | 31 / 31 | 100.0 % |
| Silence excessif | 0 / 31 | 0.0 % |
| Refus corrects (même code) | 16 / 16 | 100.0 % |
| Citations valides | 31 / 31 | 100.0 % |
| Conformité schéma Track B | 47 / 47 | 100.0 % |
| Conformité schéma commun | 47 / 47 | 100.0 % |
| Statut erreur / exceptions | 0 / 0 | |

## Cas vérifiés par DS5 (0 cas)

| Métrique | Nombre | Taux |
|---|---|---|
| Faux montants (ok attendu) | 0 / 0 | — |
| Montant au lieu d'un refus | 0 / 0 | — |
| Exactitude des montants | 0 / 0 | — |
| Silence excessif | 0 / 0 | — |
| Refus corrects (même code) | 0 / 0 | — |
| Citations valides | 0 / 0 | — |
| Conformité schéma Track B | 0 / 0 | — |
| Conformité schéma commun | 0 / 0 | — |
| Statut erreur / exceptions | 0 / 0 | |

## Par certitude

| Certitude | Cas | Exactitude montants | Refus corrects | Faux montants |
|---|---|---|---|---|
| L | 34 | 25 / 25 | 9 / 9 | 0 |
| C | 3 | 3 / 3 | 0 / 0 | 0 |
| I | 10 | 3 / 3 | 7 / 7 | 0 |

L = lu dans le PDF, C = calculé à la main, I = interprétation (Dn). Un échec sur un cas I est un désaccord d'interprétation, pas une erreur de lecture.

- Erreurs de lecture (cas L ou C en échec) : aucune
- Désaccords d'interprétation (cas I en échec) : aucun

## Détail des cas

| Cas | Cat. | Cert. | Vérifié | Attendu | Obtenu | Verdict |
|---|---|---|---|---|---|---|
| TB-01 | ok | L | non | 512.027 TND/mois | 512.027 TND/mois | correct |
| TB-02 | ok | L | non | 1011.329 TND/mois | 1011.329 TND/mois | correct |
| TB-03 | ok | L | non | 593.873 TND/mois | 593.873 TND/mois | correct |
| TB-04 | ok | L | non | 1097.992 TND/mois | 1097.992 TND/mois | correct |
| TB-05 | ok | L | non | 4.449 TND/heure | 4.449 TND/heure | correct |
| TB-06 | ok | L | non | 4.620 TND/heure | 4.620 TND/heure | correct |
| TB-07 | ok | L | non | 1040.599 TND/mois | 1040.599 TND/mois | correct |
| TB-08 | ok | L | non | 1612.548 TND/mois | 1612.548 TND/mois | correct |
| TB-09 | ok | L | non | 608.109 TND/mois | 608.109 TND/mois | correct |
| TB-10 | ok | L | non | 3.103 TND/heure | 3.103 TND/heure | correct |
| TB-11 | ok | L | non | 3.754 TND/heure | 3.754 TND/heure | correct |
| TB-12 | ok | L | non | 4.946 TND/heure | 4.946 TND/heure | correct |
| TB-13 | ok | L | non | 100.533 TND/mois | 100.533 TND/mois | correct |
| TB-14 | ok | L | non | 81.435 TND/mois | 81.435 TND/mois | correct |
| TB-15 | ok | L | non | 0.560 TND/jour | 0.560 TND/jour | correct |
| TB-16 | ok | L | non | 0.160 TND/jour | 0.160 TND/jour | correct |
| TB-17 | ok | L | non | 459.264 TND/mois | 459.264 TND/mois | correct |
| TB-18 | ok | L | non | 2.254 TND/heure | 2.254 TND/heure | correct |
| TB-19 | art13 | C D10 | non | 684.630 TND/mois | 684.630 TND/mois | correct |
| TB-20 | art13 | C D10 | non | 961.121 TND/mois | 961.121 TND/mois | correct |
| TB-21 | art13 | C D10 | non | 4.700 TND/heure | 4.700 TND/heure | correct |
| TB-22 | art13 | I D10 | non | 732.635 TND/mois | 732.635 TND/mois | correct |
| TB-23 | art13 | I D10 | non | 899.867 TND/mois | 899.867 TND/mois | correct |
| TB-24 | art13 | I D10 | non | 1085.451 TND/mois | 1085.451 TND/mois | correct |
| TB-25 | refus | I D6 | non | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-26 | refus | I D6 | non | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-27 | refus | I D10 | non | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-28 | refus | I D10 | non | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-29 | refus | I D10 | non | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-30 | refus | I D10 | non | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-31 | refus | L D9 | non | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-32 | refus | I D9 | non | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-33 | refus | L | non | HORS_SCOPE | HORS_SCOPE | correct |
| TB-34 | refus | L | non | HORS_SCOPE | HORS_SCOPE | correct |
| TB-35 | refus | L | non | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-36 | refus | L | non | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-37 | piege | L | non | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-38 | piege | L | non | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-39 | piege | L | non | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-40 | piege | L | non | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-41 | ok | L | non | 620.048 TND/mois | 620.048 TND/mois | correct |
| TB-42 | ok | L | non | 891.361 TND/mois | 891.361 TND/mois | correct |
| TB-43 | ok | L | non | 3.298 TND/heure | 3.298 TND/heure | correct |
| TB-44 | ok | L | non | 1007.111 TND/mois | 1007.111 TND/mois | correct |
| TB-45 | ok | L | non | 535.028 TND/mois | 535.028 TND/mois | correct |
| TB-46 | ok | L | non | 562.267 TND/mois | 562.267 TND/mois | correct |
| TB-47 | ok | L | non | 588.076 TND/mois | 588.076 TND/mois | correct |
