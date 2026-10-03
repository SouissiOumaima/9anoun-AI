# DECISIONS.md — Journal des décisions techniques

Format par entrée : **Décision** · **Alternatives envisagées** · **Raison**

---

## 2026 — DS5 (Track B, Oumaima Souissi)

### D1 — Abandon de la réparation section par section du JSON OCR

**Décision** : au lieu de corriger les 56 sections signalées par
`audit_ocr_quality.py` une par une dans les fichiers JSON existants, on
construit directement des fichiers **propres et structurés**
(`data/processed/smig_smag/`, `data/processed/salary_grids/`) en lisant
les PDF originaux, qui contiennent une vraie couche de texte exploitable
(ce ne sont pas des scans photo, mais des exports Word → PDF).

**Alternatives envisagées** :
- Corriger le texte OCR directement dans les fichiers `data/raw/txt/*.json`
  → rejeté : demande de re-parser du texte déjà cassé, risque de
  réintroduire des erreurs, et certaines sections contiennent des valeurs
  totalement incohérentes avec le PDF (pas juste un caractère mal lu).

**Raison** : les PDF sources permettent une extraction fiable à 100% via
`pymupdf`/`fitz` (texte natif, pas d'OCR nécessaire), donc repartir du
PDF est plus sûr et plus rapide que de déboguer l'OCR existant.

**Source des données** : uniquement `data.zip` fourni par Tradrly
(PDF + JSON). Aucune source externe consultée, conformément à la
consigne de l'équipe de travailler exclusivement sur les données
partagées.

---

### D2 — Correction confirmée : SMIG régime 40h/48h (décret n°769/2022)

**Fichier concerné** : `data/raw/txt/الأجر الأدنى المضمون لمختلف المهن في القطاعات غير الفلاحية.json`, section 2

**Source de vérification** : `data/raw/pdf/الأجر الأدنى المضمون لمختلف المهن في القطاعات غير الفلاحية.pdf`,
page 2 (décret gouvernemental n°769 du 19 octobre 2022), lue directement
en image (200 dpi, via `pymupdf`) pour éviter toute ambiguïté d'ordre de
lecture RTL dans le texte extrait.

**Problème identifié** : l'OCR n'a pas juste mal reconnu un caractère —
il a produit des valeurs entièrement incohérentes avec le document
source pour cette section.

| Catégorie | Régime | Valeur OCR (JSON, erronée) | Valeur réelle (PDF, confirmée) |
|---|---|---|---|
| Salariés payés au mois | 48h/semaine | incohérente | **459.264 DT** |
| Salariés payés au mois | 40h/semaine | incohérente | **390.692 DT** |
| Salariés payés à l'heure | 48h/semaine | incohérente | **2.208 DT** |
| Salariés payés à l'heure | 40h/semaine | incohérente | **2.254 DT** |

**Entrée en vigueur** : 1er octobre 2022 (texte daté du 19/10/2022,
Fasl 6 du décret précise l'effet au 1er du mois).

**Statut** : ✅ confirmé visuellement sur le PDF par Oumaima Souissi (DS5),
via inspection directe de l'image de la page — pas de source externe.

---

*Prochaine entrée : D3 — à ajouter après la construction du fichier
`smig_smag.json` complet (tous les textes SMIG/SMAG du corpus).*

---

### D3 — Construction de `smig_smag.json`

**Fichier créé** : `data/processed/smig_smag/smig_smag.json`

**Contenu** : 3 blocs reconstruits depuis le PDF source (pages 2 à 4) :
- `smig_non_agricole` (décret n°769/2022, effet 01/10/2022) — 4 valeurs
  (mensuel/horaire × régime 48h/40h)
- `smag_agricole` (décret n°768/2022, effet 01/10/2022) — SMAG journalier
  + primes technique/compétence
- `prime_transport` (décret n°35/2015, effet 01/05/2015, qui remplace le
  décret n°2906/2014) — montant mensuel fixe

**Statut** : ✅ toutes les valeurs confirmées visuellement sur les PDF
correspondants par Oumaima Souissi (DS5).

**Prochaine étape** : D4 sera ouverte après le traitement des grilles
salariales des conventions collectives sectorielles (étape 3 du plan DS5).

### D4 — Grille salariale METALLURGIE_BATIMENT (pages 16, 30-35)

**Fichier créé** : data/processed/salary_grids/metallurgie_batiment.json Source : الاتفاقية المشتركة القطاعية للبناء المعدني.pdf — p.30-35 (6 tableaux), p.16 (primes, art. 50/51 nouveaux)

Constat qui corrige D1 : les pages 30-35 sont des images sans couche texte (scan), pas du texte natif. pymupdf.get_text() y retourne 0 caractère → l'extraction « 100 % fiable » de D1 ne s'applique pas à ces pages. Seule la p.16 a une couche texte (utilisée comme contrôle croisé des primes).

**Méthode** : lecture visuelle des tableaux, saisie en code, contrôles automatiques (tests/test_grid_bm.py, 18 tests depuis l'ajout du contrôle d'incrément) : croissance par ancienneté, croissance par catégorie, ratio inter-années stable (~+6,6 %), cohérence des primes.

**Contenu**: 3 dates d'effet (01/12/2021, 01/01/2023, 01/01/2024) × 2 populations (admin/techniciens : 19 catégories, TND/mois ; exécution : 7 catégories, TND/heure) × 11 degrés d'ancienneté, régime 42 h. Primes : transport, présence, logement, panier (قفة), déplacement chantier, travail en hauteur.

**Vérification sur le PDF (2026-10-03)** : comparaison des valeurs du JSON
aux images des pages rastérisées à 200 dpi (images hors dépôt, non versionnées).
Degrés contrôlés : 1, 6 et 11 (dans le PDF, le degré 1 est la colonne la plus à droite).

| Page | table_id | Catégories fixes | Catégories tirées au hasard |
|---|---|---|---|
| 30 | BM_T_2021-12-01 | 1B, 18 | 5, 6 |
| 31 | BM_E_2021-12-01 | 1, 7 | 4, 6 |
| 32 | BM_T_2023-01-01 | 1B, 18 | 12, 13 |
| 33 | BM_E_2023-01-01 | 1, 7 | 2, 5 |
| 34 | BM_T_2024-01-01 | 1B, 18 | 9, 11 |
| 35 | BM_E_2024-01-01 | 1, 7 | 4, 5 |

- Catégories fixes : vérifiées exhaustivement sur le PDF par DS5 lors d'une
  session antérieure.
- Catégories tirées au hasard : 2 lignes par page, `random.Random(20261002)`,
  parmi les catégories hors fixes ; 36 cellules relues une à une sur les images
  (2026-10-03).
- Total : 72 cellules (24 lignes × 3 degrés). **Écarts dans l'échantillon : 0.**
- Contrôle complémentaire (toutes cellules) : d'une date d'effet à l'autre,
  l'augmentation est un montant **constant par ligne** (ex. cat. 4 :
  +38,703 DT de 2021 à 2023). Les lignes qui ne respectent pas cette règle ont
  été relues sur le PDF (zoom) :

  | table_id | Cellule | JSON (avant) | PDF (corrigé) |
  |---|---|---|---|
  | BM_T_2021-12-01 | cat. 4, degré 8 | 593.875 | **593.873** |
  | BM_T_2021-12-01 | cat. 15, degré 10 | 1007.131 | **1007.111** |

  Pour les tables exécution (TND/heure), on constate des écarts de ±0,001 entre lignes.
  Ils sont attribués à l'arrondi au millime, mais ces cellules n'ont pas été relues
  une à une.
  Ces 2 cellules étaient hors échantillon, et les 16 tests de `test_grid_bm.py`
  ne les détectaient pas (tolérance du ratio inter-années trop large).
- Primes p.16 : 3 dates d'effet (2021-12-01, 2023-01-01, 2024-01-01) présentes pour
  transport, présence, logement et complément logement ; montants identiques aux
  chiffres de la couche texte de la p.16 (lisibles malgré l'encodage PUA, cf. D5).
- Prime panier (قفة, art. 51 (جديد) أ) : montant unique 0,560 DT/jour (renvoi art. 89
  du Code du travail), sans date d'effet dans l'article → `effective_date: null`
  conservé ; ce n'est pas une donnée manquante.
- Fichier de tests renommé `Test_grid_bm.py` → `test_grid_bm.py`.

Non-régression : `test_increment_constant_par_table` (tests/test_grid_bm.py)
vérifie que, pour chaque catégorie, l'incrément entre deux dates d'effet est
identique sur les 11 degrés (tolérance : 0,0005 DT pour les tables T, soit exact
au millime ; 0,0015 DT pour les tables E, arrondi de ±0,001). Il échoue sur les
2 valeurs erronées ci-dessus.

**Statut** : ✅ vérifié sur échantillon + contrôle inter-années (2026-10-03),
2 cellules corrigées (page 30) ; contrôles automatiques :
`src/track_b_accounting/tests/test_grid_bm.py` (18 tests) ; validation finale DS5.

---

### D5 — Inventaire couche texte des PDF (data/raw/pdf/)

**Fichiers créés** : `data/processed/ocr_audit/pdf_text_layer.json` et `.md`,
générés par `src/track_b_accounting/tools/inventory_pdf_text_layer.py`
(tests : `tests/test_inventory.py`, PDF générés en mémoire). Les PDF sont
ouverts en lecture seule.

**Décision** : mesurer automatiquement, page par page, la présence d'une
couche texte (`page.get_text()` > 50 caractères = « texte », sinon « scan »),
son encodage et la densité de montants, avant de choisir le prochain
secteur à transcrire.

**Alternatives envisagées** :
- Repérer les grilles par mots-clés arabes (« جدول », « الأجور », « منحة »)
  → inopérant : voir constat ci-dessous (0 page trouvée hors 1 page isolée).
- S'appuyer sur `data/raw/txt/*.json` (OCR) → rejeté (D1 : chiffres corrompus).
- Inspecter chaque PDF à la main → plus lent, non reproductible.

**Raison** : prioriser les secteurs selon le coût réel de saisie, et
documenter une limite de l'extraction de texte qui corrige D1.

**Constat qui précise D1** : sur les 9 PDF, toutes les couches texte encodent
l'arabe en zone Unicode à usage privé (encodage « pua », police propriétaire) :
les mots arabes ne sont **ni lisibles ni cherchables** via `get_text()`.
Les **chiffres**, eux, sont extraits correctement (contrôle : les 4 montants
SMIG de D2 — 459.264, 390.692, 2.208, 2.254 — sont retrouvés à l'identique
p.2 du PDF SMIG). L'extraction « fiable à 100 % » de D1 ne vaut donc que pour
les chiffres des pages texte.

**Résultat résumé** :
- Accord métallurgie : p.30-35 « scan », p.16 « texte » — cohérent avec D4.
- Dans les 7 conventions sectorielles, les grilles salariales sont sur des
  pages **scannées** (annexes en fin de document) ; aucune grille en texte
  natif. Les pages texte riches en montants contiennent des primes et
  indemnités (chiffres exploitables).
- Contrôle visuel de la 1re page scannée de chaque convention (gardiennage
  p.21, BTP p.23, assurance p.20, enseignement privé p.25, associations
  handicap p.21, banques p.22) : ce sont bien des tableaux de salaires.
  Tableaux droits : gardiennage, BTP. Tableaux pivotés à 90° : assurance,
  enseignement privé, associations handicap, banques.
- `الاطارية.pdf` (convention-cadre) et le PDF SMIG : aucune page scannée.

**Classement par coût de saisie** (pages scannées hors couverture, puis
orientation) :

| Rang | Secteur | Pages grilles | Orientation |
|---|---|---|---|
| 1 | Gardiennage / transport de fonds | 21 (1 p.) | droite |
| 2 | Assurance | 20-21 (2 p.) | pivotée |
| 3 | Banques | 22-23 (2 p.) | pivotée |
| 4 | Bâtiment et travaux publics | 23-25 (3 p.) | droite (p.23) |
| 5 | Enseignement privé | 25-27 (3 p.) | pivotée |
| 6 | Métallurgie bâtiment | 30-35 (6 p.) | déjà transcrite (D4) |
| 7 | Associations handicap | 21-29 (9 p.) | pivotée |

Le nombre de tableaux par page, les dates d'effet et l'orientation des pages
suivantes restent à confirmer à l'ouverture de chaque secteur.

**Contrôle croisé avec D4** : les 15 montants de primes lus dans la couche
texte de la page 16 de l'accord métallurgie (3 dates d'effet, dont la série
2024 : 92.800, 100.533, 7.856, 26.293, 1.663) sont tous présents dans
`metallurgie_batiment.json`. Aucun écart (rectifié le 2026-10-02 : une
première lecture tronquée du JSON avait conclu à tort à une série manquante).

**Statut** : ✅ mesure automatique reproductible (`python
src/track_b_accounting/tools/inventory_pdf_text_layer.py`) ; observations
visuelles (orientation, contenu des scans) ⏳ à confirmer par DS5.

---

### D6 — Règles de calcul Track B (`src/track_b_accounting/calc/`)

**Décision** : les montants de paie ne sont produits que par des fonctions
pures et déterministes : `salaire_base`, `table_applicable`,
`degre_from_anciennete`, `prime` et `smig`. Chacune renvoie un `Result`
(montant `Decimal`, unité, détail, **≥ 1 `Citation`**) ou lève un `Refus`
bilingue FR/AR (`SOURCE_MANQUANTE`, `HORS_SCOPE`, `PARAM_INVALIDE`). Seul
`loaders.py` lit des fichiers, et uniquement les JSON vérifiés de
`data/processed/` (D3, D4). `data/raw/` est cité dans les `Citation`, mais
n'est jamais lu.

**Règles** :
- **Arrondi** : `Decimal` partout. Les JSON sont lus avec
  `parse_float=Decimal`, donc aucun float ne passe par un calcul. Les montants
  renvoyés sont arrondis au millime (`0.001`, `ROUND_HALF_UP`). Un `Result`
  dont le montant n'est pas un `Decimal`, ou qui n'a pas de citation, est
  refusé dès sa construction.
- **Choix de table par date** : on prend la table de la population dont
  `effective_date` est la plus récente ≤ date. Une date antérieure à toutes
  les tables donne un Refus `SOURCE_MANQUANTE`. Au-delà de la dernière table
  (2024-01-01), celle-ci reste appliquée : le corpus ne contient pas de grille
  plus récente. Les primes datées suivent la même règle. Le SMIG n'est
  disponible qu'à partir du 2022-10-01 (décret n°769/2022, seul barème
  vérifié). La date est toujours un paramètre : jamais l'horloge système.
