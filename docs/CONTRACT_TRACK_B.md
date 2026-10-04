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

1. **Registre explicite des secteurs.** Les secteurs connus sont listés en dur
   dans `src/track_b_accounting/calc/loaders.py` (dictionnaire `GRILLES`).
   Il faut y ajouter une ligne par nouveau secteur. Un fichier déposé sans
   cette ligne n'est pas lu, et le secteur répond `SOURCE_MANQUANTE`.
2. **Structure des données supposée.** Le code s'appuie sur la structure du
   fichier métallurgie :
   - les tables sont rattachées à une population quand leurs catégories sont
     exactement celles de la population ;
   - les intervalles de degré sont lus dans des libellés de la forme `"0-2 ans"`
     et `"20+"` ;
   - les paramètres de prime dépendent de clés JSON précises (`montants`,
     `complement_si_prime_superieure`, `montant_reduit_si_transport_assure`,
     `condition`).

   Un secteur dont la grille est organisée autrement (par exemple deux
   populations avec les mêmes catégories, ou des primes d'une autre forme)
   demandera une adaptation du code. Le schéma, lui, ne changera pas.

Le point 1 est une petite correction, que je n'ai pas encore faite. Le point 2
dépendra des grilles des autres conventions, qui ne sont pas encore
transcrites.

**Point réglé : la référence de vérification.** Le champ `decision_ref` des
citations (l'entrée de `DECISIONS.md` qui documente la vérification) est lu
dans le fichier du secteur (`_meta.decision_ref`, `"D4"` pour la métallurgie).
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

Les deux sont au format JSON Schema draft 2020-12.

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
| `secteur` | chaîne | Code du secteur, ex. `METALLURGIE_BATIMENT`. |
| `population` | chaîne | `admin_tech` (grille mensuelle) ou `execution` (grille horaire) pour la métallurgie. |
| `categorie` | chaîne ou entier | Catégorie de la grille, ex. `"1B"`, `"4"`, `7`. |
| `anciennete_annees` | nombre | Ancienneté en années. Une valeur exactement égale à une borne (2, 4, …, 20) est refusée, car le PDF ne précise pas à quel degré elle appartient (D6). |
| `date` | `AAAA-MM-JJ` | Date de calcul : la table appliquée est la plus récente dont la date d'effet est ≤ cette date. |
| `unite_souhaitee` | chaîne, optionnel | Si elle diffère de l'unité de la grille, la requête est refusée (`HORS_SCOPE`) : aucune conversion horaire ↔ mensuel n'est écrite dans les sources. |

**`params` pour `prime`** :

| Champ | Type | Description |
|---|---|---|
| `secteur` | chaîne | Code du secteur. |
| `code` | chaîne | Code de la prime, ex. `prime_transport`, `prime_presence`, `prime_logement`, `prime_panier_qefa`, `prime_deplacement_chantier`, `prime_travail_en_hauteur`. |
| `date` | `AAAA-MM-JJ` | Date de calcul. |
| `groupe` | chaîne, selon la prime | Obligatoire pour `prime_transport` : `execution_et_maitrise` ou `cadres`. |
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
| `result.detail` | objet | Contexte du calcul : table appliquée, degré, date d'effet, etc. Les valeurs sont des chaînes, des entiers, des booléens ou `null`, jamais des nombres décimaux. |
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
| `SOURCE_MANQUANTE` | `demo-10-refus-secteur-non-couvert` | Secteur `BATIMENT_TRAVAUX_PUBLICS`, sans données vérifiées. |
| `PARAM_INVALIDE` | `demo-09-refus-categorie-inconnue` | Catégorie `19`, absente de la grille. La requête est conforme au schéma ; c'est donc un `PARAM_INVALIDE` émis par le calcul, pas un refus de contrat. |

Aucune des 10 requêtes de démo n'est non conforme au schéma. L'exemple de
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
# Les 10 requêtes de démo → liste de 10 réponses
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
La démo affiche les 10 échanges : requête, réponse, puis la phrase produite
par une doublure de Track A (`MockTrackA`, dans
`src/track_b_accounting/tests/mocks.py`). Le bilan attendu est :
`Bilan : 6 ok, 4 refus, 0 erreur(s).`

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

- **Un seul secteur a des données vérifiées : `METALLURGIE_BATIMENT`.** Il
  comprend 6 grilles (3 dates d'effet × 2 populations) et 6 primes. Tout
  autre secteur répond `SOURCE_MANQUANTE` tant que son fichier n'est pas
  transcrit, vérifié et enregistré. Ce fichier doit aussi porter sa propre
  référence `_meta.decision_ref` ; sans elle, le secteur est refusé
  (`SOURCE_MANQUANTE`). Voir le §2 pour ce que demande aujourd'hui l'ajout
  d'un secteur.
- **Les dates sont bornées par le corpus.**
  - Grilles métallurgie : à partir du 2021-12-01. Après le 2024-01-01, la
    grille 2024 reste appliquée, car le corpus ne contient pas de grille plus
    récente : le module ne sait pas si une grille plus récente existe ailleurs.
  - SMIG : seul le décret n°769/2022 (effet 2022-10-01) est vérifié. Le module
    ne connaît pas de SMIG postérieur.
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
