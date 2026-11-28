# Évaluation Track B — 2026-11-28

Jeu de référence : `src/track_b_accounting/evaluation/golden_sets/track_b_golden.v0.json` (track_b_golden.v0, 514 cas, sha256 `602a786f862d…`).
Cas vérifiés sur les PDF par DS5 : **503 / 514**.

**Faux montants : 0** (montant faux pour un ok attendu, ou montant renvoyé alors qu'un refus était attendu).

## Ensemble des cas (514 cas)

| Métrique | Nombre | Taux |
|---|---|---|
| Faux montants (ok attendu) | 0 / 309 | 0.0 % |
| Montant au lieu d'un refus | 0 / 205 | 0.0 % |
| Exactitude des montants | 309 / 309 | 100.0 % |
| Silence excessif | 0 / 309 | 0.0 % |
| Refus corrects (même code ; même message s'il est fixé) | 205 / 205 | 100.0 % |
| Messages de refus différents de l'attendu | 0 / 205 | 0.0 % |
| Citations valides | 309 / 309 | 100.0 % |
| Conformité schéma Track B | 514 / 514 | 100.0 % |
| Conformité schéma commun | 514 / 514 | 100.0 % |
| Statut erreur / exceptions | 0 / 0 | |

## Cas vérifiés par DS5 (503 cas)

| Métrique | Nombre | Taux |
|---|---|---|
| Faux montants (ok attendu) | 0 / 308 | 0.0 % |
| Montant au lieu d'un refus | 0 / 195 | 0.0 % |
| Exactitude des montants | 308 / 308 | 100.0 % |
| Silence excessif | 0 / 308 | 0.0 % |
| Refus corrects (même code ; même message s'il est fixé) | 195 / 195 | 100.0 % |
| Messages de refus différents de l'attendu | 0 / 195 | 0.0 % |
| Citations valides | 308 / 308 | 100.0 % |
| Conformité schéma Track B | 503 / 503 | 100.0 % |
| Conformité schéma commun | 503 / 503 | 100.0 % |
| Statut erreur / exceptions | 0 / 0 | |

## Hors périmètre (48 cas, D110)

Jeu : `src/track_b_accounting/evaluation/golden_sets/track_b_hors_perimetre.v0.json` (track_b_hors_perimetre.v0, sha256 `8b125c37e18f…`).

| Métrique | Nombre | Taux |
|---|---|---|
| Taux de refus hors périmètre (code et motif attendus) | 48 / 48 | 100.0 % |
| Montant au lieu d'un refus | 0 / 48 | 0.0 % |
| Conformité schéma Track B | 48 / 48 | 100.0 % |

Seuil : 85 % ; **atteint**. Échecs : aucun.

| Cas | Thème | Attendu | Obtenu | Verdict |
|---|---|---|---|---|
| HP-01 | cnss | HORS_SCOPE | HORS_SCOPE | correct |
| HP-02 | cnss | HORS_SCOPE | HORS_SCOPE | correct |
| HP-03 | irpp | HORS_SCOPE | HORS_SCOPE | correct |
| HP-04 | factures | HORS_SCOPE | HORS_SCOPE | correct |
| HP-05 | depenses | HORS_SCOPE | HORS_SCOPE | correct |
| HP-06 | ratios | HORS_SCOPE | HORS_SCOPE | correct |
| HP-07 | heures_supplementaires | HORS_SCOPE | HORS_SCOPE | correct |
| HP-08 | conges | HORS_SCOPE | HORS_SCOPE | correct |
| HP-09 | indemnites | HORS_SCOPE | HORS_SCOPE | correct |
| HP-10 | faux_track_b_net | HORS_SCOPE | HORS_SCOPE | correct |
| HP-11 | faux_track_b_conversion | HORS_SCOPE | HORS_SCOPE | correct |
| HP-12 | faux_track_b_simulation | HORS_SCOPE | HORS_SCOPE | correct |
| HP-13 | faux_track_b_conversion | HORS_SCOPE | HORS_SCOPE | correct |
| HP-14 | faux_track_b_conversion | HORS_SCOPE | HORS_SCOPE | correct |
| HP-15 | heures_supplementaires | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| HP-16 | indemnites | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| HP-17 | convention_cadre | HORS_SCOPE | HORS_SCOPE | correct |
| HP-18 | convention_cadre | HORS_SCOPE | HORS_SCOPE | correct |
| HP-19 | convention_cadre | HORS_SCOPE | HORS_SCOPE | correct |
| HP-20 | convention_cadre | HORS_SCOPE | HORS_SCOPE | correct |
| HP-21 | secteur_sans_grille | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| HP-22 | secteur_sans_grille | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| HP-23 | population_inexistante | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| HP-24 | population_inexistante | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| HP-25 | cnss | HORS_SCOPE | HORS_SCOPE | correct |
| HP-26 | cnss | HORS_SCOPE | HORS_SCOPE | correct |
| HP-27 | irpp | HORS_SCOPE | HORS_SCOPE | correct |
| HP-28 | factures | HORS_SCOPE | HORS_SCOPE | correct |
| HP-29 | depenses | HORS_SCOPE | HORS_SCOPE | correct |
| HP-30 | ratios | HORS_SCOPE | HORS_SCOPE | correct |
| HP-31 | heures_supplementaires | HORS_SCOPE | HORS_SCOPE | correct |
| HP-32 | conges | HORS_SCOPE | HORS_SCOPE | correct |
| HP-33 | indemnites | HORS_SCOPE | HORS_SCOPE | correct |
| HP-34 | faux_track_b_net | HORS_SCOPE | HORS_SCOPE | correct |
| HP-35 | faux_track_b_conversion | HORS_SCOPE | HORS_SCOPE | correct |
| HP-36 | faux_track_b_simulation | HORS_SCOPE | HORS_SCOPE | correct |
| HP-37 | faux_track_b_conversion | HORS_SCOPE | HORS_SCOPE | correct |
| HP-38 | faux_track_b_conversion | HORS_SCOPE | HORS_SCOPE | correct |
| HP-39 | heures_supplementaires | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| HP-40 | indemnites | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| HP-41 | convention_cadre | HORS_SCOPE | HORS_SCOPE | correct |
| HP-42 | convention_cadre | HORS_SCOPE | HORS_SCOPE | correct |
| HP-43 | convention_cadre | HORS_SCOPE | HORS_SCOPE | correct |
| HP-44 | convention_cadre | HORS_SCOPE | HORS_SCOPE | correct |
| HP-45 | secteur_sans_grille | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| HP-46 | secteur_sans_grille | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| HP-47 | population_inexistante | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| HP-48 | population_inexistante | PARAM_INVALIDE | PARAM_INVALIDE | correct |

## Par certitude

| Certitude | Cas | Exactitude montants | Refus corrects | Faux montants |
|---|---|---|---|---|
| L | 240 | 171 / 171 | 69 / 69 | 0 |
| C | 8 | 8 / 8 | 0 / 0 | 0 |
| I | 266 | 130 / 130 | 136 / 136 | 0 |

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
| TB-80 | ok | L | oui | 551.637 TND/mois | 551.637 TND/mois | correct |
| TB-81 | ok | L | oui | 645.526 TND/mois | 645.526 TND/mois | correct |
| TB-82 | ok | L | oui | 618.390 TND/mois | 618.390 TND/mois | correct |
| TB-83 | ok | L | oui | 631.252 TND/mois | 631.252 TND/mois | correct |
| TB-84 | ok | L | oui | 811.482 TND/mois | 811.482 TND/mois | correct |
| TB-85 | ok | L | oui | 62.500 TND/mois | 62.500 TND/mois | correct |
| TB-86 | ok | L | oui | 57.166 TND/mois | 57.166 TND/mois | correct |
| TB-87 | ok | L | oui | 81.166 TND/mois | 81.166 TND/mois | correct |
| TB-88 | ok | L | oui | 80.666 TND/mois | 80.666 TND/mois | correct |
| TB-89 | ok | L | oui | 66.666 TND/mois | 66.666 TND/mois | correct |
| TB-90 | ok | L | oui | 53.000 TND/mois | 53.000 TND/mois | correct |
| TB-91 | ok | L | oui | 31.400 TND/mois | 31.400 TND/mois | correct |
| TB-92 | refus | I D6 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-93 | refus | I D38 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-94 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-95 | refus | I D38 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-96 | refus | I D38 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-97 | refus | L D38 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-98 | ok | L | oui | 1523.106 TND/mois | 1523.106 TND/mois | correct |
| TB-99 | ok | L | oui | 1862.796 TND/mois | 1862.796 TND/mois | correct |
| TB-100 | ok | L | oui | 2679.026 TND/mois | 2679.026 TND/mois | correct |
| TB-101 | ok | L | oui | 2451.146 TND/mois | 2451.146 TND/mois | correct |
| TB-102 | ok | L | oui | 3432.376 TND/mois | 3432.376 TND/mois | correct |
| TB-103 | ok | L | oui | 1803.576 TND/mois | 1803.576 TND/mois | correct |
| TB-104 | ok | L | oui | 2110.596 TND/mois | 2110.596 TND/mois | correct |
| TB-105 | ok | L | oui | 1634.216 TND/mois | 1634.216 TND/mois | correct |
| TB-106 | refus | I D6 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-107 | refus | I D46 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-108 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-109 | refus | I D46 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-110 | refus | I D46 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-111 | refus | L D46 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-112 | ok | L | oui | 344.500 TND/mois | 344.500 TND/mois | correct |
| TB-113 | ok | L | oui | 534.500 TND/mois | 534.500 TND/mois | correct |
| TB-114 | ok | L | oui | 637.500 TND/mois | 637.500 TND/mois | correct |
| TB-115 | ok | L | oui | 1028.000 TND/mois | 1028.000 TND/mois | correct |
| TB-116 | ok | I D47 | oui | 1503.000 TND/mois | 1503.000 TND/mois | correct |
| TB-117 | ok | L | oui | 20.000 TND/mois | 20.000 TND/mois | correct |
| TB-118 | ok | L | oui | 3.120 TND/mois | 3.120 TND/mois | correct |
| TB-119 | ok | L | oui | 5.200 TND/mois | 5.200 TND/mois | correct |
| TB-120 | refus | I D6 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-121 | refus | I D47 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-122 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-123 | refus | I D47 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-124 | refus | I D47 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-125 | refus | L | oui | HORS_SCOPE | HORS_SCOPE | correct |
| TB-126 | ok | I D49 | oui | 4.073 TND/heure | 4.073 TND/heure | correct |
| TB-127 | ok | L | oui | 60.610 TND/mois | 60.610 TND/mois | correct |
| TB-128 | refus | I D6 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-129 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-130 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-131 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-132 | ok | I D50 | oui | 1046.082 TND/mois | 1046.082 TND/mois | correct |
| TB-133 | ok | L | oui | 0.481 TND/jour | 0.481 TND/jour | correct |
| TB-134 | refus | I D6 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-135 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-136 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-137 | ok | I D51 | oui | 1319.652 TND/mois | 1319.652 TND/mois | correct |
| TB-138 | ok | L | oui | 93.290 TND/mois | 93.290 TND/mois | correct |
| TB-139 | refus | I D51 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-140 | refus | I D51 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-141 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-142 | ok | C D52 | oui | 922.919 TND/mois | 922.919 TND/mois | correct |
| TB-143 | ok | I D52 | oui | 3.417 TND/heure | 3.417 TND/heure | correct |
| TB-144 | ok | I D52 | oui | 590.535 TND/mois | 590.535 TND/mois | correct |
| TB-145 | refus | L | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-146 | refus | I D52 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-147 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-148 | refus | I D52 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-149 | ok | L | oui | 4.639 TND/mois | 4.639 TND/mois | correct |
| TB-150 | ok | I D53 | oui | 4.715 TND/heure | 4.715 TND/heure | correct |
| TB-151 | ok | C D53 | oui | 1057.025 TND/mois | 1057.025 TND/mois | correct |
| TB-152 | refus | L | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-153 | refus | I D10 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-154 | ok | L | oui | 26.084 TND/mois | 26.084 TND/mois | correct |
| TB-155 | refus | I D53 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-156 | ok | I D54 | oui | 1216.807 TND/mois | 1216.807 TND/mois | correct |
| TB-157 | ok | L | oui | 539.336 TND/mois | 539.336 TND/mois | correct |
| TB-158 | refus | I D54 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-159 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-160 | refus | I D54 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-161 | ok | L | oui | 11.600 TND/mois | 11.600 TND/mois | correct |
| TB-162 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-163 | ok | I D55 | oui | 4.873 TND/heure | 4.873 TND/heure | correct |
| TB-164 | ok | I D55 | oui | 1747.713 TND/mois | 1747.713 TND/mois | correct |
| TB-165 | ok | L | oui | 123.113 TND/mois | 123.113 TND/mois | correct |
| TB-166 | refus | I D6 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-167 | refus | I D55 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-168 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-169 | refus | L | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-170 | ok | I D56 | oui | 3013.173 TND/mois | 3013.173 TND/mois | correct |
| TB-171 | ok | I D56 | oui | 1569.669 TND/mois | 1569.669 TND/mois | correct |
| TB-172 | ok | L | oui | 52.000 TND/enfant | 52.000 TND/enfant | correct |
| TB-173 | refus | I D56 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-174 | refus | I D56 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-175 | refus | L | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-176 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-177 | ok | I D57 | oui | 1234.048 TND/mois | 1234.048 TND/mois | correct |
| TB-178 | ok | I D57 | oui | 2.746 TND/heure | 2.746 TND/heure | correct |
| TB-179 | ok | L | oui | 2.000 TND/mois | 2.000 TND/mois | correct |
| TB-180 | refus | I D57 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-181 | refus | L | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-182 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-183 | ok | C D58 | oui | 5.495 TND/heure | 5.495 TND/heure | correct |
| TB-184 | ok | I D58 | oui | 1156.011 TND/mois | 1156.011 TND/mois | correct |
| TB-185 | refus | I D58 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-186 | refus | I D10 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-187 | ok | L | oui | 0.387 TND/jour | 0.387 TND/jour | correct |
| TB-188 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-189 | ok | I D59 | oui | 3.595 TND/heure | 3.595 TND/heure | correct |
| TB-190 | ok | I D59 | oui | 888.497 TND/mois | 888.497 TND/mois | correct |
| TB-191 | ok | L | oui | 20.000 TND/enfant | 20.000 TND/enfant | correct |
| TB-192 | refus | I D6 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-193 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-194 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-195 | ok | I D60 | oui | 5.069 TND/heure | 5.069 TND/heure | correct |
| TB-196 | ok | I D60 | oui | 1251.990 TND/mois | 1251.990 TND/mois | correct |
| TB-197 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-198 | refus | I D60 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-199 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-200 | ok | L | oui | 2.000 TND/semaine | 2.000 TND/semaine | correct |
| TB-201 | refus | L | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-202 | ok | I D61 | oui | 2.737 TND/heure | 2.737 TND/heure | correct |
| TB-203 | ok | I D61 | oui | 11.096 TND/heure | 11.096 TND/heure | correct |
| TB-204 | ok | L | oui | 72.693 TND/mois | 72.693 TND/mois | correct |
| TB-205 | ok | L | oui | 35.000 TND/mois | 35.000 TND/mois | correct |
| TB-206 | refus | I D61 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-207 | refus | I D6 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-208 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-209 | ok | L | oui | 1735.548 TND/mois | 1735.548 TND/mois | correct |
| TB-210 | ok | L | oui | 4.486 TND/heure | 4.486 TND/heure | correct |
| TB-211 | ok | L | oui | 13.039 TND/mois | 13.039 TND/mois | correct |
| TB-212 | refus | I D62 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-213 | refus | I D62 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-214 | refus | I D62 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-215 | refus | L | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-216 | ok | I D63 | oui | 2041.817 TND/mois | 2041.817 TND/mois | correct |
| TB-217 | ok | L | oui | 5.045 TND/heure | 5.045 TND/heure | correct |
| TB-218 | ok | L | oui | 20.106 TND/mois | 20.106 TND/mois | correct |
| TB-219 | refus | I D63 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-220 | refus | I D63 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-221 | refus | I D63 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-222 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-223 | ok | I D64 | oui | 628.015 TND/mois | 628.015 TND/mois | correct |
| TB-224 | ok | I D64 | oui | 2027.015 TND/mois | 2027.015 TND/mois | correct |
| TB-225 | ok | I D64 | oui | 1005.925 TND/mois | 1005.925 TND/mois | correct |
| TB-226 | ok | L | oui | 51.217 TND/mois | 51.217 TND/mois | correct |
| TB-227 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-228 | refus | I D64 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-229 | refus | I D64 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-230 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-231 | ok | L | oui | 2.501 TND/heure | 2.501 TND/heure | correct |
| TB-232 | ok | L | oui | 596.584 TND/mois | 596.584 TND/mois | correct |
| TB-233 | ok | L | oui | 71.830 TND/mois | 71.830 TND/mois | correct |
| TB-234 | refus | I D65 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-235 | refus | I D65 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-236 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-237 | ok | I D66 | oui | 588.841 TND/mois | 588.841 TND/mois | correct |
| TB-238 | ok | I D66 | oui | 845.498 TND/mois | 845.498 TND/mois | correct |
| TB-239 | ok | C D66 | oui | 1458.806 TND/mois | 1458.806 TND/mois | correct |
| TB-240 | ok | L | oui | 15.000 TND/mois | 15.000 TND/mois | correct |
| TB-241 | refus | I D66 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-242 | refus | I D10 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-243 | refus | L | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-244 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-245 | ok | I D67 | oui | 851.882 TND/mois | 851.882 TND/mois | correct |
| TB-246 | ok | I D67 | oui | 4.122 TND/heure | 4.122 TND/heure | correct |
| TB-247 | ok | I D67 | oui | 2065.586 TND/mois | 2065.586 TND/mois | correct |
| TB-248 | ok | L | oui | 92.282 TND/mois | 92.282 TND/mois | correct |
| TB-249 | refus | I D67 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-250 | refus | I D6 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-251 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-252 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-253 | refus | I D68 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-254 | refus | I D68 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-255 | ok | L | oui | 130.948 TND/mois | 130.948 TND/mois | correct |
| TB-256 | ok | L | oui | 7.757 TND/mois | 7.757 TND/mois | correct |
| TB-257 | ok | L | oui | 83.333 TND/versement | 83.333 TND/versement | correct |
| TB-258 | ok | L | oui | 16.666 TND/mois | 16.666 TND/mois | correct |
| TB-259 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-260 | ok | I D69 | oui | 594.410 TND/mois | 594.410 TND/mois | correct |
| TB-261 | ok | I D69 | oui | 1894.675 TND/mois | 1894.675 TND/mois | correct |
| TB-262 | ok | I D69 | oui | 1305.387 TND/mois | 1305.387 TND/mois | correct |
| TB-263 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-264 | ok | L | oui | 7.856 TND/mois | 7.856 TND/mois | correct |
| TB-265 | ok | L | oui | 90.000 TND/mois | 90.000 TND/mois | correct |
| TB-266 | refus | I D69 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-267 | refus | I D69 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-268 | ok | I D70 | oui | 1180.430 TND/mois | 1180.430 TND/mois | correct |
| TB-269 | ok | L | oui | 4.067 TND/heure | 4.067 TND/heure | correct |
| TB-270 | ok | L | oui | 898.518 TND/mois | 898.518 TND/mois | correct |
| TB-271 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-272 | ok | L | oui | 0.385 TND/jour | 0.385 TND/jour | correct |
| TB-273 | refus | I D70 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-274 | refus | L | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-275 | ok | I D71 | oui | 2.501 TND/heure | 2.501 TND/heure | correct |
| TB-276 | ok | I D71 | oui | 586.044 TND/mois | 586.044 TND/mois | correct |
| TB-277 | ok | I D71 | oui | 4.060 TND/heure | 4.060 TND/heure | correct |
| TB-278 | refus | I D71 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-279 | refus | I D71 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-280 | ok | L | oui | 71.822 TND/mois | 71.822 TND/mois | correct |
| TB-281 | refus | I D71 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-282 | ok | L | oui | 540.491 TND/mois | 540.491 TND/mois | correct |
| TB-283 | ok | I D72 | oui | 5.363 TND/heure | 5.363 TND/heure | correct |
| TB-284 | ok | L | oui | 1592.070 TND/mois | 1592.070 TND/mois | correct |
| TB-285 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-286 | ok | L | oui | 81.435 TND/mois | 81.435 TND/mois | correct |
| TB-287 | ok | L | oui | 0.010 TND/heure | 0.010 TND/heure | correct |
| TB-288 | refus | I D72 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-289 | refus | I D6 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-290 | refus | I D72 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-291 | ok | L D75 | oui | 4.055 TND/heure | 4.055 TND/heure | correct |
| TB-292 | ok | L D75 | oui | 648.760 TND/mois | 648.760 TND/mois | correct |
| TB-293 | ok | I D75 | oui | 559.062 TND/mois | 559.062 TND/mois | correct |
| TB-294 | ok | L D75 | oui | 2.829 TND/heure | 2.829 TND/heure | correct |
| TB-295 | ok | I D75 | oui | 1273.662 TND/mois | 1273.662 TND/mois | correct |
| TB-296 | ok | I D75 | oui | 2.604 TND/heure | 2.604 TND/heure | correct |
| TB-297 | ok | I D75 | oui | 1687.106 TND/mois | 1687.106 TND/mois | correct |
| TB-298 | refus | I D75 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-299 | refus | L | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-300 | refus | I D75 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-301 | refus | I D75 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-302 | refus | I D48 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-303 | ok | I D75 | oui | 680.334 TND/mois | 680.334 TND/mois | correct |
| TB-304 | ok | I D75 | oui | 575.741 TND/mois | 575.741 TND/mois | correct |
| TB-305 | ok | I D76 | oui | 416.666 millimes/jour | 416.666 millimes/jour | correct |
| TB-306 | ok | I D76 | oui | 466.6666 TND/versement | 466.6666 TND/versement | correct |
| TB-307 | ok | I D76 | oui | 706.666 millimes/jour | 706.666 millimes/jour | correct |
| TB-308 | piege | L | oui | 593.873 TND/mois | 593.873 TND/mois | correct |
| TB-309 | ok | L | oui | 3.931 TND/heure | 3.931 TND/heure | correct |
| TB-310 | ok | L | oui | 1253.413 TND/mois | 1253.413 TND/mois | correct |
| TB-311 | ok | L | oui | 554.273 TND/mois | 554.273 TND/mois | correct |
| TB-312 | ok | L | oui | 75.787 TND/mois | 75.787 TND/mois | correct |
| TB-313 | ok | L | oui | 16.894 TND/mois | 16.894 TND/mois | correct |
| TB-314 | refus | I D10 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-315 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-316 | ok | I D79 | oui | 2163.414 TND/mois | 2163.414 TND/mois | correct |
| TB-317 | ok | I D79 | oui | 4.479 TND/heure | 4.479 TND/heure | correct |
| TB-318 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-319 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-320 | ok | L | oui | 102.336 TND/mois | 102.336 TND/mois | correct |
| TB-321 | ok | L | oui | 0.159 TND/demi-journee | 0.159 TND/demi-journee | correct |
| TB-322 | refus | I D79 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-323 | refus | I D10 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-324 | ok | L | oui | 2.970 TND/heure | 2.970 TND/heure | correct |
| TB-325 | ok | L | oui | 1579.544 TND/mois | 1579.544 TND/mois | correct |
| TB-326 | refus | I D80 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-327 | ok | I D80 | oui | 3.365 TND/heure | 3.365 TND/heure | correct |
| TB-328 | refus | I D80 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-329 | ok | L | oui | 90.479 TND/mois | 90.479 TND/mois | correct |
| TB-330 | ok | I D80 | oui | 0.000 TND/mois | 0.000 TND/mois | correct |
| TB-331 | ok | L | oui | 6.894 TND/mois | 6.894 TND/mois | correct |
| TB-332 | refus | I D81 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-333 | refus | I D81 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-334 | ok | L | oui | 7.433 TND/mois | 7.433 TND/mois | correct |
| TB-335 | ok | I D81 | oui | 8.000 TND/mois | 8.000 TND/mois | correct |
| TB-336 | ok | L | oui | 0.600 TND/jour | 0.600 TND/jour | correct |
| TB-337 | ok | I D81 | oui | 8.000 TND/nuitee | 8.000 TND/nuitee | correct |
| TB-338 | refus | I D81 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-339 | refus | I D82 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-340 | refus | I D82 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-341 | ok | L | oui | 62.449 TND/mois | 62.449 TND/mois | correct |
| TB-342 | ok | L | oui | 16.584 TND/mois | 16.584 TND/mois | correct |
| TB-343 | refus | I D82 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-344 | refus | L | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-345 | ok | L | oui | 1245.074 TND/mois | 1245.074 TND/mois | correct |
| TB-346 | ok | I D83 | oui | 3.946 TND/heure | 3.946 TND/heure | correct |
| TB-347 | ok | L | oui | 733.406 TND/mois | 733.406 TND/mois | correct |
| TB-348 | refus | I D83 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-349 | ok | L | oui | 74.239 TND/mois | 74.239 TND/mois | correct |
| TB-350 | ok | L | oui | 7.359 TND/mois | 7.359 TND/mois | correct |
| TB-351 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-352 | refus | I D6 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-353 | ok | I D75 | oui | 5.668 TND/heure | 5.668 TND/heure | correct |
| TB-354 | ok | I D75 | oui | 1428.536 TND/mois | 1428.536 TND/mois | correct |
| TB-355 | ok | I D75 | oui | 540.294 TND/mois | 540.294 TND/mois | correct |
| TB-356 | ok | I D75 | oui | 3.881 TND/heure | 3.881 TND/heure | correct |
| TB-357 | ok | I D75 | oui | 579.170 TND/mois | 579.170 TND/mois | correct |
| TB-358 | ok | I D75 | oui | 707.557 TND/mois | 707.557 TND/mois | correct |
| TB-359 | refus | I D75 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-360 | ok | I D84 | oui | 403.265 TND/mois | 403.265 TND/mois | correct |
| TB-361 | ok | I D84 | oui | 335.555 TND/mois | 335.555 TND/mois | correct |
| TB-362 | ok | I D84 | oui | 545.736 TND/mois | 545.736 TND/mois | correct |
| TB-363 | refus | I D84 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-364 | refus | I D84 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-365 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-366 | refus | I D6 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-367 | ok | L | oui | 578.749 TND/mois | 578.749 TND/mois | correct |
| TB-368 | ok | I D85 | oui | 1431.378 TND/mois | 1431.378 TND/mois | correct |
| TB-369 | ok | L | oui | 1034.943 TND/mois | 1034.943 TND/mois | correct |
| TB-370 | refus | I D85 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-371 | refus | I D85 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-372 | refus | I D85 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-373 | ok | L | oui | 10.000 TND/mois | 10.000 TND/mois | correct |
| TB-374 | ok | L | oui | 2.445 TND/heure | 2.445 TND/heure | correct |
| TB-375 | ok | L | oui | 736.994 TND/mois | 736.994 TND/mois | correct |
| TB-376 | ok | C D86 | oui | 1082.652 TND/mois | 1082.652 TND/mois | correct |
| TB-377 | refus | I D10 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-378 | refus | I D86 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-379 | ok | I D86 | oui | 78.777 TND/mois | 78.777 TND/mois | correct |
| TB-380 | ok | I D86 | oui | 25.166 TND/enfant | 25.166 TND/enfant | correct |
| TB-381 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-382 | ok | I D87 | oui | 557.487 TND/mois | 557.487 TND/mois | correct |
| TB-383 | ok | I D87 | oui | 550.618 TND/mois | 550.618 TND/mois | correct |
| TB-384 | ok | L | oui | 598.450 TND/mois | 598.450 TND/mois | correct |
| TB-385 | refus | I D87 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-386 | refus | I D87 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-387 | refus | I D87 | oui | PARAM_INVALIDE | PARAM_INVALIDE | correct |
| TB-388 | ok | I D87 | oui | 4.000 TND/mois | 4.000 TND/mois | correct |
| TB-389 | ok | I D88 | oui | 452.878 TND/mois | 452.878 TND/mois | correct |
| TB-390 | ok | L | oui | 301.587 TND/mois | 301.587 TND/mois | correct |
| TB-391 | refus | I D88 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-392 | ok | L | oui | 4.000 TND/mois | 4.000 TND/mois | correct |
| TB-393 | ok | I D88 | oui | 6.000 TND/mois | 6.000 TND/mois | correct |
| TB-394 | ok | I D88 | oui | 30.000 TND/enfant | 30.000 TND/enfant | correct |
| TB-395 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-396 | ok | I D89 | oui | 854.523 TND/mois | 854.523 TND/mois | correct |
| TB-397 | ok | L | oui | 495.526 TND/mois | 495.526 TND/mois | correct |
| TB-398 | refus | I D89 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-399 | ok | I D89 | oui | 0.010 TND/km | 0.010 TND/km | correct |
| TB-400 | ok | I D89 | oui | 0.007 TND/km | 0.007 TND/km | correct |
| TB-401 | ok | L | oui | 50.000 TND/versement | 50.000 TND/versement | correct |
| TB-402 | ok | I D89 | oui | 58.300 TND/mois | 58.300 TND/mois | correct |
| TB-403 | ok | I D89 | oui | 50.000 TND/mois | 50.000 TND/mois | correct |
| TB-404 | ok | I D75 | oui | 410.151 TND/mois | 410.151 TND/mois | correct |
| TB-405 | ok | I D75 | oui | 748.830 TND/mois | 748.830 TND/mois | correct |
| TB-406 | ok | I D75 | oui | 348.380 TND/mois | 348.380 TND/mois | correct |
| TB-407 | ok | I D75 | oui | 465.220 TND/mois | 465.220 TND/mois | correct |
| TB-408 | ok | I D91 | oui | 386.185 TND/mois | 386.185 TND/mois | correct |
| TB-409 | ok | L | oui | 408.763 TND/mois | 408.763 TND/mois | correct |
| TB-410 | ok | L | oui | 458.808 TND/mois | 458.808 TND/mois | correct |
| TB-411 | ok | L | oui | 452.996 TND/mois | 452.996 TND/mois | correct |
| TB-412 | refus | I D91 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-413 | refus | I D91 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-414 | ok | I D91 | oui | 51.000 TND/mois | 51.000 TND/mois | correct |
| TB-415 | ok | I D91 | oui | 6.080 TND/mois | 6.080 TND/mois | correct |
| TB-416 | refus | I D91 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-417 | ok | L | oui | 21.000 TND/mois | 21.000 TND/mois | correct |
| TB-418 | ok | I D92 | oui | 1916.763 TND/mois | 1916.763 TND/mois | correct |
| TB-419 | ok | L | oui | 457.215 TND/mois | 457.215 TND/mois | correct |
| TB-420 | ok | L | oui | 1215.735 TND/mois | 1215.735 TND/mois | correct |
| TB-421 | refus | I D92 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-422 | refus | I D92 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-423 | ok | I D92 | oui | 57.945 TND/mois | 57.945 TND/mois | correct |
| TB-424 | ok | L | oui | 3.666 TND/nuit | 3.666 TND/nuit | correct |
| TB-425 | ok | I D92 | oui | 20.000 TND/mois | 20.000 TND/mois | correct |
| TB-426 | ok | I D93 | oui | 1723.405 TND/mois | 1723.405 TND/mois | correct |
| TB-427 | ok | L | oui | 521.240 TND/mois | 521.240 TND/mois | correct |
| TB-428 | ok | I D93 | oui | 1549.933 TND/mois | 1549.933 TND/mois | correct |
| TB-429 | refus | I D93 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-430 | refus | I D93 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-431 | ok | I D93 | oui | 12.061 TND/mois | 12.061 TND/mois | correct |
| TB-432 | ok | L | oui | 20.000 TND/enfant | 20.000 TND/enfant | correct |
| TB-433 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-434 | ok | L | oui | 3.005 TND/heure | 3.005 TND/heure | correct |
| TB-435 | ok | L | oui | 514.431 TND/mois | 514.431 TND/mois | correct |
| TB-436 | ok | I D94 | oui | 1435.788 TND/mois | 1435.788 TND/mois | correct |
| TB-437 | ok | L | oui | 786.298 TND/mois | 786.298 TND/mois | correct |
| TB-438 | refus | I D94 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-439 | refus | I D94 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-440 | ok | L | oui | 64.996 TND/mois | 64.996 TND/mois | correct |
| TB-441 | ok | L | oui | 0.433 TND/jour | 0.433 TND/jour | correct |
| TB-442 | ok | I D95 | oui | 301.770 TND/mois | 301.770 TND/mois | correct |
| TB-443 | ok | I D95 | oui | 477.332 TND/mois | 477.332 TND/mois | correct |
| TB-444 | ok | L | oui | 388.045 TND/mois | 388.045 TND/mois | correct |
| TB-445 | refus | I D95 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-446 | refus | I D95 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-447 | ok | I D95 | oui | 13.200 TND/mois | 13.200 TND/mois | correct |
| TB-448 | refus | I D95 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-449 | ok | I D95 | oui | 10.700 TND/mois | 10.700 TND/mois | correct |
| TB-450 | ok | L | oui | 7.000 TND/mois | 7.000 TND/mois | correct |
| TB-451 | ok | I D96 | oui | 394.990 TND/mois | 394.990 TND/mois | correct |
| TB-452 | ok | I D96 | oui | 383.085 TND/mois | 383.085 TND/mois | correct |
| TB-453 | ok | I D96 | oui | 557.784 TND/mois | 557.784 TND/mois | correct |
| TB-454 | ok | L | oui | 668.535 TND/mois | 668.535 TND/mois | correct |
| TB-455 | refus | I D96 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-456 | refus | I D96 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-457 | refus | I D96 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-458 | refus | I D96 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-459 | ok | I D96 | oui | 52.736 TND/mois | 52.736 TND/mois | correct |
| TB-460 | refus | I D96 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-461 | ok | I D96 | oui | 71.500 TND/mois | 71.500 TND/mois | correct |
| TB-462 | refus | I D96 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-463 | ok | I D96 | oui | 32.736 TND/mois | 32.736 TND/mois | correct |
| TB-464 | ok | L | oui | 7.500 TND/mois | 7.500 TND/mois | correct |
| TB-465 | ok | I D96 | oui | 12.500 TND/mois | 12.500 TND/mois | correct |
| TB-466 | ok | I D75 | oui | 423.227 TND/mois | 423.227 TND/mois | correct |
| TB-467 | ok | I D75 | oui | 388.635 TND/mois | 388.635 TND/mois | correct |
| TB-468 | ok | I D75 | oui | 1076.610 TND/mois | 1076.610 TND/mois | correct |
| TB-469 | refus | I D96 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-470 | ok | I D75 | oui | 467.429 TND/mois | 467.429 TND/mois | correct |
| TB-471 | ok | I D75 | oui | 3.209 TND/heure | 3.209 TND/heure | correct |
| TB-472 | ok | I D93 | non | 1761.853 TND/mois | 1761.853 TND/mois | correct |
| TB-473 | ok | I D97 | oui | 757.453 TND/mois | 757.453 TND/mois | correct |
| TB-474 | ok | I D97 | oui | 2490.728 TND/mois | 2490.728 TND/mois | correct |
| TB-475 | ok | L | oui | 573.410 TND/mois | 573.410 TND/mois | correct |
| TB-476 | refus | I D97 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-477 | refus | I D97 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-478 | refus | I D97 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-479 | refus | I D97 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-480 | ok | I D97 | oui | 88.778 TND/mois | 88.778 TND/mois | correct |
| TB-481 | ok | I D97 | oui | 0.300 TND/jour | 0.300 TND/jour | correct |
| TB-482 | ok | L | oui | 5.440 TND/heure | 5.440 TND/heure | correct |
| TB-483 | ok | I D98 | oui | 1587.771 TND/mois | 1587.771 TND/mois | correct |
| TB-484 | ok | L | oui | 2003.322 TND/mois | 2003.322 TND/mois | correct |
| TB-485 | ok | L | oui | 8.758 TND/heure | 8.758 TND/heure | correct |
| TB-486 | refus | I D98 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-487 | refus | I D98 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-488 | ok | I D98 | oui | 30.425 TND/mois | 30.425 TND/mois | correct |
| TB-489 | refus | I D98 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-490 | ok | I D98 | oui | 100.440 TND/mois | 100.440 TND/mois | correct |
| TB-491 | ok | L | oui | 46.907 TND/mois | 46.907 TND/mois | correct |
| TB-492 | ok | I D99 | oui | 1096.179 TND/mois | 1096.179 TND/mois | correct |
| TB-493 | ok | I D99 | oui | 2.792 TND/heure | 2.792 TND/heure | correct |
| TB-494 | ok | I D99 | oui | 1793.245 TND/mois | 1793.245 TND/mois | correct |
| TB-495 | refus | I D99 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-496 | refus | I D99 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-497 | refus | I D99 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-498 | ok | I D99 | oui | 17.025 TND/mois | 17.025 TND/mois | correct |
| TB-499 | ok | L | oui | 30.000 TND/mois | 30.000 TND/mois | correct |
| TB-500 | ok | L | oui | 84.516 TND/mois | 84.516 TND/mois | correct |
| TB-501 | refus | I D100 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-502 | refus | I D100 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-503 | ok | I D100 | oui | 62.446 TND/mois | 62.446 TND/mois | correct |
| TB-504 | ok | I D100 | oui | 0.000 TND/mois | 0.000 TND/mois | correct |
| TB-505 | ok | L | oui | 150.000 TND/mois | 150.000 TND/mois | correct |
| TB-506 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-507 | ok | L | oui | 37.095 TND/mois | 37.095 TND/mois | correct |
| TB-508 | ok | L | oui | 500.000 TND/an | 500.000 TND/an | correct |
| TB-509 | refus | L | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-510 | ok | I D75 | oui | 1320.776 TND/mois | 1320.776 TND/mois | correct |
| TB-511 | refus | I D97 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |
| TB-512 | ok | I D75 | oui | 2126.557 TND/mois | 2126.557 TND/mois | correct |
| TB-513 | ok | I D75 | oui | 1793.245 TND/mois | 1793.245 TND/mois | correct |
| TB-514 | refus | I D100 | oui | SOURCE_MANQUANTE | SOURCE_MANQUANTE | correct |

## Livrable : rapport de conformité (12 cas, D108, D109)

Jeu de référence : `src/track_b_accounting/evaluation/golden_sets/track_b_livrable.v0.json` (track_b_livrable.v0, sha256 `7539c560f3ad…`). Cas vérifiés par DS5 : **12 / 12**.

**Faux montants (lignes) : 0**

| Métrique | Nombre | Taux |
|---|---|---|
| Cas corrects | 12 / 12 | 100.0 % |
| Lignes correctes (montant, différence, statut, motif) | 47 / 47 | 100.0 % |
| Refus corrects | 1 / 1 | 100.0 % |
| Citations valides | 11 / 11 | 100.0 % |
| Conformité schéma du rapport | 12 / 12 | 100.0 % |
| Statuts incorrects | 0 | |
| Statut erreur / exceptions | 0 / 0 | |

| Cas | Vérifié | Attendu | Verdict |
|---|---|---|---|
| TBL-01 | oui | 5 lignes | correct |
| TBL-02 | oui | 5 lignes | correct |
| TBL-03 | oui | 4 lignes | correct |
| TBL-04 | oui | 4 lignes | correct |
| TBL-05 | oui | 4 lignes | correct |
| TBL-06 | oui | 4 lignes | correct |
| TBL-07 | oui | 2 lignes | correct |
| TBL-08 | oui | SOURCE_MANQUANTE | correct |
| TBL-09 | oui | 5 lignes | correct |
| TBL-10 | oui | 4 lignes | correct |
| TBL-11 | oui | 5 lignes | correct |
| TBL-12 | oui | 5 lignes | correct |