- **Bornes de degré** : les intervalles sont lus dans les libellés de la
  liste `degres` (« 0-2 ans », …, « 18-20 », « 20+ »). Le PDF affiche « 2/0 »,
  « 4/2 », etc., sans préciser à quel degré appartiennent les bornes
  intérieures. Une ancienneté exactement égale à 2, 4, …, 18 ou 20 ans donne
  donc un Refus `PARAM_INVALIDE`, plutôt qu'un choix arbitraire. 0 an
  correspond au degré 1 ; au-delà de 20 ans, c'est le degré 11.
- **Population** : `admin_tech` (tables T, TND/mois) ou `execution`
  (tables E, TND/heure). Une table est rattachée à une population quand ses
  catégories sont exactement celles de `categories[population]`.
- **Pas de conversion inventée** : on ne fait aucune conversion
  horaire → mensuel, ni nombre d'heures par mois, prorata, net, CNSS ou IRPP.
  Un salaire demandé dans une autre unité que celle de la table
  (`unite_souhaitee`) donne un Refus `HORS_SCOPE`. Un régime SMIG absent du
  barème (ex. 42 h) donne un Refus `SOURCE_MANQUANTE`, sans interpolation.
- **Primes** : les paramètres exigés dépendent du contenu JSON de la prime.
  - `groupe` pour la prime de transport : `execution_et_maitrise` ou `cadres`.
  - `variante` pour le complément logement.
  - `transport_assure` (obligatoire) pour la prime de panier : 0,560 ou
    0,160 DT/jour.
  - `condition_remplie` (obligatoire) pour les primes soumises à condition.
    Si elle vaut `False`, on lève un Refus `HORS_SCOPE`, car la source ne
    prévoit aucun montant dans ce cas.
  - Tout paramètre non prévu donne un Refus `PARAM_INVALIDE`.
  - La prime de panier n'a pas de date d'effet dans sa source
    (`effective_date: null`, D4) : elle est servie à toute date.
