# Contrat DS2 — Legal Retrieval (`legal_retrieval.v0`)

> **Statut : v0 — proposition, à valider** par DS1 (appelant principal), DS4 et DS5.
> Enveloppe alignée sur `common.v0.schema.json` (D19).
> Owner : Abd Mouhib Souri (DS2).

## À quoi sert ce service

Il reçoit une question juridique et renvoie les **articles de loi applicables**
(conventions sectorielles, convention cadre, SMIG…), avec tout ce qu'il faut pour
les **citer** : identifiant stable, texte exact, page du PDF, dates de vigueur.
Il **n'interprète pas** le droit : l'interprétation revient à DS4/DS5.

## Comment l'appeler

| Mode | Commande |
|---|---|
| Python | `from src.legal_retrieval.contract.handler import handle` puis `handle(request_dict)` |
| CLI | `python -m src.legal_retrieval.contract.cli request.json` (ou `--demo`) |
| HTTP | `POST /legal/search` (lancer `uvicorn src.legal_retrieval.contract.api:app --port 8002`) |

## Intégration DS1 (appel Python direct)

Une seule opération : **`search`**. Le contrat est indépendant du transport : le même
message JSON passe par Python, la CLI ou HTTP.

```python
# depuis la racine du dépôt
from src.legal_retrieval.contract.handler import handle

response = handle({
    "contract_version": "legal_retrieval.v0",   # obligatoire
    "query": "ما هي منحة النقل في قطاع البناء؟",  # obligatoire
    "request_id": "req-123",                    # optionnel (audit trail)
    "reference_date": "2024-01-15",             # optionnel, AAAA-MM-JJ
    "sector": "btp",                            # optionnel
    "lang": "ar",                               # optionnel (ar par défaut)
    "top_k": 5,                                 # optionnel (10 par défaut), compte des ARTICLES
})
# handle() ne lève jamais d'exception : toujours une réponse conforme au schéma
if response["status"] == "ok":
    ...  # response["results"] (toutes les versions) + response["citations"]
elif response["status"] == "refus":
    ...  # response["refus"]["code"], ["message_fr"], ["message_ar"]
else:  # "erreur"
    ...  # response["erreur"] : incident technique, aucun détail interne
```

**Exemples prêts à l'emploi** : `data/mock_cards/legal_retrieval_requests_demo.json`
(5 requêtes avec leur réponse attendue — 2 succès, 1 refus `SOURCE_MANQUANTE`,
2 refus `PARAM_INVALIDE` — et 1 exemple `erreur`). Les réponses sont produites par le
vrai handler et un test vérifie qu'elles restent à jour.

## Requête — `legal_retrieval_search_request.v0.schema.json`

| Champ | Type | Obligatoire | Rôle |
|---|---|---|---|
| `contract_version` | `"legal_retrieval.v0"` | oui | version du contrat |
| `query` | string non vide | oui | question (AR ou FR) |
| `request_id` | string (1 à 128 car.) | non | traçabilité (audit trail) |
| `reference_date` | `AAAA-MM-JJ` (motif de `common.v0 $defs/date` + date réelle) ou null | non | la loi doit être en vigueur à cette date ; null = aujourd'hui |
| `sector` | string ou null | non | ex. `banques`, `btp`, `assurance` |
| `worker_category` | string ou null | non | ex. `ouvrier`, `cadre` |
| `lang` | `ar` / `fr` | non (`ar`) | langue des messages de la réponse (`common.v0 $defs/lang`) ; la question peut être en arabe ou en français |
| `top_k` | 1–50 | non (10) | nombre de résultats |

Aucun champ supplémentaire n'est accepté (`additionalProperties: false`).

### Valeurs reconnues — vocabulaire (D21)

Fichier de référence : `data/mock_cards/legal_retrieval_vocabulary.v0.json`
(schéma : `data/mock_cards/schemas/legal_retrieval_vocabulary.v0.schema.json`).

