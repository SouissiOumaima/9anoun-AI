# Évaluation Track B — 2026-11-11

Jeu de référence : `src/track_b_accounting/evaluation/golden_sets/track_b_golden.v0.json` (track_b_golden.v0, 201 cas, sha256 `d95b18bb6d85…`).
Cas vérifiés sur les PDF par DS5 : **191 / 201**.

**Faux montants : 0** (montant faux pour un ok attendu, ou montant renvoyé alors qu'un refus était attendu).

## Ensemble des cas (201 cas)

| Métrique | Nombre | Taux |
|---|---|---|
| Faux montants (ok attendu) | 0 / 114 | 0.0 % |
| Montant au lieu d'un refus | 0 / 87 | 0.0 % |
| Exactitude des montants | 114 / 114 | 100.0 % |
| Silence excessif | 0 / 114 | 0.0 % |
| Refus corrects (même code ; même message s'il est fixé) | 87 / 87 | 100.0 % |
| Messages de refus différents de l'attendu | 0 / 87 | 0.0 % |
| Citations valides | 114 / 114 | 100.0 % |
| Conformité schéma Track B | 201 / 201 | 100.0 % |
| Conformité schéma commun | 201 / 201 | 100.0 % |
| Statut erreur / exceptions | 0 / 0 | |

## Cas vérifiés par DS5 (191 cas)

| Métrique | Nombre | Taux |
|---|---|---|
| Faux montants (ok attendu) | 0 / 114 | 0.0 % |
| Montant au lieu d'un refus | 0 / 77 | 0.0 % |
| Exactitude des montants | 114 / 114 | 100.0 % |
| Silence excessif | 0 / 114 | 0.0 % |
| Refus corrects (même code ; même message s'il est fixé) | 77 / 77 | 100.0 % |
| Messages de refus différents de l'attendu | 0 / 77 | 0.0 % |
| Citations valides | 114 / 114 | 100.0 % |
| Conformité schéma Track B | 191 / 191 | 100.0 % |
| Conformité schéma commun | 191 / 191 | 100.0 % |
| Statut erreur / exceptions | 0 / 0 | |

## Par certitude

| Certitude | Cas | Exactitude montants | Refus corrects | Faux montants |
|---|---|---|---|---|
| L | 125 | 83 / 83 | 42 / 42 | 0 |
| C | 6 | 6 / 6 | 0 / 0 | 0 |
| I | 70 | 25 / 25 | 45 / 45 | 0 |

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
