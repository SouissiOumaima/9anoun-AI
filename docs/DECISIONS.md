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
  correspond au degré 1 ; entre 20 et 22 ans (bornes exclues), c'est le
  degré 11. À partir de 22 ans, l'article 13 (p.9) prévoit une progression
  au-delà du dernier degré, non implémentée : Refus `SOURCE_MANQUANTE` (voir
  D8, qui corrige la formulation initiale « au-delà de 20 ans, c'est le
  degré 11 »).
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
  et article du JSON. La référence de vérification est lue dans
  `_meta.decision_ref` du fichier secteur (`"D4"` pour la métallurgie,
  champ ajouté le 2026-10-04 comme métadonnée de traçabilité, sans changer
  aucune valeur vérifiée). Si elle est absente ou mal formée, on lève un
  Refus `SOURCE_MANQUANTE`. SMIG → PDF SMIG, page
  `smig_non_agricole.source_pdf_page` lue dans le JSON (= 2, cf. D2), décret
  n°769. La référence est lue dans `smig_non_agricole.decision_ref`
  (= `"D2"`). Ce champ a été ajouté le 2026-10-04 dans la section et non dans
  `_meta` : D2 documente le barème SMIG, mais pas le SMAG ni la prime de
  transport (D3). `_meta.decision_log` est conservé tel quel. Si la page ou la
  référence est absente ou invalide, on lève un Refus `SOURCE_MANQUANTE` :
  rien n'est déduit.

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

---

### D7 — Contrat JSON Track B v0 (`src/track_b_accounting/contract/`)

**Décision** : Track B expose une interface JSON unique,
`handle(request: dict) -> dict`. Elle est décrite par deux schémas JSON
Schema draft 2020-12 :
`data/mock_cards/schemas/track_b_request.v0.schema.json` et
`track_b_response.v0.schema.json`. Le contrat est marqué **« v0 — proposition
Track B, à valider avec l'équipe »**. Au 2026-10-04, `src/shared/` et
`data/mock_cards/` étaient vides : aucun contrat d'équipe n'existait à
respecter.

- **Requête** : `contract_version` (`track_b.v0`), `request_id`,
  `operation` (`salaire_base`, `prime`, `smig` ou `cotisation_cnss`), `params` et `lang`
  (`fr` ou `ar`). Les `params` de chaque opération sont typés par le schéma
  (noms et types). Les règles métier (bornes de degré, dates, catégories,
  conditions de prime) restent dans `calc/` (D6) et sont renvoyées comme refus.
- **Réponse** : `contract_version`, `request_id`, `status` (`ok`, `refus` ou
  `erreur`), `result` {`montant`, `unite`, `detail`} ou `null`,
  `citations[]`, `refus` {`code`, `message_fr`, `message_ar`} ou `null`,
  `computed_by`. En plus de la proposition initiale, un champ optionnel
  `erreur` {`type`, `message_fr`, `message_ar`} n'apparaît que si
  `status = "erreur"`. Il donne le type d'incident, mais jamais le message
  interne de l'exception.

**Choix** :
- **Montant en chaîne décimale** (`"593.873"`, motif `^-?[0-9]+\.[0-9]{3}$`) :
  un nombre JSON est lu comme un float par la plupart des clients, ce qui
  peut fausser le millime (D6). Les valeurs `Decimal` de `detail` sont aussi
  converties en chaînes. Le schéma interdit tout nombre non entier dans
  `detail`.
- **Codes de refus** : ce sont ceux de D6 (`SOURCE_MANQUANTE`, `HORS_SCOPE`,
  `PARAM_INVALIDE`), toujours avec un message FR et un message AR. Le
  handler applique les contrôles dans cet ordre, et distingue explicitement
  deux types de refus :
  1. **Refus de contrat** (le schéma est invalide : c'est un bug de
     l'appelant). Une requête qui ne valide pas le schéma de requête donne
     `PARAM_INVALIDE`, avec un message « Requête non conforme au contrat… »
     et `computed_by = "track_b_accounting.contract"`. Cela couvre aussi une
     opération inconnue du contrat (ex. `calcul_irpp`) et un champ manquant.
     Ce contrôle passe en premier, y compris pour `cotisation_cnss`.
  2. **Refus métier hors périmètre** (le schéma est valide, l'appelant n'a
     pas fait d'erreur). `cotisation_cnss` est une valeur valide de
     `operation`, mais Track B la refuse toujours avec `HORS_SCOPE`, car
     aucune source vérifiée ne couvre la CNSS. `computed_by` vaut
     `"track_b_accounting.contract"`, car `calc/` n'est pas appelé. La liste
     de ces opérations est `OPERATIONS_HORS_PERIMETRE` dans `handler.py`.
  3. **Refus métier de `calc/`** (le schéma est valide, mais les paramètres
     sont refusés par les règles D6 : date, degré, catégorie, secteur…).
     `computed_by` vaut `"track_b_accounting.calc.<op>"`.

  Le statut `erreur` est réservé aux exceptions inattendues : la réponse ne
  contient alors aucun montant.
- **Invariant de citation, imposé par le schéma** : `ok` ⇒ `result` non nul,
  `citations` avec au moins un élément (`minItems: 1`) et `refus` nul.
  `refus` et `erreur` ⇒ `result` nul et `citations` vide. Chaque citation a
  un `data_file` sous `data/processed/` et un `decision_ref` de la forme `Dn`.
- **Garde-fou** : le handler valide aussi sa propre réponse. Si elle n'est
  pas conforme, il la remplace par une réponse `erreur`. Il ne fait aucun
  calcul et ne lit que les schémas : les données passent par `calc/` et ses
  loaders.

**Alternatives envisagées** :
- Montant en nombre JSON : rejeté (risque de float, cf. D6).
- Un seul message, dans la langue de `lang` : rejeté. Les deux langues sont
  toujours renvoyées, et Track A choisit selon `lang`. Le coût est faible et
  évite un aller-retour.
- Attendre le contrat de l'orchestrateur ou de Track A : rejeté pour ne pas
  bloquer Track B. Cette version v0 est jetable si l'équipe adopte un autre
  format.

**Démo** : `python -m src.track_b_accounting.demo`, depuis la racine. Elle joue
10 échanges entre `MockOrchestrator`, le handler et `MockTrackA`
(`tests/mocks.py`) : 6 `ok` cités et 4 `refus` (CNSS, date antérieure au
2021-12-01, catégorie inconnue, secteur non couvert). `MockTrackA` recopie
le montant et les sources sans rien calculer.
CLI : `python -m src.track_b_accounting.contract.cli <fichier.json>`, ou
l'entrée standard. La sortie est en UTF-8, avec `ensure_ascii=False`.

**Statut** : ⏳ proposition v0, à valider avec l'équipe (orchestrateur, Track A).

---

### D8 — Ancienneté au-delà du dernier degré : refus explicite à partir de 22 ans (métallurgie, art. 13)

**Constat** : l'article 13 (جديد), §ب « التقدم », de la convention métallurgie
(`data/raw/pdf/الاتفاقية المشتركة القطاعية  للبناء المعدني.pdf`, **page 9**,
couche texte PUA, page rastérisée à 200 dpi et lue visuellement le 2026-10-05,
texte net) dit :

> وإذا بلغ العامل آخر درجة في السلم المرتب به، فإنه يواصل التمتع كل سنتين إلى
> آخر حياته المهنية بالفارق بين القيمة المالية لآخر درجة في السلم المرتب به
> والقيمة المالية للدرجة التي تسبقها.

Autrement dit, une fois au degré 11 (atteint à 20 ans), le travailleur continue
de percevoir, tous les deux ans et jusqu'à la fin de sa carrière, l'écart entre
le degré 11 et le degré 10. Le même article permet de raccourcir ou d'allonger
de six mois la durée de séjour dans un degré (note annuelle ≥ 17/20, ou sanction
du deuxième degré).

D6 disait « au-delà de 20 ans, c'est le degré 11 ». Le module renvoyait donc,
**sans alerte**, la valeur du degré 11 pour toute ancienneté supérieure à
20 ans (relevé au 2024-06-01) :

| Ancienneté | admin_tech, cat. 4 | execution, cat. 7 |
|---|---|---|
| 21 ans | 680.334 TND/mois ✅ | 4.620 TND/heure ✅ |
| 22, 25, 30, 45 ans | 680.334 ❌ (identique) | 4.620 ❌ (identique) |

Pour la catégorie 4 en 2024, l'écart degré 11 − degré 10 vaut
680.334 − 678.186 = 2.148 TND par tranche de deux ans. Un test
(`test_calc_salary.py`, ancienneté 25 ans attendue au degré 11) figeait ce
comportement.

**Décision (correctif minimal)** :
- **Données** : ajout d'un bloc `au_dela_dernier_degre` dans
  `metallurgie_batiment.json` : `anciennete_max_couverte_annees: 22`,
  `source_pdf_page: 9`, `source_article: "13 (جديد) ب"`, le texte arabe
  cité ci-dessus, une traduction et un `statut` explicite (« RÈGLE NON
  IMPLÉMENTÉE »). Il s'agit d'un **ajout de métadonnée** : **aucun montant,
  aucune date et aucun autre champ vérifié n'a été modifié**.
- **Code** : `degre_from_anciennete` (`calc/salary.py`) lève un Refus
  `SOURCE_MANQUANTE` pour toute ancienneté **≥ 22 ans**. Les messages FR et AR
  citent l'article 13 et la page 9, lus dans le JSON. `valider_grille`
  (`calc/loaders.py`) **exige ce bloc pour toute grille** : chaque futur
  secteur (BTP compris) devra déclarer ce que dit sa source au-delà du dernier
  degré, sans quoi la grille est refusée.
- **Bornes** : 21 et 21,99 ans → degré 11 (inchangé) ; 22, 23 et 30 ans →
  refus. Le test « 25 ans » passe à 21 ans (même cellule, même montant
  1359.212, même page 34).
- Les 10 requêtes de démo donnent des réponses identiques à l'octet près
  (la seule au-delà de 20 ans, demo-02, est à 21 ans).

**Alternatives envisagées** :
- `PARAM_INVALIDE` : rejeté, car le paramètre est valide. C'est la règle qui
  n'est pas transcrite dans les données vérifiées, ce qui correspond à l'usage
  de `SOURCE_MANQUANTE` (D6).
- Implémenter l'article 13 tout de suite (`montant = d11 + n × (d11 − d10)`,
  `n = ⌊(a − 20) / 2⌋`) : reporté, voir les points ouverts.
- Plafond codé en dur dans `salary.py` : rejeté, car il dépend de chaque
  convention (le BTP prévoit une autre règle, après 3 ans au degré 11). Il est
  lu dans les données, avec sa source.

**Points ouverts avant d'implémenter l'article 13 (travail futur)** :
1. **Cumul** : « يواصل التمتع كل سنتين بالفارق » se lit comme un écart
   supplémentaire tous les deux ans. C'est la lecture la plus probable, mais
   elle n'est pas écrite explicitement.
2. **Bornes** : à 22, 24, 26 ans exactement, il y a la même ambiguïté qu'aux
   bornes 2…20 (D6). Il faudra décider à quel moment l'écart s'ajoute.
3. **±6 mois** : la durée de séjour peut être réduite (note ≥ 17/20) ou
   allongée (sanction). Le module suppose une progression normale, mais
   au-delà du degré 11 l'effet se cumule sur toute la carrière.
4. **Nature du montant** : l'écart est peut-être un complément versé à part,
   et non le salaire de base lui-même. Cela changerait le `detail` et les
   citations (p.9 et pages 30-35).

**Statut** : ✅ correctif minimal appliqué ; implémentation de l'article 13
en attente des 4 points ci-dessus.
→ **Remplacé par D10** : l'article 13 est implémenté (écart cumulé, paliers
exacts refusés) ; les 4 points ci-dessus y sont tranchés comme hypothèses.

---

### D9 — Grille salariale BATIMENT_TRAVAUX_PUBLICS (pages 8, 15, 16, 23-25)

**Source** : `data/raw/pdf/الاتفاقية المشتركة القطاعية  للبناء والأشغال العامة.pdf`
(25 pages). Les tableaux des pages 23 à 25 sont des **scans sans couche texte**
(image d'environ 1652 × 1976 px, soit ~200 dpi natifs). Chaque page porte deux
tableaux :

| Tableau | Page | Population | Unité | Date d'effet | Cellules |
|---|---|---|---|---|---|
| 1 | 23 | العملة العرضيين (ouvriers occasionnels) | TND/heure | 2021-12-01 | 10 |
| 2 | 23 | الأعوان الاداريون والفنيون الخالصون بالشهر (admin_tech) | TND/mois | 2021-12-01 | 209 |
| 3 | 24 | ouvriers occasionnels | TND/heure | 2023-01-01 | 10 |
| 4 | 24 | admin_tech | TND/mois | 2023-01-01 | 209 |
| 5 | 25 | ouvriers occasionnels | TND/heure | 2024-01-01 | 10 |
| 6 | 25 | admin_tech | TND/mois | 2024-01-01 | 209 |

Total : **657 cellules** (3 × 209 + 3 × 10). Données :
`data/processed/salary_grids/batiment_travaux_publics.json` ; contrôles
automatiques : `src/track_b_accounting/tests/test_grid_btp.py`.

**Méthode de transcription (2026-10-07/08)** :
1. **Double lecture indépendante** de chaque tableau :
   - lecture A : rendu 200 dpi, bandes horizontales de 4 à 5 lignes (tables
     administratives) ou tableau entier avec les libellés (occasionnels) ;
   - lecture B : rendu 300 dpi, bandes verticales de 3 à 4 colonnes avec la
     colonne des catégories accolée (administratives) ou colonne des valeurs
     seule en deux demi-tableaux (occasionnels).

   Résultat : **0 divergence et 0 cellule douteuse** sur les 657 cellules.
2. **Relecture en pixels natifs agrandis ×4** des cellules signalées par les
   contrôles (tableau 2) : lecture confirmée.
3. **Règle entre années, cellule par cellule** (voir ci-dessous) : les 418
   cellules administratives de 2023 et 2024 et les 20 cellules occasionnels de
   2023 et 2024 sont conformes.
4. **Validation par DS5** : les 5 cellules anormales du tableau 2 ont été
   vérifiées directement sur le PDF.

**Règle de revalorisation constatée** (elle n'est pas écrite dans la
convention ; elle est déduite des tables et vérifiée sur toutes les cellules) :
- **admin_tech** : entre deux dates d'effet, chaque catégorie reçoit
  `degré 1 de l'année précédente × 6,75 %`, **ajouté tel quel à ses 11
  degrés**. Ce n'est donc pas un ratio uniforme : le test « nouveau = ancien ×
  1,0675 » échoue sur 190 cellules sur 209, seul le degré 1 passe. Écart
  maximal à la règle : 0,0009 TND (arrondis).
- **ouvriers occasionnels** : chaque taux horaire est multiplié par 1,0675
  puis arrondi au millime (|nouveau − ancien × 1,0675| ≤ 0,0005 × 2,0675 ≈
  0,00104 ; résidus constatés entre −0,0006 et +0,0008).

**Limites des contrôles** :
- Le **test d'incrément constant par catégorie** (utilisé pour la métallurgie,
  D4) **n'est pas discriminant sur cette grille** : 15 catégories sur 19 du
  tableau 2 sont signalées, à cause de la structure imprimée elle-même (sauts,
  changements de pas). Il n'est gardé que comme indicateur.
- Avec la tolérance de ±0,001, la règle entre années détecte une erreur de
  lecture de **0,002 TND ou plus** dans une table administrative ; une erreur
  de 0,001 peut passer (mesuré par mutation). La double lecture reste donc la
  vérification principale. Pour les occasionnels, une erreur de 0,001 est
  détectée, et les 30 valeurs sont en plus figées dans les tests.
- Les contrôles ne prouvent pas l'exactitude : ils repèrent des erreurs de
  lecture.

**5 anomalies d'incrément conservées telles qu'imprimées** (champ
`anomalies_increment` des 3 tables administratives). L'écart avec le degré
précédent se retrouve **à l'identique en valeur absolue** en 2023 et 2024, ce
qui découle de la règle ci-dessus :

| Cellule (tableau 2, p.23) | 2021 | 2023 | 2024 | Constat |
|---|---|---|---|---|
| cat. 1, degré 11 | 535,028 | 570,375 | 608,109 | écart 0,450 contre 0,432-0,433 dans la ligne |
| cat. 2, degré 11 | 562,267 | 599,828 | 639,924 | écart 1,617 contre 0,465-0,466 |
| cat. 3, degré 7 | 588,076 | 627,469 | 669,521 | écart 1,761, puis 1,860-1,861 |
| cat. 6, degré 3 | 678,440 | 723,903 | 772,435 | écarts 2,439 puis 2,500 contre 2,469-2,470 |
| cat. 14, degré 6 | 1220,466 | 1300,939 | 1386,844 | écarts 5,164 puis 5,144 contre 5,153-5,154 |

Elles pourraient être des coquilles de la convention. Elles ne sont **pas
corrigées** : le texte imprimé fait foi, et le module sert la valeur imprimée.

**Sauts de +2,500 TND (origine non expliquée)** : dans 10 catégories, une
seule transition entre deux degrés dépasse de +2,500 l'incrément habituel. Le
degré où tombe le saut **varie** :

| Saut vers le degré | Catégories (saut constaté en 2021) |
|---|---|
| 2 | 15 (8,191 ; +2,501) |
| 5 | 6 (4,969), 14 (7,653) |
| 6 | 13 (7,332) |
| 8 | 5 (4,862), 7 (5,721), 12 (7,010) |
| 9 | 11 (6,801) |
| 11 | 4 (4,608), 10 (6,587) |

Les sauts sont identiques en 2023 et 2024 (±0,001). Le montant constant et
leur reprise d'une année sur l'autre font penser à un élément voulu par la
convention (rattrapage ou reclassement ?), mais aucun texte du document ne
l'explique. Les valeurs sont conservées telles qu'imprimées.

**Note sous chaque tableau** : les salaires incluent l'indemnité
complémentaire provisoire (المنحة التكميلية المؤقتة, décret n° 437 du
7 avril 1981, relevée par le décret n° 501 du 16 mars 1982) ;
`_meta.remarque_pdf`.

**`regime_hebdomadaire_heures`** : laissé à `null`, car les pages 23 à 25 ne
l'indiquent pas.

**Décisions de structure (validées par DS5 avant transcription)** :
1. **Sous-catégories des ouvriers occasionnels** (p.23) : la catégorie 6
   comprend « عامل ذو كفاءة عالية I » et « II » (clés `6_I`, `6_II`), la
   catégorie 7 « رئيس فريق درجة أولى / ثانية / ثالثة » (clés `7_1`, `7_2`,
   `7_3`). La requête porte `categorie` (6 ou 7) et `sous_categorie`
   (« I », « II », « 1 », « 2 », « 3 »). Une sous-catégorie manquante,
   inconnue ou fournie pour une catégorie qui n'en a pas donne
   `PARAM_INVALIDE` ; la clé technique (`6_I`) n'est pas acceptée comme
   catégorie. Les libellés FR et AR du PDF (« درجة » traduit par « degré »)
   sont renvoyés dans `detail`.
2. **Degrés et plafond (admin_tech)** : en-tête « مدة البقاء بالدرجة » (p.23),
   tranches cumulées 0-2, 2-4, …, 10-12, 12-15, 15-18, 18-21, 21-24, 24+ :
   le degré 11 est atteint à 24 ans. L'article 13 (جديد) ب (p.8) prévoit,
   après 3 ans au degré 11, un salaire selon une table de correspondance.
   Cette règle n'est **pas implémentée** : toute ancienneté **≥ 27 ans** donne
   un refus `SOURCE_MANQUANTE` qui cite l'article 13 et la page 8, avec la
   même sémantique de borne que la métallurgie (D8). Les bornes communes (2,
   4, …, 12, 15, 18, 21, 24) donnent `PARAM_INVALIDE`, comme en D6. Les textes
   FR et AR du refus sont dans le JSON (`au_dela_dernier_degre.admin_tech`) ;
   la métallurgie a aussi déplacé les siens dans son JSON, sans les modifier.
3. **Prime de panier (qefa) non exposée** (art. 51 (جديد) أ, p.15) : le texte
   imprimé fixe 800 millimes et conditionne la prime à « سبع سنوات متتالية »
   (sept ans consécutifs), mais la phrase ajoute « y compris la pause d'une
   heure au plus », ce qui renvoie plutôt à des heures de travail (la même
   prime, côté métallurgie, renvoie à l'article 89 du Code du travail). Refus `SOURCE_MANQUANTE` qui expose les deux
   lectures ; pas de paramètre `condition_remplie`.
4. **Populations** : seuls `ouvriers_occasionnels` (TND/heure, sans degré ;
   `anciennete_annees` **refusé**, `PARAM_INVALIDE`) et `admin_tech`
   (TND/mois, 11 degrés) sont couverts. Les **ouvriers permanents** relèvent
   de l'annexe 4 (citée à l'article 56, p.16), **absente** du PDF fourni comme
   de `data.zip` (fichiers identiques, même empreinte SHA-256) : refus
   `SOURCE_MANQUANTE`.

**Changements de code et de contrat associés** (étape a, puis intégration) :
- les degrés et le bloc `au_dela_dernier_degre` sont déclarés **par
  population** (`degres.<population>`), y compris pour la métallurgie. Cela
  remplace la liste unique `degres` décrite en D6, sans changer aucun montant
  métallurgie ;
- plus de secteur par défaut : `secteur` absent ou vide → `PARAM_INVALIDE` ;
- schéma de requête : `anciennete_annees` n'est plus obligatoire au schéma
  (le calcul l'exige ou le refuse selon la population) ; nouveau champ
  optionnel `sous_categorie` ;
- un secteur enregistré dont `_meta.tables_transcrites` n'est pas `true` est
  refusé comme un secteur inconnu ;
- `_meta.decision_ref = "D9"` dans le fichier BTP ;
- démo : `demo-10-refus-secteur-non-couvert` visait `BATIMENT_TRAVAUX_PUBLICS`,
  désormais couvert. Elle utilise maintenant le code fictif
  `SECTEUR_FICTIF_NON_SUPPORTE`, pour garder un refus « secteur inconnu ».
  Trois requêtes BTP ont été ajoutées (demo-11 à demo-13 : 699.751 TND/mois,
  4.276 TND/heure, refus à 28 ans). Les réponses des demo-01 à demo-09 sont
  inchangées à l'octet près.

**Questions ouvertes** :
1. **Qefa** : « sept ans » imprimé contre contexte horaire (heures de travail
   consécutives ?). À trancher avec un texte de référence ou un juriste avant
   d'exposer la prime.
2. **Annexe 4** (ouvriers permanents) : absente du corpus. Il faut la retrouver
   pour couvrir cette population.
3. **Article 13 au-delà de 27 ans** : la table de correspondance de la p.8
   n'est ni transcrite ni implémentée. → **Traité en D10** (catégories 1 à 18
   pendant leur fenêtre ; catégorie 19 refusée).
4. **Origine des sauts de +2,500 et des 5 anomalies** : non expliquée par le
   document.
5. **Autres primes BTP** (transport, etc.) : non transcrites ; toute demande
   donne `SOURCE_MANQUANTE` (« aucune prime transcrite »).

**Statut** : ✅ 6 tables vérifiées et validées par DS5 ; questions 1 à 5
ouvertes.

---

### D10 — Article 13 : règle au-delà du dernier degré (métallurgie p.9, BTP p.8)

**Contexte** : D8 (métallurgie) et D9 (BTP) refusaient toute ancienneté au-delà
d'un plafond (22 et 27 ans), faute de règle implémentée. Les deux conventions
disent pourtant, dans leur article 13 (جديد) §ب, ce qui se passe après le dernier
degré. Pages relues à 250-300 dpi le 2026-10-09 ; décisions validées par DS5.

#### Métallurgie : écart cumulé tous les deux ans (p.9)

**Texte** (§ب « التقدم ») :

> يتمثل التقدم في التدرج الآلي حسب الأقدمية كل سنتين وذلك طبقا لجداول الأجور
> المرفقة بالاتفاقية. وإذا بلغ العامل آخر درجة في السلم المرتب به، فإنه يواصل
> التمتع كل سنتين إلى آخر حياته المهنية بالفارق بين القيمة المالية لآخر درجة في
> السلم المرتب به والقيمة المالية للدرجة التي تسبقها.
> و يمكن التنقيص في مدة البقاء بالدرجة بستة أشهر بالنسبة للعملة المتميزين
> والمتحصلين على عدد مهني سنوي لا يقل عن 17 من 20.
> كما يمكن الزيادة في مدة البقاء بالدرجة بستة أشهر بالنسبة للعملة الذين سلطت
> عليهم عقوبة من الدرجة الثانية وذلك بعد استشارة النواب النقابيين وإن لم يوجدوا
> فممثلي العملة بالمؤسسة.