- **Citations** : grilles et primes → PDF de l'accord, page `source_pdf_page`
  et article du JSON, réf. D4. SMIG → PDF SMIG, page
  `smig_non_agricole.source_pdf_page` lue dans le JSON (= 2, cf. D2), décret
  n°769, réf. D2. Si ce champ est absent ou invalide, on lève un Refus
  `SOURCE_MANQUANTE` : aucune page n'est déduite.

**Ajout de métadonnée dans `smig_smag.json` (2026-10-03)** : ce fichier,
vérifié manuellement en D2 et D3, reçoit un champ `source_pdf_page` (même nom
que dans `metallurgie_batiment.json`) dans chacune de ses trois sections :
`smig_non_agricole` → 2, `smag_agricole` → 3, `prime_transport` → 4. Ces pages
ont été relevées dans la couche texte du PDF SMIG, ouvert en lecture seule (les
chiffres y sont lisibles, cf. D5). Les montants vérifiés y apparaissent :
p.2 → 459.264, 390.692, 2.208, 2.254 (décret 769) ; p.3 → 17.664, 0.942, 1.772
(décret 768) ; p.4 → 36,112 (décrets 2906 et 35). Le résultat est cohérent avec
D2 (SMIG en p.2) et D3 (« pages 2 à 4 »). Il s'agit d'un **ajout de
métadonnée de traçabilité** : **aucun montant, aucune date et aucun autre champ
vérifié n'a été modifié**. Ce champ permet d'éviter une seconde source de vérité
(numéro de page codé en dur dans le module SMIG, aujourd'hui `calc/smig_calc.py`).

**Observation non traitée — montants 2019, page 5 du PDF SMIG** : la couche
texte de la p.5 contient des montants (47.424, 39.519, 61.984, 51.652) dans un
texte daté de 2019. Ils sont absents de `smig_smag.json` (vérifié en D2/D3).
Leur nature et leur pertinence n'ont pas été examinées. Ils ne sont ni ajoutés
au JSON ni utilisés par aucune fonction. À vérifier lors d'une prochaine session,
avant toute décision de les intégrer ou de les écarter définitivement.

**Alternatives envisagées** :
- Attribuer chaque borne au degré supérieur (pratique courante) : rejeté,
  car aucune source du corpus ne le dit.
- Convertir le taux horaire en mensuel (× 182 h, etc.) : rejeté, car la base
  horaire n'est écrite dans aucune source vérifiée.
- Calculer en float, puis arrondir : rejeté, à cause du risque d'écart d'un
  millime sur les montants.

**Raison** : appliquer la règle « Citation ou Silence ». Un montant sans
source vérifiée n'est jamais produit ; l'appelant reçoit un refus motivé.

**Tests** : `src/track_b_accounting/tests/test_calc_*.py`. Les valeurs
attendues sont relues dans le JSON par les tests, et des cellules vérifiées
en D4 et D2 sont codées en dur. Des tests dédiés vérifient les invariants :
aucun float dans les `Result`, au moins une `Citation` par résultat, modules
purs. Couverture de `calc/` : 100 %
(`python -m pytest --cov=src/track_b_accounting/calc src/track_b_accounting/tests`).

**Statut** : ✅ implémenté et testé (2026-10-03) ; en attente de revue DS5.