| Champ | Valeurs | Règle pour DS1 |
|---|---|---|
| `sector` | 7 codes : `gardiennage_securite_transport_fonds`, `construction_metallique`, `btp`, `associations`, `assurance`, `enseignement_prive`, `banques` (libellés FR/AR et alias dans le fichier) | valeur explicite dans la question, sinon `null`. « البناء / construction » est ambigu (`btp` ou `construction_metallique`) : demander une précision |
| `worker_category` | 9 codes tirés du corpus : `execution`, `maitrise`, `cadre`, `agent_service`, `agent_realisation`, `agent_encadrement`, `enseignant`, `educateur`, `administratif` | valeur explicite, sinon `null` ; « ouvrier » n'est pas une catégorie de classement → `null` |
| `reference_date` | `AAAA-MM-JJ` (date réelle) ; `null` = date du jour | date d'application de la loi, pas date de la question |

Accès Python, sans recopier les listes :
```python
from src.legal_retrieval.contract.vocabulary import sector_codes, worker_category_codes
```
Le statut d'emploi (permanent / temporaire / occasionnel) est une **proposition v0.1** :
il n'est pas encore un champ de la requête.

## Réponse — `legal_retrieval_search_response.v0.schema.json`

L'enveloppe est **conforme au schéma commun de l'équipe**
(`src/shared/schemas/common.v0.schema.json`, `$defs/response_envelope`), vérifié
par un test qui valide chaque type de réponse contre ce fichier.

| `status` | Quand | `results` / `citations` | `refus` / `erreur` | HTTP |
|---|---|---|---|---|
| `ok` | au moins un article pertinent | ≥ 1 article, **une citation par article** (même ordre) | `refus: null` | 200 |
| `refus` + `SOURCE_MANQUANTE` | **Citation ou Silence** : aucun article assez pertinent | vides | `{code, message_fr, message_ar}` | 200 |
| `refus` + `PARAM_INVALIDE` | requête non conforme au schéma (refus de contrat, comme Track B) | vides | `{code, message_fr, message_ar}`, `computed_by = legal_retrieval.contract` | 422 |
| `erreur` | incident technique inattendu (aucun détail interne exposé) | vides | `erreur {type, message_fr, message_ar}` | 500 |

Champs DS2 en plus de l'enveloppe : `mode` (`mock` / `live`) et `results`.

