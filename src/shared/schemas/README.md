# Schémas JSON partagés entre rôles

Les rôles (DS1-DS5) n'échangent que des messages JSON. Chaque message est
décrit par un JSON Schema, selon la convention ci-dessous. C'est celle que
Track B (DS5) applique déjà.

## Convention

- **Format** : JSON Schema **draft 2020-12**
  (`"$schema": "https://json-schema.org/draft/2020-12/schema"`).
- **Nom de fichier** : `<rôle>_<objet>.v<N>.schema.json`, en minuscules,
  toujours terminé par `.v<N>.schema.json`.
  - `<rôle>` est le préfixe du rôle qui publie le schéma : `orchestrator`,
    `legal_retrieval`, `document_intelligence`, `track_a`, `track_b`.
    Le préfixe `common` est réservé aux définitions partagées par tous les
    rôles (`common.v0.schema.json`).
  - Exemples : `track_b_request.v0.schema.json`,
    `track_b_response.v0.schema.json`, `common.v0.schema.json`.
- **Statut** : tant que l'équipe ne l'a pas accepté, la `description` du
  schéma contient « **vN — proposition, à valider** » (ou « vN : proposition,
  à valider par l'équipe »). La même version figure dans les messages eux-mêmes
  (ex. `"contract_version": "track_b.v0"`).
- **Versionnement** : un changement **incompatible** crée une **nouvelle
  version**, c'est-à-dire un nouveau fichier `.v<N+1>`. L'ancien reste en
  place tant qu'un rôle l'utilise. Exemples de changements incompatibles :
  champ supprimé ou renommé, type modifié, champ rendu obligatoire, valeur
  retirée d'un `enum`.
- **Validation** : chaque rôle valide les messages qu'il reçoit et ceux qu'il
  émet contre le schéma.

## Le schéma commun des réponses : `common.v0.schema.json`

> **v0 : proposition, à valider par l'équipe.** Aucun track ne le référence
> encore avec `$ref` ; Track B n'a pas été modifié.

**Rôle.** Donner à toutes les réponses des tracks la même enveloppe et les
mêmes briques : un `status`, des citations, un refus motivé en français et en
arabe. Les définitions sont reprises **à l'identique** de ce que Track B émet
déjà (`data/mock_cards/schemas/track_b_response.v0.schema.json`). Aucun nom ni
aucun champ n'a été changé. Le test `src/shared/tests/test_common_schema.py`
vérifie que les réponses du handler Track B aux 14 requêtes de démo (et un
refus de contrat, et une erreur) sont conformes.

**Contenu (`$defs`).**

| Définition | Ce qu'elle décrit |
|---|---|
| `response_envelope` | Enveloppe de base d'une réponse. La racine du fichier y renvoie : valider contre le fichier, c'est valider une enveloppe. |
| `status` | `ok`, `refus` ou `erreur`. |
| `citation` | `source_file`, `page`, `article`, `data_file` (`data/processed/…`), `decision_ref` (`Dn`). |
| `refus`, `refus_code` | `{code, message_fr, message_ar}` ; codes `SOURCE_MANQUANTE`, `HORS_SCOPE`, `PARAM_INVALIDE`. |
| `erreur` | `{type, message_fr, message_ar}`, incident technique. |
| `montant` | Chaîne à 3 décimales (`"593.873"`), jamais un nombre JSON. |
| `date` | `AAAA-MM-JJ`, vérifiée par un motif. |
| `lang` | `fr` ou `ar`. |
| `contract_version` | `<track>.v<N>`, ex. `track_b.v0`. |
| `request_id`, `response_request_id` | Identifiant de requête (1 à 128 caractères) ; dans la réponse, chaîne ou `null`. |
| `case_id` | **Optionnel** : identifiant de dossier (voir les questions ouvertes). |

**Invariants de l'enveloppe** (règle « Citation ou Silence ») :
- `ok` : au moins une citation, `refus` nul, pas d'`erreur` ;
- `refus` : aucune citation, `refus` renseigné, pas d'`erreur` ;
- `erreur` : aucune citation, `refus` nul, `erreur` renseignée.

Champs obligatoires : `contract_version`, `request_id`, `status`, `citations`,
`refus`. `case_id`, `erreur` (sauf si `status = erreur`) et `computed_by` sont
facultatifs.

**Comment un track l'étend.** L'enveloppe ne fixe pas le contenu métier : chaque
track ajoute le sien (Track B : `result` avec `montant`, `unite`, `detail`).
Pour garder un schéma fermé, on combine l'enveloppe avec `allOf` et on ferme
avec `unevaluatedProperties` (et non `additionalProperties`, qui ne voit pas
les propriétés déclarées dans l'`allOf`) :

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "track_x_response.v0.schema.json",
  "allOf": [{"$ref": "common.v0.schema.json#/$defs/response_envelope"}],
  "properties": {
    "contract_version": {"const": "track_x.v0"},
    "result": {"type": ["object", "null"]}
  },
  "unevaluatedProperties": false
}
```

Les définitions peuvent aussi être reprises une à une, par exemple
`{"$ref": "common.v0.schema.json#/$defs/citation"}` ou
`{"$ref": "common.v0.schema.json#/$defs/montant"}`.

## Emplacement actuel

Ce dossier contient le schéma commun. Les schémas de Track B se trouvent
toujours dans [`data/mock_cards/schemas/`](../../../data/mock_cards/schemas/),
où son code les lit. L'emplacement définitif des schémas propres à chaque
track (ici ou dans `data/mock_cards/`) reste à décider en équipe. D'ici là,
les deux emplacements suivent la même convention de nommage.

## Questions ouvertes pour l'équipe

1. **Erreur de validation du contrat ou refus métier ?** Aujourd'hui, Track B
   renvoie le même `refus` `PARAM_INVALIDE` pour une requête non conforme au
   schéma (refus de contrat, `computed_by = track_b_accounting.contract`) et
   pour un paramètre refusé par le calcul (refus métier,
   `computed_by = track_b_accounting.calc.<operation>`). Seul `computed_by`
   permet de les distinguer. Proposition, **non appliquée à Track B** : un
   champ optionnel `origine` sur le refus, avec les valeurs `contrat` ou
   `metier`. Il serait ajouté à `$defs/refus` dans une v1 (ajout compatible si
   le champ reste facultatif).
2. **`case_id` pour relier les réponses d'un même dossier.** La requête
   Track A v0 (DS4) l'exige ; Track B v0 ne le connaît pas. Proposition :
   `case_id` optionnel dans l'enveloppe (c'est le cas ici), recopié tel quel
   de la requête dans la réponse quand il est fourni, afin que l'orchestrateur
   relie les réponses de Track A et de Track B sur un même dossier.
3. **Comment chaque track référence le schéma commun.** Ensuite, chaque schéma
   de réponse passerait à
   `"allOf": [{"$ref": "common.v0.schema.json#/$defs/response_envelope"}]`.
   Il faudra décider : l'`$id` (relatif, comme ici, ou une URL), l'endroit
   où les validateurs trouvent le fichier (registre `referencing` en Python),
   et si l'on duplique ou non les définitions le temps de la transition.
4. **Mode d'intégration** (à décider avec DS1 et DS4) : appel Python direct
   (`handle(request) -> response`, comme Track B aujourd'hui), ligne de
   commande (JSON sur l'entrée et la sortie standard), ou service HTTP. Le
   schéma commun vaut pour les trois : il décrit le message, pas le transport.
5. **Format des dates.** Track B vérifie un motif (`^[0-9]{4}-[0-9]{2}-[0-9]{2}$`) ;
   la requête Track A v0 utilise `"format": "date"`, qui **n'est pas vérifié**
   par défaut par la bibliothèque `jsonschema` (Python). Proposition : utiliser
   `$defs/date` du schéma commun partout.