**Règle implémentée** : `montant = d11 + n × (d11 − d10)`, avec
`n = ⌊(a − 20) / 2⌋` ; d10 et d11 sont lus dans la table en vigueur à la date du
calcul. Premier palier à 22 ans ; entre 20 et 22 ans, c'est le degré 11 simple.

**Bornes** : 22, 24, 26… ans pile → `PARAM_INVALIDE`, avec un message FR + AR
qui explique que la convention ne dit pas si le palier est acquis à cette date
exacte. C'est la même règle que pour 2, 4, …, 20 ans (D6) : sinon, 20 ans pile
serait refusé et 22 ans pile accepté.

**Exemples calculés à la main** (tables 2024, p.34 et 35, testés) :

| Ancienneté | n | admin_tech cat. 4 (d11 680,334 ; écart 2,148) | execution cat. 7 (d11 4,620 ; écart 0,016) |
|---|---|---|---|
| 22,5 ans | 1 | 682,482 TND/mois | 4,636 TND/heure |
| 24,5 ans | 2 | 684,630 | 4,652 |
| 30,5 ans | 5 | 691,074 | 4,700 |

**Hypothèses** (renvoyées dans `detail.hypotheses` et `detail.hypotheses_ar`) :
1. **Écart cumulé** : « يواصل التمتع كل سنتين » est lu comme un écart de plus tous
   les deux ans. Le texte ne dit pas explicitement « cumulé ».
2. **Progression normale** : les ±6 mois (note ≥ 17/20, sanction du 2e degré)
   ne sont pas pris en compte ; les requêtes ne contiennent ni note ni sanction.
   C'est déjà le cas pour les degrés 1 à 11 (D6).
3. **Salaire de base** : le montant obtenu est traité comme du salaire de base
   (le texte est dans « التقدم » ; il ne dit ni « أجر أساسي » ni « منحة »).
4. **Grille en vigueur** : d10 et d11 sont ceux de la table applicable à la date
   du calcul, et non ceux de l'année où chaque palier a été atteint.

#### BTP : table de correspondance (p.8)

**Texte** (§ب « التدرج ») :

> التدرج العادي يتمثل في الارتقاء بصفة متواصلة إلى درجة أعلى مباشرة حسب الأقدمية
> في الدرجة طبق الجدول الملحق بهذه الاتفاقية.
> يتقاضى كل عامل وعون مرتب في الدرجة 11 من شبكة الأجور المتعلقة بالأعوان الإداريين
> والفنيين الخالصين بالشهر وذلك مهما كان صنفه، وبعد قضاء 3 سنوات في هذه الدرجة أجرا
> أساسيا وفق الجدول التالي:

Note n° 10 : « نقح بالملحق التعديلي عدد 9 » (avenant n° 9, 2009).

**Transcription de la table** (19 lignes, « التأجير الحالي » 11/c → « مستوى التأجير
الجديد ») : double lecture (250 dpi tableau entier ; 400 dpi colonne seule),
0 divergence ; les 18 paires et la ligne 19 ont été vérifiées sur le PDF par DS5.
Format « degré/catégorie » : dans les tables 2021, 2023 et 2024, les 18 cases
cibles sont toutes supérieures au degré 11 de la catégorie d'origine.

**Règle implémentée** : après 27 ans (24 + 3), le salaire de base est celui de
la case cible, lue dans la grille en vigueur à la date du calcul.

**Fenêtres de validité** (choix de DS5) : la convention ne dit pas ce qui se
passe après la nouvelle case (la progression reprend-elle à partir de là ?).
Plutôt que de servir la même case indéfiniment, le module ne la sert que pendant
la durée de la tranche de son degré (en-tête p.23) ; ensuite, refus.