**Citation** (`common.v0 $defs/citation`) : `source_file` (PDF du corpus), `page`,
`article` (en-tête tel qu'écrit, ex. `الفصل 50 (جديد)`), `data_file`
(`data/processed/legal_corpus/legal_articles.jsonl`), `decision_ref` (`D11` :
méthode d'ingestion ; `D18` : abrogation établie par vérification manuelle).

Chaque résultat contient : `citation` (voir ci-dessus), `article_id` (ex. `CCS-BANQUES-ART-14-v1`), `source_id`,
`source_title`, `article_number`, `hierarchy_path`, `text` (**texte exact, jamais
normalisé**), `page`, `effective_from`, `effective_to` (null = en vigueur),
`status` (`en_vigueur` / `modifie` / `abroge` / `inconnu`), `sector` (null = tous
secteurs), `related` (voisins dans le graphe), `score` (0–1).

## Opération `get_article` — consulter un article par sa référence (D22)

Besoin exprimé par DS4 (et DS1 pour réafficher une citation). Requête :
`data/mock_cards/schemas/legal_retrieval_get_article_request.v0.schema.json`.
**Réponse : exactement le format de `search`** (même enveloppe `common.v0`, mêmes résultats,
toutes les versions de l'article, la plus récente d'abord).

| Désigner l'article | Exemple |
|---|---|
| `article_id` (avec ou sans `-vN`) | `{"contract_version": "legal_retrieval.v0", "article_id": "CCS-BTP-ART-39"}` |
| `source_id` + `article` | `{"contract_version": "legal_retrieval.v0", "source_id": "CCS-BTP", "article": "7BIS"}` |

`article` : `"39"`, `"7BIS"` (مكرر), `"54TER"` (ثالثا / مثلث), `"46-3"` (sous-article).
Une source qui contient plusieurs textes (Assurance) renvoie l'article de chaque texte
(identifiants `-P2-`, `-P3-`, chemin `جزء N`).

| Cas | Réponse | HTTP |
|---|---|---|
| Article trouvé (y compris **abrogé** : la mention d'abrogation est la réponse) | `ok`, `mode` `live` | 200 |
| Article inconnu | `refus` `SOURCE_MANQUANTE` | 200 |
| Trou vérifié à la main (Cadre 5, Assurance 40 : présents dans le PDF, absents du corpus ; Cadre 40, Associations 20 : absents du PDF) | `refus` `SOURCE_MANQUANTE` **avec la raison** en FR/AR | 200 |
| Requête non conforme (aucune référence, les deux à la fois, format invalide) | `refus` `PARAM_INVALIDE` | 422 |

```python
from src.legal_retrieval.contract.get_article import get_article   # appel Python direct
```
HTTP : `POST /legal/article`. **Mode** : `live` dès que le corpus a été ingéré sur la machine
(`python -m src.legal_retrieval.corpus.ingest_sections`, données hors git) ; sinon `mock`
(articles de démonstration, jamais un article inventé). `/health` indique `get_article_mode`.
v0 : `reference_date` est acceptée mais le filtre daté arrive au Sprint 5 ;
`applicable_at_reference_date` = version consolidée en vigueur ; `page` = `null` (pas de page
par article dans le digest Tradrly).

## Règle « toutes les versions » (D17)

Quand un avocat, un client ou un comptable pose une question, **toutes les versions
connues** de chaque article pertinent sont renvoyées : la version en vigueur, les
anciennes versions modifiées, et les articles abrogés. L'agent qui rédige la réponse
(DS4/DS5) doit **annoncer les deux** : « voici la règle actuelle, et voici ce qu'elle
était avant l'avenant n° X ».

| Champ | Sens |
|---|---|
| `version_group` | identifiant commun à toutes les versions d'un article (ex. `CCS-BTP-ART-50`) |
| `version` | 1 = plus ancienne version connue |
| `applicable_at_reference_date` | `true` sur **au plus une** version par article : celle en vigueur à `reference_date` |
| `modified` | `true` si l'article porte « (جديد) » |
| `amended_by` | avenant qui a modifié ou abrogé cette version |
| `previous_version_available` | `false` = l'article a été modifié, mais le texte précédent n'est pas dans le corpus (texte consolidé) : **l'appelant doit l'annoncer** |

`top_k` compte des **articles**, jamais des versions : `top_k=1` peut renvoyer
plusieurs lignes (toutes les versions d'un même article).

### Ce que l'appelant doit afficher

| Cas | Message attendu |
|---|---|
| 2 versions disponibles | règle actuelle **et** ancienne règle, avec l'avenant et les dates |
| `previous_version_available = false` | règle actuelle **+** « cet article a été modifié par un avenant ; l'ancienne version n'est pas disponible dans le corpus » |
| `status = abroge` | « cet article a été abrogé par l'avenant n° X » (jamais « introuvable ») |

## Exemple

Voir `data/mock_cards/legal_retrieval_search_demo.json`. En mode `mock`, les textes
sont **faux** et marqués `[MOCK]`. Il contient les trois cas : un article en 2 versions,
un article modifié sans ancienne version disponible, et un article abrogé.

## Points à valider en équipe

1. DS1 : `reference_date` et `sector` sont-ils extraits par votre parser d'entités ?
1b. DS4/DS5 : vos agents savent-ils afficher plusieurs versions d'un même article (règle D17) ?
2. DS5 : les barèmes SMIG doivent-ils venir de DS2 (une seule source versionnée) ou rester dans `data/processed/smig_smag/` ?
3. Emplacement définitif des schémas : `src/shared/schemas/` ou `data/mock_cards/schemas/` ?
