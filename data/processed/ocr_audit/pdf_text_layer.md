# Inventaire couche texte des PDF — data/raw/pdf/

Seuil : une page est « texte » si `page.get_text()` contient plus de 50 caractères, sinon « scan ».
Encodage `pua` : l'arabe est encodé en zone Unicode à usage privé (police propriétaire) —
les mots arabes ne sont pas cherchables, mais les chiffres restent lisibles.

## Résumé par PDF

| PDF | Pages | Texte | Scan | Pages scan | Encodage texte | Pages mots-clés | Pages ≥ 3 montants (texte) |
|---|---|---|---|---|---|---|---|
| أعوان مؤسسات الحراسة والسلامة ونقل العملة.pdf | 21 | 20 | 1 | 21 | pua | — | — |
| الأجر الأدنى المضمون لمختلف المهن في القطاعات غير الفلاحية.pdf | 5 | 5 | 0 | — | pua | — | 2, 3, 5 |
| الاتفاقية المشتركة القطاعية  للبناء المعدني.pdf | 35 | 29 | 6 | 30, 31, 32, 33, 34, 35 | pua | — | 16, 17 |
| الاتفاقية المشتركة القطاعية  للبناء والأشغال العامة.pdf | 25 | 22 | 3 | 23, 24, 25 | pua | — | 15 |
| الاتفاقية المشتركة القطاعية للتأميـن.pdf | 21 | 18 | 3 | 1, 20, 21 | pua | 11 | — |
| الاتفاقية المشتركة القطاعية للتعليم الخا ص.pdf | 27 | 23 | 4 | 1, 25, 26, 27 | pua | — | 15, 16, 17, 18 |
| الاتفاقيّة المشتركة القطاعيّة لأعوان جمعيّات رعاية الأشخاص المعوّقيـن.pdf | 29 | 20 | 9 | 21, 22, 23, 24, 25, 26, 27, 28, 29 | pua | — | 14 |
| الاطارية.pdf | 13 | 13 | 0 | — | pua | — | — |
| البنوك.pdf | 23 | 21 | 2 | 22, 23 | pua | — | — |

## Classement par coût de saisie (automatique)

Critère : nombre de pages scannées hors couverture (page 1), croissant.
Hypothèse à confirmer visuellement : ces pages contiennent les grilles salariales.

| Rang | PDF | Pages scannées hors couverture | Nb |
|---|---|---|---|
| 1 | أعوان مؤسسات الحراسة والسلامة ونقل العملة.pdf | 21 | 1 |
| 2 | الاتفاقية المشتركة القطاعية للتأميـن.pdf | 20, 21 | 2 |
| 3 | البنوك.pdf | 22, 23 | 2 |
| 4 | الاتفاقية المشتركة القطاعية  للبناء والأشغال العامة.pdf | 23, 24, 25 | 3 |
| 5 | الاتفاقية المشتركة القطاعية للتعليم الخا ص.pdf | 25, 26, 27 | 3 |
| 6 | الاتفاقية المشتركة القطاعية  للبناء المعدني.pdf | 30, 31, 32, 33, 34, 35 | 6 |
| 7 | الاتفاقيّة المشتركة القطاعيّة لأعوان جمعيّات رعاية الأشخاص المعوّقيـن.pdf | 21, 22, 23, 24, 25, 26, 27, 28, 29 | 9 |

Sans page scannée hors couverture : الأجر الأدنى المضمون لمختلف المهن في القطاعات غير الفلاحية.pdf, الاطارية.pdf.