| Fenêtre | Catégories (case cible) | Ancienneté servie |
|---|---|---|
| 2 ans (degrés cibles 1 à 6) | 1 (2/2), 2 (2/3), 3 (5/4), 4 (5/5), 5 (5/6), 6 (1/7), 7 (6/8), 13 (2/14), 14 (4/15), 16 (6/17), 18 (3/19) | 27 < a < 29 |
| 3 ans (degrés cibles 7 à 10) | 8 (7/9), 11 (10/13), 15 (10/16), 17 (8/18) | 27 < a < 30 |
| 3 ans (degré cible 11 : l'article 13 s'appliquerait à nouveau, d'où un refus au-delà) | 9 (11/10), 10 (11/11), 12 (11/13) | 27 < a < 30 |

**Bornes** : 27 ans pile → `PARAM_INVALIDE` (« بعد قضاء 3 سنوات » ne dit pas si
27 ans pile en relève, comme en D6). Fin de fenêtre pile (29 ou 30 ans) et
au-delà → `SOURCE_MANQUANTE`, sur le même principe que les plafonds de D8 et D9
(refus dès que l'ancienneté atteint la limite). Messages FR + AR dans le JSON,
qui citent l'article 13 et la page 8.

**Catégorie 19 refusée** : la table donne « 950 دينارا » comme nouveau salaire
de base. Ce montant, probablement fixé par l'avenant n° 9 (2009), est inférieur
au degré 11 actuel de la catégorie 19 (1841,256 TND en 2021, 2084,729 en 2024) :
l'appliquer ferait baisser le salaire de plus de moitié. Refus `SOURCE_MANQUANTE`,
texte FR + AR dans le JSON.

**Hypothèses** (renvoyées dans `detail`) : lecture « degré/catégorie » ; grille
en vigueur à la date du calcul ; case servie pendant sa fenêtre seulement.

#### Mise en œuvre

- **Données** : `au_dela_dernier_degre.<population>` porte désormais une
  `regle` : `ecart_cumule_biennal` (métallurgie, les deux populations),
  `table_correspondance` (BTP `admin_tech`, avec `table_correspondance`,
  `fenetre_annees` par catégorie et `categories_refusees`), ou `refus` (simple
  plafond de D8, gardé pour un futur secteur). Chaque bloc porte sa page, son
  article, son texte arabe, sa `decision_ref` (« D10 »), ses hypothèses FR/AR et
  ses messages de refus. **Aucun montant de grille n'a été modifié.**
- **Validation** (`calc/loaders.py`) : le dernier degré doit être ouvert et
  atteint à l'âge déclaré ; chaque catégorie BTP a soit une case cible, soit un
  refus ; la case imprimée correspond au degré et à la catégorie ; chaque fenêtre
  est égale à la durée de la tranche du degré cible (dérivée des libellés de
  degré, 3 ans pour le degré 11).
- **Calcul** (`calc/salary.py`, `regle_au_dela_dernier_degre`) : le degré est
  toujours lu dans la grille ; au dernier degré, la règle de l'article 13
  s'applique. `detail` reçoit `regle_art13`, `n_paliers` ou `case_cible`
  (`degre_cible`, `categorie_cible`, `fenetre_debut_annees`,
  `fenetre_fin_annees`), `ecart`, `montant_dernier_degre`, `hypotheses` et
  `hypotheses_ar`. La réponse porte **deux citations** : la grille (page de la
  table) et l'article 13 (page 9 ou 8, article « 13 (جديد) ب », D10).
- **Contrat** : le schéma de réponse accepte désormais, dans `detail`, des
  listes de chaînes non vides (`hypotheses`). DS1 et DS4 doivent afficher ces
  hypothèses avec le montant (§3.2 et §7 du contrat).
- **Démo** : demo-13 (BTP, catégorie 19, 28 ans) reste un refus, avec le texte
  de la catégorie 19. Ajout de demo-14 (métallurgie, admin_tech cat. 4, 25 ans,
  2024 : 684,630 TND/mois, deux citations). Les réponses de demo-01 à demo-12
  sont inchangées.

#### Risques : ce qui peut encore produire un montant faux avec une citation

1. **Métallurgie, cumul** : si l'écart n'est pas cumulé, l'erreur vaut
   (n − 1) × écart, soit 8,592 TND/mois de trop à 30 ans pour la catégorie 4
   (1,3 %).
2. **Métallurgie, ±6 mois** : un salarié bien noté ou sanctionné peut avoir un
   palier d'avance ou de retard (même risque que pour les degrés 1 à 11).
3. **Métallurgie, nature du montant** : si l'écart est une prime distincte, le
   total est juste mais présenté comme salaire de base, ce qui fausserait les
   calculs futurs fondés sur le salaire de base.
4. **Les deux secteurs, grille de quelle année** : si la convention vise les
   valeurs de l'année où le palier ou la case ont été atteints, le montant est
   surestimé.
5. **BTP, pendant la fenêtre** : si la progression reprenait plus tôt à partir
   de la nouvelle case, le montant serait sous-estimé ; au-delà de la fenêtre,
   le module refuse.

Ces points sont visibles dans `detail.hypotheses` : ils ne sont pas silencieux,
mais ce sont des interprétations.

**Statut** : ✅ implémenté (métallurgie ; BTP catégories 1 à 18 pendant leur
fenêtre) ; catégorie 19 du BTP et BTP au-delà des fenêtres refusés.

---

## 2026 — DS2 (Legal Retrieval, Abd Mouhib Souri)

Les décisions DS2 suivent la numérotation continue du journal (à la suite de D10),
comme l'impose le motif `decision_ref` (`^D[0-9]+$`) du schéma commun
`src/shared/schemas/common.v0.schema.json`.

### D11 — Ingestion hybride : texte de l'OCR, chiffres vérifiés sur le PDF

**Décision** : le texte arabe des articles vient de `data/raw/txt/*.json` (OCR fourni
par Tradrly). Chaque nombre d'un article est recherché dans la couche texte du PDF
correspondant (`data/raw/pdf`). Les nombres non retrouvés sont listés dans le champ
`numbers_unverified` de l'article : ils ne doivent jamais être cités sans vérification.

**Alternatives envisagées** :
- Texte depuis la couche texte des PDF → rejeté : l'arabe y est encodé en zone
  « Private Use » (constat D5 de DS5, quantifié en D16).
- Texte OCR seul, sans contrôle des chiffres → rejeté : les chiffres de l'OCR sont
  parfois incohérents (D1, D2 de DS5).

**Raison** : chaque source est utilisée pour ce qu'elle a de fiable. Mesure du
2026-10-10 sur les 9 fichiers (`tools/diagnose_pua.py`) : OCR = 95,8 à 99,8 % de
lettres arabes et 20 à 132 « فصل » par fichier ; couche texte PDF = 0 à 1 « فصل ».

**Limite** : la couche texte PDF n'expose que 110 à 315 nombres distincts par fichier
(les grilles sont des pages scannées, D4/D5). `numbers_unverified` signifie donc
« non confirmé », pas « faux ». Les montants de paie restent ceux vérifiés par DS5
(`data/processed/smig_smag/`, `data/processed/salary_grids/`).

---

### D12 — Un chunk = un article

**Décision** : l'unité de recherche est un article (« الفصل N ») ; un chunk ne
chevauche jamais deux articles.

**Alternatives envisagées** :
- Chunks de taille fixe (ex. 512 tokens) → rejeté : un article coupé en deux n'est
  plus citable tel quel.

**Raison** : règle « Citation ou Silence ».

---

### D13 — Texte original pour les citations, texte normalisé pour la recherche

**Décision** : chaque article stocke `text` (original, après NFKC) et
`text_normalized` (sans diacritiques ni tatweel, alef unifié, chiffres ASCII).

**Alternatives envisagées** :
- Normaliser le texte directement → rejeté : la vérification des citations échouerait.

**Raison** : la normalisation forte ne sert qu'à la recherche par mots-clés.

---

### D14 — Détection du texte arabe inversé

**Décision** : le rapport d'ingestion calcule `reversed_text_ratio` (part de « لصف »
parmi les « فصل »). Un fichier signalé n'est pas corrigé automatiquement.

**Alternatives envisagées** :
- Inverser automatiquement chaque ligne → rejeté pour l'instant : inverserait aussi
  les nombres (14 → 41).

**Raison** : cas observé dans l'OCR de la convention métallurgie bâtiment
(28 « لصف » pour 122 « فصل », ratio 0,19).

---

### D15 — Identifiants d'articles versionnés

**Décision** : `article_id = <SOURCE>-ART-<N>[BIS]-v<version>`. Un article « مكرر »
(bis) est un article distinct (`ART-7BIS`), pas un doublon. Un numéro réellement
répété reçoit `-DUP<k>` en attendant la correction du chargeur (Sprint 2).

**Raison** : la validation doit pouvoir retrouver la version exacte du texte cité.

---

### D16 — Complément à D5 : la couche texte PDF n'est pas réparable pour l'arabe

**Constat** (`tools/diagnose_pua.py`, 2026-10-10) : confirme et quantifie D5. Dans les
9 PDF, l'arabe est encodé en `U+F2xx` (8 988 à 75 077 caractères par fichier).
Trois décodages ont été testés (cp1256, ISO-8859-6, Mac Arabic, sur la plage
`U+F0xx` des polices « symbole ») : aucun ne restaure de texte (0 « فصل »).
Les codes `U+F2xx` sont des numéros de glyphes propres à chaque police : aucune
table de conversion standard n'existe.

**Conséquence** : pour le texte arabe, la seule source exploitable du corpus est
l'OCR `data/raw/txt/*.json` (D11). DS3 rencontrera probablement le même
encodage sur les PDF des utilisateurs : la couche texte ne suffira pas, prévoir l'OCR.

---

### D17 — Toujours renvoyer toutes les versions d'un article

**Décision** : pour chaque article pertinent, la recherche renvoie toutes ses versions
connues (en vigueur, modifiées, abrogées). Une seule version au plus est marquée
`applicable_at_reference_date`. L'appelant (DS4, DS5) annonce l'ancienne **et** la
nouvelle règle. Si l'ancien texte n'est pas dans le corpus (texte consolidé, mention
« (جديد) »), `previous_version_available = false` et l'appelant le dit explicitement.
`top_k` compte des articles, pas des versions.

**Alternatives envisagées** :
- Ne renvoyer que la version en vigueur → rejeté : un avocat ou un comptable doit voir
  l'historique (litige sur une période passée, rappel de salaire, contestation).
- Supprimer les « doublons » → rejeté : une nouvelle version n'est pas un doublon
  (proposé par Abd Mouhib Souri après vérification manuelle des PDF).

**Raison** : transparence pour le professionnel, précision temporelle (≥ 90 %),
règle « Citation ou Silence ».

**Contrat** : champs `version_group`, `version`, `applicable_at_reference_date`,
`modified`, `amended_by`, `previous_version_available` dans
`legal_retrieval_search_response.v0.schema.json` (voir `docs/CONTRACT_LEGAL_RETRIEVAL.md`).

---

### D18 — Vérification manuelle des articles manquants (37/37 expliqués)

**Décision** : chaque numéro d'article absent du découpage automatique est vérifié
visuellement dans le PDF avant toute correction du code. Le détail est dans
`docs/ds2/VERIFICATION_MANUELLE_CORPUS_2026-10-10.md`.

**Résultat** (7 conventions, 2026-10-10) :

| Cause | Articles |
|---|---|
| Abrogés par un avenant (`الفصول … ألغيت بمقتضى الملحق التعديلي عدد N`) | 22 |
| En-tête mal lu par l'OCR ou collé en milieu de ligne | 9 |
| En-tête sans espace (`الفصل56`) | 4 |
| Absents du PDF source (cadre art. 40, associations art. 20) | 2 |

**Conséquences** : un article abrogé est enregistré avec `status: abroge` et l'avenant
qui l'abroge (jamais « introuvable ») ; chaque convention a sa propre numérotation
d'avenants (`CCS-BTP-AVENANT-5` ≠ `CCS-CONSTRUCTION-METALLIQUE-AVENANT-5`) ;
les dates des avenants sont nécessaires au filtre temporel (à obtenir auprès de Tradrly).

**Statut** : ✅ vérification visuelle par Abd Mouhib Souri (DS2) ; règles de découpage
correspondantes à coder au Sprint 2.

---

### D19 — Contrat DS2 aligné sur l'enveloppe commune `common.v0`

**Décision** : la réponse `legal_retrieval.v0` suit `src/shared/schemas/common.v0.schema.json`
(`$defs/response_envelope`) : `status` `ok` / `refus` / `erreur`, `citations[]` (une par
article, objet `$defs/citation`), `refus {code, message_fr, message_ar}`, `erreur`,
`computed_by`. DS2 y ajoute `mode` et `results`. Correspondances avec la proposition
initiale DS2 : `success` → `ok` ; `no_decisive_source` → `refus` / `SOURCE_MANQUANTE` ;
requête invalide → `refus` / `PARAM_INVALIDE` (comme Track B) ; `language` → `lang`.
Dates de la requête : motif `$defs/date` **et** `format: date` (rejette aussi 2024-13-45).

**Alternatives envisagées** :
- Garder un format propre à DS2 → rejeté : l'orchestrateur (DS1) devrait gérer un format
  de statut et de citation par rôle.
- Référencer le schéma commun par `$ref` → reporté : aucun rôle ne le fait encore
  (question ouverte n° 3 du README des schémas) ; les définitions sont recopiées à
  l'identique, et un test valide chaque réponse DS2 contre le vrai fichier commun.

**Raison** : un seul format de statut, de citation et de refus pour toute l'équipe ;
la règle « Citation ou Silence » devient vérifiable de la même façon partout.

**Statut** : ⏳ v0, proposition à valider ; conformité prouvée par
`test_every_response_conforms_to_the_team_common_envelope` (ok, refus SOURCE_MANQUANTE,
refus PARAM_INVALIDE) et par appels HTTP réels.

---

### D20 — Lecture des sections Tradrly (1 section = 1 article) et historique des avenants

**Décision** : à partir du Sprint 2, l'ingestion des fichiers `data/raw/txt/*.json` lit les
`sections` déjà découpées par Tradrly (`corpus/ingest_sections.py`) au lieu de redécouper
le texte :
- texte d'un article = `content` **seulement** (`paragraphs` répète le même texte : c'était
  la cause du comptage surestimé de 492 au lieu d'environ 451) ;
- la section `legal_history_reconstructed_from_page_images` donne les dates de la
  convention et de chaque avenant (signature, approbation ministérielle) → `avenants.json`,
  identifiants préfixés par la convention (`CCS-BTP-AVENANT-5`, règle R7) ;
- règles de D18 appliquées **à l'intérieur** des textes : en-tête d'un article manquant
  caché dans une autre section → article découpé (R1/R4, ex. Cadre art. 5) ; listes
  d'abrogation (pluriel, duel, « مكرر », « : » optionnel) → entrées `abroge` reliées à
  leur avenant (R2/R3), ligne retirée de l'article qui la contenait ; renvois jamais
  coupés (R5) ; « (جديد) » → `modified`, `previous_version_available: false` (R6, D17) ;
- numérotation qui repart à 1 → nouvelle partie (`-P2-` dans l'identifiant), pas un doublon ;
- trous vérifiés à la main → `corpus/manual_checks.json` (R8), exclus des alertes.

**Alternatives envisagées** :
- Garder le découpage par regex du Sprint 1 → rejeté : il lisait le texte deux fois et
  ignorait les métadonnées fournies par Tradrly.
- Remplir `effective_from` / `effective_to` avec les dates d'avenant → reporté : la date
  d'effet (signature ou approbation ministérielle ?) est une question juridique ouverte,
  posée à Tradrly. Les deux dates sont conservées dans `avenants.json`.

**Ajouts après le premier passage réel (2026-10-10)** :
- une nouvelle partie ne commence que si la numérotation **repart à 1** ; un numéro répété
  ou dans le désordre reste dans sa partie (identifiant `-DUP2`, jamais supprimé) et est
  listé dans le rapport (`numbering_out_of_order`, outil `tools/inspect_sections.py`) ;
- tiret cadratin « — » accepté dans les listes d'abrogation (Gardiennage, Construction) ;
- « الغيابات » (absences), « الغير », « الغيار » ne sont pas des abrogations ;
- **R9** : « 50, 5, 52 » → le 5 est l'article 51 dont l'OCR a perdu le dernier chiffre ;
  corrigé seulement si les deux voisins le prouvent, numéro d'origine gardé
  (`numbers_corrected_r9`) ;
- `manual_checks.json` (R8) accepte le verdict `abroge` : complète une abrogation que
  l'OCR a cassée (BTP « 38 -39- ()I4 41 », Construction « عدد؟ ») avec le texte lu dans le
  PDF ; verdict `present_pdf_absent_digest` pour Cadre 5 et Assurance 40.

**Ajouts après l'inspection des sections (2026-10-10, `tools/inspect_sections.py`)** :
- **R10** : Tradrly a parfois coupé une section sur un **renvoi** et non sur un en-tête
  (« وينص الفصل 46 من هذه الاتفاقية », « الفصل 36 من هذه الاتفاقية. », « بالفصل 5 من الأمر
  المؤرخ في 8 جانفي 1948 ») ; ces sections sont recollées à l'article précédent (rien n'est
  perdu, positions listées dans `continuations_r10`) ;
- R9 s'exécute **après** R10 : au premier passage, R9 avait « corrigé » en 51 le renvoi
  BTP « بالفصل 5 من الأمر » — fausse correction détectée par l'inspection ;
- suffixes lus dans l'en-tête : « مثلث / ثالثا » → `TER`, « رابعا » → `QUATER`,
  sous-articles « الفصل 46 - 3: » → `46-3` (Gardiennage 46-3/46-4, Enseignement 54 ثالثا
  et 54-5, Cadre 51 ثالثا) : ce ne sont pas des doublons ;
- le texte placé **après le dernier article** (« تاريخ التطبيق ») devient une **annexe**
  (`<SOURCE>-ANNEXE-<k>`, statut `inconnu`, renvoi à l'article cité) au lieu d'être collé
  au dernier article : liste des sanctions (Construction, renvoi au fasl 36), conditions de
  recrutement (Enseignement, renvoi au fasl 15). Résultat après inspection : 0 doublon,
  0 désordre sur les 9 fichiers ;
- en-tête interne écrit « إلفصل » par l'OCR (alef hamza) accepté : BTP art. 51
  « إلفصل 51 (جديد): منح القفة » est découpé de l'article 50 (R4).

**Limites connues** : pas de page par article dans le digest (`page_start` vide) ; l'avenant
qui a modifié un article « (جديد) » n'est pas indiqué (`amended_by` vide pour ces articles).

**Statut** : ⏳ codé et testé sur des formes réelles (parseur validé sur l'historique réel
BTP : convention 16/01/1975 – 12/03/1975 et 16 avenants, 0 ligne non lue) ; exécution sur
les 9 fichiers à faire en local par DS2.

---

### D21 — Vocabulaire des champs de la requête DS2, tiré du corpus

**Décision** : les valeurs que DS1 transmet dans `sector` et `worker_category` sont des
**codes stables** définis dans `data/mock_cards/legal_retrieval_vocabulary.v0.json`
(libellés FR/AR, alias pour l'extraction, schéma JSON, accès Python
`src/legal_retrieval/contract/vocabulary.py`) :
- `sector` : les 7 secteurs du registre DS2, exactement (un test l'impose) ; la convention
  cadre et le SMIG s'appliquent à tous les secteurs ; ambiguïté « البناء » signalée ;
- `worker_category` : 9 catégories **comptées dans le corpus** (outil
  `tools/diagnose_vocabulary.py`, 2026-10-11 : « أعوان التنفيذ » 18 articles,
  « أعوان التسيير » 16, « الإطارات » 12, catégories propres aux banques et assurances,
  à l'enseignement et aux associations) ;
- statut d'emploi (قار / وقتي / عرضي) : **proposé pour v0.1**, pas ajouté au contrat v0 ;
- « المتعاقدين » exclu : désigne surtout les parties signataires de la convention.

**Alternatives envisagées** :
- Rendre `sector` et `worker_category` obligatoirement égaux à ces codes (`enum` dans le
  schéma de requête) → reporté à v0.1, après accord DS1 : changer la validation casserait
  les appels existants.
- Écrire une liste « classique » (ouvrier, employé, cadre) → rejeté : ces mots ne sont pas
  les catégories de classement des conventions tunisiennes ; la recherche filtrerait mal.

**Limites** : les équivalences entre catégories des banques et assurances (service,
réalisation, encadrement) et catégories générales (exécution, maîtrise) ne sont pas
déduites ; elles sont à valider par un juriste.

**Statut** : ⏳ v0 proposée à DS1 (Achref) ; cohérence avec le registre et le contrat
prouvée par `test_legal_vocabulary.py`.

**D21 v0.1 (2026-10-15)** — demandé par DS5 pour la table des secteurs (D30) :
- « bâtiment » n'est plus un alias de `btp` : il rejoint l'ambiguïté « البناء / construction »
  (le code DS5 `METALLURGIE_BATIMENT` le contient aussi) → DS1 demande une précision ;
- « métallurgie » n'est pas un alias de `construction_metallique` : la convention couvre la
  seule construction métallique ; sans précision, `sector = null` ;
- `associations` est le code stable ; le vocabulaire DS2 reste la source de vérité, la table
  `src/shared/sectors/` est vérifiée contre lui.

---

### D22 — Opération `get_article` : un article par sa référence, sur le corpus réel

**Décision** : DS2 expose une seconde opération, `get_article` (Python
`src.legal_retrieval.contract.get_article.get_article`, HTTP `POST /legal/article`), demandée
par DS4 :
- désignation par `article_id` (avec ou sans version) **ou** par `source_id` + `article`
  (`"39"`, `"7BIS"`, `"54TER"`, `"46-3"`), schéma de requête dédié ;
- **même format de réponse que `search`** (enveloppe `common.v0`, toutes les versions, D17) ;
- répond en mode **`live` sur le corpus réel** (466 articles, D20) dès qu'il est ingéré sur la
  machine, sinon en mode `mock` ; un article abrogé est renvoyé avec sa mention d'abrogation
  et son avenant ;
- « Citation ou Silence » : un article inconnu donne `SOURCE_MANQUANTE` ; pour un trou vérifié
  à la main (R8), le refus **donne la raison** (absent du PDF / absent du digest).

**Alternatives envisagées** :
- Passer par `search` avec la référence dans `query` → rejeté : une recherche renvoie des
  articles *proches*, alors qu'une référence doit donner l'article exact ou un refus.
- Un format de réponse propre à `get_article` → rejeté : DS1 et DS4 n'auraient pas un seul
  format à lire.

**Limites v0** : pas de filtre daté (Sprint 5) ; pas de page par article (digest Tradrly).

**Statut** : ⏳ v0 proposée à DS4 et DS1 ; preuve HTTP réelle : 200 `ok` `live` (article
abrogé avec son avenant), 200 `refus` (trou vérifié à la main), 422 (requête non conforme).

---

### D23 — Grille salariale ASSOCIATIONS_PERSONNES_HANDICAPEES (pages 7, 14-29)

**Numéro** : D23. D11 à D22 sont pris par DS2 (`origin/DS2_Legal_Retrieval_Track`,
`origin/DS2_Sprint2`, dont D21 vocabulaire et D22 `get_article`) ; `origin/main`
s'arrête à D10. Vérifié avec `git fetch origin` le 2026-10-13 : aucune branche
distante ne contient de D23.

**Source** : `data/raw/pdf/الاتفاقيّة المشتركة القطاعيّة لأعوان جمعيّات رعاية الأشخاص المعوّقيـن.pdf`
(29 pages). Grilles scannées p.21 à 29 (15 tables : 5 populations × 3 dates,
1er décembre 2021, 1er janvier 2023, 1er janvier 2024) ; annexes de
classification p.16 à 20 ; article 12 (جديد) (progression) p.7 ; article 14
(جديد) (durée du travail) p.8 ; article 42 (جديد) (primes) p.14 et 15.

**Constat** :
- Les lignes des grilles sont titrées « الرتبة » et numérotées en chiffres
  romains ; elles sont rattachées aux catégories (« الصنف ») des annexes d'après
  leur position (hypothèse) : même nombre de lignes que de catégories dans
  chaque annexe ; seul l'article 42 (جديد) 9 (p.15) le confirme pour une ligne,
  la IV des ouvriers, agents administratifs et surveillants : « بالصنف 4 من جدول
  التصنيف المهني عدد 3 ».
- Deux populations (éducation spécialisée, sport) ont les mêmes lignes
  {I, II, III} : leurs tables ne peuvent pas être rattachées à une population
  par leurs seules catégories.
- Agents techniques : ligne imprimée « III+II ». L'annexe 4 (p.19) liste les
  catégories 2 et 3 séparément, sans dire qu'elles partagent une ligne.
- En-tête d'ancienneté : « مدة البقاء بالدرجة » = 2 pour les 16 degrés ;
  « الأقدمية الفعلية » = 2, 4, …, 32 (un seul nombre par degré ; dernière colonne
  « 32 », sans « + »).
- L'article 12 (جديد) ب (p.7) renvoie aux grilles annexées et ne dit rien
  au-delà du dernier degré.
- Aucune phrase de la convention ne précise l'unité des grilles (mensuelle ou
  horaire). L'article 40 (p.13) parle de « معدل الأجور الشهري » pour l'indemnité
  de fin de service, sans viser les grilles.

#### Décisions (validées par DS5)

1. **Clé de catégorie** = chiffre romain imprimé dans la grille ; alias en
   chiffres arabes (numérotation des annexes) déclarés par population dans le
   JSON (`alias_categories`). La réponse donne `categorie` (clé) et
   `categorie_demandee` (alias reçu).
2. **Champ `population`** explicite par table ; le validateur l'exige quand
   plusieurs populations ont exactement les mêmes catégories.
3. **« III+II »** : une seule clé, **sans** alias « 2 » ni « 3 » (ni « II »,
   « III ») tant que l'annexe ne confirme pas le partage de la ligne. Pour les
   techniciens, le seul alias est « 1 » → « I » ; « II », « III », « 2 » et
   « 3 » sont refusés (`PARAM_INVALIDE`).
4. **Degré k = de 2k−2 à 2k ans** (libellés « 0-2 » … « 30-32 ») ; bornes
   exactes 2, 4, …, 30 refusées (`PARAM_INVALIDE`, D6) ; à partir de 32 ans,
   refus `SOURCE_MANQUANTE` qui cite l'article 12 (جديد) ب (p.7). Lecture
   affichée dans `detail.hypotheses` (FR et AR).
5. **Primes exposées** (article 42 (جديد), p.14) : transport, présence et prime
   spécifique (« منحة خاصة لرعاية المعوقين »). La date « بداية من » est la date
   d'effet ; « بعنوان سنة » n'est qu'une information (`au_titre_de`).
   - Groupes de la prime de transport, choisis par l'appelant :
     `execution_et_gestion` (« أعوان التنفيذ والتسيير », agents d'exécution et
     de gestion) et `cadres` (« الإطارات ») ; libellés FR et AR renvoyés dans
     `detail` (`groupe_libelle`, `groupe_libelle_ar`). La métallurgie garde ses
     clés (`execution_et_maitrise`, `cadres`).
   - La phrase qui exclut de la prime de transport les montants des décrets
     503/1982 et 691/1986 (« ولا يتضمن مقدار منحة النقل المقادير المنصوص عليها
     بالأمر عدد 503 المؤرخ في 16 مارس 1982 والمنقح بالأمر عدد 691 المؤرخ في 19
     جويلية 1986 ») est recopiée dans `detail` (`note`, `note_ar`), sans calcul.
   - Primes de frais scolaires, pédagogique, de santé, fonctionnelle et des
     chauffeurs : `primes_non_couvertes`, motif « montant sans date d'effet dans
     la source » (texte arabe et page dans le JSON). Prime de production :
     refusée, motif « formule, pas de montant ».
6. **Unité mensuelle**, déduite de l'ordre de grandeur des montants ; hypothèse
   affichée dans `detail.hypotheses`.

**Montants transcrits** : 864 cellules de grille et 12 montants de primes
(transport : 30,199 / 32,238 / 34,414 pour les agents d'exécution et de
gestion, 36,239 / 38,685 / 41,296 pour les cadres ; présence : 6,281 / 6,705 /
7,158 ; prime spécifique : 54,358 / 58,027 / 61,944 TND/mois, aux dates d'effet
du 2021-12-01, du 2023-01-01 et du 2024-01-01), par double lecture indépendante,
0 divergence.

#### Anomalies imprimées conservées

Neuf cellules s'écartent de 0,002 de la progression habituelle de leur ligne.
Chacune est lue nettement (deux lectures concordantes, relecture en pixels
natifs, vérification visuelle par DS5) ; la valeur imprimée est conservée,
**aucune correction** (`anomalies_increment` des tables 10, 12, 13 et 15) :

| Table (page) | Ligne | Degré | Valeur imprimée |
|---|---|---|---|
| 10, المكونين المهنيين, 2023 (p.26) | III (معلم تعليم تقني) | 12 | 1 225,010 |
| 12, أعوان الرياضة, 2024 (p.27) | I (مرافق رياضة) | 6 | 665,982 |
| 12, أعوان الرياضة, 2024 (p.27) | I | 16 | 811,828 |
| 13, العملة والأعوان الإداريين و القيمين, 2024 (p.28) | I (عامل بدون اختصاص) | 4 | 492,399 |
| 13 (p.28) | II (عامل مختص) | 6 | 665,982 |
| 13 (p.28) | II | 16 | 811,828 |
| 15, المكونين المهنيين, 2024 (p.29) | I (مرافق تدريب تقني) | 6 | 665,982 |
| 15 (p.29) | I | 16 | 811,828 |
| 15 (p.29) | III (معلم تعليم تقني) | 14 | 1 360,529 |

D'une date à l'autre, ces cellules suivent la même relation que leurs voisines.
La source n'explique pas leur écart : la cause (arrondis du texte imprimé ou
autre) n'est pas établie, et la valeur imprimée est conservée.

#### Limite des contrôles de lecture

- Deux régularités ont été **observées** entre les montants imprimés : environ
  2 % d'un degré au suivant dans une ligne, et environ 6,75 % d'une date d'effet
  à la suivante. Aucun texte de la convention ne les fixe. Elles servent
  uniquement de contrôles de lecture dans les tests (tolérance ±0,001), jamais
  à calculer ni à corriger un montant.
- Ces contrôles ne détectent pas toute erreur : 29 cellules ne sont protégées
  par aucun d'eux contre une erreur de 0,002. **Vérification visuelle faite le
  2026-10-12** : les 29 cellules et les 12 montants de primes correspondent au
  PDF.
- La double lecture indépendante et la vérification visuelle sont les vrais
  contrôles.

#### Note de source (avenants)

Au bas de la page 15, la note 8 se lit « نقح بالملحق التعديلي 1 ثم عدد 2 ثم عدد3 ».
Son appel est placé à la fin de l'article 42 (جديد) (après le point 9, « منحة
السواق ») : l'article 42 a été modifié par l'avenant 1, puis par les avenants 2
et 3. Les montants transcrits sont ceux du texte consolidé tel qu'imprimé ; les
avenants eux-mêmes ne figurent pas dans les sources.

#### Hypothèses affichées (`detail.hypotheses`, `detail.hypotheses_ar`)

- Lecture des degrés : le degré k couvre de 2k−2 à 2k ans.
- Unité mensuelle, déduite de l'ordre de grandeur des montants.
- Rattachement de chaque ligne de grille à la catégorie de l'annexe de même
  numéro, d'après l'ordre des lignes (pour la ligne IV des ouvriers, agents
  administratifs et surveillants, confirmé par l'article 42 (جديد) 9).
- Ligne « III+II » des techniciens : catégories 2 et 3 de l'annexe 4
  rattachées d'après le seul libellé de la grille.
- Présence et prime spécifique : le texte les prévoit pour toutes les
  catégories (« لكل الأصناف »).

#### Mise en œuvre

- **Données** : `data/processed/salary_grids/associations_personnes_handicapees.json`
  (`_meta.decision_ref` = « D23 », `tables_transcrites` = true) : 15 tables dans
  `grilles` (population, date, page, unité, valeurs, anomalies), 3 primes dans
  `primes`, `primes_non_couvertes`, `regle_date_effet_primes`, hypothèses,
  alias, refus au-delà de 32 ans.
- **Calcul** : `calc/loaders.py` (`population_de_table`, alias, hypothèses de
  grille, textes des primes : `note_ar`, `hypotheses`, `libelles_groupes`
  validés) ; `calc/salary.py` (tables choisies par population, alias, hypothèses
  avant celles de l'article 13) ; `calc/primes.py` (`groupe_libelle`,
  `note_ar`, `hypotheses` dans `detail`, lus seulement s'ils sont présents).
- **Non-régression** : réponses de la métallurgie et du BTP identiques à l'octet
  près ; seule la liste des secteurs disponibles des refus « secteur inconnu »
  s'allonge (demo-10). Démo : demo-15 à demo-18. Évaluation : 63/63 (dont 16 cas de ce secteur, TB-48 à TB-63, vérifiés par DS5). Les 47 cas précédents sont inchangés, sauf le message de TB-35 (liste des secteurs).

#### Points non tranchés par la source (hypothèses retenues)

Consigne d'encadrement du 2026-10-13 : travailler avec les données disponibles.
Ces points sont documentés comme hypothèses et ne bloquent pas
l'implémentation ; un refus reste la règle quand aucune source ne contient la
valeur.

1. **Correspondance ligne-catégorie** des populations 1, 2, 4 et 5 (éducation
   spécialisée, sport, techniciens, formateurs professionnels) : déduite de
   l'ordre des lignes, non écrite dans la convention.
2. **Sens de « III+II »** : faut-il accepter « 2 » et « 3 » comme alias ? Seule
   la grille l'indique ; l'annexe 4 liste les deux catégories séparément.
3. **Unité mensuelle**, déduite de l'ordre de grandeur : aucune phrase ne la fixe.
4. **Lecture de l'ancienneté** (degré 1 = de 0 à 2 ans) et **règle au-delà de
   32 ans** : l'article 12 (جديد) ب ne dit rien après le degré 16.
5. **Catégories de chaque groupe de transport** : la classification de cette
   convention ne définit ni « أعوان التنفيذ والتسيير » ni « الإطارات ».
6. **Régime hebdomadaire de la population 3** (ouvriers, agents administratifs
   et surveillants) : l'article 14 (جديد) (p.8) fixe 48 h pour les ouvriers et
   40 h pour les agents administratifs et les surveillants, dans une même grille ;
   non renseigné.
7. **Article 13** : dans cette convention, l'article 13 (p.7, « تكليف الأعوان
   بوظائف غير مطابقة لأصنافهم ») ne porte pas sur l'ancienneté au-delà du dernier
   degré (contrairement à l'article 13 (جديد) ب de la métallurgie et du BTP,
   D10). Il prévoit une prime égale à la différence de salaire en cas
   d'affectation temporaire à une catégorie supérieure (trois mois au plus) ;
   cette prime n'est pas couverte.
8. **Primes avec montant mais sans date d'effet** : frais scolaires (10 d par
   enfant, début de l'année scolaire), pédagogique (30 d par mois), santé (30 d
   par mois) et fonctionnelle (150 d par mois), art. 42 (جديد) 4 à 7 (p.14).
   Elles restent refusées (SOURCE_MANQUANTE) car aucune date d'effet n'est
   donnée. Elles pourraient être exposées plus tard avec une hypothèse affichée
   « date d'effet non précisée par la source », si l'équipe le décide.

**Statut** : ✅ implémenté et exposé (2026-10-13) ; vérification visuelle
terminée le 2026-10-12.

---

### D24 — Graphe juridique v0 : sources, articles, avenants, textes externes

*(Numérotée D24 : D23 est prise par DS5 pour Track B, secteur associations.)*

**Décision** : `src/legal_retrieval/graph/build.py` construit, à partir du corpus ingéré, un
graphe JSON (`legal_graph.json`, hors git comme le corpus) :
- nœuds `SECTOR` (vocabulaire D21), `SOURCE`, `ARTICLE` (un par article, toutes versions),
  `AVENANT` (daté si présent dans l'historique, sinon `known: false`), `EXTERNAL` (Code du
  travail article par article, décrets `DECRET-501-1982`, lois — cités mais absents du corpus) ;
- arêtes `APPARTIENT_A`, `S_APPLIQUE_AU_SECTEUR` (convention cadre et SMIG → tous les
  secteurs), `AVENANT_DE`, `ABROGE` (avenant → article abrogé), `MENTIONNE_AVENANT`, `CITE` ;
- chaque arête de citation garde sa **preuve** (le renvoi tel qu'écrit, ≤ 60 caractères) ;
  une citation déduite (numéro absent de la convention, Code du travail nommé dans le même
  article) porte `inferred: true`.

Lecture des renvois (`graph/references.py`), construite sur le diagnostic du corpus réel
(142 articles sur 468 citent un autre texte) : « بالفصل / للفصل / الفصلين » ; cible lue dans
les mots qui suivent (« من مجلة الشغل », « من الاتفاقية الإطارية », « من الأمر ») ; « … مجلة
الشغل وخاصة الفصل 143 منها » (renvoi en arrière) ; forme OCR « مجل الشغل » ; jamais un en-tête
(R1/R4) ni une liste d'abrogation (R2).

**Constats du diagnostic** : les 22 renvois « introuvables » (articles 76 à 333) sont tous des
articles du **Code du travail** ; la convention cadre cite 6 fois son avenant n° 3, absent de
son historique ; l'Enseignement cite un avenant n° 12 (historique : 11).

**Alternatives envisagées** :
- Une base de graphe (Neo4j) → reportée : 468 articles tiennent dans un JSON ; aucun service
  de plus à installer pour l'équipe.
- Une arête `MODIFIE` avenant → article pour chaque « (جديد) » → rejetée : le digest ne dit
  pas quel avenant a modifié l'article ; on ne crée que ce qui est écrit (`MENTIONNE_AVENANT`).

**Statut** : ⏳ v0 ; démonstration du plan : `python -m src.legal_retrieval.graph.query
--sector banques` (convention des banques + convention cadre + SMIG).

---

### D25 — Corpus traité versionné dans le dépôt, vérifié contre les sources

**Décision** : les sorties de l'ingestion `data/processed/legal_corpus/legal_articles.jsonl`,
`legal_sources.json` et `avenants.json` sont commitées, pour que tous les rôles (DS1 en
premier) aient le corpus réel sans relancer l'ingestion ; `get_article` passe alors en mode
`live` sur toutes les machines. Les rapports et le graphe (`ingestion_report.json`,
`*_diagnosis.json`, `legal_graph.json`) restent générés localement.

Un test (`test_legal_corpus_committed.py`) relance l'ingestion sur `data/raw/` et exige que
les fichiers commités soient **identiques** : un corpus commité ne peut pas dériver du code ni
des sources.

**Alternatives envisagées** :
- Garder le corpus hors git, chaque rôle relançant l'ingestion → rejeté : DS1 a constaté que
  le corpus « n'est pas dans la branche » ; l'intégration dépendait d'une étape manuelle.
- Stockage partagé externe → rejeté : un service de plus, et des données hors des outils
  Tradrly.

**Confidentialité** : les sources (`data/raw/pdf`, `data/raw/txt`) sont déjà dans ce dépôt
privé ; le corpus traité n'en est qu'une transformation, il n'augmente pas l'exposition.

**Statut** : ✅ accepté par DS5 (Oumaima) le 2026-10-14 ; corpus commité.

---

### D26 — Recherche réelle v0 : référence d'article + BM25, sans dépendance externe

**Décision** : `POST /legal/search` (et `handle()`) répond en mode **`live`** dès que le corpus
est ingéré sur la machine (`computed_by = legal_retrieval.search.live`) ; sinon le mock reste
servi (`mode = mock`). Ordre de la réponse :
1. les articles dont le **numéro est demandé** (« الفصل 42 مكرر », « article 14 bis »,
   « الفصل 46 - 3 ») → score 1.0, conventions sectorielles avant la convention cadre ;
2. puis **BM25** (k1 = 1.5, b = 0.75) sur le texte normalisé (`text_normalized`, D13),
   racinisation arabe légère (« ال », « بال », « لل »… ; « ات », « ين », « ه »…), mots vides
   retirés ; score = score / meilleur score.

Filtre `sector` identique au mock : un article s'applique à son secteur ou à tous
(`sector = null` : convention cadre, SMIG). `top_k` compte des articles, chaque article
avec toutes ses versions (D17). Aucun mot en commun avec le corpus → refus
`SOURCE_MANQUANTE`. Le texte renvoyé reste le texte exact.

`handle(request, live=False)` force le mock : le fichier d'exemples partagé avec DS1
(`legal_retrieval_requests_demo.json`) ne change pas selon la machine.

**Alternatives envisagées** :
- Bibliothèque `rank_bm25` → rejetée pour la v0 : 60 lignes de Python suffisent, aucune
  dépendance à faire valider, résultat déterministe (égalités départagées par identifiant).
- Embeddings denses + fusion RRF dès maintenant → reportés : il faut un modèle validé par
  Tradrly, et aucune donnée ne doit sortir vers un service externe (hors Gemini 3).

**Limites connues (v0)** :
- une question en **français** ne trouve rien (le corpus est en arabe) → refus ; un glossaire
  FR → AR est la prochaine amélioration ;
- `worker_category` est accepté mais pas encore filtré (pas de catégorie par article) ;
- `reference_date` : version en vigueur seulement (filtre daté au sprint 5) ;
- l'abstention hors périmètre repose sur « aucun mot en commun » : un seuil sera fixé avec le
  golden set (Recall@10 ≥ 88 %, abstention ≥ 85 %, spec §8.4).

**Statut** : ⏳ v0 ; essai sur le corpus réel :
`python -m src.legal_retrieval.tools.try_search "منحة النقل" --sector btp`.

---

### D27 — Golden set de la recherche et mesure (Recall@k, abstention, seuil)

**Décision** : la recherche DS2 est mesurée sur `src/legal_retrieval/evaluation/golden_set_retrieval.v0.json`
par `python -m src.legal_retrieval.evaluation.metrics` (résultats datés dans `evaluation/results/`).
- Types de questions : `sujet` (mots d'un travailleur, **pas** ceux de l'article), `numero`,
  `dialecte` (tunisien), `francais`, `hors_perimetre` (DS2 doit refuser).
- Succès = **au moins un** article attendu (`version_group`) dans les k premiers.
- Chiffre de référence : Recall@10 sur `sujet` + `numero` (cible ≥ 88 %) ; abstention sur
  `hors_perimetre` (cible ≥ 85 %) — spec Tradrly §8.4. Dialecte et français sont mesurés à part
  (limites connues de la v0).
- Les articles attendus sont choisis avec `evaluation/find_candidates.py`, recherche par mot
  **indépendante du moteur** : on ne note pas le système avec ses propres réponses.
- Étude de seuil : le premier résultat a toujours un score normalisé de 1.0 ; seul le score
  BM25 **brut** peut dire « rien de pertinent ». `metrics` montre, pour chaque seuil candidat,
  le Recall@10 conservé et l'abstention atteinte ; le seuil retenu sera fixé dans `bm25.py`.

**Alternatives envisagées** :
- Questions tirées des titres des articles → rejeté : elles reprennent les mots exacts de
  l'article et surestiment le BM25.
- Golden set généré par un LLM → rejeté : données confidentielles, et les questions doivent
  venir de personnes qui connaissent le métier (DS2, DS4).

**Statut** : ⏳ v0 : 43 questions (12 complètes : 4 `numero`, 8 `hors_perimetre` ; 31 à compléter).

**Première mesure (2026-10-14, 12 questions complètes)** : numéros R@10 = 100 %, mais N04
(« الفصل 39 من الاتفاقية الإطارية ») au rang 8 ; abstention **37,5 %** (cible 85 %) : 5 questions
hors sujet partagent un mot rare avec un article (score brut 6,6 à 10, autant qu'une vraie question).
Corrections :
- convention nommée dans la question (mots-clés du registre) → seul son article est renvoyé ;
- nouveau signal **couverture** (part de la question, pondérée par l'idf, trouvée dans le meilleur
  article), étudié à côté du score brut pour fixer le seuil d'abstention ;
- mots interrogatifs (« كم », « كيف »…) ajoutés aux mots vides ; un mot long commençant par
  ب/ل/ك/ف donne aussi sa forme sans cette lettre (« بعطلة » → « عطل »), « بطاقة » reste « بطاق ».

**Mesure 2026-10-14 (28 questions complètes)** : `sujet` + `numero` R@10 = **93,8 %** (cible 88 %),
R@1 62,5 %, MRR 0,77 ; ratée : G06 (« توفي » ≠ « الوفاة », racines différentes) ; dialecte et
français 0 % (limites connues). Ni le score brut ni la couverture seuls ne séparent le hors sujet :
G03 (couv. 0,27) et G12 (0,375) sont aussi bas que H08 (0,38).

**Règle d'abstention retenue** (`bm25.py`, `MIN_RAW = 8.0`, `MIN_COVERAGE = 0.5`) : sans numéro
d'article demandé, refus si le meilleur article est **à la fois** faible (brut < 8,0) **et**
partiel (couverture < 0,5). 8,0 est entre le hors sujet le plus fort refusable (7,45) et la
question légitime la plus faible (9,17) ; la couverture protège les questions courtes et
complètes (« منحة النقل »). Effet attendu sur ce jeu : abstention 37,5 % → 75 %, R@10 inchangé.
Plafond des signaux lexicaux : H06 (vol) et H08 (change) partagent de vrais mots avec un article ;
les 85 % demanderont un signal sémantique (embeddings) ou le tri d'intention de DS1 en amont.
⚠️ Valeurs fixées sur 28 questions : à revérifier quand le golden set grandit.
---

### D28 — Recherche par le sens : embeddings Gemini + fusion RRF avec BM25

**Décision** : quand une clé Gemini et le cache de vecteurs existent, l'ordre des résultats
(après les numéros d'article demandés) est la **fusion RRF** (k = 60) du classement BM25 et du
classement par similarité cosinus des embeddings Gemini (`src/legal_retrieval/search/embeddings.py`).
- Gemini est le **seul service externe autorisé** pour les données (règle Tradrly) ; la clé est lue
  dans `GEMINI_API_KEY` ou dans `.env` (ignoré par Git), jamais dans le code.
- Les vecteurs des articles sont calculés **une fois** (`python -m src.legal_retrieval.search.embeddings
  --build`) et gardés en local dans `data/processed/legal_corpus/embeddings/<modèle>.json` (ignoré par
  Git) ; le fichier porte une empreinte SHA-256 du corpus : un cache périmé n'est jamais utilisé.
- À la recherche, seule la **question** est envoyée à Gemini.
- Sans clé, sans cache ou sans réseau : **BM25 seul**, sans erreur (repli automatique, testé).
- Modèle choisi par `DS2_EMBED_MODEL` (défaut `gemini-embedding-001`, dimension 768) ; modèles
  disponibles avec la clé du projet : `gemini-embedding-001`, `gemini-embedding-2`, `gemini-embedding-2-preview`.
- La règle d'abstention D27 est **inchangée** ; `metrics` mesure en plus le signal cosinus.

**Alternatives envisagées** :
- Modèle d'embedding local → rejeté pour la v0 : pas de GPU, et Gemini est déjà fourni par Tradrly.
- Remplacer BM25 par les embeddings → rejeté : BM25 trouve les termes juridiques exacts, les
  embeddings le sens ; la fusion garde les deux.

**Statut** : ⏳ code et tests prêts (faux modèle, sans réseau) ; corpus **pas encore envoyé** à Gemini :
attente de la confirmation de Tradrly pour le modèle d'embedding. Ensuite : mesure golden set
BM25 seul vs hybride, `gemini-embedding-001` vs `gemini-embedding-2`, puis seuil d'abstention.


---

### D29 — Grille salariale ASSURANCE (pages 1, 9-11, 17, 20-21)

**Numéro** : D29. D24 à D28 sont pris ou réservés par DS2 ; D30 est la table de correspondance des secteurs.

**Source** : `data/raw/pdf/الاتفاقية المشتركة القطاعية للتأميـن.pdf` (21 pages). Page de titre (p.1) : « الاتفاقية المشتركة القطاعية للتأمين ». Pages 1 à 19 : couche texte
sans arabe lisible ; textes lus sur les images. Pages 20 et 21 : grilles scannées (attribut de rotation 270
appliqué au rendu). Articles utilisés : art. 14 (p.9, catégories), art. 16 (جديد) أ (p.9, progression),
art. 19 (جديد) (p.11, grille et unité), art. 20 (جديد) à 22 (جديد) (p.11, primes), art. 44, 46 et 47 (جديد)
(p.17, avantages sociaux).

**Constat** :
- Deux tables : « جدول الأجور عدد 1 », en vigueur à partir du 1er octobre 2020 (p.20), et « جدول الأجور عدد 2 »,
  en vigueur à partir du 1er juin 2021 (p.21). 22 lignes × 14 degrés chacune, soit 616 montants ; TND/mois
  (art. 19 (جديد), p.11 : le salaire mensuel résulte de la grille annexée).
- En-tête : degrés 1 à 14 (degré 1 à droite) ; durées de séjour 1, 1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 3, 3 ;
  ancienneté effective en tranches 0-1 … 27-30, puis « 30+ » (degré 13 imprimé « 27-30 » p.20 et « 30-27 »
  p.21, mêmes bornes).
- Lignes, de haut en bas : échelles 21 à 4, puis la ligne « استثنائي » (cellule fusionnée, sans lettre de
  sous-groupe), puis 3, 2, 1. Catégories imprimées 1 à 5, conformes à l'art. 14 (p.9).
- Art. 19 (جديد) (p.11) : l'agent atteint le degré 14 au terme de 33 ans de service effectif ; l'en-tête des
  grilles ouvre le degré 14 à 30 ans.
- Art. 16 (جديد) أ (p.9) : « يتمثل التدرج في الارتقاء آليا من درجة إلى درجة أعلى مباشرة بصفة مستمرة كما هو مقرر بسلم الأجور. »
- Art. 20 (جديد) (p.11) : une prime de transport pour tous les agents des sociétés d'assurance, montant du
  décret n° 503 du 16 mars 1982 inclus : 75 dinars par mois à partir du 1er juin 2016, 85 dinars par mois à
  partir du 1er juin 2017. Note 11 (p.11) : la prime de transport entre dans le calcul de la prime de
  production et des 13e et 14e mois.
- Note sous chaque tableau (p.20 et 21) : les salaires incluent l'indemnité complémentaire provisoire
  (décret n° 437 du 7 avril 1981, relevée par le décret n° 501 du 16 mars 1982) ; `_meta.remarque_pdf`,
  mention reproduite sans calcul.

#### Décisions (validées par DS5)

1. **Population unique** `tous_agents` (« كافة أعوان شركات التأمين », art. 20 (جديد), p.11). **Changement de contrat** :
   `population` n'est plus obligatoire au schéma de requête ; pour un secteur à une seule population, elle
   peut être omise, et si elle est donnée elle doit être `tous_agents` (sinon `PARAM_INVALIDE`). Pour un
   secteur à plusieurs populations, rien ne change : omise, elle est refusée par calc/ (`PARAM_INVALIDE`).
   Changement à annoncer à DS1.
2. **Clé de ligne** : numéro d'échelle imprimé (`"21"` à `"1"`) ; la ligne « استثنائي » a sa propre clé, sans alias,
   et n'est reliée à aucune autre catégorie : aucun texte ne fait ce lien.
3. **Règle « ouvert » du dernier degré** (`au_dela_dernier_degre.regle = "ouvert"`, art. 16 (جديد) أ, p.9) : le
   degré 14 est servi dès 30 ans, sans plafond ni extrapolation. Les 33 ans de l'art. 19 (جديد) sont une note
   de lecture affichée (`detail.hypotheses`), jamais une borne.
4. **Bornes exactes** 1, 2, 3, 4, 6, 8, 10, 13, 16, 19, 23, 27 et 30 ans : refusées (`PARAM_INVALIDE`, D6).
5. **Dates** : avant le 2020-10-01, aucune grille : `SOURCE_MANQUANTE`. Après le 2021-06-01, la grille du
   2021-06-01 reste servie (D6), avec l'hypothèse affichée qu'aucune grille postérieure n'est présente dans
   les sources.
6. **Prime de transport** (`prime_transport`, art. 20 (جديد), p.11) : même montant pour tous les agents ;
   75.000 TND/mois à partir du 2016-06-01, 85.000 TND/mois à partir du 2017-06-01 ; avant le 2016-06-01,
   `SOURCE_MANQUANTE`. `detail` recopie la mention du décret n° 503 du 16 mars 1982 (montant inclus) et la
   note 11 (`note`, `note_ar`), sans calcul, et l'hypothèse qu'aucune révision postérieure au 2017-06-01
   n'est présente dans les sources. Double lecture des montants et des dates : aucun écart.
7. **Primes non couvertes** (`primes_non_couvertes`, `SOURCE_MANQUANTE`, refus lu dans le JSON) :
   - 13e et 14e mois (art. 20 (جديد), p.11) : formule ;
   - prime de production (art. 20 (جديد), p.11) : formule selon un tableau (50 % à 150 % du salaire brut de
     décembre) ;
   - prime fonctionnelle (art. 21 (جديد), p.11) : montant absent (fixé par chaque société) ;
   - prime de l'art. 22 (جديد) (p.11) : montant absent (fixé par chaque société) ;
   - aide en cas de décès (art. 44, p.17) : formule (trois mois de salaire) ;
   - aide scolaire (art. 46, p.17) : montant absent (fixé par l'employeur) ;
   - prime de départ à la retraite (art. 47 (جديد), p.17) : formule (quatre mois, six mois en départ anticipé).
8. **Régime hebdomadaire** : `null` ; les tables n'indiquent aucun régime horaire.
9. **Table des secteurs** (D30) : l'entrée `assurance` passe à `actif`, `ds5_code` `ASSURANCE`,
   `ds5_decision_ref` D29, preuve `meme_source_file` (même fichier que `_meta.source_file`).

#### Hypothèses affichées (`detail.hypotheses`, `detail.hypotheses_ar`)

- « L'article 19 (جديد) (p.11) indique que l'agent atteint le degré 14 « في موفى 33 سنة من الخدمة الفعلية » ; l'en-tête des grilles (p.20 et 21) ouvre le degré 14 à 30 ans (« 30+ ») : le degré 14 est servi à partir de 30 ans, sans plafond ; les 33 ans ne sont pas une borne. »
- « Aucune grille postérieure au 2021-06-01 n'est présente dans les sources ; la grille du 2021-06-01 est la dernière transcrite. »

#### Contrôles de lecture

- Double lecture indépendante de chaque lot (200 dpi ligne par ligne, 300 dpi colonne par colonne), relecture
  en pixels natifs des signes ambigus, vérification humaine par lot.
- **Contrôle croisé entre les deux tables** : pour chaque ligne, l'écart « table 2 − table 1 » est le même
  aux 14 degrés : +235 (catégorie 1, échelles 21 à 16), +200 (catégorie 2, 15 à 13), +185 (catégorie 3, 12 à
  10), +170 (catégorie 4, 9 à 4), +160 (catégorie 5, « استثنائي », 3, 2, 1) ; aucune exception sur les 308 paires
  (616 cellules). C'est un **contrôle de lecture** : il n'est jamais utilisé pour déduire, corriger ou
  calculer un montant.

#### Mise en œuvre

- Données : `data/processed/salary_grids/assurance.json` (`_meta.decision_ref` D29, 2 tables, 616 montants,
  1 prime, 7 primes non couvertes).
- `calc/loaders.py` : `"regle": "ouvert"` accepté avec sa source (`source_pdf_page`, `source_article`,
  `texte_source_ar`) et un dernier degré au libellé `"n+"`. `calc/salary.py` : population omise admise pour
  un secteur à une seule population.
- Schéma de requête : `population` facultative ; `docs/CONTRACT_TRACK_B.md` mis à jour.
- Tests : `test_dernier_degre_ouvert_population_unique.py`, `test_assurance_primes.py`, et les listes de
  secteurs des tests existants ; le golden set garde un cas « secteur non couvert » (TB-35, sur le
  gardiennage).

#### Points non tranchés par la source (hypothèses retenues)

1. **Degré 14 et 33 ans** : la somme des durées de séjour des degrés 1 à 13 vaut 30, et 30 + 3 (durée du
   degré 14) = 33. Observation de lecture seulement ; aucune règle déduite.
2. **Ligne « استثنائي »** : catégorie 5 par position ; non reliée à une autre catégorie (décision 2).
3. **Sous-groupes imprimés dans la grille** : aucun texte de la convention ne les définit ; non exposés.

**Statut** : ✅ activée (2026-10-17) ; `pytest` complet : tous réussis.

---

### D30 — Table de correspondance des secteurs DS2 ↔ DS5 (`src/shared/sectors/sectors.v0.json`)

**Constat** : deux vocabulaires de secteurs coexistent sans lien écrit.
- DS2 (D21) : 7 codes en minuscules (`btp`, `construction_metallique`, `associations`, …), chacun relié à une
  source (`CCS-BTP`, …) par `src/legal_retrieval/corpus/registry.py` ;
- DS5 : les codes des grilles vérifiées (`_meta.secteur_code` de `data/processed/salary_grids/*.json`, registre
  `loaders.GRILLES`) : `METALLURGIE_BATIMENT` (D4), `BATIMENT_TRAVAUX_PUBLICS` (D9),
  `ASSOCIATIONS_PERSONNES_HANDICAPEES` (D23).

Les noms ne suffisent pas à les relier : `METALLURGIE_BATIMENT` correspond à la **construction métallique**, pas au
« bâtiment » (alias DS2 de `btp`). DS1 détecte le secteur Track B par des mots codés en dur (dans la PR #13 de
DS1, pas encore sur main) ; DS3 renvoie, dans sa PR #12 (contrat v2, pas encore sur main),
`WageGrid.sector_code = null` « tant que la table n'est pas fixée ».

**Décision** : une table de données commune, sans code métier, dans `src/shared/` :
- `src/shared/sectors/sectors.v0.json` (`table_version` `common.sectors.v0`, `vocabulary_ref` D21) ;
- schéma `src/shared/schemas/common_sectors.v0.schema.json` (v0 : proposition, à valider par l'équipe) ;
- une entrée par secteur D21 : `ds2_code`, `source_id`, `label_fr`, `label_ar`, `aliases` (copie fidèle du
  vocabulaire D21, `origin/DS2_Sprint4`), puis `ds5_code`, `ds5_status`, `ds5_decision_ref`, `evidence` ;
- `ds5_status` : `actif` (grille vérifiée dans le registre DS5 ; les trois champs DS5 sont obligatoires),
  `en_preparation` ou `aucun` (les trois champs à `null`, imposé par le schéma).

| ds2_code | source_id | ds5_code | ds5_status |
|---|---|---|---|
| `construction_metallique` | CCS-CONSTRUCTION-METALLIQUE | `METALLURGIE_BATIMENT` (D4) | actif |
| `btp` | CCS-BTP | `BATIMENT_TRAVAUX_PUBLICS` (D9) | actif |
| `associations` | CCS-ASSOCIATIONS | `ASSOCIATIONS_PERSONNES_HANDICAPEES` (D23) | actif |
| `assurance` | CCS-ASSURANCE | null | en_preparation (grille non fusionnée : non supportée) |
| `gardiennage_securite_transport_fonds` | CCS-GARDIENNAGE | null | aucun |
| `enseignement_prive` | CCS-ENSEIGNEMENT-PRIVE | null | aucun |
| `banques` | CCS-BANQUES | null | aucun |

La convention cadre (`CC-CADRE`) et le SMIG (`SMIG-GRILLE`) s'appliquent à tous les secteurs : pas d'entrée.

**Preuve exécutable** (`src/shared/tests/test_sectors_table.py`) : une correspondance n'est inscrite que si la grille
DS5 et la source DS2 désignent **le même fichier** de `data/raw/pdf/` (`evidence.type = meme_source_file`).
Le test vérifie :
1. le schéma et la conformité de la table, et que le schéma refuse un statut incohérent avec les champs DS5 ;
2. tout `ds5_code` non nul est dans `loaders.GRILLES` et `secteurs_disponibles()`, avec `decision_ref`,
   `source_file` et `convention_ar` égaux au `_meta` de la grille ;
3. chaque secteur DS5 disponible figure une fois dans la table (une nouvelle grille ne peut pas être oubliée) ;
4. `match_source` (registre DS2) appliqué au `source_file` DS5 rend le `source_id` et le `ds2_code` de l'entrée ;
5. les 7 `ds2_code` et `source_id` sont ceux du registre DS2 déjà sur main ;
6. copie fidèle du vocabulaire D21 : **ignoré** tant que `data/mock_cards/legal_retrieval_vocabulary.v0.json` est
   absent de main, exécuté automatiquement dès qu'il est présent (vérifié hors dépôt sur la copie de
   `origin/DS2_Sprint4` : conforme).

**Ambiguïtés non tranchées** : le bloc `sector_ambiguities` de D21 v0.1 est recopié à l'identique :
- « البناء / construction / bâtiment » → `btp` ou `construction_metallique` : DS1 demande une précision
  (« bâtiment » n'est plus un alias de `btp`) ;
- « métallurgie / المعادن » → pas de choix automatique : la convention du corpus couvre seulement la construction
  métallique ; sans précision, `sector = null`.
`ambiguity_note_fr` : aucune de ces trois formes seules (« البناء », « bâtiment », « métallurgie ») ne mène à
`METALLURGIE_BATIMENT` ; la table ne résout aucune ambiguïté, l'appelant la gère. Le schéma accepte désormais un
bloc d'ambiguïté à un seul code (`minItems` 1 au lieu de 2), forme du bloc « métallurgie ».

**Alternatives envisagées** :
- Module Python dans `src/shared` → rejeté : `src/shared/README.md` interdit le code métier ; des données JSON
  suffisent et se lisent depuis n'importe quel rôle.
- Correspondance par ressemblance de nom → rejetée : elle aurait relié « bâtiment » à `METALLURGIE_BATIMENT`.
- Inscrire un code DS5 pour l'assurance → rejeté : aucune grille assurance n'est fusionnée ; statut
  `en_preparation`, `ds5_code` null jusqu'à la fusion.

**Ce qui change** :
- DS1 : lire la table au lieu de la détection codée en dur ; appeler Track B seulement si `ds5_status = actif`,
  avec `ds5_code` ; sinon répondre sans calcul. Gérer l'ambiguïté « البناء » (demande de précision).
- DS2 : aucun changement de code ; tout ajout ou renommage de secteur D21 doit être répercuté dans la table
  (tests 5 et 6).
- DS3 : `WageGrid.sector_code` reçoit le `ds2_code` (comme le dit déjà son schéma v2), ou `null` si le
  rapprochement n'est pas certain ; le code DS5 se lit dans la table.
- DS5 : une grille ajoutée (assurance) fait échouer le test 3 tant que la table n'est pas mise à jour
  (`ds5_status` → `actif`, `ds5_code`, `ds5_decision_ref`, `evidence`).

**Réponses de DS2** (PR #15, D21 v0.1, 2026-10-15) :
1. `associations` est le code stable.
2. « métallurgie » n'est pas un alias de `construction_metallique` : c'est une ambiguïté ; sans précision,
   `sector = null`.
3. « bâtiment » seul n'est plus un alias de `btp` : il devient ambigu comme « البناء ».
4. Le vocabulaire `legal_retrieval_vocabulary.v0.json` et D21 v0.1 arrivent sur main avec la PR #15 (non fusionnée
   au 2026-10-15) ; le test 6 est réussi sur une fusion à blanc de cette PR.
5. Le vocabulaire DS2 reste la source de vérité ; la table est vérifiée contre lui (test 6).

**Statut** : ⏳ v0 alignée sur D21 v0.1 (PR #15 de DS2), proposée à DS1, DS2, DS3 ;
`pytest src/shared/tests/test_sectors_table.py` : 12 réussis, 1 ignoré sur la branche (vocabulaire D21 absent de
main) ; 13 réussis sur une fusion à blanc avec la PR #15.

Mise à jour : l'entrée assurance est passée à actif (D29).
Mise à jour : l'entrée enseignement_prive est passée à actif (D38).
Mise à jour : l'entrée banques est passée à actif (D46).
Mise à jour : l'entrée gardiennage_securite_transport_fonds est passée à actif (D47).

---

### D31 — Contrat DS3 `ds3.v2` aligné sur l'enveloppe commune `common.v0`

**Numéro** : D31 à D37 réservés pour DS3 le 2026-10-15. Vérifié avec `git fetch origin` :
D20–D22 et D24–D28 sont pris par DS2, D29 par DS5 (assurance), D30 par la table des secteurs
(PR #14).

**Décision** : la réponse DS3 suit `src/shared/schemas/common.v0.schema.json`
(`$defs/response_envelope`) : `status` `ok` / `refus` / `erreur`, `refus {code, message_fr,
message_ar}`, `erreur {type, message_fr, message_ar}`, `computed_by` obligatoire
(`document_intelligence.mock` / `document_intelligence.service`), `result` toujours présent
(`null` si refus ou erreur). DS3 y ajoute `mode` (`mock` / `live`) à la racine, `ds3_code`
(code DS3 détaillé, pour le diagnostic) et `retryable` (seulement si `erreur`). Un résultat
partiel est un `ok` avec `result.complete = false`. Correspondances avec `ds3.v1` :
`INVALID_REQUEST`, `UNSUPPORTED_OPERATION`, `FILE_EMPTY_OR_CORRUPTED`, `FILE_TOO_LARGE` →
`PARAM_INVALIDE` ; `UNSUPPORTED_FORMAT` → `HORS_SCOPE` ; `ACCESS_DENIED` → `ACCES_REFUSE`
(nouveau code, message neutre, `document_id` non renvoyé) ; `UNREADABLE_DOCUMENT`,
`NO_TABLE_FOUND` → `SOURCE_MANQUANTE` ; `TIMEOUT`, `INTERNAL_ERROR` → `erreur`.
Les citations sont des citations de document `{citation_id, document_id, page, bbox, excerpt}`.

**Alternatives envisagées** :
- Garder les statuts `success` / `partial` / `error` de `ds3.v1` → rejeté : DS1 devrait gérer
  un format de statut de plus.
- Utiliser la citation du corpus de `common.v0` → impossible : un document de carte n'a ni
  `data_file` dans `data/processed/`, ni `decision_ref`. Proposition d'ajouter
  `document_citation` et `ACCES_REFUSE` dans `common.v1`.

**Raison** : un seul format de statut et de refus pour toute l'équipe ; un document d'une autre
carte est refusé sans révéler son existence.

**Statut** : ⏳ v2 livrée (PR #12) ; `common.v1` à venir. Conformité prouvée par
`test_response_matches_common_v1_draft` (common.v0 + les deux ajouts) et
`test_refusals_without_citations_already_match_common_v0`.

---

### D32 — Extraction DS3 : Gemini localise, le code vérifie (« Citation ou Silence »)

**Décision** : pour chaque champ, Gemini renvoie seulement le texte recopié tel qu'il est imprimé
(`raw`) et l'identifiant de la ligne lue (`line_id`), au format JSON imposé, température 0. Le
code vérifie ensuite que la ligne existe, qu'elle est lisible et que la valeur y figure **en
entier** (un nombre n'est pas accepté s'il n'est qu'un morceau d'un autre nombre : « 3 » dans
« 2023 », « 275,000 » dans « 1.275,000 »). Sinon la valeur est rejetée (`null`,
`valeur_incoherente`, avec un avertissement). La citation est la ligne du document (page, bbox,
texte exact). La confiance est celle de la ligne (1.0 en natif, valeur de l'OCR sinon), jamais
une confiance donnée par le modèle. Le résumé est écrit par le code à partir des valeurs retenues.

**Alternatives envisagées** :
- Laisser Gemini renvoyer directement les valeurs normalisées et sa confiance → rejeté : une
  valeur inventée ou « corrigée » ne serait pas détectable, et la confiance déclarée par un
  modèle n'est pas mesurée.
- Accepter une valeur sans ligne citée → rejeté : contraire à « Citation ou Silence ».

**Raison** : toute valeur renvoyée par DS3 peut être retrouvée et surlignée sur le document ;
une invention du modèle devient un `null` visible, pas une erreur silencieuse.

**Limite connue** : la vérification porte sur la ligne entière, pas sur la colonne. Sur une ligne
qui porte plusieurs nombres (« Salaire de base  208  2.388  496.704 »), une valeur juste mais
rattachée au mauvais libellé n'est pas détectée. Amélioration prévue : associer chaque valeur à sa
colonne (bbox horizontale). En attendant, la confiance et la citation restent à confirmer par
l'utilisateur côté DS1.

**Statut** : ⏳ proposition ; prouvée par `test_invented_value_is_rejected`,
`test_numbers_must_appear_whole`, `test_invented_value_is_null_and_response_incomplete`,
`test_confidence_comes_from_the_line_not_from_gemini`.

---

### D33 — Normalisation des valeurs lues par règles fixes

**Décision** : la conversion au format du contrat est faite par du code, jamais par le modèle.
Montants : chaîne à 3 décimales ; avec un seul séparateur (« , » ou « . »), c'est le séparateur
décimal (les fiches de paie tunisiennes impriment les millimes) ; deux séparateurs différents :
le dernier est décimal ; même séparateur répété (« 1.275.000 ») ou plus de 3 décimales → `null`.
Dates : JJ/MM/AAAA (usage tunisien) ou AAAA-MM-JJ ; année sur 2 chiffres ou date impossible →
`null`. Mois de paie (« Mars 2026 », « مارس 2026 ») → premier et dernier jour du mois.
Catégorie : lettres arabes → latines (« 1 ب » → `1B`, « 1 أ » → `1A`). Régime horaire :
208 h/mois → 48 ; 173,33 h/mois → 40 ; 40 ou 48 repris tels quels ; toute autre valeur → `null`.
Chiffres arabes orientaux (٠-٩) convertis. Toute valeur non convertible → `null` avec
`valeur_incoherente`, en gardant sa citation pour que DS1 montre où elle est imprimée.

**Alternatives envisagées** :
- Interpréter « 1.275 » comme 1 275 dinars → rejeté : ambigu ; la règle du séparateur unique
  suit l'usage des fiches de paie.
- Deviner le siècle d'une année sur 2 chiffres → rejeté : on ne devine pas.

**Raison** : des règles écrites et testées donnent toujours le même résultat ; les cas ambigus
sont signalés au lieu d'être devinés.

**Statut** : ⏳ proposition ; prouvée par `test_document_intelligence_normalize.py` (48 cas) et le
cas piège DS3-04 du jeu de référence.

---

### D34 — Aucune interprétation dans DS3

**Décision** : DS3 lit et cite ; il ne déduit pas. Les mots imprimés ne sont traduits que s'ils
figurent dans un vocabulaire fixe (`permanent` / `titulaire` / `قار` → `permanent`, etc.).
« CDD » et « CDI » ne sont pas traduits en `temporaire` / `permanent` : le champ vaut `null`
(`valeur_incoherente`) et le mot imprimé reste visible dans la citation. La `population`, le
`groupe`, le `code` de prime DS5 et l'ancienneté sont déduits par DS1 / DS5 et confirmés par
l'utilisateur. `sector_code` reçoit le code DS2 de la table des secteurs (D30) seulement si le
libellé arabe ou le titre exact de la convention lu sur le document correspond ; jamais à partir
d'un alias, faits pour les questions et trompeurs sur un document (« sécurité » dans « Caisse
nationale de sécurité sociale », « banque » dans un virement) ; sinon `null`.

**Alternatives envisagées** :
- Traduire CDD → `temporaire` et CDI → `permanent` → reporté : c'est une interprétation
  juridique ; à ajouter au vocabulaire seulement si DS2 et DS5 la valident.

**Raison** : une erreur d'interprétation dans DS3 serait invisible pour DS1 et DS5.

**Statut** : ⏳ proposition, question ouverte pour DS2 / DS5 (CDD / CDI) ; prouvée par
`test_enums_only_accept_printed_words`, `test_wage_grid_sector_code_comes_from_the_shared_table`
et le cas DS3-04.

---

### D35 — Lecteur de PDF natif : lignes visuelles, arabe et texte illisible

**Décision** : le lecteur `reading/pdf_natif.py` (v0.3) regroupe les morceaux de texte posés sur
la même ligne visuelle (recouvrement vertical ≥ 50 %), de gauche à droite, ou de droite à gauche
si la ligne a plus de morceaux arabes que français : « Salaire de base » et « 424,100 » dans deux
colonnes donnent une seule ligne. Les formes de présentation arabes (U+FB50–U+FDFF,
U+FE70–U+FEFF) sont ramenées aux lettres normales (NFKC). Les lignes cassées (caractères
« Private Use », U+FFFD, glyphes sans code, ≥ 20 % des caractères) deviennent des zones à passer
à l'OCR ; si au moins la moitié des lignes d'une page sont cassées, toute la page part à l'OCR.

**Alternatives envisagées** :
- Garder les morceaux séparés → rejeté : la citation d'un montant ne montrerait pas son libellé.
- Réparer le texte « Private Use » → rejeté (voir D16) : la couche texte arabe du corpus n'est
  pas réparable.

**Raison** : chaque citation montre le libellé avec la valeur ; le texte arabe devient lisible
par le modèle et comparable par la vérification (D32).

**Statut** : ⏳ proposition ; prouvée par `test_label_and_amount_in_two_columns_become_one_line`,
`test_merge_rows_reads_arabic_rows_right_to_left`,
`test_arabic_presentation_forms_are_turned_into_normal_letters`,
`test_unreadable_line_goes_to_ocr`.

---

### D36 — Jeu de référence DS3 sur documents fictifs

**Décision** : Tradrly ne fournit pas de documents de carte ; DS3 génère ses documents de test
(`evaluation/fictive_documents.py`) : fiches de paie et facture fictives (mention « DOCUMENT
FICTIF », aucune donnée personnelle), en français et en arabe, natives et scannées, avec cas
pièges. Les valeurs attendues sont écrites une seule fois et reprises dans les PDF,
`ds3_golden.v0.json` et `sources_documents.csv`. Seuls ces documents fictifs (et des documents
publics anonymisés) sont envoyés à Gemini ; aucun document Tradrly réel sans l'accord de
l'encadrant (NDA). Score : `correct` / `faux` / `silence` / `invention` par champ ; objectif
0 invention.

**Alternatives envisagées** :
- Uniquement des fiches publiques trouvées en ligne → insuffisant : valeurs attendues
  incertaines, données personnelles à masquer ; elles viendront en complément.

**Raison** : valeurs attendues exactes, cas pièges choisis, aucun risque de confidentialité.

**Statut** : ⏳ v0 (5 documents) ; première évaluation avec Gemini le 2026-10-15 : 4 cas,
60 champs, 100 % corrects, 0 invention (documents faciles, à compléter par des fiches réelles et
des scans via l'OCR). Chaîne prouvée par `test_pipeline_gives_the_expected_answer` et
`test_perfect_gemini_scores_100_percent`.

---

### D37 — Confiance du type de document (règle provisoire)

**Décision** : `document_type_confidence` = 0,95 si le type lu correspond au type attendu par DS1
(`options.expected_type`), 0,80 si DS1 n'indique pas de type attendu, 0,50 avec un avertissement
s'ils diffèrent. Si aucun champ n'est vérifié (ex. une facture envoyée comme fiche de paie), la
réponse est un refus `SOURCE_MANQUANTE`.

**Alternatives envisagées** :
- Utiliser une confiance donnée par le modèle → rejeté (voir D32).

**Raison** : règle simple et explicable en attendant des mesures sur de vrais documents.

**Statut** : ⏳ provisoire, à recalibrer avec le jeu de référence complété ; prouvée par
`test_type_mismatch_lowers_confidence_and_warns` et le cas DS3-05.

---

### D38 — Grille salariale ENSEIGNEMENT_PRIVE (pages 3, 8, 11, 15-27)

**Numéro** : D38. `origin/main` s'arrête à D30 ; D31 à D37 sont réservés à DS3 (vérifié avec `git fetch origin` le
2026-10-19 : aucune de ces décisions n'est sur main).

**Source** : `data/raw/pdf/الاتفاقية المشتركة القطاعية للتعليم الخا ص.pdf` (27 pages). Couche texte : chiffres lisibles, arabe illisible (glyphes privés) ; pages 25
à 27 sans couche texte (scans tournés à 270°). Tous les textes ont été lus sur les images. Pages utilisées : p.3
(avenant n° 12), art. 15 (جديد) (p.8, progression), art. 25 (جديد) (p.11, horaires), art. 46 مكرر à 55 (p.15 à 19,
primes), dispositions transitoires (p.20), annexes 1 à 4 (p.21 à 24, classification), grilles (p.25 à 27).

**Constat** :
- Cinq grilles « جدول الأجور عدد 1 » à « عدد 5 », toutes en vigueur à partir du 1er septembre 2015 (avenant n° 12,
  p.3 : signé le 27 avril 2016, effet au 1er septembre 2015, révision des salaires et des articles 48 à 51 et 54).
  Ouvriers (p.25, 5 lignes), administratifs et surveillants (p.25, 8 lignes), instituteurs (p.26, 3 lignes),
  secondaire et formateurs (p.26, 5 lignes), professeurs d'école primaire (p.27, 2 lignes) : 23 lignes × 16 degrés,
  soit 368 montants.
- En-tête : degrés 1 à 16 (degré 1 à droite) ; durées de séjour 1, 1, 2 (×8), 3 (×6) ; ancienneté effective
  imprimée en un seul nombre par degré, 1, 2, 4, …, 36, égal à la somme des durées des degrés 1 à k : il marque la
  fin du degré k.
- Art. 15 (جديد) ب (p.8) : progression continue de degré en degré selon les grilles annexées ; six mois
  d'ancienneté gagnés pour une note d'au moins 17/20. Aucun texte au-delà du degré 16.
- Unité : la grille des ouvriers est titrée « payés au mois » ; les autres ne précisent pas l'unité.
- Annexe 2 (p.22) : 13 rangs pour 8 lignes de grille (des lignes regroupent 2 ou 3 rangs). Annexe 3 (p.23) : 5 rangs,
  répartis sur les grilles 3 (3 lignes) et 5 (2 lignes). Annexe 4 (p.24) : 6 rangs pour 5 lignes ; le rang des
  formateurs adjoints n'a pas de ligne (dispositions transitoires 4, p.20 : rang supprimé progressivement).
- Note sous chaque grille : les salaires incluent l'indemnité complémentaire provisoire (décret n° 437 du 7 avril
  1981, relevée par le décret n° 501 du 16 mars 1982) ; `_meta.remarque_pdf`, mention reproduite sans calcul.

#### Décisions (validées par DS5)

1. **Cinq populations, une par grille** (comme D23) : `ouvriers`, `administratifs_surveillants`, `instituteurs`,
   `secondaire_formateurs`, `professeurs_primaire` ; chaque grille cite sa propre page (25, 25, 26, 26, 27).
   `population` est obligatoire (secteur à plusieurs populations).
2. **Clé de catégorie** : ligne imprimée de la grille (code), avec la liste des rangs qu'elle couvre
   (`libelles_categories`). Les rangs de l'annexe 2 qui partagent une ligne sont des alias vers elle
   (`alias_categories`), ainsi que les numéros de catégorie 1 à 5 de l'annexe 1 pour les ouvriers.
3. **Formateurs adjoints** : pas de ligne de grille ; la demande est refusée comme catégorie inconnue
   (`PARAM_INVALIDE`). Mention dans `_meta.remarque_pdf`.
4. **Degrés** : libellés « 0-1 » … « 33-36 » ; bornes exactes 1, 2, 4, …, 33 ans refusées (`PARAM_INVALIDE`, D6) ;
   à partir de 36 ans, refus `SOURCE_MANQUANTE` qui cite l'art. 15 (جديد) ب (p.8).
5. **Dates** : avant le 2015-09-01, aucune grille : `SOURCE_MANQUANTE`. Après, la grille du 2015-09-01 reste servie
   (D6), avec l'hypothèse affichée qu'aucune grille postérieure n'est présente dans les sources.
6. **Unité** : TND/mois ; hypothèse affichée pour les grilles 2 à 5 (unité déduite de l'ordre de grandeur).
7. **Ancienneté** : l'ancienneté reçue est l'ancienneté de progression déjà établie ; les six mois de bonification
   et les reclassements lors des promotions ne sont pas calculés (hypothèse affichée).
8. **Primes couvertes** (une par article, groupes = rangs de l'article, groupe obligatoire) :
   - transport, montants au 2015-09-01 : `prime_transport_ouvriers` (art. 48 (جديد), p.15),
     `prime_transport_administratifs` (art. 49 (جديد), p.16), `prime_transport_surveillants` (art. 50 (جديد), p.16),
     `prime_transport_primaire` (art. 51 (جديد), p.17), `prime_transport_secondaire` (art. 54 (جديد), p.18). Note :
     montant du décret n° 503 du 16 mars 1982 inclus (art. 48), et du décret n° 503 modifié par le décret n° 691 du
     19 juillet 1986 (art. 49 à 54) ; hypothèse : aucune révision postérieure au 2015-09-01 dans les sources ;
   - pédagogique, 4 dates (1er juillet 2008, 2009, 2010, 2011) : `prime_pedagogique_primaire` (art. 51 (جديد),
     p.17), `prime_pedagogique_secondaire` (art. 54 (جديد), p.18) ; hypothèse : aucune révision postérieure au
     2011-07-01 dans les sources.
   - Un format de prime ne porte qu'une page et un article : une prime par article.
9. **Primes non couvertes** (`primes_non_couvertes`, `SOURCE_MANQUANTE`, refus lu dans le JSON) : présence des
   ouvriers (2,080 à l'art. 48 et 3,000 à l'art. 54-5, sans lien établi ni date), spécifiques des administratifs et
   des surveillants (sans date), production des ouvriers et des administratifs et surveillants (formules),
   production du primaire et du secondaire (montants fixes sans date), direction (art. 54 مكرر, fonction absente des
   grilles), avantages pour les enfants (art. 54 ثالث, en nature), compensation des primes antérieures (art. 55),
   aide en cas de décès (art. 46 مكرر, sans date).
10. **Régime hebdomadaire** : `null` (art. 25 (جديد), p.11 : plusieurs régimes dans une même population).
11. **Table des secteurs** (D30) : l'entrée `enseignement_prive` passe à `actif`, `ds5_code` `ENSEIGNEMENT_PRIVE`,
    `ds5_decision_ref` D38, preuve `meme_source_file`.

#### Textes arabes

La couche texte du PDF est inutilisable : aucun texte arabe n'est cité (`texte_source_ar` absent). Les libellés et
messages arabes du fichier sont rédigés à la main (`libelle_ar_redige` pour les populations) ; libellés arabes des
lignes de grille non recopiés.

#### Contrôles de lecture

- Double lecture indépendante des 368 cellules (200 dpi ligne par ligne, 300 dpi colonne par colonne avec l'en-tête
  et la colonne des rangs) : 0 écart ; relecture en pixels natifs (600 dpi) des zones à risque ; vérification
  humaine de tous les lots, sans correction.
- Contrôles (jamais utilisés pour corriger) : lignes strictement croissantes ; 39 incréments hors du rythme de leur
  ligne signalés et confirmés à l'image (dont la grille 3 au degré 3, motif identique sur ses 3 lignes) ; aucune
  cellule sous le SMIG vérifié (D2).

#### Mise en œuvre

- Données : `data/processed/salary_grids/enseignement_prive.json` (`_meta.decision_ref` D38, 5 tables, 368
  montants, 7 primes, 11 primes non couvertes). Aucune modification de `calc/` ni de schéma.
- Tests : `test_enseignement_prive.py` ; listes de secteurs actifs des tests existants ; démos et jeu de référence.

**Statut** : ✅ activée (2026-10-19) ; `pytest` complet : tous réussis.

---

### D39 — Le seuil de confiance appartient au consommateur

**Numéro** : D39, à la suite de D31–D37 (DS3) ; D38 est prise par DS5 (enseignement privé, PR #21).

**Décision** : DS3 n'applique **aucun** seuil de confiance. Chaque champ renvoie sa confiance réelle
(`fields[...].confidence`), et c'est le consommateur qui décide de l'utiliser ou non. DS1 exige
**0,90** avant tout calcul DS5 : en dessous, le champ passe « à confirmer » et n'est jamais pré-coché.
Le champ `options.min_confidence` du contrat devient facultatif, sans valeur par défaut (il valait
0,80, jamais utilisé) ; il reste seulement comme indication que l'appelant peut transmettre.

**Alternatives envisagées** :
- Garder le défaut 0,80 et filtrer côté DS3 → rejeté : un seuil appliqué deux fois (DS3 puis DS1) et
  deux valeurs différentes (0,80 puis 0,90) rendraient le comportement ambigu ; retenu par Oumaima
  (DS5) à la relecture de la PR #18.
- Rendre `min_confidence` obligatoire → rejeté : casserait les requêtes qui ne le fournissent pas.

**Raison** : un seul endroit décide du seuil (le consommateur), avec une seule valeur (0,90 pour DS5) ;
DS3 reste neutre et transmet l'information brute.

**Statut** : ⏳ proposition ; `min_confidence` est désormais `float | None = None` dans
`contract/v2/models.py`, documenté dans `CONTRACT_DOCUMENT_INTELLIGENCE_V2.md`.

---

### D40 — Service DS3 live : même interface que le mock, périmètre et stockage provisoires

**Numéro** : D40. Les numéros D41 à D45 restent réservés à DS3 pour ses prochaines décisions (aucune PR ne les utilise à ce jour) ; une décision d'un autre DS ne les prend pas.

**Décision** : `src/document_intelligence/service.py` expose `handle_request(request)`, avec exactement la même
entrée et la même sortie que le mock v2 ; seules les valeurs `mode = "live"` et
`computed_by = "document_intelligence.service"` changent, et DS1 ne modifie qu'une ligne d'import. Le service
ne lève jamais d'exception. Périmètre live actuel : `analyze_document` sur une fiche de paie en PDF (texte natif) ;
le reste donne un refus explicite en français et en arabe (`extract_wage_grid` : `PARAM_INVALIDE` ; autre format
ou autre type de document : `HORS_SCOPE` ; page scannée : `SOURCE_MANQUANTE` en attendant l'OCR). Stockage
provisoire : dossier racine `DS3_STORAGE_ROOT`, `storage_ref` en `tradrly://cards/<carte>/documents/<document>`
ou `local://<chemin>`. Contrôles avant toute lecture : carte du document et carte du `storage_ref` égales à la
carte active, chemin dans le dossier racine, `file_name` sans dossier, taille ≤ 20 Mo.

**Alternatives envisagées** :
- Faire passer à DS1 un chemin de fichier → rejeté : le contrat ne transmet que `storage_ref`, jamais le contenu.
- Attendre l'accès au stockage Tradrly avant de livrer → rejeté : DS1 a besoin d'un service live pour tester
  l'intégration ; seule la résolution de `storage_ref` changera.

**Raison** : DS1 peut tester un scénario réel dès maintenant, sans changer de contrat ; l'isolation des cartes
est vérifiée avant de lire le moindre fichier.

**Statut** : ⏳ provisoire (stockage à définir avec DS1 et le backend) ; prouvée par
`test_document_intelligence_service.py` (cas nominal, même interface que le mock, accès refusés sans appel à
Gemini, fichier absent, vide ou trop grand, opérations et formats hors périmètre, Gemini indisponible).

---

### D46 — Grille salariale BANQUES (pages 2-3, 8-13, 19-23)

**Numéro** : D46. D31 à D45 sont réservés à DS3 ; `origin/main` s'arrête à D39 (vérifié avec `git fetch origin` le
2026-10-28).

**Source** : `data/raw/pdf/البنوك.pdf` (23 pages). Couche texte des pages 1 à 21 : chiffres lisibles, arabe illisible
(glyphes privés) ; pages 22 et 23 sans couche texte (scans tournés à 270°). Tous les textes ont été lus sur les images ;
les chiffres de la couche texte (p.19 et 20) servent de seconde source. Pages utilisées : p.2-3 (révisions et avenants),
art. 10 à 13 (p.8-11, recrutement, stage, classification, progression), art. 16 (p.12), art. 17 (p.12), art. 21 (p.13),
art. 47 (p.19, salaire), art. 49 à 54 (جديد) (p.20-21, primes), art. 57 (p.21), grilles (p.22-23).

**Constat** :
- Convention révisée signée le 29 novembre 2013, en vigueur au 1er mai 2012 (art. 57, p.21) ; avenants 1 à 5 (p.3), le
  5e signé le 22 août 2022 avec effet au 1er septembre 2020 (art. 54 et salaires).
- Deux grilles « barème n° 01 », en vigueur à partir du 1er septembre 2020 (p.22), et « barème n° 02 », à partir du
  1er mai 2021 (p.23) : 34 lignes × 19 colonnes chacune, soit 1 292 montants. Les grilles des avenants 1 à 4 ne
  figurent pas dans la source.
- Chaque ligne imprime son grade et son échelon ; les 34 lignes sont les 34 postes de l'art. 12 (p.8-9), répartis en
  trois catégories (exécution et services, lignes 1-8 ; réalisation, 9-20 ; gestion administrative et encadrement,
  21-34).
- En-tête : colonne 1 (à droite) « stage », colonnes 2 à 19 = degrés 2 à 19 ; durée de séjour vide (stage), 1 (degrés 2
  à 5), 2 (degrés 6 à 19) ; ancienneté effective 1, 2, 3, 4, 5, 7, …, 33, égale à la somme des durées jusqu'à la colonne
  (stage compté pour 1 an).
- Art. 47 (p.19) : le salaire **mensuel** est fixé par la grille annexée selon le grade, l'échelon et le degré ; le plus
  haut degré est atteint en **33 ans au plus**. L'article ne précise pas ce qui s'applique au-delà.
- Art. 11 (p.8) : stage ou essai d'un an, renouvelable une fois ; la grille n'indique pas ce qui vaut pendant le
  renouvellement. Art. 13 (جديد) أ (p.10) : progression automatique et continue selon la
  grille (règle des 15 jours, absences non payées exclues ; service national et services antérieurs reconnus, p.11).
- Écarts entre l'art. 12 et les grilles : nom de la 3e catégorie, ordre des agents de suivi et des agents de services,
  échelons en lettres (art. 12) ou en chiffres (grilles), « principal » imprimé dans la colonne des échelons (lignes 4
  et 8) ; les libellés suivent les grilles.
- Note sous chaque grille : les salaires incluent l'indemnité complémentaire provisoire (décret n° 437 du 7 avril 1981,
  relevée par le décret n° 501 du 16 mars 1982) et sa hausse de 15 dinars (avenant n° 1 de la convention nationale du
  9 mars 1989) ; `_meta.remarque_pdf`, mention reproduite sans calcul.

#### Décisions (validées par DS5)

1. **Population unique** `tous_agents` (une grille par date pour les 34 postes) : facultative dans la requête (D29) ;
   donnée, elle doit être `tous_agents` (sinon `PARAM_INVALIDE`).
2. **34 clés plates** (grade et échelon imprimés), sans alias : `agent_services_3/2/1`, `agent_services_principal`,
   `agent_suivi_3/2/1`, `agent_suivi_principal`, `agent_bureau_4/3/2/1`, `commis_3/2/1`, `commis_principal_3/2/1`,
   `chef_section`, `chef_section_hors_classe`, `redacteur_3/2/1`, `redacteur_principal`, `sous_chef_service_2/1`,
   `chef_service`, `chef_service_principal`, `fonde_pouvoir`, `sous_directeur`, `directeur_adjoint`, `directeur_3/2/1`.
3. **Degrés** : libellés « 0-1 » (stage), « 1-2 », …, « 5-7 », …, « 31-33 » (le nombre imprimé marque la fin de la
   colonne, comme D38) ; bornes exactes 1, 2, 3, 4, 5, 7, …, 31 refusées (`PARAM_INVALIDE`, D6). Colonne « stage »
   servie de 0 à 1 an (art. 11, p.8 : un an, renouvelable une fois ; la grille n'indique pas ce qui vaut pendant le
   renouvellement), hypothèse affichée.
4. **Au-delà du dernier degré** : à partir de 33 ans, refus `SOURCE_MANQUANTE` qui cite l'art. 47 (p.19) ; la règle
   « ouvert » n'est pas retenue.
5. **Dates** : avant le 2020-09-01, `SOURCE_MANQUANTE` ; du 2020-09-01 au 2021-04-30, grille n° 01 ; à partir du
   2021-05-01, grille n° 02, avec l'hypothèse affichée qu'aucune grille postérieure n'est présente dans les sources.
6. **Unité** : TND/mois, écrite dans l'art. 47 : aucune hypothèse d'unité.
7. **Ancienneté** : l'ancienneté reçue est l'ancienneté de progression déjà établie ; les règles de l'art. 13 ne sont
   pas calculées (hypothèse affichée).
8. **Aucune prime couverte.** Primes non couvertes (`primes_non_couvertes`, `SOURCE_MANQUANTE`, refus lu dans le JSON),
   selon la consigne de travailler avec les données telles qu'elles sont :
   - `prime_transport` (art. 49, p.20) et `prime_representation` (art. 50, p.20) : montants par grade sans date
     d'effet, et aucun avenant ne révise ces articles (p.3) ; tableaux recopiés pour mémoire dans la note de lecture ;
   - `prime_13e_mois` (art. 51, p.20), `prime_production` (art. 52, p.20, 0 à 250 % du salaire), `prime_bilan`
     (art. 53, p.20, jusqu'à 200 %), `prime_depart_retraite` (art. 54 (جديد), p.21, douze mois de salaire à partir du
     31 mai 2021), `prime_fonction_superieure` (art. 16, p.12, différence de salaire entre grades) : formules ;
   - `prime_travail_sous_terre` (art. 21, p.13, l'alinéa sur les agents qui travaillent sous terre) : prime fixée par
     décision de l'employeur pour les agents en travail continu sous terre, sans montant.
9. **Régime hebdomadaire** : `null` (art. 17, p.12 : durée du travail selon la législation, sans nombre d'heures).
10. **Table des secteurs** (D30) : l'entrée `banques` passe à `actif`, `ds5_code` `BANQUES`, `ds5_decision_ref` D46,
    preuve `meme_source_file`.

#### Anomalies imprimées conservées

Valeurs imprimées conservées telles quelles, **aucune correction** ; chacune est la **même anomalie dans les deux
tables** et a été relue à 600 dpi (`anomalies_imprimees` de chaque table, `_meta.remarque_anomalies`). Lignes de haut
en bas, colonnes depuis la droite (colonne 1 = stage).

| Ligne | Colonne | Table 1 (p.22) | Voisines (col. −1 / +1) | Table 2 (p.23) | Voisines (col. −1 / +1) |
|---|---|---|---|---|---|
| 4 et 5 | toutes | lignes identiques (agent de services principal et agent de suivi, échelon 3) | — | lignes identiques | — |
| 4 | 6 | 1470,216 | 1558,506 / 1567,926 | 1634,216 | 1722,506 / 1731,926 |
| 5 | 6 | 1470,216 | 1558,506 / 1567,926 | 1634,216 | 1722,506 / 1731,926 |
| 10 | 5 | 1807,346 | 1806,566 / 1818,126 | 1983,346 | 1982,566 / 1994,126 |
| 16 | 16 | 1928,226 | 1921,446 / 1935,146 | 2104,226 | 2097,446 / 2111,146 |
| 18 | 6 | 1871,896 | 1865,646 / 1879,346 | 2047,896 | 2041,646 / 2055,346 |
| 18 | 12 | 1934,596 | 1906,746 / 1920,446 | 2110,596 | 2082,746 / 2096,446 |

#### Hypothèses affichées (`detail.hypotheses`, `detail.hypotheses_ar`)

- Lecture des degrés : le nombre « ancienneté effective » marque la fin de la colonne (stage : de 0 à 1 an ; degré 19 :
  de 31 à 33 ans).
- Colonne « stage » servie de 0 à 1 an (art. 11, p.8 : un an, renouvelable une fois ; la grille n'indique pas ce qui
  vaut pendant le renouvellement) ; la situation de stage n'est pas vérifiée.
- Ancienneté reçue = ancienneté de progression déjà établie (art. 13, p.10-11, non calculé).
- Aucune grille postérieure au 2021-05-01 dans les sources.

#### Textes arabes

La couche texte du PDF est inutilisable : aucun texte arabe n'est cité (`texte_source_ar` absent). Les libellés arabes
(population, catégories, lignes) reprennent le mot imprimé sur les grilles, saisi à la main depuis l'image
(`libelle_ar_redige`) ; les messages et hypothèses arabes sont rédigés.

#### Contrôles de lecture

- Double lecture indépendante des 1 292 cellules (200 dpi ligne par ligne, 300 dpi colonne par colonne) : 1 écart
  (table 1, ligne 28, colonne 7), tranché à 600 dpi (2659,326 ; erreur de saisie de la première lecture).
- Contrôles (jamais utilisés pour corriger ni remplir une cellule) : l'écart table 2 − table 1 est constant sur chaque
  ligne, sans exception (+164 lignes 1-8, +176 lignes 9-18, +208 lignes 19-23, +239 lignes 24-28, +298 lignes 29-34) ;
  anomalies ci-dessus signalées et confirmées à l'image ; aucune cellule sous le SMIG vérifié (D2).
- **Statut de vérification** : Les tables 1 et 2 ont été relues cellule par cellule sur l'image (1 292 cellules) par
  une seconde lecture indépendante de la double lecture initiale ; l'écart entre la table 2 et la table 1 est constant
  sur chaque ligne ; contrôle humain des extrémités de chaque ligne et des cellules signalées.

#### Mise en œuvre

- Données : `data/processed/salary_grids/banques.json` (`_meta.decision_ref` D46, 2 tables, 1 292 montants, aucune
  prime, 8 primes non couvertes). Aucune modification de `calc/` ni de schéma.
- Tests : `test_banques.py` ; listes de secteurs actifs des tests existants ; démos 34 à 39 et jeu de référence.

**Statut** : ✅ activée (2026-10-28) ; `pytest` complet : tous réussis.

---

### D47 — Grille salariale GARDIENNAGE_SECURITE_TRANSPORT_FONDS (pages 2, 8-9, 13-21)

**Numéro** : D47, à la suite de D46 ; `origin/main` s'arrête à D46 et aucune branche distante ne réserve D47 (vérifié
avec `git fetch origin` le 2026-10-28).

**Source** : `data/raw/pdf/أعوان مؤسسات الحراسة والسلامة ونقل العملة.pdf` (21 pages). Couche texte des pages 1 à 20 :
chiffres lisibles, arabe illisible (glyphes privés) ; page 21 sans couche texte (scan en basse résolution, environ
100 dpi). Tous les textes ont été lus sur les images ; les chiffres de la couche texte (p.14) servent de seconde
source. Pages utilisées : p.2 (avenants 1 à 7), art. 13 et 16 (p.8), art. 17 (جديد) (p.9), art. 39 (جديد) (p.13),
art. 43 (جديد) à 47 (p.14), art. 50 et 51 (p.15), classification (p.16 à 20), grille (p.21).

**Constat** :
- Une seule grille, « barème n° 2 », en vigueur à partir du 1er mai 2010 (p.21) : 15 lignes (catégories 1 à 15) ×
  14 degrés, soit 210 montants. Le barème n° 1 n'est pas dans la source.
- Avenant n° 7 (p.2) : signé le 17 avril 2013, effet au 1er mai 2011, révise l'art. 46 et les salaires ; sa grille n'est
  pas dans la source.
- En-tête : degrés 1 à 14 (degré 1 à droite) ; durée de séjour 1, 1, puis 2 ; ancienneté imprimée en tranches « 0-1 »,
  « 1-2 », « 2-4 », …, « 22-24 », et « 24 » seul pour le degré 14. Art. 44 (p.14) : système d'ancienneté réparti sur
  26 ans (somme des durées imprimées : 26).
- Art. 43 (جديد) (p.14) : salaire **mensuel** fixé par la grille annexée.
- Art. 17 (جديد) (p.9) : 48 h ; 60 h à partir du 1er mai 2008 pour les agents de gardiennage et leurs chefs ; 54 h pour
  les chauffeurs et convoyeurs de fonds. Une même grille pour tous ces régimes.
- Classification (p.16 à 20) : 15 catégories numérotées, décrites par métiers (liste ouverte) ; la grille reprend les
  mêmes numéros.
- Note sous la grille (p.21) : les salaires incluent l'indemnité complémentaire provisoire (décret n° 437 du 7 avril
  1981, relevée par le décret n° 501 du 16 mars 1982), sans montant ni date ; `_meta.remarque_pdf`.

#### Décisions (validées par DS5)

1. **Population unique** `tous_agents`, facultative dans la requête (D29) ; donnée, elle doit être `tous_agents`.
2. **Clés de catégorie** : numéros imprimés « 1 » à « 15 », sans alias par métier ; le numéro de catégorie est requis
   (classification p.16 à 20).
3. **Degrés** : libellés imprimés « 0-1 » … « 22-24 » ; degré 14 lu **« 24-26 »** (durée imprimée de 2 ans et art. 44),
   hypothèse affichée ; bornes exactes 1, 2, 4, …, 22, **24** refusées (`PARAM_INVALIDE`, D6) ; à partir de 26 ans,
   refus `SOURCE_MANQUANTE` qui cite l'art. 44 (p.14).
4. **Dates** : avant le 2010-05-01, `SOURCE_MANQUANTE` (barème n° 1 absent) ; du 2010-05-01 au 2011-04-30, barème
   n° 2 ; **à partir du 2011-05-01, `SOURCE_MANQUANTE`** (avenant n° 7, p.2 : salaires révisés, grille absente). Champ
   facultatif `valide_jusqu_au` de la table (voir « Mise en œuvre »).
5. **Unité** : TND/mois, écrite dans l'art. 43 : aucune hypothèse d'unité.
6. **Régimes horaires** (art. 17) : **aucun recalcul d'heures** ; `regime_hebdomadaire` null ; hypothèse affichée.
7. **Ancienneté** : ancienneté de progression déjà établie ; degrés supplémentaires de la promotion (art. 16 ب) et
   du reclassement (art. 51) non calculés (hypothèse affichée).
8. **Primes couvertes** :
   - `prime_transport` (art. 46 (جديد), p.14), à partir du 2012-05-01 : 20,000 (`execution_gestion`, agents
     d'exécution et de gestion) et 25,000 (`cadres`) TND/mois ; le montant **comprend** celui du décret n° 503 du
     16 mars 1982 (total, aucune addition) ; groupe choisi par l'appelant (la classification ne rattache pas les
     catégories aux groupes) ;
   - `prime_presence` (art. 46-3, p.14), à partir du 2006-05-01 : 3,120 TND/mois (120 millimes par jour de présence) ;
   - `prime_panier` (art. 46-4, p.14), à partir du 2006-05-01 : 5,200 TND/mois (200 millimes par jour de travail
     effectif), condition : agent de gardiennage permanent ou contractuel, en travail continu de plus de 7 h le jour du
     panier (`condition_remplie`) ;
   - présence et panier : montants mensuels imprimés servis tels quels, sans recalcul selon les jours (hypothèse
     affichée).
9. **Non couverts** (`primes_non_couvertes`, `SOURCE_MANQUANTE`, refus lu dans le JSON), selon la consigne de
   travailler avec les données telles qu'elles sont :
   - `prime_risque_exceptionnel` (art. 46 مكرر, p.14) : 20 dinars par mois sans date d'effet ; article ajouté par
     l'avenant n° 4, l'art. 46 ensuite modifié par les avenants n° 5 et n° 7 ;
   - `prime_production` (art. 47, p.14) : formule pour les 48 h ; 5 dinars par mois sans date pour les 54 et 60 h ;
   - `prime_affectation_categorie_superieure` (art. 13, p.8) et `indemnite_fin_service` (art. 39 (جديد), p.13) :
     formules ;
   - `indemnite_complementaire_provisoire` (note sous la grille, p.21) : incluse dans les salaires, sans montant ni
     date d'effet.
10. **Table des secteurs** (D30) : l'entrée `gardiennage_securite_transport_fonds` passe à `actif`, `ds5_code`
    `GARDIENNAGE_SECURITE_TRANSPORT_FONDS`, `ds5_decision_ref` D47, preuve `meme_source_file`.

#### Hypothèses affichées (`detail.hypotheses`, `detail.hypotheses_ar`)

- Degré 14 lu de 24 à 26 ans (durée imprimée de 2 ans, art. 44 : 26 ans).
- Ancienneté reçue = ancienneté de progression déjà établie (art. 16 ب et 51 non calculés).
- Une même grille pour plusieurs régimes horaires (art. 17) : aucun recalcul d'heures.
- Primes de présence et de panier : montant mensuel imprimé, aucun recalcul selon les jours.
- Prime de transport : groupe choisi par l'appelant.

#### Anomalies et contrôles de lecture

- Aucune baisse dans la grille : chaque ligne croît de degré en degré et chaque catégorie dépasse celle du dessus.
- 53 changements de pas d'un degré à l'autre, conservés tels qu'imprimés (aucune correction) ; sauts isolés relus à
  500 dpi (valeurs telles qu'imprimées) : ligne 1 degré 12 (371.200), ligne 2 degré 8 (409.800), ligne 3 degrés 5
  et 13 (440.400 ; 479.700), ligne 4 degrés 3 et 11 (488.000 ; 534.500), ligne 7 degré 4 (637.500), ligne 12
  degrés 13 et 14 (1,220.000 ; 1,224.000), ligne 13 degré 14 (1,278.000).
- 37 cellules (lignes 1 à 3) sont sous le SMIG vérifié de 2022 (D2) : information seulement ; la grille n'est pas
  servie après le 2011-04-30.
- **Statut de vérification** : barème n° 2 (p.21) : 210 cellules lues par une double lecture indépendante (0 écart),
  puis relues contre l'image par une relecture indépendante (aucun écart) ; montants des primes (p.14) relus contre
  l'image (aucun écart) ; cas du jeu de référence TB-112 à TB-125 vérifiés à l'image.

#### Textes arabes

La couche texte du PDF est inutilisable : aucun texte arabe n'est cité (`texte_source_ar` absent). Les titres des
primes (p.14) et de la convention (p.21) sont saisis depuis l'image ; les libellés de population et de catégorie, les
messages et les hypothèses sont rédigés (`libelle_ar_redige`).

#### Mise en œuvre

- Données : `data/processed/salary_grids/gardiennage.json` (`_meta.decision_ref` D47, 1 table, 210 montants, 3 primes,
  5 versements non couverts).
- **Changement de calc/ (accordé à l'arrêt 3)** : champ facultatif `valide_jusqu_au` sur une table de `grilles`
  (`date`, `source_pdf_page`, `source_article`, `message_fr`, `message_ar`). `calc/loaders.py` (`valider_grille`) contrôle
  la date (format, pas avant `effective_date`) et le refus déclaré ; `calc/salary.py` (`table_applicable`) refuse
  (`SOURCE_MANQUANTE`, texte lu dans le JSON) toute date postérieure. Aucune autre grille ne porte ce champ : les
  autres secteurs, les démos existantes et la baseline sont inchangés. Aucun schéma modifié.
- Tests : `test_gardiennage.py` (règles, primes, `valide_jusqu_au` et son validateur) ; listes de secteurs actifs des
  tests existants ; démos 40 à 46 et jeu de référence (TB-112 à TB-125). `test_sectors_table.py` fabrique désormais son
  exemple d'entrée inactive (les sept secteurs sont actifs) ; TB-35 (« secteur non couvert ») porte un code fictif.
- **Effet sur DS1** : l'alias « sécurité » de l'entrée (vocabulaire D21) fait correspondre « sécurité sociale » au
  secteur désormais actif ; le test DS1 `test_sector_detection_does_not_match_unrelated_substrings` échoue jusqu'à la
  correction de la correspondance par DS1 (le message sur la sécurité sociale doit rester sans secteur).

**Statut** : ✅ activée (2026-10-28) ; `pytest` complet : tous réussis sauf le test DS1 cité ci-dessus (échec
attendu, correction demandée à DS1) ; cas du jeu de référence TB-112 à TB-125 vérifiés à l'image.

---

### D48 — Grilles : case illisible, ancienneté refusée au milieu de la grille, case exclue de l'écart cumulé

**Numéro** : D48, à la suite de D47 ; `origin/main` s'arrête à D47 et aucune branche distante n'utilise D48 à D59
(vérifié avec `git fetch origin` le 2026-11-10).

**Décision** : trois champs facultatifs dans les fichiers de grilles. Absents, ils n'ont aucun effet ; présents, ils
produisent un refus `SOURCE_MANQUANTE` dont le texte est lu dans le fichier (page et raison), jamais un montant.
1. `cellules_source_manquante` (sur une table de `grilles`) : liste `{categorie, degre, source_pdf_page,
   source_article, raison, message_fr, message_ar}` ; la case vaut `null` dans `valeurs`. Une case lue `null` est
   refusée, y compris quand l'écart cumulé (D10) ou une table de correspondance l'utilise.
2. `anciennetes_refusees` (au niveau de la grille, par population à degrés) : liste `{au_dela_de, jusqu_a_inclus,
   source_pdf_page, source_article, message_fr, message_ar}` ; toute ancienneté `a` avec `au_dela_de < a ≤
   jusqu_a_inclus` est refusée ; les bornes imprimées restent refusées en `PARAM_INVALIDE` (D6).
3. `cases_refusees` (dans un bloc `au_dela_dernier_degre` de règle `ecart_cumule_biennal`) : liste `{table_id,
   categorie, source_pdf_page, source_article, message_fr, message_ar}` ; au-delà du premier palier (n ≥ 1), la case
   de cette table et de cette catégorie est refusée ; avant (n = 0), le dernier degré est servi tel qu'imprimé.

**Alternatives** : retirer les tables qui ont une case illisible (perte de toutes les autres cases) ; refuser l'écart
cumulé pour toute une population ; ne pas tenir compte d'un article contraire à l'en-tête de la grille. Toutes
écartées (accord à l'arrêt 3 du 2026-11-10).

**Raison** : consigne « Citation ou Silence » : ce que la source ne permet pas de lire ou ne tranche pas est déclaré,
avec sa page, au lieu d'être rempli ou choisi.

**Mise en œuvre** : `calc/loaders.py` (`valider_grille`, `_cellules_manquantes`, `_valider_anciennetes_refusees`,
`_valider_cases_refusees` : case existante, `null` seulement pour une case déclarée et toute case déclarée à `null`,
bornes entières croissantes, refus déclaré complet) ; `calc/salary.py` (`degre_from_anciennete`, `salaire_base`,
`montant_case`, `_appliquer_art13`). Aucun schéma JSON modifié. Les 7 grilles déjà actives ne portent aucun de ces
champs : baseline (125 cas) et 46 démos identiques à l'octet près avant et après le changement.

**Utilisé par** : D52 (confiserie : les trois champs) et D54 (cosmétiques : `cellules_source_manquante`).

**Tests** : `test_champs_optionnels_grille.py` (données fictives : champ présent, absent, valeur refusée, borne
exacte, validateur).

**Statut** : ✅ mis en œuvre (2026-11-10) ; tests réussis.

---

### D49 — Grille salariale TORREFACTION_CAFE (pages 2-3, 8, 10, 14-18)

**Source** : `data/raw/pdf/قلي القهوة.pdf` (18 pages). Tableaux de salaires sans couche texte (scans) ; tous les textes
lus sur les images. Pages : p.2-3 (avenants), art. 16 (p.8), art. 27 (p.10), art. 48 à 51-4 (p.14-15), art. 52 (جديد)
(p.15), classification (annexe 1, p.16), tableaux n° 1 à 3 (p.17-18).

**Lecture** : 3 tableaux (2021-12-01, 2023-01-01 p.17 ; 2024-01-01 p.18), 5 catégories × 13 degrés = 195 montants ;
durée de séjour imprimée 2 pour chaque degré ; libellés « 0-2 » … « 24-26 ».

#### Décisions (validées par DS5)

1. Population unique `ouvriers_horaires`, facultative ; `employes_mensuels` (annexe 1, catégories 3 à 5 ; art. 16)
   refusée (`populations_non_couvertes`, aucun tableau mensuel).
2. **Unité TND/heure en hypothèse affichée** : non imprimée ; montants de 2,961 à 4,862.
3. Bornes exactes 2, 4, …, 24 refusées (D6) ; à partir de 26 ans, refus (art. 52 (جديد), p.15 : système réparti sur
   26 ans).
4. Dates : refus avant le 2021-12-01 ; la table de 2024 reste appliquée ensuite (aucun avenant ultérieur, p.2-3).
5. Primes couvertes : `prime_presence` (art. 49 مكرر (جديد), 3 dates), `prime_transport` (art. 50 (جديد), 3 dates),
   `prime_panier` (art. 50 مكرر (جديد), 0,533 par jour, sans date, comme D4), `prime_chaleur_salete_poussiere_groupe_a`
   et `_groupe_b` (art. 51 مكرر (جديد), 8,333 et 6,333, condition de poste), `prime_scolaire_enseignement_base`,
   `_secondaire`, `_superieur` (art. 51-3 (جديد), par enfant), `prime_deces` (art. 51-4, 110 dinars, condition).
   Montants sans date : un code par montant, servis tels qu'imprimés (hypothèse affichée).
6. `SOURCE_MANQUANTE` : `prime_depart_retraite` (art. 48 (جديد), mois de salaire), `prime_production` (art. 49 (جديد),
   pourcentage).
7. Hypothèses affichées : unité ; ancienneté de progression (reclassement de l'art. 52 non calculé) ; régime horaire
   non imprimé.

**Mise en œuvre** : `data/processed/salary_grids/torrefaction_cafe.json` ; tests `test_vague1.py` ; démos 47 à 52 ;
jeu de référence TB-126 à TB-131.

**Statut de vérification** : 195 cellules en double lecture indépendante (0 écart), lots relus contre l'image par DS5
(« LOTS VALIDÉS », 2026-11-10) ; primes lues deux fois et relues par DS5. Cas du jeu de référence : en attente de
vérification humaine.

---

### D50 — Grille salariale AGENCES_VOYAGES (pages 2-3, 8, 15-19)

**Source** : `data/raw/pdf/وكالات الاسفار.pdf` (19 pages). Pages : p.2-3, art. 13 (جديد) (p.8), art. 43 à 48-2 (p.15-16),
art. 49 et 50 (p.16), classification (p.17), tableaux n° 1 et 2 (p.18-19).

**Lecture** : 2 tableaux (2022-05-01 p.18, 2023-05-01 p.19), régime de 48 h imprimé ; 10 catégories (exécution 1-5,
gestion 6-8, cadres 9-10) × 13 degrés = 260 montants ; durées 1, 2 (×6), 3 (×5), « - ».

#### Décisions (validées par DS5)

1. Population unique `tous_agents`, facultative ; catégories « 1 » à « 10 » ; TND/mois ; régime 48 h.
2. Libellés « 0-1 », « 1-3 », …, « 25-28 », **« 28+ »** : degré 13 ouvert (règle « ouvert », D29), texte de l'art. 13
   (جديد) saisi depuis l'image. Le passage à la catégorie supérieure au terme du degré 13 et les promotions automatiques
   (15, 20, 25, 30 ans) ne sont pas calculés (hypothèses affichées).
3. Bornes exactes refusées (D6) ; refus avant le 2022-05-01.
4. Primes couvertes : `prime_transport` (art. 45 (جديد), `execution_gestion` / `cadres`, 2 dates, décret 503/1982
   compris), `prime_presence_par_jour` (TND/jour) et `prime_presence_mensuelle` (art. 46 (جديد), les deux composantes,
   2 dates), `prime_entretien` (art. 48, 15 dinars, condition), `prime_risque` (art. 48-1, 15 dinars, condition).
5. `SOURCE_MANQUANTE` : `prime_repas` (art. 47 (جديد), période non indiquée), `prime_scolaire` (art. 48 مكرر, montant
   fixé par l'entreprise), `aide_deces` (art. 48-2), `prime_production` (art. 44 (جديد)), `prime_depart_retraite`
   (art. 43 (جديد)).
6. Remarque : l'art. 49 (p.16) cite encore les tableaux de 1996 à 1998 (texte non mis à jour).

**Mise en œuvre** : `agences_voyages.json` ; `test_vague1.py` ; démos 53 à 57 ; TB-132 à TB-136.

**Statut de vérification** : 260 cellules en double lecture (0 écart), lots validés par DS5 (2026-11-10). Cas du jeu de
référence : en attente de vérification humaine.

---

### D51 — Grille salariale HOTELS_TOURISTIQUES (pages 2-3, 8-9, 15-18, 42-44)

**Source** : `data/raw/pdf/النزل السياحية والمؤسسات المشابهة لها2.pdf` (44 pages). Pages : p.2-3, art. 15 et 15 مكرر
(جديد) (p.8), art. 49 à 53 (جديد) (p.15-17), classification (p.42), tableaux n° 1 et 2 (p.43-44).

**Lecture** : 2 tableaux (2022-05-01 p.43, 2023-05-01 p.44) ; 10 lignes × 13 degrés = 260 montants, virgule décimale et
espace de milliers ; ancienneté effective imprimée 1, 3, …, 27, 30.

#### Décisions (validées par DS5)

1. Population unique `tous_agents` ; clés `direction_1`, `direction_2`, `superieur_1`, `superieur_2`, `premier_1`,
   `premier_2`, `execution_1` à `execution_3`, `services` (lignes imprimées) ; alias `cadre_1`, `cadre_2` (« إطار »
   de la classification et de l'art. 51) ; sections (أ)/(ب) au même salaire, non demandées.
2. **Hôtels 5 étoiles** : population `hotels_5_etoiles` refusée, citant la note 2 (p.43-44, +10 %), sans calcul.
3. Libellés « 0-1 » … « 27-30 » ; bornes exactes refusées ; à partir de 30 ans, refus (art. 15 مكرر (جديد), p.8) ;
   promotions automatiques de l'art. 15 (15 et 27 ans) non calculées. Refus avant le 2022-05-01.
4. Primes couvertes : `prime_transport` (art. 51 (جديد), groupes `services_a_superieur_2` et
   `superieur_1_et_cadres`, 2 dates, condition : l'employeur n'assure pas le transport), `prime_presence` (art. 51
   مكرر (جديد), 2 dates), `prime_caisse_premiers_caissiers` et `prime_caisse_caissiers` (art. 53 (جديد), 21,666 et
   16,666, conditions).
5. `SOURCE_MANQUANTE` : `prime_production` (art. 50 (جديد)), `avantage_nourriture_logement` (art. 52 (جديد), en
   nature), `prime_depart_retraite` (art. 49 (جديد)).

**Mise en œuvre** : `hotels_touristiques.json` ; `test_vague1.py` ; démos 58 à 62 ; TB-137 à TB-141.

**Statut de vérification** : 260 cellules en double lecture (0 écart), lots validés par DS5 (2026-11-10). Cas du jeu de
référence : en attente de vérification humaine.

---

### D52 — Grille salariale CONFISERIE_BISCUITERIE_CHOCOLATERIE (pages 2-3, 7-8, 13-18, 21-23)

**Source** : `data/raw/pdf/صناعة الحلويات و البسكوي والشكلاطة والمرطبات.pdf` (23 pages). Pages : p.2-3, art. 14 (جديد)
(p.7), art. 48 à 53 (p.13-14), annexes 1 et 3 (p.16, 18), tableaux n° 1 à 6 (p.21-23).

**Lecture** : 6 tableaux, 3 dates (2021-12-01, 2023-01-01, 2024-01-01) × 2 populations : mensuels 6 × 15, horaires
4 × 15 = 450 montants. En-tête « الأقدمية بالدرجة » : vide, 1, puis 2.

#### Décisions (validées par DS5)

1. Populations `mensuels` et `horaires` (titres imprimés), obligatoires ; catégories « 1 » à « 6 » et « 1 » à « 4 ».
2. **Lecture A** de l'en-tête : « 0-1 », « 1-2 », « 2-4 », …, « 24-26 », degré 15 à partir de 26 ans ; art. 14 (جديد)
   أ (p.7) : écart cumulé tous les 2 ans au-delà (règle D10, période 2) ; paliers 28, 30… refusés (`PARAM_INVALIDE`).
3. **Art. 53 (p.14)** : de 4 ans exclus à 5 ans inclus, l'article (degré 3) contredit l'en-tête (degré 4) :
   `SOURCE_MANQUANTE` (`anciennetes_refusees`, D48), pour les deux populations et les trois dates ; 4 ans pile reste
   une borne (`PARAM_INVALIDE`). Les degrés supplémentaires des points a) et b) de l'art. 53 et la promotion
   automatique de l'art. 14 ب ne sont pas calculés (hypothèses affichées).
4. **Anomalie imprimée** : tableau n° 1 (p.21), ligne 2, degré 15 = 590,535 (< degré 14 : 688,217), conservée ; servie
   de 26 à 28 ans ; au-delà, écart de l'art. 14 refusé pour cette seule case (`cases_refusees`, D48).
5. **Cases illisibles** (`cellules_source_manquante`, D48), colonne 8 : tableau n° 1 (p.21), lignes 2, 3, 5 (dernier
   chiffre abîmé) ; tableau n° 5 (p.23), lignes 2, 3 (dernier chiffre) et 6 (avant-dernier chiffre).
6. Note des tableaux : salaires incluant la présence de 112 millimes par jour, non ajoutée ; `prime_presence` de
   l'art. 51 est le forfait mensuel distinct.
7. Primes couvertes (art. 51 et 52 (جديد), p.14) : `prime_panier` (0,200 par jour), `prime_deplacement_plus_12h`
   (1,800) et `prime_deplacement_plus_18h` (4,000), `prime_caisse` (7 dinars), `prime_presence` (3 dates),
   `prime_transport` (3 dates). `SOURCE_MANQUANTE` : `prime_production` (art. 49), `prime_depart_retraite` (art. 48).

**Mise en œuvre** : `confiserie_biscuiterie.json` ; `test_vague1.py` ; démos 63 à 70 ; TB-142 à TB-149.

**Statut de vérification** : 450 cellules en double lecture (1 écart tranché à l'image, 7 cases non tranchées dont 6 ici,
déclarées illisibles), lots validés par DS5 (2026-11-10). Cas du jeu de référence : en attente de vérification humaine.

---

### D53 — Grille salariale PATES_ALIMENTAIRES_COUSCOUS (pages 2-3, 8-9, 15-21)

**Source** : `data/raw/pdf/العجين الغذائي و الكسكسي.pdf` (21 pages). Pages : p.2-3, art. 14 (جديد) (p.8), art. 48 à 54
مكرر (جديد) (p.15-16), annexe 1 (p.18), tableaux n° 1 à 6 (p.19-21).

**Lecture** : 6 tableaux, 3 dates × 2 populations : horaires 6 lignes (I, II, III × 1, 2), mensuels 8 lignes (III أ, ب,
ج ; IV I, II ; V I, II, III) × 12 degrés = 504 montants ; durées 1, 2 (×9), 3, 3.

#### Décisions (validées par DS5)

1. Populations `horaires` et `mensuels`, obligatoires (catégorie III dans les deux) ; catégorie et `sous_categorie`
   obligatoires.
2. Libellés « 0-1 », « 1-3 », …, « 19-22 », « 22+ » ; art. 14 (جديد) أ (p.8) : écart cumulé tous les 3 ans au-delà de
   22 ans, sans plafond ; paliers 25, 28… refusés. Promotion de l'art. 14 ب non calculée.
3. Primes couvertes : `prime_deplacement_repas`, `prime_deplacement_deux_repas`, `prime_deplacement_nuitee` (art. 53
   (جديد), condition), `prime_panier` (art. 53 مكرر (جديد), 0,280 par jour depuis le 2005-05-01), `prime_presence`
   (art. 53-3 (جديد), 3 dates), `prime_transport` et `prime_logement` (art. 54 et 54 مكرر (جديد), groupes
   `categorie_1` à `categorie_5`, 3 dates, groupe choisi par l'appelant).
4. `SOURCE_MANQUANTE` : `prime_transport_niveau_salaire_minimum` et `prime_logement_niveau_salaire_minimum` (groupe
   « مستوى الأجر الأدنى » non défini), `prime_vente` (art. 52, montant imprimé incohérent), `prime_productivite`
   (art. 49 (جديد), en nature), `prime_production` (art. 51 (جديد)), `prime_depart_retraite` (art. 48 (جديد)).

**Mise en œuvre** : `pates_alimentaires.json` ; `test_vague1.py` ; démos 71 à 76 ; TB-150 à TB-155.

**Statut de vérification** : 504 cellules en double lecture (0 écart), lots validés par DS5 (2026-11-10). Cas du jeu de
référence : en attente de vérification humaine.

---

### D54 — Grille salariale COSMETIQUES_PARFUMS (pages 2-3, 8-9, 15-23)

**Source** : `data/raw/pdf/صناعة مواد التجميل والعطورات.pdf` (23 pages). Pages : p.2-3, art. 49 à 59 (p.15-16),
classification (p.18-20), tableaux n° 1 à 6 (p.21-23).

**Lecture** : 6 tableaux, 3 dates × 2 populations imprimées : administratifs, services et cadres 9 × 12 ; production :
catégorie 1 « درجة وحيدة » (une cellule) et catégories 2 à 6 × 12 ; 507 montants ; ancienneté imprimée « 1-0 » …
« 26-23 », « +26 ».

#### Décisions (validées par DS5)

1. Populations `administratifs`, `production` (catégories 2 à 6) et `production_categorie_1` (catégorie 1, un degré
   « 0-1 ») ; population obligatoire. TND/mois (art. 49).
2. Libellés « 0-1 » … « 23-26 », « 26+ » (règle « ouvert ») ; texte de l'art. 49 saisi depuis l'image (durée de 3 ans
   jusqu'au degré 12, rien au-delà : hypothèse affichée). Classement de l'art. 50 non calculé.
3. Catégorie 1 de la production : servie de 0 à 1 an ; à partir d'1 an, refus (art. 49 : passage au degré 1 de la
   catégorie 2, non calculé).
4. Case illisible (`cellules_source_manquante`, D48) : tableau n° 1 (p.21), ligne 6, colonne 8 (« 787.:77 »).
5. Primes couvertes : `prime_transport` (art. 53 (جديد), seul groupe `execution_gestion`, 3 dates), `prime_panier`
   (art. 54 (جديد), 0,875 par jour, condition), `prime_deplacement_retour_20h` (2 dinars) et
   `prime_deplacement_avec_nuitee` (7 dinars), `prime_scolaire` (art. 54 مكرر (جديد)), `prime_risque` (54-3),
   `prime_salete` (54-4), `prime_presence` (art. 55 (جديد), 3 dates ; 2024 : 11,600 lu à 170 et 300 dpi),
   `prime_caisse_caissier` et `prime_caisse_aide_caissier` (art. 56 (جديد)).
6. `SOURCE_MANQUANTE` : `prime_transport_cadres` (aucune catégorie désignée comme cadre),
   `prime_deplacement_promoteurs_livreurs` (accord d'entreprise), `avantage_lait` (54-5, en nature),
   `prime_production` (57), `aide_deces` (58, montant mixte), `prime_depart_retraite` (59).

**Mise en œuvre** : `cosmetiques_parfums.json` ; `test_vague1.py` ; démos 77 à 83 ; TB-156 à TB-162.

**Statut de vérification** : 507 cellules en double lecture (0 écart, 1 case non tranchée déclarée illisible), lots
validés par DS5 (2026-11-10). Cas du jeu de référence : en attente de vérification humaine.

**Communs à D49 à D54** : les 6 secteurs sont activés dans le registre DS5 sans entrée dans la table des secteurs, en
attente de validation DS2 (noms, codes et alias) ; seule exemption du test `test_chaque_secteur_ds5_disponible_figure_une_fois`
(liste `EN_ATTENTE_DS2`, qui exige aussi leur absence de la table) ; table des secteurs et D30 non modifiés ; textes arabes des libellés de primes et de populations saisis depuis l'image, libellés de catégorie,
messages et hypothèses rédigés (`libelle_ar_redige`) ; note des tableaux (décrets 437/1981 et 501/1982) reprise en
remarque, sans calcul.

---

### D55 — Grille salariale SAVONNERIE_RAFFINAGE_GRIGNONS (pages 2-3, 12-22)

**Numéro** : D55, à la suite de D54 ; `origin/main` (8f9d345) s'arrête à D54 et aucune branche distante n'utilise D55 à
D69 (vérifié avec `git fetch origin` le 2026-11-11). D55 à D60 forment la vague 2, dans l'ordre du triage.

**Source** : `data/raw/pdf/صناعة الصابون والتكرير واستخراج الزيت من الفيتورة.pdf` (22 pages). Grilles sans couche texte
(scans pivotés) ; textes lus sur les images, chiffres des articles confirmés par la couche texte. Pages : p.2-3, art. 24
à 39-4 (p.12-16), classification (p.17-19), tableaux n° 1 à 3 (p.20-22).

**Lecture** : un tableau par date (2021-12-01, 2023-01-01, 2024-01-01), 13 lignes imprimées (I à V, V مكرر, VI à XII) ×
12 degrés = 468 montants ; lignes I à V مكرر en montants horaires, lignes VI à XII en montants mensuels.

#### Décisions (validées par DS5)

1. Deux populations découpées dans le même tableau imprimé : `horaires` (I à V_bis, TND/heure) et `mensuels` (VI à XII,
   TND/mois), population obligatoire. L'art. 26 (p.12) dit seulement que l'échelle fixe les salaires « horaires ou
   mensuels » selon la catégorie et le degré : l'unité est celle de la ligne imprimée ; le rattachement des fonctions
   des annexes (p.17-19) aux lignes n'est pas modélisé (hypothèse affichée).
2. Degrés (art. 28 (جديد), p.12) : 1 an aux degrés 1 à 3, 2 ans ensuite ; libellés « 0-1 » … « 19-21 » ; bornes exactes
   refusées (D6) ; **à partir de 21 ans, refus** : le passage dans l'échelle de la catégorie suivante et le degré
   supplémentaire avant la retraite ne sont pas calculés.
3. Primes couvertes : `prime_transport` (art. 32 (جديد), `execution_gestion` / `cadres`, 3 dates), `prime_presence`
   (art. 32 مكرر (جديد), 3 dates), `prime_salete` (art. 35 (جديد), 0,022 par heure, condition de poste), `prime_caisse`
   (art. 35 مكرر (جديد), 48,333), `prime_risque` (art. 38 (جديد), 10 dinars, condition de poste),
   `prime_scolaire_enseignement_base`, `_secondaire`, `prime_scolaire_etudiant` (art. 39-3 (جديد)),
   `prime_aid_el_fitr` et `prime_aid_el_adha` (art. 39-4 (جديد)). Montants sans date servis tels qu'imprimés (comme D4).
4. `SOURCE_MANQUANTE` : `prime_panier` (art. 37 مكرر, montant de base absent), `prime_anciennete` (art. 30, comprise dans
   la grille), `prime_travail_nuit` (art. 31, 35 %), `prime_production` (art. 34), `avantage_lait` (art. 36),
   `avantage_savon` (art. 37), `prime_depart_retraite` (art. 39 مكرر (1)), `aide_deces` (art. 39 مكرر (2)).
5. Remarque : fonds social de l'art. 39 (7 + 7 dinars par mois), cotisation, ni salaire ni prime.

**Mise en œuvre** : `savonnerie_raffinage.json` ; `test_vague2.py` ; démos 84 à 90 ; TB-163 à TB-169.

**Statut de vérification** : 468 cellules en double lecture (0 écart), lots validés par DS5 (2026-11-11). Cas du jeu de
référence : en attente de vérification humaine.

---

### D56 — Grille salariale COMMERCE_DISTRIBUTION_PETROLE (pages 2-3, 7-10, 15-17, 19-20)

**Source** : `data/raw/pdf/تجارة و توزيع النفط و جميع مشتقاته.pdf` (20 pages). Pages : p.2-3, art. 8 (p.7), art. 13
(جديد) (p.9), art. 17 (جديد) (p.10), art. 43 et 44 (جديد) (p.15-17), tableaux n° 1 à 3 (p.19-20).

**Lecture** : 3 tableaux (2021-12-01 p.19 ; 2023-01-01 et 2024-01-01 p.20), 14 lignes (catégories 1 à 5 divisées en
rangs) × 14 colonnes (« - » puis degrés 1 à 13) = 588 montants, imprimés « 1 285,125 ».

#### Décisions (validées par DS5)

1. Population unique `tous_agents` ; clé = catégorie et rang imprimé (`sous_categorie` 1 à 4, de haut en bas),
   sous-catégorie obligatoire. **Unité TND/mois en hypothèse affichée** (non imprimée).
2. Colonne « - » (durée imprimée 1) lue comme l'année d'entrée (0-1 an), puis degré 1 de 1 à 2 ans (hypothèse
   affichée) ; durées 1, 1, 2 (×6), 3 (×6) : libellés « 0-1 » … « 29-32 » ; **à partir de 32 ans, refus** (art. 13 (جديد),
   p.9, rien au-delà). Progression exceptionnelle (note ≥ 18/20) non calculée.
3. Primes couvertes : `prime_transport` (art. 43 (جديد), 3 dates), `prime_presence` (art. 44-12, 3 dates),
   `prime_caisse_chauffeurs` (10 d) et `prime_caisse_caissiers` (20 d, en toutes lettres) (art. 44-2),
   `prime_scolaire_base_1_6`, `_base_7_9`, `_secondaire`, `_superieur` (art. 44-7 : 32, 37, 42, 52 d), `prime_risque`
   (art. 44-10, 15 d), `prime_standard_telephonique` (art. 44-11, 10 d).
4. `SOURCE_MANQUANTE` : `prime_responsabilite` (art. 44-6, montant de départ absent), `prime_productivite` (art. 8),
   `prime_13e_mois`, `aide_deces`, `avantage_proprete`, `avance_maladie`, `prime_depart_retraite`, `prime_production`
   (art. 44).

**Mise en œuvre** : `distribution_petrole.json` ; `test_vague2.py` ; démos 91 à 97 ; TB-170 à TB-176.

**Statut de vérification** : 588 cellules en double lecture (0 écart), lots validés par DS5 (2026-11-11). Cas du jeu de
référence : en attente de vérification humaine.

---

### D57 — Grille salariale PLASTURGIE (pages 2-3, 8-10, 14-16, 22-24)

**Source** : `data/raw/pdf/صناعة وتحويل البلاستيك.pdf` (24 pages). Pages : p.2-3, art. 13 (جديد) (p.8), art. 17 (p.9),
art. 46 à 51 (p.14-16), tableaux n° 1 à 6 (p.22-24).

**Lecture** : 6 tableaux, 3 dates × 2 populations imprimées : employés et cadres de maîtrise 8 × 16, ouvriers payés à
l'heure 6 × 16 = 672 montants, imprimés à la virgule.

#### Décisions (validées par DS5)

1. Populations `employes_maitrise` (TND/mois) et `ouvriers_horaires` (TND/heure), obligatoires.
2. Degrés : 16 de 2 ans (« 0-2 » … « 30-32 ») ; **à partir de 32 ans, refus** ; le passage dans l'échelle suivante
   (art. 13 (جديد) أ) n'est pas calculé. Remarque : l'art. 47 (p.14) annonce 14 degrés ; les tableaux, qui en impriment
   16, sont servis tels qu'imprimés.
3. Primes couvertes (art. 48 (جديد), p.14-15) : `prime_presence` (3 dates), `prime_presence_complement_sans_panier`
   (2 d, en toutes lettres, condition), `prime_panier` (13,086 par mois, condition), `prime_caisse` (22 d),
   `prime_transport` (`execution_gestion` / `cadres`, 3 dates), `prime_deplacement_dejeuner`, `_diner` (5,466) et
   `_logement` (5,600) (condition : plus de 50 km), `prime_scolaire` (10 d par élève).
4. `SOURCE_MANQUANTE` : `prime_production` (art. 49), `prime_depart_retraite` (art. 51), `indemnite_fin_service`
   (art. 17).

**Mise en œuvre** : `plasturgie.json` ; `test_vague2.py` ; démos 98 à 103 ; TB-177 à TB-182.

**Statut de vérification** : 672 cellules en double lecture (0 écart), lots validés par DS5 (2026-11-11). Cas du jeu de
référence : en attente de vérification humaine.

---

### D58 — Grille salariale MINOTERIES (pages 2-3, 8-9, 15-22)

**Source** : `data/raw/pdf/مطاحن.pdf` (22 pages). Pages : p.2-3, art. 14 (جديد) (p.8-9), art. 49 à 58 (p.15-16),
classification (p.17-19), tableaux n° 1 à 6 (p.20-22).

**Lecture** : 6 tableaux, 3 dates × 2 populations imprimées : agents payés à l'heure (I à V) et au mois (1 à 11), degrés
imprimés 0 à 13 = 672 montants.

#### Décisions (validées par DS5)

1. Populations `horaires` (TND/heure) et `mensuels` (TND/mois), obligatoires.
2. Degrés : durée 1 au degré 0, puis 2 ; libellés « 0-1 » … « 23-25 », « 25+ » (degré 13 atteint à 25 ans).
3. **Art. 14 (جديد) أ (p.8)** : seules les catégories V (horaires) et 11 (mensuels) reçoivent tous les 2 ans l'écart
   entre les degrés 13 et 12 (règle D10, période 2) ; paliers 27, 29… refusés (`PARAM_INVALIDE`). Les 14 autres
   catégories passent à la catégorie supérieure (promotion non calculée) : `cases_refusees` (D48, 42 cases) ; le degré
   13 est servi de 25 à 27 ans pour toutes, puis refusé (`SOURCE_MANQUANTE`) pour elles. Correction de l'ARRÊT 1 (Q9) :
   le premier écart vient à 27 ans (2 ans après le degré 13), et non à 29 ans.
4. Primes couvertes : `prime_productivite` (art. 49 (جديد), 10 d par semestre, en toutes lettres), `prime_production`
   (art. 53 (جديد), 10 d par mois), `prime_presence` et `prime_panier` (art. 54 (جديد), 3 dates), `prime_transport`
   (art. 55 (جديد), 3 dates), `prime_logement` (art. 56 مكرر (جديد), 3 dates).
5. `SOURCE_MANQUANTE` : `prime_caisse` (art. 56, renvoi à la législation), `prime_depart_retraite` et `aide_deces`
   (art. 50), `avantages_nature` (art. 51), `prime_fin_annee` (art. 52).

**Mise en œuvre** : `minoteries.json` ; `test_vague2.py` ; démos 104 à 109 ; TB-183 à TB-188.

**Statut de vérification** : 672 cellules en double lecture (0 écart), lots validés par DS5 (2026-11-11). Cas du jeu de
référence : en attente de vérification humaine.

---

### D59 — Grille salariale TEINTURERIES_PRESSINGS (pages 2-3, 9-12, 14, 17, 19-22)

**Source** : `data/raw/pdf/مصابغ ومعامل التنظيف.pdf` (22 pages). Pages : p.2-3, art. 16 à 30 (p.9-12), art. 39 (p.14),
art. 57 (p.17), classification (p.19), tableaux n° 1 à 6 (p.20-22).

**Lecture** : 6 tableaux, 3 dates × 2 populations imprimées : agents d'exécution (6 catégories, horaires) et agents
administratifs et techniciens (10 catégories, mensuels) × 14 degrés = 672 montants.

#### Décisions (validées par DS5)

1. Populations `execution` (TND/heure) et `administratifs_techniciens` (TND/mois), obligatoires.
2. Ancienneté effective imprimée « 1-0 » … « 23-21 », « 23 + » : libellés « 0-1 » … « 21-23 », « 23+ » (dernier degré
   ouvert, D29) ; promotion automatique au dernier degré (art. 30 (جديد) ب) non calculée.
3. Primes couvertes : `prime_transport` (art. 20 (جديد), `execution_gestion` / `cadres`, 3 dates), `prime_panier`
   (art. 21 (جديد), 700 millimes par jour, en toutes lettres, condition), `prime_caisse` (art. 22 (جديد), 22 d ; phrase
   sur le minimum de 21,666 en note), `prime_presence` (art. 23 (جديد), 3 dates), `prime_etudes_jardin_enfants`,
   `_enseignement_base`, `_enseignement_secondaire`, `_enseignement_superieur` (art. 24 (جديد) ; plafond de 93,333 en
   note, non calculé).
4. `SOURCE_MANQUANTE` : `prime_lait_salete` (art. 23 مكرر), `prime_assiduite` (art. 25), `prime_production` (art. 26),
   `aide_deces` (art. 27), `prime_depart_retraite` (art. 28), `indemnite_licenciement` (art. 57).

**Mise en œuvre** : `teintureries_pressings.json` ; `test_vague2.py` ; démos 110 à 115 ; TB-189 à TB-194.

**Statut de vérification** : 672 cellules en double lecture (0 écart), lots validés par DS5 (2026-11-11). Cas du jeu de
référence : en attente de vérification humaine.

---

### D60 — Grille salariale BOISSONS_GAZEUSES (pages 2-3, 8, 14-22)

**Source** : `data/raw/pdf/معامل المشروبات الغازية غير الكحولية.pdf` (22 pages, scan moyen). Pages : p.2-3, art. 14
(جديد) (p.8), art. 45 à 51-8 (p.14-17), classification (p.18-19), tableaux n° 1 à 6 (p.20-22).

**Lecture** : 6 tableaux, 3 dates × 2 populations imprimées : ouvriers payés à l'heure (6 catégories) et au mois (9) ×
15 degrés = 675 montants.

#### Décisions (validées par DS5)

1. Populations `horaires` (TND/heure) et `mensuels` (TND/mois), obligatoires.
2. Degrés (art. 14 (جديد), p.8, et en-tête) : 1 an aux degrés 1-2, 2 ans aux degrés 3-13, 3 ans aux degrés 14-15 ;
   libellés « 0-1 » … « 27-30 » ; **à partir de 30 ans, refus**. Remarque : les art. 46 (p.14) et 48 (p.16) annoncent
   11 et 14 degrés ; les tableaux, qui en impriment 15, sont servis tels qu'imprimés.
3. **Cases illisibles** (`cellules_source_manquante`, D48), colonne 8, chiffre cassé à l'impression, relues à 400 dpi :
   tableau n° 1 (p.20) ligne 5 ; tableau n° 3 (p.21) ligne 2 ; tableau n° 4 (p.21) ligne 1 ; tableau n° 5 (p.22)
   ligne 5 ; tableau n° 6 (p.22) lignes 4 et 7.
4. Primes couvertes : `prime_dix_ans_entreprise` (art. 14 (جديد), dernier alinéa, 15 d par mois, condition ; libellé
   arabe rédigé), `prime_transport` (art. 51 (جديد), `execution_gestion` / `cadres`, 3 dates), `prime_froid` (art. 51-3,
   2 d par semaine ; plafond de 8 d par mois en note), `prime_scolaire_enseignement_base` et
   `prime_scolaire_secondaire_superieur` (art. 51-4 (جديد)), `prime_presence` (art. 51-8, 3 dates).
5. `SOURCE_MANQUANTE` : `prime_panier` (art. 51 مكرر, 0,367 sans période), `prime_risque` (art. 51-2, 5 %),
   `prime_production` (art. 45, 10 %), `prime_productivite` (art. 51-5), `prime_fin_annee` (art. 51-6, 4 %),
   `prime_depart_retraite` (art. 49).

**Mise en œuvre** : `boissons_gazeuses.json` ; `test_vague2.py` ; démos 116 à 122 ; TB-195 à TB-201.

**Statut de vérification** : 675 cellules en double lecture (0 écart, 6 cases non tranchées déclarées illisibles), lots
validés par DS5 (2026-11-11). Cas du jeu de référence : en attente de vérification humaine.

**Communs à D55 à D60** : aucun changement de `calc/` ni de schéma (champs de D48 seulement) ; les 6 secteurs sont
activés dans le registre DS5 sans entrée dans la table des secteurs, en attente de validation DS2 (liste
`EN_ATTENTE_DS2` du test `test_chaque_secteur_ds5_disponible_figure_une_fois`) ; titres des conventions repris des pages
de titre (p.1) ; libellés de catégorie, messages et hypothèses rédigés (`libelle_ar_redige`) ; note des tableaux
(décrets 437/1981 et 501/1982) reprise en remarque, sans calcul.

---

### D61 — Grille salariale MECANIQUE_STATIONS_SERVICE (pages 3, 8-9, 11, 16-17, 22-24)

**Numéro** : D61, à la suite de D60 ; `origin/main` (a4294a0) s'arrête à D60 et aucune branche distante n'utilise D61 à
D69 (vérifié avec `git fetch origin` le 2026-11-11). D61 à D66 forment la vague 3, dans l'ordre du triage.

**Source** : `data/raw/pdf/ميكانيك العام و محطات بيع الوقود.pdf` (24 pages). Grilles sans couche texte (scans
pivotés) ; textes lus sur les images, chiffres des articles confirmés par la couche texte. Pages : avenant n° 10 (p.3,
effet au 2021-12-01), art. 12-13 (p.8), art. 17 (جديد) (p.9), art. 27 (جديد) (p.11), art. 48 à 54 مكرر (p.16-17),
tableaux n° 1 à 3 (p.22-24).

**Lecture** : 3 tableaux (2021-12-01, 2023-01-01, 2024-01-01) × 16 catégories × 15 degrés = 720 montants.

#### Décisions (validées par DS5)

1. Population unique `tous_agents`, catégories `1` à `16` (exécution 1-7, gestion 8-11, cadres 12-16).
2. **Unité non imprimée : TND/heure en hypothèse affichée**, pour toutes les catégories, cadres compris (montants de
   2,737 à 11,096 ; Q2, comme le café).
3. Degrés (art. 17 (جديد) أ et en-tête) : 15 degrés de 2 ans, libellés « 0-2 » … « 28-30 » ; **à partir de 30 ans,
   refus** (`SOURCE_MANQUANTE`, art. 17 p.9 : passage au barème de la catégorie suivante, non calculé).
4. Primes couvertes : `prime_transport` et `prime_presence` (art. 51 et 52 (جديد), `execution_gestion` / `cadres`, 3
   dates), `prime_fonction_*` (art. 50 : 50, 40, 35 et 25 d, un code par montant, Q3), `prime_continuite_travail`
   (art. 54 (جديد), 0,500 d par jour, condition), `prime_specifique` (art. 54 مكرر, 4 d par mois, condition).
5. `SOURCE_MANQUANTE` : `prime_productivite` (art. 13), `prime_fin_annee` (art. 48, formule), `prime_gestion_fonds`
   (art. 49) et `prime_courtage` (art. 53), fixées par l'employeur.

**Mise en œuvre** : `mecanique_stations_service.json` ; `test_vague3.py` ; démos 123 à 129 ; TB-202 à TB-208.

**Statut de vérification** : 720 cellules lues en double lecture indépendante sur image (rendus à 200 et 280 dpi, saisie dans deux ordres) et comparées
par script : 0 écart, 0 cellule douteuse ; contrôle de hausse entre deux dates voisines (montant fixe par ligne) sur 720 cellules comparables : aucun
écart au-delà de 1 millime ; montants des primes lus sur l'image et confirmés par les chiffres de la couche texte.
Vérifié par DS5 sur les images, aucune correction : les 108 montants de primes servis, dont les 9 montants en toutes lettres ; les 43 cas TB-202 à TB-244, avec la page, la ligne et la colonne de chacun ; chez les déchets, les 2 cellules retenues au zoom (1 367.052 et 1 149.697) et la cellule de la ligne 8 degré 3 sur les quatre tableaux ; la cellule de l'habillement tranchée au zoom (1 114,395) ; la première et la dernière ligne d'un lot par secteur, avec leurs libellés. Les autres cellules des grilles reposent sur la double lecture et sur le contrôle de hausse, sans relecture humaine cellule par cellule.

---

### D62 — Grille salariale BOISSONS_ALCOOLISEES (pages 3, 8, 14-15, 21-23)

**Source** : `data/raw/pdf/صناعة وتجارة المشروبات الكحولية.pdf` (23 pages). Pages : avenants (p.3), art. 15 (جديد)
(p.8), art. 49 à 53 ثالثا (p.14-15), tableaux n° 1 à 6 (p.21-23).

**Lecture** : 6 tableaux, 3 dates × 2 populations imprimées : travailleurs payés au mois (catégories I à X) et à l'heure
(6 rangs nommés) × 15 degrés = 720 montants (le triage annonçait 765 : 16 lignes par date, et non 17).

#### Décisions (validées par DS5)

1. Populations `mensuels` (TND/mois, `I` à `X`) et `horaires` (TND/heure, six rangs, clés en français, libellés arabes
   imprimés), obligatoires.
2. Degrés : durées imprimées 1, 2 (×9), 3 (×5), soit 34 ans ; libellés « 0-1 », « 1-3 » … « 31-34 » ; **à partir de 34
   ans, refus** (Q4 : l'art. 52 (جديد) ne dit rien au-delà de « la fin de 31 ans »).
3. Primes couvertes : `prime_presence` (art. 53-1, 3 dates), `prime_transport` (art. 53-2) et `prime_logement` (art. 53
   مكرر), cinq groupes chacune (`execution`, `gestion_moyenne`, `gestion_superieure`, `cadres_moyens`,
   `cadres_superieurs`, 3 dates), `prime_rentree_scolaire_*` (art. 49 مكرر, 20 / 30 / 30 d, montants en toutes
   lettres), `prime_responsabilite` (art. 53 ثالثا, 50 d), `prime_haute_specialisation` (art. 15 (جديد), 15 d).
4. `SOURCE_MANQUANTE` : `prime_transport_niveau_salaire_minimum` et `prime_logement_niveau_salaire_minimum` (groupe non
   défini, comme les pâtes, Q5) ; **`prime_panier`** (art. 53-3 : « 416.666 م » par jour, montant à plus de trois
   décimales, non arrondi, Q6) ; `prime_production_fin_annee` (art. 50, pourcentages) ; `prime_fin_carriere` (art. 49).

**Mise en œuvre** : `boissons_alcoolisees.json` ; `test_vague3.py` ; démos 130 à 136 ; TB-209 à TB-215.

**Statut de vérification** : 720 cellules lues en double lecture indépendante sur image (rendus à 200 et 280 dpi, saisie dans deux ordres) et comparées
par script : 0 écart, 0 cellule douteuse ; contrôle de hausse entre deux dates voisines (montant fixe par ligne) sur 720 cellules comparables : aucun
écart au-delà de 1 millime ; montants des primes lus sur l'image et confirmés par les chiffres de la couche texte (montants écrits en toutes lettres : lus sur l'image seulement).
Vérifié par DS5 sur les images, aucune correction : les 108 montants de primes servis, dont les 9 montants en toutes lettres ; les 43 cas TB-202 à TB-244, avec la page, la ligne et la colonne de chacun ; chez les déchets, les 2 cellules retenues au zoom (1 367.052 et 1 149.697) et la cellule de la ligne 8 degré 3 sur les quatre tableaux ; la cellule de l'habillement tranchée au zoom (1 114,395) ; la première et la dernière ligne d'un lot par secteur, avec leurs libellés. Les autres cellules des grilles reposent sur la double lecture et sur le contrôle de hausse, sans relecture humaine cellule par cellule.

---

### D63 — Grille salariale BOIS_AMEUBLEMENT_LIEGE (pages 3, 9, 16-18, 24-26)

**Source** : `data/raw/pdf/صناعة الخشب والموبيليا والخفاف.pdf` (26 pages). Pages : avenants (p.3), art. 14 (جديد)
(p.9), art. 50 à 62 (p.16-18), tableaux n° 1 à 6 (p.24-26).

**Lecture** : 6 tableaux, 3 dates × 2 populations imprimées : mensuels (catégories 1 à 14, régime de 40 h imprimé) et
horaires (7 rangs nommés) × 13 degrés = 819 montants.

#### Décisions (validées par DS5)

1. Populations `mensuels` (TND/mois, `1` à `14`) et `horaires` (TND/heure, `1` à `7`, l'art. 14 parlant du « صنف
   السابع » des horaires), obligatoires.
2. Degrés : ancienneté effective imprimée « 1-0 » … « 26-23 », « 26 + » ; durées 1, 1, 1, 2 (×4), 3 (×5), 1.
3. **Degré 13 (Q7, règle de la confiserie)** : l'en-tête imprime « 26 + », l'art. 50 (جديد) (p.16) limite le séjour au
   degré 13 à un an et l'art. 14 (جديد) أ (p.9) fait passer l'agent dans l'échelle suivante. Le degré 13 est servi de 26
   à 27 ans ; **27 ans pile : `PARAM_INVALIDE`** ; au-delà, refus `SOURCE_MANQUANTE` citant les pp. 9, 16 et 24-26.
   Représentation : règle `table_correspondance` sans case cible, toutes les catégories refusées (comme la catégorie 19
   du BTP, D10). `anciennetes_refusees` (D48) n'est pas utilisé : il servirait le palier exact au lieu de le refuser.
4. Primes couvertes : `prime_transport` (art. 54, 3 dates), `prime_presence` (art. 58, 3 dates, condition),
   `prime_panier` (art. 55, 0,650 d par jour), primes de déplacement de l'art. 57 (transport 1 ou 2 d selon le rayon de
   40 km, petit-déjeuner 1 d, dîner 3 d, nuitée 9 d ; chauffeurs : petit-déjeuner 1 d, dîner 3 d, nuitée 7 d),
   `prime_caisse_degre_1` et `_2` (art. 59, 6 et 10 d), `prime_risque` (art. 61 مكرر, 11 d).
5. `SOURCE_MANQUANTE` : **`aide_deces`** (art. 61 : « 466.6666 د », montant à plus de trois décimales, non arrondi, Q6) ;
   `avantage_lait` (art. 56, nature) ; `prime_production_fin_annee` (art. 60, pourcentages) ; `prime_depart_retraite`
   (art. 62).

**Mise en œuvre** : `bois_ameublement_liege.json` ; `test_vague3.py` ; démos 137 à 143 ; TB-216 à TB-222.

**Statut de vérification** : 819 cellules lues en double lecture indépendante sur image (rendus à 200 et 280 dpi, saisie dans deux ordres) et comparées
par script : 0 écart, 0 cellule douteuse ; contrôle de hausse entre deux dates voisines (montant fixe par ligne) sur 819 cellules comparables : aucun
écart au-delà de 1 millime ; montants des primes lus sur l'image et confirmés par les chiffres de la couche texte (montants écrits en toutes lettres : lus sur l'image seulement).
Vérifié par DS5 sur les images, aucune correction : les 108 montants de primes servis, dont les 9 montants en toutes lettres ; les 43 cas TB-202 à TB-244, avec la page, la ligne et la colonne de chacun ; chez les déchets, les 2 cellules retenues au zoom (1 367.052 et 1 149.697) et la cellule de la ligne 8 degré 3 sur les quatre tableaux ; la cellule de l'habillement tranchée au zoom (1 114,395) ; la première et la dernière ligne d'un lot par secteur, avec leurs libellés. Les autres cellules des grilles reposent sur la double lecture et sur le contrôle de hausse, sans relecture humaine cellule par cellule.

---

### D64 — Grille salariale GESTION_DECHETS (pages 2, 6, 12-13, 16-19)

**Source** : `data/raw/pdf/التصرف في النفايات الصلبة.pdf` (19 pages). Pages : avenants (p.2), art. 12 (جديد) (p.6),
art. 38 et 39 (p.12-13), tableaux n° 1 à 4 (p.16-19).

**Lecture** : 4 tableaux (du 2020-05-01 au 2021-11-30, puis 2021-12-01, 2023-01-01, 2024-01-01) × 19 catégories × 11
degrés = 836 montants, imprimés au format « 1,018.107 ».

#### Décisions (validées par DS5)

1. Population unique `tous_agents`, catégories `1` à `19` (art. 39 : exécution 1-6, gestion 7-12, cadres 13-19).
2. **Unité non imprimée : TND/mois en hypothèse affichée** (montants de 628,015 à 2 027,015).
3. Dates : refus avant le 2020-05-01 (la grille de l'avenant n° 3, effet au 2018-06-01, n'est pas dans la source). La
   date de fin imprimée du tableau n° 1 est suivie le lendemain par le tableau n° 2 : aucun `valide_jusqu_au`.
4. Degrés : ancienneté imprimée « 2-0 » … « 24-21 », « +24 ». **Dernier degré (Q8, Q-A)** : l'art. 12 (جديد) (p.6) fait
   continuer la progression « pendant une durée correspondant à deux degrés », sans montant, et fixe des séjours de 2 ou
   3 ans. Degré 11 servi de 24 à 26 ans ; **26 ans pile : `PARAM_INVALIDE`** ; au-delà, refus `SOURCE_MANQUANTE` citant
   la p.6 et l'en-tête. Même représentation que D63.
5. **Cases illisibles** (`cellules_source_manquante`, D48), toutes au degré 9, chiffre cassé à l'impression, relues à
   400 dpi : tableau n° 1 (p.16) lignes 10 et 11 ; n° 2 (p.17) lignes 13, 14 et 16 ; n° 3 (p.18) lignes 3, 11, 13 et
   14 ; n° 4 (p.19) lignes 8, 13, 16 et 18. Ligne 8, degré 3 : montant supérieur aux degrés 2 et 4 sur les quatre
   tableaux, imprimé net, servi tel quel.
6. Primes couvertes : `prime_presence` et `prime_transport` (art. 38, 4 dates), `prime_panier` (25 d par mois),
   `prime_risque` (50 d), `prime_proprete_savon` (70 d), avec condition.
7. `SOURCE_MANQUANTE` : **`prime_lait`** (35 d, entrée en vigueur liée à la « parution » de l'avenant n° 3, qui porte
   plusieurs dates, Q9) ; `prime_productivite` (formule) ; `prime_13e_mois` (un mois de salaire).

**Mise en œuvre** : `gestion_dechets.json` ; `test_vague3.py` ; démos 144 à 151 ; TB-223 à TB-230.

**Statut de vérification** : 836 cellules lues en double lecture indépendante sur image (rendus à 200 et 280 dpi, saisie dans deux ordres) et comparées
par script : 0 écart ; 15 cellules douteuses du degré 9 relues au zoom à 400 dpi, 2 tranchées et 13 non tranchées déclarées illisibles ; contrôle de hausse entre deux dates voisines (montant fixe par ligne) sur 815 cellules comparables (8 cellules n'ont pour voisine qu'une cellule illisible) : aucun
écart au-delà de 1 millime ; montants des primes lus sur l'image et confirmés par les chiffres de la couche texte.
Vérifié par DS5 sur les images, aucune correction : les 108 montants de primes servis, dont les 9 montants en toutes lettres ; les 43 cas TB-202 à TB-244, avec la page, la ligne et la colonne de chacun ; chez les déchets, les 2 cellules retenues au zoom (1 367.052 et 1 149.697) et la cellule de la ligne 8 degré 3 sur les quatre tableaux ; la cellule de l'habillement tranchée au zoom (1 114,395) ; la première et la dernière ligne d'un lot par secteur, avec leurs libellés. Les autres cellules des grilles reposent sur la double lecture et sur le contrôle de hausse, sans relecture humaine cellule par cellule.

---

### D65 — Grille salariale HABILLEMENT (pages 3, 8, 15-16, 26-29)

**Source** : `data/raw/pdf/صناعة الملابس المنسوجة و الجاهزة.pdf` (29 pages). Pages : avenants (p.3, n° 17 : effet au
2021-09-01), art. 12 (جديد) (p.8), art. 45 à 50-4 (p.15-16), tableaux n° 1 à 4 (p.26-29).

**Lecture** : 4 tableaux, 2 dates (2021-09-01, 2022-05-01) × 2 populations imprimées : horaires (I à VI) et mensuels
(1 أ, 1 ب, 2 à 17) × 18 degrés = 864 montants.

#### Décisions (validées par DS5)

1. Populations `horaires` (TND/heure) et `mensuels` (TND/mois), obligatoires ; mensuels : catégorie `1` avec
   `sous_categorie` `a` (1 أ) ou `b` (1 ب), puis `2` à `17`.
2. Degrés : durées 1, 1, 1 puis 2 ; ancienneté effective 1, 2, 3, 5 … 33 ; libellés « 0-1 » … « 31-33 » ; **à partir de
   33 ans, refus** (art. 12 : promotion automatique non calculée). Aucune grille après le 2022-05-01 : la table de 2022
   reste appliquée.
3. Primes couvertes : `prime_presence` (art. 49-1, 2 dates), `prime_transport` (art. 49-2, `execution_gestion` /
   `cadres`, 2 dates).
4. `SOURCE_MANQUANTE` : **`prime_assiduite`** (art. 49, points 3 et 4 : imprimée deux fois avec des montants
   différents, Q10) ; `prime_production_fin_annee` (art. 46) ; `prime_depart_retraite` et `aide_deces` (art. 50 et 50-4,
   un mois de salaire).

**Mise en œuvre** : `habillement.json` ; `test_vague3.py` ; démos 152 à 157 ; TB-231 à TB-236.

**Statut de vérification** : 864 cellules lues en double lecture indépendante sur image (rendus à 200 et 280 dpi, saisie dans deux ordres) et comparées
par script : 1 écart, tranché au zoom à 400 dpi, 0 cellule douteuse ; contrôle de hausse entre deux dates voisines (pourcentage fixe par ligne) sur 864 cellules comparables : aucun
écart au-delà de 1 millime ; montants des primes lus sur l'image et confirmés par les chiffres de la couche texte.
Vérifié par DS5 sur les images, aucune correction : les 108 montants de primes servis, dont les 9 montants en toutes lettres ; les 43 cas TB-202 à TB-244, avec la page, la ligne et la colonne de chacun ; chez les déchets, les 2 cellules retenues au zoom (1 367.052 et 1 149.697) et la cellule de la ligne 8 degré 3 sur les quatre tableaux ; la cellule de l'habillement tranchée au zoom (1 114,395) ; la première et la dernière ligne d'un lot par secteur, avec leurs libellés. Les autres cellules des grilles reposent sur la double lecture et sur le contrôle de hausse, sans relecture humaine cellule par cellule.

---

### D66 — Grille salariale COMMERCE_GROS_DETAIL (pages 3, 8, 14-15, 22-27)

**Source** : `data/raw/pdf/تجارة الجملة ونصف الجملة و التفصيل.pdf` (27 pages). Pages : avenants (p.3), art. 12 (جديد)
(p.8), art. 45 à 49 مكرر (p.14-15), tableaux n° 1 à 6 (p.22-27).

**Lecture** : 6 tableaux, 3 dates × 2 tableaux imprimés : agents (ligne horaire et catégories 10 à 21, 13 lignes) et
sous-chefs de rayon, chefs de rayon et gérants (catégories 16 et 17 × sous-niveaux أ à هـ, 10 lignes) × 13 degrés = 897
montants.

#### Décisions (validées par DS5)

1. Populations `agents` et `chefs_rayon_gerants`, obligatoires (les numéros 16 et 17 existent dans les deux tableaux).
   Chefs : catégorie `16` ou `17` avec `sous_categorie` `a` à `e` (أ à هـ, imprimés en ordre décroissant).
2. **Unité non imprimée : TND/mois en hypothèse affichée.** Ligne « شغال بالساعة » (Q11) : servie telle qu'imprimée
   (clé `ouvrier_horaire_ligne_imprimee`), l'hypothèse affichée rappelle que l'unité n'est pas imprimée et que la case
   porte la mention « (شهريا) » ; elle n'est pas affirmée mensuelle.
3. Degrés : 13 degrés de 2 ans, ancienneté effective 2 … 26 ; libellés « 0-2 » … « 22-24 », « 24+ ». **Art. 12 (جديد) أ
   (Q12, comme les minoteries)** : catégorie 21, écart entre les degrés 13 et 12 tous les 2 ans à partir de 26 ans
   (écart cumulé, D10, période 2) ; le chiffre imprimé (16,686 d) est égal à l'écart des trois tableaux ; paliers exacts
   (26, 28… ans) : `PARAM_INVALIDE` ; autres catégories des deux tableaux refusées au-delà de 26 ans (`cases_refusees`).
4. Primes couvertes : `prime_transport` (art. 48, `execution_gestion` / `cadres`, 3 dates), `prime_presence` (art. 48
   مكرر, 3 dates), `prime_caisse_*` (art. 47 : 5, 10 et 15 d selon l'ancienneté), `prime_scolaire_*` (art. 47 مكرر :
   20, 30 et 40 d), `prime_deces_travailleur` (150 d) et `prime_deces_pere_mere` (100 d, art. 45-3).
5. `SOURCE_MANQUANTE` : `prime_depart_retraite` (art. 45 مكرر, 4 mois), `prime_productivite` (art. 49, pourcentages),
   `prime_fin_annee` (art. 49 مكرر, demi-mois).

**Mise en œuvre** : `commerce_gros_detail.json` ; `test_vague3.py` ; démos 158 à 165 ; TB-237 à TB-244.

**Statut de vérification** : 897 cellules lues en double lecture indépendante sur image (rendus à 200 et 280 dpi, saisie dans deux ordres) et comparées
par script : 0 écart, 0 cellule douteuse ; contrôle de hausse entre deux dates voisines (montant fixe par ligne) sur 897 cellules comparables : aucun
écart au-delà de 1 millime ; montants des primes lus sur l'image et confirmés par les chiffres de la couche texte.
Vérifié par DS5 sur les images, aucune correction : les 108 montants de primes servis, dont les 9 montants en toutes lettres ; les 43 cas TB-202 à TB-244, avec la page, la ligne et la colonne de chacun ; chez les déchets, les 2 cellules retenues au zoom (1 367.052 et 1 149.697) et la cellule de la ligne 8 degré 3 sur les quatre tableaux ; la cellule de l'habillement tranchée au zoom (1 114,395) ; la première et la dernière ligne d'un lot par secteur, avec leurs libellés. Les autres cellules des grilles reposent sur la double lecture et sur le contrôle de hausse, sans relecture humaine cellule par cellule.

**Communs à D61 à D66** : contrôle de hausse sur 4 835 des 4 843 cellules lisibles, aucun écart au-delà de 1 millime ;
aucun changement de `calc/` ni de schéma (champs de D48 et règles D10 existantes) ; les 6
secteurs sont activés dans le registre DS5 sans entrée dans la table des secteurs, en attente de validation DS2 (liste
`EN_ATTENTE_DS2`) ; primes à montant fixe imprimé seulement, un code par montant sans date ; promotions, reclassements
et passages d'échelle non calculés, affichés en hypothèse ; libellés de catégorie, messages et hypothèses rédigés
(`libelle_ar_redige`), libellés des rangs repris de l'image ; note des tableaux (décrets 437/1981 et 501/1982) reprise
en remarque, sans calcul.
