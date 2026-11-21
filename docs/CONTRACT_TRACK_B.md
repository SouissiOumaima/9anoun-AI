# Contrat JSON Track B — v0

> **Statut : v0 — proposition Track B, à valider avec l'équipe.**
> Document de travail destiné à l'orchestrateur, à Track A (`track_a_legal`) et à
> toute personne qui appellera le module comptable. Le contrat peut changer après
> vos retours. Le détail des décisions se trouve dans
> [`docs/DECISIONS.md`](DECISIONS.md) (D6 : règles de calcul, D7 : contrat).

## 1. Résumé

Le Track B expose une fonction unique, `handle(request) -> response`, qui
reçoit une requête JSON de calcul de paie (droit du travail tunisien) et
renvoie une réponse JSON. Trois opérations sont calculées :
- le **salaire de base** conventionnel, selon la catégorie, l'ancienneté et la date ;
- une **prime** conventionnelle ;
- le **SMIG** non agricole.

La règle **« Citation ou Silence »** est vérifiée par le schéma de réponse
lui-même : une réponse `ok` contient toujours au moins une citation (PDF
source, page, fichier de données vérifié, entrée de `DECISIONS.md`). Si le
module ne peut pas citer de source, il ne renvoie aucun montant, mais un
refus explicite, motivé en français et en arabe.

## 2. Le contrat est-il générique à tous les secteurs ?

**Côté schéma, oui.** Le champ `params.secteur` est une chaîne libre, pas une
liste fermée. Ajouter un secteur ne demande donc aucune modification des
schémas JSON, et les appelants n'ont rien à changer.

**Côté code, pas encore entièrement.** Aujourd'hui, ajouter un secteur ne se
limite pas à déposer un fichier dans `data/processed/salary_grids/` :

