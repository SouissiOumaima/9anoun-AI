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
7 avril 1981, modifié par le décret n° 501 du 16 mars 1982) ;
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
