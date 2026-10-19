# Contrat DS3 — Document Intelligence (ds3.v2)

La v2 aligne la réponse DS3 sur le schéma commun (`common.v0`, et `common.v1` en préparation) et ajoute les
champs de fiche de paie dont DS1 a besoin pour alimenter DS5. Le mock `ds3.v1` reste disponible pendant la
transition (`docs/CONTRACT_DOCUMENT_INTELLIGENCE.md`).

## Interface

```python
from src.document_intelligence.contract.v2.mock import handle_request, list_operations

response = handle_request(request)   # dict JSON en entrée, dict JSON en sortie, jamais d'exception
```

Quand le service réel sera prêt, seul l'import changera ; `computed_by` passera de
`document_intelligence.mock` à `document_intelligence.service`, et `mode` de `mock` à `live`.

## Fichiers

| Fichier | Contenu |
|---|---|
| `src/document_intelligence/contract/v2/models.py` | modèles Pydantic du contrat |
| `src/document_intelligence/contract/v2/mock.py` | mock : `handle_request`, `list_operations` |
| `src/document_intelligence/contract/v2/generate_examples.py` | régénère schémas et exemples |
| `data/mock_cards/schemas/document_intelligence_request.v2.schema.json` | schéma JSON de la requête |
| `data/mock_cards/schemas/document_intelligence_response.v2.schema.json` | schéma JSON de la réponse |
| `data/mock_cards/schemas/document_intelligence_operations.v2.json` | opérations et champs obligatoires |
| `data/mock_cards/document_intelligence_requests_demo.v2.json` | 11 requêtes d'exemple et leurs réponses |
| `src/document_intelligence/tests/test_document_intelligence_mock_v2.py` | tests (dont conformité au schéma commun) |

Régénérer après une modification : `python -m src.document_intelligence.contract.v2.generate_examples`.

## Requête

```json
{
  "contract_version": "ds3.v2",
  "request_id": "req-101",
  "lang": "fr",
  "case_id": "case_015",
  "operation": "analyze_document",
  "context": {"organization_id": "org_demo", "user_id": "user_comptable_01", "role": "accountant",
              "card_id": "company_042", "card_type": "company"},
  "document": {"document_id": "doc_7f3a", "card_id": "company_042", "file_name": "paie_mars_2026.pdf",
               "mime_type": "application/pdf", "storage_ref": "tradrly://cards/company_042/documents/doc_7f3a"},
  "options": {"expected_type": "fiche_de_paie", "min_confidence": 0.9}
}
```

Nouveau par rapport à la v1 : `lang` (`fr` / `ar`, **obligatoire**) et `case_id` (facultatif, repris dans la
réponse). Opérations : `analyze_document` (résultat `DocumentAnalysis`) et `extract_wage_grid` (résultat `WageGrid`).

**Seuil de confiance.** `options.min_confidence` est seulement indicatif : DS3 **n'applique aucun seuil**. Il
renvoie toujours la confiance réelle de chaque champ (`fields[...].confidence`), et c'est le **consommateur** qui
décide quoi en faire. DS1 exige **0,90** avant tout calcul DS5 ; en dessous, le champ passe « à confirmer » et
n'est jamais pré-coché. Le champ n'a donc pas de valeur par défaut (voir D38).

## Réponse : que faire selon le statut

| `status` | Contenu | Ce que fait DS1 |
|---|---|---|
| `ok` et `result.complete = true` | `result`, au moins une citation | afficher les champs pour confirmation |
| `ok` et `result.complete = false` | une ou plusieurs valeurs à `null` avec `unreadable_reason` | afficher ce qui est lu ; demander à l'utilisateur les valeurs manquantes ; pas de calcul automatique sur un champ `null` |
| `refus` | `refus { code, message_fr, message_ar }`, `result = null`, aucune citation | afficher le message dans la langue de l'utilisateur |
| `erreur` | `erreur { type, message_fr, message_ar }`, `retryable` | si `retryable = true`, proposer de réessayer |

Champs présents dans toutes les réponses : `contract_version`, `request_id` (ou `null` si illisible), `status`,
`refus`, `computed_by`, `mode`, `operation`, `card_id`, `document_id`, `citations`, `result`, `warnings`,
`ds3_code`, `meta`. Les clés `erreur` et `retryable` n'apparaissent que si `status = "erreur"`, et `case_id`
seulement s'il a été envoyé (règles de `common.v0`).

**Correspondance des codes** (`ds3_code` garde le code détaillé pour le diagnostic) :

| `ds3_code` | `status` | `refus.code` / `erreur.type` |
|---|---|---|
| `INVALID_REQUEST`, `UNSUPPORTED_OPERATION`, `FILE_EMPTY_OR_CORRUPTED`, `FILE_TOO_LARGE` | `refus` | `PARAM_INVALIDE` |
| `UNSUPPORTED_FORMAT` | `refus` | `HORS_SCOPE` |
| `ACCESS_DENIED` | `refus` | `ACCES_REFUSE` (message neutre ; `document_id` non renvoyé) |
| `UNREADABLE_DOCUMENT`, `NO_TABLE_FOUND` | `refus` | `SOURCE_MANQUANTE` |
| `TIMEOUT`, `INTERNAL_ERROR` | `erreur` | même valeur que `ds3_code` |

## Citations de document