1. **Registre des secteurs : réglé.** Les secteurs sont découverts
   automatiquement dans `data/processed/salary_grids/*.json`
   (`decouvrir_grilles`, `src/track_b_accounting/calc/loaders.py`) : un
   fichier est chargé s'il porte un `_meta.secteur_code` et un
   `_meta.decision_ref` valide (`D` suivi d'un nombre). Un fichier sans
   référence valide, illisible, ou dont le code est porté par un autre
   fichier est ignoré, et le secteur répond `SOURCE_MANQUANTE` comme un
   secteur inconnu. Ce n'est donc plus une limite.
2. **Structure des données supposée.** Le code s'appuie sur la structure du
   fichier métallurgie, étendue pour les associations pour personnes
   handicapées (D23) :
   - les tables sont rattachées à une population quand leurs catégories sont
     exactement celles de la population. Quand plusieurs populations ont les
     mêmes catégories, chaque table porte un champ `population` explicite,
     obligatoire dans ce cas. Exemple : dans
     `ASSOCIATIONS_PERSONNES_HANDICAPEES`, `education_specialisee` et `sport`
     ont toutes deux les lignes I, II et III ;
   - une population peut déclarer des alias de catégorie
     (`alias_categories`, ex. « 1 » → « I ») et des hypothèses de lecture de
     sa grille (`hypotheses_grille`, `hypotheses_categories`), renvoyées dans
     `detail` ;
   - les degrés sont déclarés **par population** (`degres.<population>`, liste
     vide pour une population sans degré) ; leurs intervalles sont lus dans
     des libellés de la forme `"0-2 ans"`, `"12-15"` et `"20+"` ;
   - une catégorie peut avoir des sous-catégories (`sous_categories`), une
     population ou une prime peut être déclarée non couverte
     (`populations_non_couvertes`, `primes_non_couvertes`) avec son texte
     de refus FR/AR dans le JSON ;
   - chaque population à degrés doit déclarer, dans
     `au_dela_dernier_degre.<population>`, ce que dit sa source au-delà du
     dernier degré (ancienneté maximale couverte, page, article et textes de
     refus FR/AR où seul `{a}` est remplacé) ; sans ce bloc, la grille est
     refusée (D8, D9). Une ancienneté maximale couverte de 0 refuse toute
     demande de salaire de base avec ce texte (grille sans durée de degré
     imprimée, D68) ; les primes du secteur restent servies. Avec `"regle": "ouvert"`, le dernier degré (libellé
     `"n+"`) est servi sans plafond ni extrapolation ; le bloc cite alors sa
     source (`source_pdf_page`, `source_article`, `texte_source_ar`),
     sinon la grille est refusée (D29) ;
   - un secteur à une seule population peut la laisser omettre dans la
     requête (D29) ;
   - les paramètres de prime dépendent de clés JSON précises (`montants`,
     `complement_si_prime_superieure`, `montant_reduit_si_transport_assure`,
     `condition`) ; une prime peut aussi porter des libellés de groupe
     (`libelles_groupes`), une mention de la source (`note`, `note_ar`) et des
     hypothèses (`hypotheses`), recopiés dans `detail`.

   Un secteur dont la grille ou les primes sont organisées autrement
   demandera une adaptation du code. Le schéma de requête n'a changé qu'une
   fois pour cela : `population` est facultative au schéma (D29), et calc/
   l'exige pour un secteur à plusieurs populations.

Le point 2 dépendra des grilles des autres conventions, qui ne sont pas encore
transcrites.

**Point réglé : la référence de vérification.** Le champ `decision_ref` des
citations (l'entrée de `DECISIONS.md` qui documente la vérification) est lu
dans le fichier du secteur (`_meta.decision_ref` : `"D4"` pour la métallurgie,
`"D9"` pour le BTP, `"D23"` pour les associations pour personnes handicapées).
Il n'est plus écrit en dur dans le code. Le SMIG suit la même règle : sa
référence est lue dans `smig_non_agricole.decision_ref` (`"D2"`) de
`smig_smag.json`. Chaque nouveau fichier de secteur
devra donc porter sa propre référence. Si le champ est absent ou mal formé
(format attendu : `D` suivi d'un nombre), le calcul est refusé
(`SOURCE_MANQUANTE`) : le module ne cite jamais une référence inventée.

## 3. Schémas

Les fichiers sources font foi :
- `data/mock_cards/schemas/track_b_request.v0.schema.json`
- `data/mock_cards/schemas/track_b_response.v0.schema.json`

Les deux sont au format JSON Schema draft 2020-12. Le schéma commun v0 des réponses de tous les tracks (statut, citation, refus), proposé à l'équipe, est [`src/shared/schemas/common.v0.schema.json`](../src/shared/schemas/common.v0.schema.json) : les réponses Track B y sont déjà conformes.

### 3.1 Requête

| Champ | Type | Description |
|---|---|---|
| `contract_version` | `"track_b.v0"` | Version du contrat ; toute autre valeur est refusée. |
| `request_id` | chaîne, 1 à 128 caractères | Identifiant choisi par l'appelant, renvoyé tel quel dans la réponse. |
| `operation` | `salaire_base` \| `prime` \| `smig` \| `cotisation_cnss` | Calcul demandé. `cotisation_cnss` est accepté par le schéma, mais toujours refusé (`HORS_SCOPE`, cf. §4). |
| `params` | objet | Paramètres de l'opération (tableaux ci-dessous). |
| `lang` | `fr` \| `ar` | Langue préférée de l'appelant. La réponse contient toujours les deux langues ; ce champ est surtout utile au formatage côté Track A. |

Aucun autre champ n'est accepté à la racine.

**`params` pour `salaire_base`** (aucun champ supplémentaire accepté) :

| Champ | Type | Description |
|---|---|---|
| `secteur` | chaîne | Code du secteur : `METALLURGIE_BATIMENT`, `BATIMENT_TRAVAUX_PUBLICS`, `ASSOCIATIONS_PERSONNES_HANDICAPEES`, `ASSURANCE`, `ENSEIGNEMENT_PRIVE`, `BANQUES`, `GARDIENNAGE_SECURITE_TRANSPORT_FONDS`, `TORREFACTION_CAFE`, `AGENCES_VOYAGES`, `HOTELS_TOURISTIQUES`, `CONFISERIE_BISCUITERIE_CHOCOLATERIE`, `PATES_ALIMENTAIRES_COUSCOUS`, `COSMETIQUES_PARFUMS` (vague 1, D49 à D54), `SAVONNERIE_RAFFINAGE_GRIGNONS`, `COMMERCE_DISTRIBUTION_PETROLE`, `PLASTURGIE`, `MINOTERIES`, `TEINTURERIES_PRESSINGS`, `BOISSONS_GAZEUSES` (vague 2, D55 à D60), `MECANIQUE_STATIONS_SERVICE`, `BOISSONS_ALCOOLISEES`, `BOIS_AMEUBLEMENT_LIEGE`, `GESTION_DECHETS`, `HABILLEMENT`, `COMMERCE_GROS_DETAIL` (vague 3, D61 à D66), `IMPRIMERIE_EDITION_CARTONNAGE`, `VERRE_MIROIRS`, `CONCESSIONNAIRES_MATERIEL_AGRICOLE`, `BOULANGERIES`, `TEXTILE` ou `FONDERIE_METALLURGIE_MECANIQUE` (vague 4, D67 à D72) ; voir §7. Obligatoire : une chaîne vide est refusée (`PARAM_INVALIDE`). |
| `population` | chaîne, selon le secteur | **Facultative au schéma (D29).** Obligatoire pour un secteur à plusieurs populations (tous les secteurs actuels sauf `ASSURANCE`, `BANQUES`, `GARDIENNAGE_SECURITE_TRANSPORT_FONDS`, `TORREFACTION_CAFE`, `AGENCES_VOYAGES`, `HOTELS_TOURISTIQUES`, `COMMERCE_DISTRIBUTION_PETROLE`, `MECANIQUE_STATIONS_SERVICE`, `GESTION_DECHETS` et `CONCESSIONNAIRES_MATERIEL_AGRICOLE`) : omise, elle est refusée (`PARAM_INVALIDE`, refus émis par calc/). Pour un secteur à une seule population, elle peut être omise ; si elle est donnée, elle doit être celle-là (sinon `PARAM_INVALIDE`), et `detail.population` la renvoie dans les deux cas. Métallurgie : `admin_tech` (grille mensuelle) ou `execution` (grille horaire). BTP : `admin_tech` (mensuelle) ou `ouvriers_occasionnels` (horaire, sans degré d'ancienneté) ; `ouvriers_permanents` est refusé (`SOURCE_MANQUANTE`, cf. §7). Associations pour personnes handicapées (toutes mensuelles, 16 degrés) : `education_specialisee` (أعوان التربية المختصون), `sport` (أعوان الرياضة), `ouvriers_administratifs_surveillants` (العملة والأعوان الإداريين و القيمين), `techniciens` (الأعوان الفنيين), `formateurs_professionnels` (المكونين المهنيين). Assurance : une seule population, `tous_agents` (كافة أعوان شركات التأمين), qui peut être omise. Enseignement privé (toutes mensuelles, 16 degrés) : `ouvriers`, `administratifs_surveillants`, `instituteurs`, `secondaire_formateurs`, `professeurs_primaire`. Banques : une seule population, `tous_agents` (أعوان البنوك والمؤسسات المالية), qui peut être omise. Gardiennage, sécurité et transport de fonds : une seule population, `tous_agents` (أعوان مؤسسات الحراسة والسلامة ونقل العملة), qui peut être omise ; la catégorie est le numéro « 1 » à « 15 » de la classification (pages 16 à 20 de la convention), sans alias par métier. |
| `categorie` | chaîne ou entier | Catégorie de la grille, ex. `"1B"`, `"4"`, `7`. Pour une catégorie à sous-catégories, donner la catégorie seule (ex. `6`) et préciser `sous_categorie`. Associations pour personnes handicapées : la clé est le chiffre romain imprimé sur la ligne de la grille (`"I"` à `"VI"` selon la population) ; le numéro de catégorie de l'annexe est accepté comme alias (`"1"` → `"I"`, `"2"` → `"II"`…), et `detail` renvoie `categorie` (clé) et `categorie_demandee` (alias reçu). Pour `techniciens`, seuls `"I"` (alias `"1"`) et `"III+II"` existent : `"III+II"` est une clé unique, et `"II"`, `"III"`, `"2"` ou `"3"` sont refusés (`PARAM_INVALIDE`), car l'annexe 4 ne confirme pas que les catégories 2 et 3 partagent cette ligne (D23). |
| `sous_categorie` | chaîne, optionnel | **Nouveau.** Obligatoire si la catégorie a des sous-catégories, refusé sinon (`PARAM_INVALIDE`). Seul cas actuel, BTP `ouvriers_occasionnels` : catégorie 6 → `"I"` ou `"II"` (ouvrier hautement qualifié I/II) ; catégorie 7 → `"1"`, `"2"` ou `"3"` (chef d'équipe 1er/2e/3e degré). Le libellé exact du PDF est renvoyé dans `detail` (`libelle_fr`, `libelle_ar`). |
| `anciennete_annees` | nombre, selon la population | **Désormais optionnel au schéma.** Obligatoire pour une population à degrés d'ancienneté (toutes, sauf BTP `ouvriers_occasionnels`), refusé pour une population sans degré (`PARAM_INVALIDE`). Une valeur exactement égale à une borne (métallurgie : 2, 4, …, 20 ; BTP : 2, …, 12, 15, 18, 21, 24) est refusée, car le PDF ne précise pas à quel degré elle appartient (D6). **Plus de plafond fixe** : au-delà du dernier degré, l'article 13 de chaque convention s'applique (D10, voir §7). Métallurgie : paliers exacts 22, 24, 26… ans refusés (`PARAM_INVALIDE`). BTP `admin_tech` : 27 ans pile refusé (`PARAM_INVALIDE`) ; au-delà de la fenêtre de la case cible (29 ou 30 ans selon la catégorie) et pour la catégorie 19, refus `SOURCE_MANQUANTE`. Associations pour personnes handicapées : le degré k couvre de 2k−2 à 2k ans (lecture affichée dans `detail.hypotheses`) ; bornes 2, 4, …, 30 refusées (`PARAM_INVALIDE`) ; à partir de 32 ans, refus `SOURCE_MANQUANTE`, car la convention ne prévoit rien au-delà du degré 16 (D23). |
| `date` | `AAAA-MM-JJ` | Date de calcul : la table appliquée est la plus récente dont la date d'effet est ≤ cette date. |
| `unite_souhaitee` | chaîne, optionnel | Si elle diffère de l'unité de la grille, la requête est refusée (`HORS_SCOPE`) : aucune conversion horaire ↔ mensuel n'est écrite dans les sources. |

**`params` pour `prime`** :

| Champ | Type | Description |
|---|---|---|
| `secteur` | chaîne | Code du secteur. |
| `code` | chaîne | Code de la prime. Métallurgie : `prime_transport`, `prime_presence`, `prime_logement`, `prime_panier_qefa`, `prime_deplacement_chantier`, `prime_travail_en_hauteur`. Associations pour personnes handicapées : `prime_transport`, `prime_presence`, `prime_specifique_handicap` (« منحة خاصة لرعاية المعوقين ») ; les autres primes de l'article 42 (جديد) sont refusées (cf. §7). |
| `date` | `AAAA-MM-JJ` | Date de calcul. |
| `groupe` | chaîne, selon la prime | Obligatoire pour `prime_transport`, **selon le secteur**. Métallurgie : `execution_et_maitrise` ou `cadres`. Associations pour personnes handicapées : `execution_et_gestion` (« أعوان التنفيذ والتسيير », agents d'exécution et de gestion) ou `cadres` (« الإطارات ») ; les libellés FR et AR sont renvoyés dans `detail` (`groupe_libelle`, `groupe_libelle_ar`). |
| `variante` | chaîne, selon la prime | `prime_logement` : `base` (défaut) ou `complement_si_prime_superieure`. |
| `transport_assure` | booléen, selon la prime | Obligatoire pour `prime_panier_qefa` (0,560 ou 0,160 DT/jour). |
| `condition_remplie` | booléen, selon la prime | Obligatoire pour les primes soumises à condition. `false` donne un refus `HORS_SCOPE`. |

Un paramètre qui n'est pas prévu pour la prime demandée est refusé
(`PARAM_INVALIDE`).

**`params` pour `smig`** (aucun champ supplémentaire accepté) :

| Champ | Type | Description |
|---|---|---|
| `mode` | chaîne | `mensuel` ou `horaire`. |
| `regime_heures` | entier | Régime hebdomadaire : seuls 48 et 40 figurent au barème vérifié. Un autre régime (ex. 42) donne `SOURCE_MANQUANTE`. |
| `date` | `AAAA-MM-JJ` | Date de calcul : ≥ 2022-10-01 (décret n°769/2022, seul barème vérifié). |

**`params` pour `cotisation_cnss`** : objet libre, jamais exploité. La réponse
est toujours un refus `HORS_SCOPE`.

### 3.2 Réponse

| Champ | Type | Description |
|---|---|---|
| `contract_version` | `"track_b.v0"` | Version du contrat. |
| `request_id` | chaîne ou `null` | Copie de `request_id` de la requête ; `null` si la requête n'en contenait pas de lisible. |
| `status` | `ok` \| `refus` \| `erreur` | Issue du traitement. |
| `result` | objet ou `null` | Présent seulement si `ok` : `{montant, unite, detail}`. |
| `result.montant` | chaîne | Montant décimal à exactement 3 chiffres après le point (millimes), ex. `"593.873"`. C'est une chaîne et **jamais un nombre JSON**, pour éviter les erreurs d'arrondi des floats. |
| `result.unite` | chaîne | Unité, ex. `TND/mois`, `TND/heure`, `TND/jour`. Le module ne fait aucune conversion. |
| `result.detail` | objet | Contexte du calcul : table appliquée, degré, date d'effet, etc. Les valeurs sont des chaînes, des entiers, des booléens ou `null`, jamais des nombres décimaux, ou **des listes de chaînes** (nouveau, D10 : `hypotheses`, `hypotheses_ar`). |
| `result.detail.regle_art13` | chaîne, si présente | Règle de l'article 13 appliquée au-delà du dernier degré (D10) : `ecart_cumule_biennal` (métallurgie ; avec `n_paliers`, `ecart`, `montant_dernier_degre`) ou `table_correspondance` (BTP ; avec `case_cible`, `degre_cible`, `categorie_cible`, `ecart`, `montant_dernier_degre`, `fenetre_debut_annees`, `fenetre_fin_annees`). `ecart` et `montant_dernier_degre` sont des chaînes décimales. |
| `result.detail.hypotheses` / `hypotheses_ar` | liste de chaînes, si présente | Hypothèses d'interprétation de la source sur lesquelles repose le montant, en français et en arabe. **DS1 (orchestration) et DS4 doivent les afficher à l'utilisateur avec le montant**, dans sa langue : le montant n'est exact que si ces hypothèses le sont. |
| `result.detail.label_fr` / `label_ar` | chaîne, si présente (`prime`) | Libellé de la prime : `label_ar` tel qu'imprimé dans la convention, `label_fr` **traduction** de ce libellé (pas une citation de la source). |
| `citations` | liste | Au moins un élément si `ok` ; vide si `refus` ou `erreur`. |
| `citations[].source_file` | chaîne | PDF source du corpus (`data/raw/pdf/...`). |
| `citations[].page` | entier ou `null` | Page du PDF où la valeur a été lue. |
| `citations[].article` | chaîne ou `null` | Article ou décret, quand la source en donne un. |
| `citations[].data_file` | chaîne | Fichier de données vérifié réellement utilisé (toujours sous `data/processed/`). |
| `citations[].decision_ref` | chaîne `Dn` | Entrée de `docs/DECISIONS.md` qui documente la vérification de la donnée. |
| `refus` | objet ou `null` | Présent seulement si `refus` : `{code, message_fr, message_ar}`. |
| `erreur` | objet, optionnel | Présent seulement si `erreur` : `{type, message_fr, message_ar}`. Il donne le type d'incident, sans détail interne. |
| `computed_by` | chaîne | Composant qui a produit la réponse : `track_b_accounting.calc.<operation>` si le calcul a été appelé, `track_b_accounting.contract` sinon. |

**Invariants imposés par le schéma de réponse** :
- `ok` ⇒ `result` non nul, `citations` avec au moins un élément, `refus` nul ;
- `refus` ⇒ `result` nul, `citations` vide, `refus` renseigné ;
- `erreur` ⇒ `result` nul, `citations` vide, `erreur` renseigné.

Le handler valide aussi sa propre réponse avant de la renvoyer. Si elle n'est
pas conforme, il la remplace par une réponse `erreur`.

## 4. Les trois codes de refus

| Code | Signification | Côté appelant |
|---|---|---|
| `PARAM_INVALIDE` | La requête n'est pas conforme au schéma (**refus de contrat**), **ou** elle est conforme mais une valeur de paramètre est invalide pour les données (catégorie inexistante, borne d'ancienneté ambiguë…). | À corriger par l'appelant. |
| `HORS_SCOPE` | La requête est valide, mais la demande sort du périmètre du Track B (CNSS, IRPP, net, conversion d'unité, condition de prime non remplie). | Refus métier légitime : ce n'est pas un bug. |
| `SOURCE_MANQUANTE` | La requête est valide, mais la donnée n'existe pas dans le corpus vérifié (secteur non transcrit, date antérieure à la première grille, régime SMIG absent du barème…). | Refus métier légitime : la donnée manque. |

**Comment distinguer un refus de contrat d'un refus métier.** Le champ
`computed_by` et le message permettent de faire la différence :
- un **refus de contrat** a `computed_by = "track_b_accounting.contract"` et un
  `message_fr` qui commence par « Requête non conforme au contrat » ;
- `cotisation_cnss` a le même `computed_by`, mais avec le code `HORS_SCOPE` ;
- les refus émis par le calcul ont `computed_by = "track_b_accounting.calc.<operation>"`.

**Exemples tirés de `data/mock_cards/track_b_requests_demo.json`** :

| Code | Requête de démo | Motif |
|---|---|---|
| `HORS_SCOPE` | `demo-07-refus-cnss` | Opération `cotisation_cnss` (voir §5.2). |
| `SOURCE_MANQUANTE` | `demo-08-refus-date-anterieure` | Date 2021-11-30, avant la première grille (2021-12-01). |
| `SOURCE_MANQUANTE` | `demo-10-refus-secteur-non-couvert` | Secteur fictif `SECTEUR_FICTIF_NON_SUPPORTE` (avant D9, cette requête visait `BATIMENT_TRAVAUX_PUBLICS`, désormais couvert). |
| `SOURCE_MANQUANTE` | `demo-13-refus-btp-anciennete-27-ans` | BTP `admin_tech`, catégorie 19, ancienneté de 28 ans : l'article 13 fixe « 950 dinars », montant périmé (inférieur au degré 11), non appliqué (D10). |
| `SOURCE_MANQUANTE` | `demo-17-refus-associations-anciennete-33-ans` | Associations pour personnes handicapées, `sport`, 33 ans : les grilles s'arrêtent au degré 16 (32 ans) et l'article 12 (جديد) ب (page 7) ne prévoit rien au-delà (D23). |
| `PARAM_INVALIDE` | `demo-09-refus-categorie-inconnue` | Catégorie `19`, absente de la grille. La requête est conforme au schéma ; c'est donc un `PARAM_INVALIDE` émis par le calcul, pas un refus de contrat. |

Aucune des 18 requêtes de démo n'est non conforme au schéma. L'exemple de
refus de contrat du §5.4 a donc été produit à part, avec une opération
inconnue.

## 5. Exemples complets

Les réponses ci-dessous sont copiées telles quelles depuis la sortie de
`handle()` sur les requêtes du fichier de démo (§5.1 à §5.3), puis sur une
requête construite pour l'exemple (§5.4). Vous pouvez les reproduire avec la
commande du §6.2.

### 5.1 `ok` : salaire de base avec citation (`demo-01-salaire-admin-2022`)

Requête :
```json
{
  "contract_version": "track_b.v0",
  "request_id": "demo-01-salaire-admin-2022",
  "operation": "salaire_base",
  "params": {
    "secteur": "METALLURGIE_BATIMENT",
    "population": "admin_tech",
    "categorie": "4",
    "anciennete_annees": 15,
    "date": "2022-06-01"
  },
  "lang": "fr"
}
```

Réponse :
```json
{
  "contract_version": "track_b.v0",
  "request_id": "demo-01-salaire-admin-2022",
  "status": "ok",
  "result": {
    "montant": "593.873",
    "unite": "TND/mois",
    "detail": {
      "secteur": "METALLURGIE_BATIMENT",
      "population": "admin_tech",
      "categorie": "4",
      "degre": 8,
      "anciennete_annees": "15",
      "table_id": "BM_T_2021-12-01",
      "effective_date": "2021-12-01",
      "date_calcul": "2022-06-01",
      "regime_hebdomadaire_heures": 42,
      "regles": "D6"
    }
  },
  "citations": [
    {
      "source_file": "data/raw/pdf/الاتفاقية المشتركة القطاعية  للبناء المعدني.pdf",
      "page": 30,
      "article": null,
      "data_file": "data/processed/salary_grids/metallurgie_batiment.json",
      "decision_ref": "D4"
    }
  ],
  "refus": null,
  "computed_by": "track_b_accounting.calc.salaire_base"
}
```

### 5.2 `refus` métier `HORS_SCOPE` (`demo-07-refus-cnss`)

Requête (conforme au schéma) :
```json
{
  "contract_version": "track_b.v0",
  "request_id": "demo-07-refus-cnss",
  "operation": "cotisation_cnss",
  "params": {
    "salaire_brut": "1000.000",
    "date": "2024-01-01"
  },
  "lang": "fr"
}
```

Réponse :
```json
{
  "contract_version": "track_b.v0",
  "request_id": "demo-07-refus-cnss",
  "status": "refus",
  "result": null,
  "citations": [],
  "refus": {
    "code": "HORS_SCOPE",
    "message_fr": "Opération 'cotisation_cnss' hors du périmètre Track B v0 (disponibles : salaire_base, prime, smig). CNSS, IRPP, salaire net et conversions ne sont pas couverts par une source vérifiée.",
    "message_ar": "العملية 'cotisation_cnss' خارج نطاق المسار B (المتوفر: salaire_base, prime, smig). الضمان الاجتماعي والضريبة على الدخل والأجر الصافي غير مشمولة بمصدر مُتحقَّق منه."
  },
  "computed_by": "track_b_accounting.contract"
}
```

### 5.3 `refus` métier `SOURCE_MANQUANTE` (`demo-08-refus-date-anterieure`)

Requête :
```json
{
  "contract_version": "track_b.v0",
  "request_id": "demo-08-refus-date-anterieure",
  "operation": "salaire_base",
  "params": {
    "secteur": "METALLURGIE_BATIMENT",
    "population": "admin_tech",
    "categorie": "4",
    "anciennete_annees": 15,
    "date": "2021-11-30"
  },
  "lang": "ar"
}
```

Réponse :
```json
{
  "contract_version": "track_b.v0",
  "request_id": "demo-08-refus-date-anterieure",
  "status": "refus",
  "result": null,
  "citations": [],
  "refus": {
    "code": "SOURCE_MANQUANTE",
    "message_fr": "Aucune grille METALLURGIE_BATIMENT/admin_tech en vigueur au 2021-11-30 (première date d'effet disponible : 2021-12-01).",
    "message_ar": "لا يوجد جدول أجور METALLURGIE_BATIMENT/admin_tech ساري المفعول بتاريخ 2021-11-30 (أول تاريخ نفاذ متوفر: 2021-12-01)."
  },
  "computed_by": "track_b_accounting.calc.salaire_base"
}
```

### 5.4 Refus de contrat `PARAM_INVALIDE` (requête hors fichier de démo)

Requête (opération inconnue du contrat) :
```json
{"contract_version": "track_b.v0", "request_id": "exemple-contrat-invalide", "operation": "calcul_irpp", "params": {}, "lang": "fr"}
```

Réponse :
```json
{
  "contract_version": "track_b.v0",
  "request_id": "exemple-contrat-invalide",
  "status": "refus",
  "result": null,
  "citations": [],
  "refus": {
    "code": "PARAM_INVALIDE",
    "message_fr": "Requête non conforme au contrat track_b.v0 (operation) : 'calcul_irpp' is not one of ['salaire_base', 'prime', 'smig', 'cotisation_cnss']",
    "message_ar": "الطلب غير مطابق للعقد track_b.v0 (operation): 'calcul_irpp' is not one of ['salaire_base', 'prime', 'smig', 'cotisation_cnss']"
  },
  "computed_by": "track_b_accounting.contract"
}
```

Le détail technique en fin de message vient de la bibliothèque `jsonschema` et
reste en anglais, même dans `message_ar` (voir §7).

## 6. Appeler le module

**Prérequis** : Python 3.13 (version utilisée pour les tests ; les versions
antérieures n'ont pas été testées) et les dépendances :
```
python -m pip install -r src/track_b_accounting/requirements.txt
```
Toutes les commandes se lancent **depuis la racine du dépôt**.

### 6.1 Import Python

```python
from src.track_b_accounting.contract.handler import handle

reponse = handle({
    "contract_version": "track_b.v0",
    "request_id": "test-1",
    "operation": "smig",
    "params": {"mode": "mensuel", "regime_heures": 48, "date": "2024-01-01"},
    "lang": "fr",
})
print(reponse["status"], reponse["result"]["montant"], reponse["citations"][0]["page"])
# ok 459.264 2
```

`handle()` ne lève jamais d'exception vers l'appelant : tout incident
inattendu donne une réponse `status: "erreur"`, sans montant. Elle accepte un
`dict` Python, c'est-à-dire du JSON déjà décodé.

### 6.2 Ligne de commande (sans écrire de code)

Le CLI lit une requête, ou une liste de requêtes, dans un fichier ou sur
l'entrée standard. Il écrit la réponse JSON en UTF-8 sur la sortie standard
(arabe en clair, `ensure_ascii=False`).

```
# Les 18 requêtes de démo → liste de 18 réponses
python -m src.track_b_accounting.contract.cli data/mock_cards/track_b_requests_demo.json

# Une requête dans un fichier à vous
python -m src.track_b_accounting.contract.cli ma_requete.json

# Une requête sur l'entrée standard (bash)
echo '{"contract_version":"track_b.v0","request_id":"x","operation":"smig","params":{"mode":"horaire","regime_heures":40,"date":"2023-05-01"},"lang":"ar"}' \
  | python -m src.track_b_accounting.contract.cli
```

Le code de sortie vaut 0 si l'entrée a pu être lue, même quand la réponse est
un refus, et 1 si le fichier est illisible ou le JSON mal formé. Dans ce cas,
la réponse imprimée a le statut `erreur`.

### 6.3 Démo de bout en bout

```
python -m src.track_b_accounting.demo
```
La démo affiche les 18 échanges : requête, réponse, puis la phrase produite
par une doublure de Track A (`MockTrackA`, dans
`src/track_b_accounting/tests/mocks.py`). Le bilan attendu est :
`Bilan : 12 ok, 6 refus, 0 erreur(s).` Les échanges 11 à 13 portent sur le BTP
(administratif, ouvrier occasionnel avec `sous_categorie`, refus de la
catégorie 19 au-delà de 27 ans). L'échange 14 applique l'article 13 de la
métallurgie (25 ans : deux citations et des hypothèses dans `detail`).
Les échanges 15 à 18 portent sur les associations pour personnes handicapées
(D23) :
- 15 : prime de transport du groupe `execution_et_gestion` au 2024-06-01, avec
  les libellés du groupe et la mention des décrets 503/1982 et 691/1986 dans
  `detail` ;
- 16 : salaire demandé avec l'alias de catégorie `"3"` (ligne III des ouvriers,
  agents administratifs et surveillants) ;
- 17 : refus à 33 ans (`SOURCE_MANQUANTE`), au-delà du degré 16 ;
- 18 : salaire à la date d'effet exacte d'une grille (2023-01-01).

La réponse de référence des 18 échanges est conservée dans
`src/track_b_accounting/tests/references/track_b_responses_demo.json` et
comparée à l'octet près par les tests. Ces réponses sont celles que produit le
module : elles montrent son comportement, elles ne prouvent pas que les
montants sont exacts. L'exactitude est mesurée par le jeu de référence lu dans
les PDF (`src/track_b_accounting/evaluation/`).

`MockTrackA` ne fait que mettre en forme : il recopie le montant et les
sources de la réponse, sans rien calculer. C'est une doublure de test, pas
une proposition d'implémentation de Track A.

### 6.4 Valider vos propres messages

Pour vérifier une requête ou une réponse sans passer par le module, validez-la
contre les schémas avec n'importe quelle bibliothèque JSON Schema draft
2020-12. Exemple en Python :
```python
import json
from jsonschema import Draft202012Validator
schema = json.load(open("data/mock_cards/schemas/track_b_request.v0.schema.json", encoding="utf-8"))
Draft202012Validator(schema).validate(ma_requete)
```

## 7. Ce qui n'est pas encore couvert

- **Trente et un secteurs ont des données vérifiées :**
  - `METALLURGIE_BATIMENT` (D4) : 6 grilles (3 dates d'effet × 2 populations)
    et 6 primes ;
  - `BATIMENT_TRAVAUX_PUBLICS` (D9) : 6 grilles (3 dates d'effet × 2
    populations), aucune prime ;
  - `ASSOCIATIONS_PERSONNES_HANDICAPEES` (D23) : 15 grilles (3 dates d'effet
    × 5 populations, 864 montants) et 3 primes datées ;
  - `ASSURANCE` (D29) : 2 grilles (2 dates d'effet, une seule population,
    616 montants) et 1 prime datée ;
  - `ENSEIGNEMENT_PRIVE` (D38) : 5 grilles (1 date d'effet, 5 populations,
    368 montants) et 7 primes datées ;
  - `BANQUES` (D46) : 2 grilles (2 dates d'effet, une seule population,
    1 292 montants), aucune prime couverte ;
  - `GARDIENNAGE_SECURITE_TRANSPORT_FONDS` (D47) : 1 grille (1 date d'effet,
    une seule population, 210 montants, valable jusqu'au 2011-04-30) et
    3 primes datées ;
  - vague 1 (D49 à D54) : `TORREFACTION_CAFE` (3 grilles, 195 montants), `AGENCES_VOYAGES` (2 grilles, 260),
    `HOTELS_TOURISTIQUES` (2 grilles, 260), `CONFISERIE_BISCUITERIE_CHOCOLATERIE` (6 grilles, 450, dont 6 cases
    illisibles refusées), `PATES_ALIMENTAIRES_COUSCOUS` (6 grilles, 504) et `COSMETIQUES_PARFUMS` (9 tables, 507,
    dont 1 case illisible refusée). Détail ci-dessous ;
  - vague 2 (D55 à D60) : `SAVONNERIE_RAFFINAGE_GRIGNONS` (3 tableaux, 468 montants), `COMMERCE_DISTRIBUTION_PETROLE`
    (3, 588), `PLASTURGIE` (6, 672), `MINOTERIES` (6, 672), `TEINTURERIES_PRESSINGS` (6, 672) et `BOISSONS_GAZEUSES`
    (6, 675, dont 6 cases illisibles refusées). Détail ci-dessous ;
  - vague 3 (D61 à D66) : `MECANIQUE_STATIONS_SERVICE` (3 tableaux, 720 montants), `BOISSONS_ALCOOLISEES` (6, 720),
    `BOIS_AMEUBLEMENT_LIEGE` (6, 819), `GESTION_DECHETS` (4, 836, dont 13 cases illisibles refusées), `HABILLEMENT`
    (4, 864) et `COMMERCE_GROS_DETAIL` (6, 897). Détail ci-dessous ;
  - vague 4 (D67 à D72, vérification humaine partielle, voir les décisions) : `IMPRIMERIE_EDITION_CARTONNAGE` (6 tableaux, 855
    montants), `VERRE_MIROIRS` (6, 900, salaire de base refusé), `CONCESSIONNAIRES_MATERIEL_AGRICOLE` (3, 912, dont
    8 cases illisibles refusées), `BOULANGERIES` (9, 1 014, dont 12 cases illisibles refusées), `TEXTILE` (4, 1 050,
    dont 136 cellules transcrites non servies) et `FONDERIE_METALLURGIE_MECANIQUE` (6, 1 092, dont 1 case illisible
    refusée). Détail ci-dessous.

  Tout autre secteur répond `SOURCE_MANQUANTE` tant que son fichier n'est pas
  transcrit, vérifié et enregistré. Ce fichier doit aussi porter sa propre
  référence `_meta.decision_ref` ; sans elle, le secteur est refusé
  (`SOURCE_MANQUANTE`). Voir le §2 pour ce que demande aujourd'hui l'ajout
  d'un secteur.
- **Les dates sont bornées par le corpus.**
  - Grilles de la métallurgie, du BTP et des associations : à partir du
    2021-12-01. Après le 2024-01-01, la grille 2024 reste appliquée, car le corpus ne contient pas
    de grille plus récente : le module ne sait pas si une grille plus récente
    existe ailleurs.
  - Grilles de l'assurance : à partir du 2020-10-01 ; après le 2021-06-01,
    la grille du 2021-06-01 reste appliquée, pour la même raison
    (hypothèse affichée dans `detail`).
  - Grilles de l'enseignement privé : à partir du 2015-09-01 ; après, la
    grille du 2015-09-01 reste appliquée, pour la même raison (hypothèse
    affichée dans `detail`).
  - Grilles des banques : à partir du 2020-09-01 ; après le 2021-05-01, la
    grille du 2021-05-01 reste appliquée, pour la même raison (hypothèse
    affichée dans `detail`).
  - Grille du gardiennage : du 2010-05-01 au 2011-04-30 seulement ; avant
    et après, refus `SOURCE_MANQUANTE` (barème n° 1 absent ; l'avenant n° 7,
    effet 2011-05-01, a révisé les salaires et sa grille est absente).
  - SMIG : seul le décret n°769/2022 (effet 2022-10-01) est vérifié. Le module
    ne connaît pas de SMIG postérieur.
- **Secteur `BATIMENT_TRAVAUX_PUBLICS` : couvert pour deux populations
  seulement (D9).**
  - Couvert : `admin_tech` (agents administratifs et techniciens, TND/mois,
    11 degrés, puis article 13 au-delà, voir ci-dessous) et `ouvriers_occasionnels` (العملة
    العرضيين, TND/heure, sans degré d'ancienneté ; `anciennete_annees` est
    **refusé** pour cette population, `PARAM_INVALIDE`, et `sous_categorie`
    est obligatoire pour les catégories 6 et 7).
  - **Non couvert : les ouvriers permanents (`ouvriers_permanents`).** Leur
    grille (annexe 4, citée à l'article 56, page 16) est absente du document
    fourni. Ils reçoivent un refus `SOURCE_MANQUANTE` explicite :
    l'orchestrateur ne doit pas router vers ce secteur une question sur un
    ouvrier permanent du BTP.
  - **Non couvert : la prime de panier (qefa) du BTP.** Sa condition d'octroi
    est ambiguë dans la source (art. 51 (جديد) أ, p.15 : « sept ans »
    imprimé, contexte horaire) ; refus `SOURCE_MANQUANTE`. Aucune autre prime
    BTP n'est transcrite.
  - **Article 13 au-delà de 27 ans (`admin_tech`), couvert en partie (D10).**
    Après 3 ans au degré 11 (atteint à 24 ans), l'article 13 (جديد) ب
    (page 8) renvoie à une case de la grille (table de correspondance,
    « degré/catégorie »). Le module sert cette case **seulement pendant la
    durée de la tranche de son degré** : de 27 à 29 ans exclus (degrés
    cibles 1 à 6) ou de 27 à 30 ans exclus (degrés cibles 7 à 11). 27 ans
    pile → `PARAM_INVALIDE` ; fin de fenêtre et au-delà → `SOURCE_MANQUANTE`,
    car la convention ne dit pas ce qui se passe ensuite.
    **Non couvert : la catégorie 19**, pour laquelle la table donne
    « 950 dinars », montant périmé (inférieur au degré 11 actuel) :
    refus `SOURCE_MANQUANTE`.
- **Secteur `ASSOCIATIONS_PERSONNES_HANDICAPEES` (D23).**
  - Couvert : les 5 populations des grilles (pages 21 à 29), TND/mois,
    16 degrés de 2 ans chacun, aux trois dates d'effet (2021-12-01,
    2023-01-01, 2024-01-01). Les 9 montants imprimés qui s'écartent de la
    progression habituelle de leur ligne sont servis tels qu'imprimés
    (aucune correction).
  - Primes couvertes (article 42 (جديد), page 14), avec comme date d'effet
    la date « بداية من » (« بعنوان سنة » est renvoyé à titre d'information
    dans `au_titre_de`) : `prime_transport` (groupes `execution_et_gestion`
    et `cadres`), `prime_presence` et `prime_specifique_handicap`. Pour la
    prime de transport, la phrase de la source qui exclut les montants des
    décrets 503/1982 et 691/1986 est recopiée dans `detail` (`note`,
    `note_ar`), sans aucun calcul.
  - Refusé (`SOURCE_MANQUANTE`), avec le texte de refus lu dans le JSON :
    - toute ancienneté à partir de 32 ans : la convention ne dit rien
      au-delà du degré 16 (article 12 (جديد) ب, page 7) ;
    - les primes de frais scolaires, pédagogique, de santé, fonctionnelle et
      des chauffeurs : montant sans date d'effet dans la source ;
    - la prime de production : définie par une formule (note professionnelle
      annuelle), sans montant.
  - Refusé (`PARAM_INVALIDE`) : les bornes exactes 2, 4, …, 30 ans (D6), et
    les catégories `"II"`, `"III"`, `"2"`, `"3"` des `techniciens` (ligne
    imprimée « III+II », clé unique).
  - **Hypothèses affichées dans `detail`** (`hypotheses`, `hypotheses_ar`),
    à montrer à l'utilisateur avec le montant :
    - lecture des degrés (degré k de 2k−2 à 2k ans) ;
    - unité mensuelle, déduite de l'ordre de grandeur des montants, car la
      convention ne la précise pas ;
    - rattachement de la ligne de la grille à la catégorie de l'annexe de
      même numéro, déduit de l'ordre des lignes ;
    - pour la ligne « III+II » des `techniciens`, rattachement des
      catégories 2 et 3 de l'annexe 4 d'après le seul libellé de la grille ;
    - pour la présence et la prime spécifique : le texte les prévoit pour
      toutes les catégories (« لكل الأصناف »).
  - Le régime hebdomadaire n'est pas renseigné : l'article 14 (جديد) (page 8)
    prévoit des régimes différents à l'intérieur d'une même population.
- **Secteur `ASSURANCE` (D29).**
  - Une seule population, `tous_agents` (كافة أعوان شركات التأمين) : `population` peut
    être omise ; si elle est donnée, elle doit valoir `tous_agents`
    (sinon `PARAM_INVALIDE`).
  - Catégories : le numéro d'échelle imprimé dans la grille, `"21"` à `"1"`,
    et la ligne `"استثنائي"` (clé propre), soit 22 lignes ; TND/mois ;
    14 degrés.
  - 2 tables : 2020-10-01 (page 20) et 2021-06-01 (page 21), 616 montants.
    Avant le 2020-10-01 : refus `SOURCE_MANQUANTE`.
  - Degrés : tranches 0-1, 1-2, …, 27-30, puis « 30+ ». Règle « ouvert »
    au-delà du dernier degré : le degré 14 est servi dès 30 ans, sans plafond
    ni extrapolation (article 16 (جديد) أ, page 9). Les bornes exactes 1, 2, 3,
    4, 6, 8, 10, 13, 16, 19, 23, 27 et 30 ans sont refusées (`PARAM_INVALIDE`,
    D6). Les 33 ans de l'article 19 (جديد) (page 11) figurent dans les
    hypothèses affichées, pas comme une borne.
  - Prime couverte : `prime_transport` (article 20 (جديد), page 11), même
    montant pour tous les agents : 75.000 TND/mois à partir du 2016-06-01,
    85.000 TND/mois à partir du 2017-06-01 ; avant le 2016-06-01, refus
    `SOURCE_MANQUANTE`. `detail` recopie la mention du décret n° 503 du
    16 mars 1982 (montant inclus) et la note 11 de la page 11 (`note`,
    `note_ar`), sans calcul, et l'hypothèse « aucune révision après le
    2017-06-01 ».
  - Refusées (`SOURCE_MANQUANTE`), avec le texte de refus lu dans le JSON :
    13e et 14e mois et prime de production (article 20 (جديد), formules),
    prime fonctionnelle (article 21 (جديد)) et prime de l'article 22 (جديد)
    (montant absent), aide en cas de décès (article 44, formule), aide
    scolaire (article 46, montant absent), départ à la retraite (article 47
    (جديد), formule).
  - Le régime hebdomadaire n'est pas renseigné : les tables n'en indiquent
    aucun.
- **Secteur `ENSEIGNEMENT_PRIVE` (D38).**
  - Cinq populations, une par grille (pages 25 à 27) : `ouvriers`,
    `administratifs_surveillants`, `instituteurs`, `secondaire_formateurs`,
    `professeurs_primaire` ; `population` est obligatoire. TND/mois (unité
    déduite pour les grilles 2 à 5, hypothèse affichée) ; 16 degrés ; une seule
    date d'effet, 2015-09-01 (avant : `SOURCE_MANQUANTE`).
  - Catégories : code de la ligne imprimée de la grille ; les rangs de
    l'annexe qui partagent une ligne sont acceptés comme alias (ex. `commis`,
    `surveillant_2e_rang`), ainsi que les numéros 1 à 5 de l'annexe 1 pour les
    ouvriers ; `detail` renvoie `categorie` et `categorie_demandee`.
  - Degrés : l'ancienneté imprimée (1, 2, 4, …, 36) marque la fin du degré ;
    bornes exactes 1, 2, 4, …, 33 ans refusées (`PARAM_INVALIDE`) ; à partir de
    36 ans, refus `SOURCE_MANQUANTE` (article 15 (جديد) ب, page 8, rien
    au-delà du degré 16).
  - Formateurs adjoints (annexe 4) : pas de ligne de grille, refusés comme
    catégorie inconnue (`PARAM_INVALIDE`).
  - Primes couvertes, une par article, `groupe` = rang de l'article
    (obligatoire) : transport (`prime_transport_ouvriers`, `_administratifs`,
    `_surveillants`, `_primaire`, `_secondaire`, articles 48 à 54, effet
    2015-09-01) et pédagogique (`prime_pedagogique_primaire`, `_secondaire`,
    articles 51 et 54, effets du 1er juillet 2008 au 1er juillet 2011). `detail`
    recopie la mention des décrets (503/1982, et 691/1986 pour les articles 49
    à 54) sans calcul.
  - Refusées (`SOURCE_MANQUANTE`), avec le texte de refus lu dans le JSON :
    présence des ouvriers, primes spécifiques, primes de production, direction,
    avantages pour les enfants, compensation des primes antérieures, aide en
    cas de décès.
  - Le régime hebdomadaire n'est pas renseigné : plusieurs régimes dans une
    même population (article 25 (جديد), page 11).
- **Secteur `BANQUES` (D46).**
  - Une seule population, `tous_agents` (une grille par date pour les 34
    postes, pages 22 et 23), qui peut être omise. TND/mois (article 47,
    page 19) ; 19 colonnes : « stage » puis degrés 2 à 19. Dates d'effet
    2020-09-01 et 2021-05-01 (avant : `SOURCE_MANQUANTE`).
  - Catégories : 34 clés, grade et échelon imprimés sur la ligne de la
    grille, sans alias : `agent_services_3`, `_2`, `_1`,
    `agent_services_principal`, `agent_suivi_3`, `_2`, `_1`,
    `agent_suivi_principal`, `agent_bureau_4` à `_1`, `commis_3` à `_1`,
    `commis_principal_3` à `_1`, `chef_section`, `chef_section_hors_classe`,
    `redacteur_3` à `_1`, `redacteur_principal`, `sous_chef_service_2`,
    `_1`, `chef_service`, `chef_service_principal`, `fonde_pouvoir`,
    `sous_directeur`, `directeur_adjoint`, `directeur_3` à `_1`.
  - Degrés : l'ancienneté imprimée (1, 2, 3, 4, 5, 7, …, 33) marque la fin de
    la colonne ; la colonne « stage » est servie de 0 à 1 an (article 11,
    page 8 : un an, renouvelable une fois ; la grille n'indique pas ce qui
    vaut pendant le renouvellement ; hypothèse affichée) ; bornes exactes 1, 2, 3, 4, 5, 7, …, 31 ans
    refusées (`PARAM_INVALIDE`) ; à partir de 33 ans, refus
    `SOURCE_MANQUANTE` (article 47, page 19 : plus haut degré atteint en
    33 ans au plus, rien au-delà).
  - Aucune prime couverte. Refusées (`SOURCE_MANQUANTE`), avec le texte de
    refus lu dans le JSON : `prime_transport` et `prime_representation`
    (articles 49 et 50, montants sans date d'effet), `prime_13e_mois`,
    `prime_production`, `prime_bilan`, `prime_depart_retraite`,
    `prime_fonction_superieure` (formules) et `prime_travail_sous_terre`
    (article 21, montant fixé par l'employeur).
  - Anomalies imprimées conservées sans correction (même anomalie dans les
    deux grilles, listées dans le JSON et dans D46).
  - Le régime hebdomadaire n'est pas renseigné (article 17, page 12).
- **Secteur `GARDIENNAGE_SECURITE_TRANSPORT_FONDS` (D47).**
  - Une seule population, `tous_agents` (une grille pour les 15
    catégories, page 21), qui peut être omise. TND/mois (article 43
    (جديد), page 14) ; 14 degrés.
  - Catégories : numéro « 1 » à « 15 » imprimé dans la grille, le même que
    dans la classification (pages 16 à 20) ; le numéro est requis, aucun
    alias par métier.
  - Dates : barème n° 2, du 2010-05-01 au 2011-04-30. Avant, refus
    `SOURCE_MANQUANTE` (barème n° 1 absent) ; à partir du 2011-05-01,
    refus `SOURCE_MANQUANTE` lu dans le fichier (champ `valide_jusqu_au` de
    la table : avenant n° 7, page 2, salaires révisés, grille absente).
  - Degrés : tranches imprimées « 0-1 », « 1-2 », « 2-4 », …, « 22-24 » ;
    degré 14 lu « 24-26 » (hypothèse affichée) ; bornes exactes 1, 2, 4,
    …, 24 ans refusées (`PARAM_INVALIDE`) ; à partir de 26 ans, refus
    `SOURCE_MANQUANTE` (article 44, page 14).
  - Régimes horaires (48, 54 ou 60 heures, article 17 (جديد), page 9) :
    une même grille, aucun recalcul d'heures ; régime non renseigné.
  - Primes couvertes : `prime_transport` (article 46 (جديد), à partir du
    2012-05-01 ; `groupe` obligatoire : `execution_gestion` ou `cadres` ;
    montant total, décret n° 503/1982 compris), `prime_presence` (article
    46-3, à partir du 2006-05-01) et `prime_panier` (article 46-4, à partir
    du 2006-05-01 ; `condition_remplie` obligatoire : agent de gardiennage
    permanent ou contractuel, travail continu de plus de 7 h le jour du
    panier). Présence et panier : montant mensuel imprimé, sans recalcul
    selon les jours.
  - Refusés (`SOURCE_MANQUANTE`), avec le texte de refus lu dans le JSON :
    `prime_risque_exceptionnel` (sans date), `prime_production`,
    `prime_affectation_categorie_superieure`, `indemnite_fin_service`
    (formules) et `indemnite_complementaire_provisoire` (incluse dans la
    grille, sans montant).
- **Vague 1 (D49 à D54) : particularités visibles pour DS1.** Codes de primes exacts dans chaque fichier
  (`primes`, `primes_non_couvertes`) ; une prime à plusieurs montants sans date est découpée en un code par montant
  (ex. `prime_scolaire_enseignement_base`), un groupe refusé a son propre code (ex.
  `prime_transport_niveau_salaire_minimum`).
  - `TORREFACTION_CAFE` (D49) : population unique `ouvriers_horaires`, facultative ; **TND/heure en hypothèse
    affichée** (unité non imprimée) ; `employes_mensuels` refusée (`SOURCE_MANQUANTE`, aucun tableau mensuel) ;
    catégories « 1 » à « 5 » ; refus à partir de 26 ans.
  - `AGENCES_VOYAGES` (D50) : population unique `tous_agents` ; catégories « 1 » à « 10 » ; régime 48 h ; degré 13
    ouvert (« 28+ ») ; présence en deux codes, `prime_presence_par_jour` (TND/jour) et `prime_presence_mensuelle`.
  - `HOTELS_TOURISTIQUES` (D51) : population unique `tous_agents` ; catégories `direction_1` … `services`, **alias
    `cadre_1`, `cadre_2`** ; `hotels_5_etoiles` refusée (note 2, +10 % non calculés) ; refus à partir de 30 ans ;
    `prime_transport` : `groupe` (`services_a_superieur_2`, `superieur_1_et_cadres`) et `condition_remplie`.
  - `CONFISERIE_BISCUITERIE_CHOCOLATERIE` (D52) : populations `mensuels` et `horaires` (obligatoire) ; degré 15 avec
    écart cumulé tous les 2 ans (art. 14) ; **de 4 ans exclus à 5 ans inclus : `SOURCE_MANQUANTE`** (art. 53) ;
    cases illisibles et une case sans écart de l'art. 14 refusées (voir ci-dessous).
  - `PATES_ALIMENTAIRES_COUSCOUS` (D53) : populations `horaires` et `mensuels` (obligatoire) ; **catégorie +
    `sous_categorie` obligatoires** (horaires I, II, III → « 1 », « 2 » ; mensuels III → « a », « b », « c » ; IV →
    « I », « II » ; V → « I », « II », « III ») ; degré 12 avec écart cumulé tous les 3 ans (art. 14).
  - `COSMETIQUES_PARFUMS` (D54) : populations `administratifs`, `production` (catégories 2 à 6) et
    `production_categorie_1` (degré unique, servi avant 1 an, refusé ensuite) ; degré 12 ouvert (« 26+ ») ;
    `prime_transport` : seul `groupe` `execution_gestion`, `prime_transport_cadres` refusée.
- **Vague 2 (D55 à D60) : particularités visibles pour DS1.** Mêmes conventions de codes de primes que la vague 1.
  Les six secteurs ne figurent pas encore dans la table des secteurs (en attente DS2).
  - `SAVONNERIE_RAFFINAGE_GRIGNONS` (D55) : un tableau imprimé à deux unités, découpé en `horaires` (lignes `I` à `V`,
    `V_bis` ; TND/heure) et `mensuels` (`VI` à `XII` ; TND/mois), population obligatoire ; refus à partir de 21 ans.
  - `COMMERCE_DISTRIBUTION_PETROLE` (D56) : population unique `tous_agents` ; **catégorie `1` à `5` + `sous_categorie`
    (rang, `1` à `4`) obligatoires** ; colonne « - » = 0-1 an et TND/mois en hypothèses affichées ; refus à partir de
    32 ans.
  - `PLASTURGIE` (D57) : `employes_maitrise` (TND/mois) et `ouvriers_horaires` (TND/heure) ; 16 degrés ; refus à partir
    de 32 ans.
  - `MINOTERIES` (D58) : `horaires` (`I` à `V`) et `mensuels` (`1` à `11`) ; degré imprimé 0 = premier degré ; écart
    cumulé tous les 2 ans au-delà de 25 ans pour `V` et `11` seulement, refus au-delà de 27 ans pour les autres.
  - `TEINTURERIES_PRESSINGS` (D59) : `execution` (TND/heure) et `administratifs_techniciens` (TND/mois) ; dernier degré
    ouvert (« 23+ »).
  - `BOISSONS_GAZEUSES` (D60) : `horaires` et `mensuels` ; refus à partir de 30 ans ; 6 cases illisibles refusées
    (`SOURCE_MANQUANTE`, page et raison).
- **Vague 3 (D61 à D66) : particularités visibles pour DS1.** Mêmes conventions de codes de primes que les vagues 1
  et 2. Les six secteurs ne figurent pas encore dans la table des secteurs (en attente DS2).
  - `MECANIQUE_STATIONS_SERVICE` (D61) : population unique `tous_agents`, catégories `1` à `16` ; **TND/heure en
    hypothèse affichée** (unité non imprimée) ; refus à partir de 30 ans.
  - `BOISSONS_ALCOOLISEES` (D62) : `mensuels` (`I` à `X`) et `horaires` (six rangs : `travailleur_manuel`,
    `travailleur_manuel_specialise`, `aide_ouvrier`, `ouvrier_fabrication`, `ouvrier_qualifie`,
    `ouvrier_hautement_qualifie`) ; refus à partir de 34 ans ; `prime_transport` et `prime_logement` à cinq groupes,
    groupe « niveau du salaire minimum » refusé à part.
  - `BOIS_AMEUBLEMENT_LIEGE` (D63) : `mensuels` (`1` à `14`) et `horaires` (`1` à `7`) ; degré 13 servi de 26 à 27
    ans, 27 ans pile `PARAM_INVALIDE`, refus au-delà.
  - `GESTION_DECHETS` (D64) : population unique `tous_agents`, catégories `1` à `19`, **TND/mois en hypothèse
    affichée** ; première table au 2020-05-01 ; degré 11 servi de 24 à 26 ans, 26 ans pile `PARAM_INVALIDE`, refus
    au-delà ; 13 cases illisibles refusées (`SOURCE_MANQUANTE`, page et raison).
  - `HABILLEMENT` (D65) : `horaires` (`I` à `VI`) et `mensuels` (`1` + `sous_categorie` `a` / `b`, puis `2` à `17`) ;
    première table au 2021-09-01 ; refus à partir de 33 ans.
  - `COMMERCE_GROS_DETAIL` (D66) : `agents` (`ouvrier_horaire_ligne_imprimee`, `10` à `21`) et `chefs_rayon_gerants`
    (`16` ou `17` + `sous_categorie` `a` à `e`), population obligatoire ; TND/mois en hypothèse affichée ; écart cumulé
    tous les 2 ans au-delà de 24 ans pour la catégorie `21` seulement, refus au-delà de 26 ans pour les autres.
- **Vague 4 (D67 à D72) : particularités visibles pour DS1.** Mêmes conventions de codes de primes que les vagues 1
  à 3. Les six secteurs ne figurent pas encore dans la table des secteurs (en attente DS2). Vérification humaine
  partielle (cas de référence, primes sans date, zooms, échantillon), décrite dans D67 à D72.
  - `IMPRIMERIE_EDITION_CARTONNAGE` (D67) : `administratifs_mensuels` (lignes `1`, `2`, `3-4-5-6`, `7-8-9`, `10`,
    `11-12`, `13-14-15` ; rangs `1` à `15` en alias), `horaires` (`I` à `III` + `sous_categorie` `1` à `3`, position
    imprimée) et `techniciens_mensuels` (`IV` + `sous_categorie` `1` à `3`, TND/mois en hypothèse) ; refus à partir
    de 31 ans.
  - `VERRE_MIROIRS` (D68) : `horaires` (`1` à `7`) et `mensuels` (`1` + `a` / `b`, `2` à `18`) ; **salaire de base
    toujours refusé** (`SOURCE_MANQUANTE` : aucune durée de degré imprimée) ; primes servies, dont `prime_transport`
    avec la variante `complement_si_prime_superieure`.
  - `CONCESSIONNAIRES_MATERIEL_AGRICOLE` (D69) : population unique `tous_agents`, catégories `1` à `16`, **TND/mois en
    hypothèse affichée** ; refus à partir de 40 ans ; `prime_transport` refusée (montant révisé absent).
  - `BOULANGERIES` (D70) : `administratifs` (`1` à `8`), `traditionnelles_horaires` et `traditionnelles_mensuels`
    (`passeur_de_plaques`, `peseur`, `petrisseur`, `chef_de_four`), `industrielles_horaires` et
    `industrielles_mensuels` (`1` à `5`) ; refus à partir de 24 ans.
  - `TEXTILE` (D71) : `horaires` (`I`, `II`, `III` + `1` à `3`, `IV` + `1` / `2`) et `mensuels` (`1` + `a` / `b`, `2`
    à `17`) ; première table au 2021-09-01 ; colonne « stage » refusée ; refus à partir de 35 ans (horaires) et 36 ans
    (mensuels) ; `prime_assiduite` refusée (dates incohérentes).
  - `FONDERIE_METALLURGIE_MECANIQUE` (D72) : `mensuels` (`1` + `a` / `b`, `2` à `18`) et `horaires` (`1` à `7`) ;
    degré 14 (imprimé « +32 ») servi de 32 à moins de 35 ans, refus à partir de 35 ans (note de l'art. 58 contraire à
    l'en-tête) ; `prime_transport` à deux groupes, « au titre de » 2021, 2023, 2024 tel qu'imprimé.
- **Trois refus lus dans les fichiers (D48), sans effet sur les autres secteurs.**
  - Case illisible (`cellules_source_manquante` d'une table, valeur `null`) : `SOURCE_MANQUANTE` avec la page et la
    raison.
  - Ancienneté refusée au milieu de la grille (`anciennetes_refusees`) : `SOURCE_MANQUANTE`, message avec l'article.
  - Case exclue de l'écart cumulé (`cases_refusees`) : `SOURCE_MANQUANTE` au-delà du dernier degré ; le dernier degré
    reste servi tel qu'imprimé avant le premier palier.
- **Article 13 de la métallurgie (au-delà du degré 11, atteint à 20 ans),
  couvert sous hypothèses (D10).** Montant = degré 11 + n × (degré 11 −
  degré 10), avec n = ⌊(ancienneté − 20) / 2⌋, valeurs de la grille en
  vigueur à la date du calcul (page 9). Les paliers exacts (22, 24, 26… ans)
  sont refusés (`PARAM_INVALIDE`). Il n'y a plus de plafond d'ancienneté.
- **Hypothèses à afficher.** Quand l'article 13 s'applique, `detail` contient
  `regle_art13`, les hypothèses d'interprétation (`hypotheses`,
  `hypotheses_ar`) et la réponse porte deux citations : la grille et
  l'article 13 avec sa page. **DS1 et DS4 doivent afficher ces hypothèses à
  l'utilisateur** avec le montant (écart cumulé, progression normale sans
  les ±6 mois liés à la note ou aux sanctions, montant intégré au salaire de
  base, valeurs de la grille en vigueur ; BTP : case servie pendant sa
  fenêtre). Ce sont des interprétations, pas des certitudes (voir les risques
  en D10).
- **Le SMAG et la prime de transport SMIG** figurent dans
  `data/processed/smig_smag/smig_smag.json`, mais aucune opération ne les
  expose encore.
- **Calculs non couverts** : salaire net, CNSS, IRPP, conversion horaire ↔
  mensuel, prorata et heures supplémentaires. Ils donnent un refus
  (`HORS_SCOPE` ou `PARAM_INVALIDE`). Aucune règle de ces calculs n'est
  écrite dans les sources vérifiées.
- **Messages en partie en anglais** : pour un refus de contrat, le détail
  technique produit par `jsonschema` (ex. `'calcul_irpp' is not one of [...]`)
  reste en anglais, y compris dans `message_ar`.
- **Pas de transport réseau** : le module est une fonction Python et un CLI.
  Il n'existe ni service HTTP ni file de messages. L'intégration avec
  l'orchestrateur reste à définir ensemble.
- **Le contrat est en v0.** Les noms de champs, les codes de refus, la forme
  de `detail` et la liste des opérations peuvent changer après vos retours.
  Je propose qu'un changement incompatible fasse passer `contract_version` à
  une nouvelle valeur ; c'est à valider avec vous.

## 8. Retours attendus

Points sur lesquels l'avis de l'équipe est utile :
- l'enveloppe commune (`contract_version`, `request_id`, `status`, `lang`) :
  convient-elle à l'orchestrateur, ou existe-t-il un format de message
  commun à tous les rôles ?
- le montant en chaîne décimale plutôt qu'en nombre : est-ce acceptable pour
  Track A ?
- la séparation entre refus de contrat et refus métier (`computed_by` + code) :
  est-elle suffisante, ou faut-il un champ dédié ?
- les opérations à ajouter en priorité.
