# Évaluation Track B — 2026-10-14

Jeu de référence : `src/track_b_accounting/evaluation/golden_sets/track_b_golden.v0.json` (track_b_golden.v0, 79 cas, sha256 `34c958e5c351…`).
Cas vérifiés sur les PDF par DS5 : **69 / 79**.

**Faux montants : 0** (montant faux pour un ok attendu, ou montant renvoyé alors qu'un refus était attendu).

## Ensemble des cas (79 cas)

| Métrique | Nombre | Taux |
|---|---|---|
| Faux montants (ok attendu) | 0 / 52 | 0.0 % |
| Montant au lieu d'un refus | 0 / 27 | 0.0 % |
| Exactitude des montants | 52 / 52 | 100.0 % |
| Silence excessif | 0 / 52 | 0.0 % |
| Refus corrects (même code ; même message s'il est fixé) | 27 / 27 | 100.0 % |
| Messages de refus différents de l'attendu | 0 / 27 | 0.0 % |
| Citations valides | 52 / 52 | 100.0 % |
| Conformité schéma Track B | 79 / 79 | 100.0 % |
| Conformité schéma commun | 79 / 79 | 100.0 % |
| Statut erreur / exceptions | 0 / 0 | |

## Cas vérifiés par DS5 (69 cas)

| Métrique | Nombre | Taux |
|---|---|---|
| Faux montants (ok attendu) | 0 / 52 | 0.0 % |
| Montant au lieu d'un refus | 0 / 17 | 0.0 % |
| Exactitude des montants | 52 / 52 | 100.0 % |
| Silence excessif | 0 / 52 | 0.0 % |
| Refus corrects (même code ; même message s'il est fixé) | 17 / 17 | 100.0 % |
| Messages de refus différents de l'attendu | 0 / 17 | 0.0 % |
| Citations valides | 52 / 52 | 100.0 % |
| Conformité schéma Track B | 69 / 69 | 100.0 % |
| Conformité schéma commun | 69 / 69 | 100.0 % |
| Statut erreur / exceptions | 0 / 0 | |

## Par certitude

| Certitude | Cas | Exactitude montants | Refus corrects | Faux montants |
|---|---|---|---|---|
| L | 56 | 43 / 43 | 13 / 13 | 0 |
| C | 3 | 3 / 3 | 0 / 0 | 0 |
| I | 20 | 6 / 6 | 14 / 14 | 0 |

L = lu dans le PDF, C = calculé à la main, I = interprétation (Dn). Un échec sur un cas I est un désaccord d'interprétation, pas une erreur de lecture.

- Erreurs de lecture (cas L ou C en échec) : aucune
- Désaccords d'interprétation (cas I en échec) : aucun

## Détail des cas

| Cas | Cat. | Cert. | Vérifié | Attendu | Obtenu | Verdict |
|---|---|---|---|---|---|---|
| TB-01 | ok | L | oui | 512.027 TND/mois | 512.027 TND/mois | correct |
| TB-02 | ok | L | oui | 1011.329 TND/mois | 1011.329 TND/mois | correct |
| TB-03 | ok | L | oui | 593.873 TND/mois | 593.873 TND/mois | correct |
| TB-04 | ok | L | oui | 1097.992 TND/mois | 1097.992 TND/mois | correct |
| TB-05 | ok | L | oui | 4.449 TND/heure | 4.449 TND/heure | correct |
| TB-06 | ok | L | oui | 4.620 TND/heure | 4.620 TND/heure | correct |
| TB-07 | ok | L | oui | 1040.599 TND/mois | 1040.599 TND/mois | correct |
| TB-08 | ok | L | oui | 1612.548 TND/mois | 1612.548 TND/mois | correct |
| TB-09 | ok | L | oui | 608.109 TND/mois | 608.109 TND/mois | correct |
| TB-10 | ok | L | oui | 3.103 TND/heure | 3.103 TND/heure | correct |
| TB-11 | ok | L | oui | 3.754 TND/heure | 3.754 TND/heure | correct |
| TB-12 | ok | L | oui | 4.946 TND/heure | 4.946 TND/heure | correct |
| TB-13 | ok | L | oui | 100.533 TND/mois | 100.533 TND/mois | correct |
| TB-14 | ok | L | oui | 81.435 TND/mois | 81.435 TND/mois | correct |
| TB-15 | ok | L | oui | 0.560 TND/jour | 0.560 TND/jour | correct |
| TB-16 | ok | L | oui | 0.160 TND/jour | 0.160 TND/jour | correct |
| TB-17 | ok | L | oui | 459.264 TND/mois | 459.264 TND/mois | correct |
| TB-18 | ok | L | oui | 2.254 TND/heure | 2.254 TND/heure | correct |
| TB-19 | art13 | C D10 | oui | 684.630 TND/mois | 684.630 TND/mois | correct |
| TB-20 | art13 | C D10 | oui | 961.121 TND/mois | 961.121 TND/mois | correct |
| TB-21 | art13 | C D10 | oui | 4.700 TND/heure | 4.700 TND/heure | correct |
| TB-22 | art13 | I D10 | oui | 732.635 TND/mois | 732.635 TND/mois | correct |
| TB-23 | art13 | I D10 | oui | 899.867 TND/mois | 899.867 TND/mois | correct |
| TB-24 | art13 | I D10 | oui | 1085.451 TND/mois | 1085.451 TND/mois | correct |
| TB-25 | refus | I D6 | non | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-26 | refus | I D6 | non | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-27 | refus | I D10 | non | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-28 | refus | I D10 | non | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-29 | refus | I D10 | non | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-30 | refus | I D10 | non | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-31 | refus | L D9 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-32 | refus | I D9 | non | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-33 | refus | L | non | HORS_SCOPE | HORS_SCOPE | correct |
| TB-34 | refus | L | non | HORS_SCOPE | HORS_SCOPE | correct |
| TB-35 | refus | L | non | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-36 | refus | L | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-37 | piege | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-38 | piege | L | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-39 | piege | L | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-40 | piege | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-41 | ok | L | oui | 620.048 TND/mois | 620.048 TND/mois | correct |
| TB-42 | ok | L | oui | 891.361 TND/mois | 891.361 TND/mois | correct |
| TB-43 | ok | L | oui | 3.298 TND/heure | 3.298 TND/heure | correct |
| TB-44 | ok | L | oui | 1007.111 TND/mois | 1007.111 TND/mois | correct |
| TB-45 | ok | L | oui | 535.028 TND/mois | 535.028 TND/mois | correct |
| TB-46 | ok | L | oui | 562.267 TND/mois | 562.267 TND/mois | correct |
| TB-47 | ok | L | oui | 588.076 TND/mois | 588.076 TND/mois | correct |
| TB-48 | ok | L | oui | 1323.587 TND/mois | 1323.587 TND/mois | correct |
| TB-49 | ok | L | oui | 716.630 TND/mois | 716.630 TND/mois | correct |
| TB-50 | ok | L | oui | 906.083 TND/mois | 906.083 TND/mois | correct |
| TB-51 | ok | I D23 | oui | 1119.767 TND/mois | 1119.767 TND/mois | correct |
| TB-52 | ok | L | oui | 1519.237 TND/mois | 1519.237 TND/mois | correct |
| TB-53 | ok | L | oui | 1018.335 TND/mois | 1018.335 TND/mois | correct |
| TB-54 | piege | I D23 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-55 | refus | I D23 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-56 | refus | I D6 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-57 | refus | L | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-58 | refus | I D23 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-59 | refus | I D23 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-60 | piege | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-61 | ok | L | oui | 38.685 TND/mois | 38.685 TND/mois | correct |
| TB-62 | ok | L | oui | 6.281 TND/mois | 6.281 TND/mois | correct |
| TB-63 | ok | L | oui | 61.944 TND/mois | 61.944 TND/mois | correct |
| TB-64 | ok | L | oui | 2444.852 TND/mois | 2444.852 TND/mois | correct |
| TB-65 | ok | L | oui | 2195.134 TND/mois | 2195.134 TND/mois | correct |
| TB-66 | ok | L | oui | 2021.621 TND/mois | 2021.621 TND/mois | correct |
| TB-67 | ok | L | oui | 1716.244 TND/mois | 1716.244 TND/mois | correct |
| TB-68 | ok | L | oui | 1510.891 TND/mois | 1510.891 TND/mois | correct |
| TB-69 | ok | L | oui | 2821.764 TND/mois | 2821.764 TND/mois | correct |
| TB-70 | ok | L | oui | 1598.617 TND/mois | 1598.617 TND/mois | correct |
| TB-71 | ok | L | oui | 1935.459 TND/mois | 1935.459 TND/mois | correct |
| TB-72 | ok | L | oui | 75.000 TND/mois | 75.000 TND/mois | correct |
| TB-73 | ok | L | oui | 85.000 TND/mois | 85.000 TND/mois | correct |
| TB-74 | ok | I D29 | oui | 2821.764 TND/mois | 2821.764 TND/mois | correct |
| TB-75 | ok | I D29 | oui | 1716.244 TND/mois | 1716.244 TND/mois | correct |
| TB-76 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-77 | refus | I D6 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-78 | refus | L D29 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-79 | refus | I D29 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