```json
{"citation_id": "c7", "document_id": "doc_7f3a", "page": 1, "bbox": [400, 300, 470, 318],
 "excerpt": "Salaire de base 424.100"}
```

`bbox` = `[x0, y0, x1, y1]` en points PDF, origine en haut à gauche, ou `null` si la position n'est pas connue.
Chaque `citation_id` d'un champ, d'une ligne de paie ou d'une grille renvoie à une citation de la liste.

**Portée de la vérification.** DS3 vérifie que la valeur figure bien dans la **ligne citée**, pas en face du bon
libellé. Sur une ligne qui porte plusieurs nombres (« Salaire de base  208  2.388  496.704 »), une valeur juste
mais rattachée au mauvais libellé n'est pas détectée. La confiance et la citation restent donc à vérifier par
l'utilisateur (écran de revue DS1). Renforcer ce contrôle (associer chaque valeur à sa colonne) est une amélioration
prévue, notée dans D32.

## Champs de la fiche de paie

Chaque champ : `{value, value_type, confidence, citation_id, unreadable_reason, currency}`. Les 15 champs sont
toujours présents ; un champ non imprimé vaut `null` avec `unreadable_reason = "absent_du_document"` (cela ne rend
pas le résultat incomplet).

| Champ | `value_type` | Exemple | Pour DS5 |
|---|---|---|---|
| `employee_name` | `texte` | `Ahmed Ben Salah` | — |
| `period_start`, `period_end` | `date` | `2026-03-01`, `2026-03-31` | `date` = `period_start` |
| `hire_date` | `date` | `2019-09-01` | `anciennete_annees` calculée par DS1 |
| `seniority_years_printed` | `texte` | `6 ans 6 mois` | contrôle seulement |
| `category` | `texte` | `3`, `1B` (`1 ب` normalisé) | `categorie` |
| `sub_category` | `texte` | `II` | `sous_categorie` |
| `grade` | `entier` | `2` | contrôle de cohérence |
| `job_qualification` | `texte` | `Agent administratif` | `population`, `groupe` : proposés par DS1, confirmés par l'utilisateur |
| `employment_status` | `enum` : `permanent`, `temporaire`, `occasionnel` | `permanent` | idem |
| `pay_mode` | `enum` : `mensuel`, `horaire` | `mensuel` | `mode` |
| `work_hours_regime` | `entier` | `48` | `regime_heures` |
| `base_salary`, `gross_salary`, `cnss_employee` | `montant` | `424.100` | détection d'anomalie (tolérance 0,010 TND) |

`pay_lines` (à côté de `fields`) : primes et indemnités imprimées, `{label, amount, confidence, citation_id,
unreadable_reason}` ; le `code` de prime DS5 est une interprétation confirmée par l'utilisateur.

Conversion fixe de `work_hours_regime` : 208 h/mois → `48` ; 173,33 h/mois → `40` ; valeur hebdomadaire 40 ou 48
reprise telle quelle ; toute autre valeur → `null` avec `valeur_incoherente`.

Formats : montant = chaîne à 3 décimales (`"424.100"`, à lire en `Decimal`) ; date = `AAAA-MM-JJ` ; entier = chiffres.
Le modèle Pydantic refuse toute valeur qui ne respecte pas son `value_type`.

## Grille de salaires (`extract_wage_grid`)

Inchangée depuis la v1, sauf `sector_code` : le code DS2 du secteur, pris dans la table commune
`src/shared/sectors/sectors.v0.json` (D30), seulement si le libellé arabe ou le titre exact de la convention
correspond (jamais à partir d'un alias, trompeur sur un document : « sécurité sociale », « virement bancaire ») ;
sinon `null`. Le mock renvoie `gardiennage_securite_transport_fonds`.
`sector_ar` reste fourni. La citation est une citation de document (page 21, `bbox = null`).

## Comportement du mock

| Requête | Réponse |
|---|---|
| fiche de paie normale | `ok`, complète, en français |
| nom de fichier contenant `illisible` | `ok`, `complete = false`, `cnss_employee = null` (`zone_illisible`) |
| nom de fichier contenant `arabe` | `ok`, fiche en arabe, catégorie `1 ب` → `1B`, 173,33 h → `40` |
| `extract_wage_grid` | grille n° 2 du gardiennage (catégories 1 et 15) |
| document d'une autre carte | `refus` `ACCES_REFUSE` |
| extension non supportée (`.zip`…) | `refus` `HORS_SCOPE` |
| nom contenant `corrompu` | `refus` `PARAM_INVALIDE` |
| nom contenant `blanc` | `refus` `SOURCE_MANQUANTE` |
| requête non conforme (ex. `lang` manquant) ou opération inconnue | `refus` `PARAM_INVALIDE` |
| nom contenant `timeout` | `erreur` `TIMEOUT`, `retryable = true` |

Le résumé (`summary`) suit la langue demandée (`lang`). Toutes les données de fiche de paie sont fictives.

## Conformité au schéma commun

Les tests valident chaque réponse d'exemple contre `common.v0` complété des deux ajouts acceptés pour
`common.v1` : la citation de document (`document_citation`) et le code de refus `ACCES_REFUSE`. Les refus et
erreurs sans ces ajouts sont déjà valides contre `common.v0` tel quel. Quand `common.v1` sera dans le dépôt, le
test pointera directement sur ce fichier.
