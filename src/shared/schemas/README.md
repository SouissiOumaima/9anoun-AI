# Schémas JSON partagés entre rôles

Les rôles (DS1-DS5) n'échangent que des messages JSON. Chaque message est
décrit par un JSON Schema, selon la convention ci-dessous. C'est celle que
Track B (DS5) applique déjà.

## Convention

- **Format** : JSON Schema **draft 2020-12**
  (`"$schema": "https://json-schema.org/draft/2020-12/schema"`).
- **Nom de fichier** : `<rôle>_<objet>.v<N>.schema.json`, en minuscules.
  - `<rôle>` est le préfixe du rôle qui publie le schéma : `orchestrator`,
    `legal_retrieval`, `document_intelligence`, `track_a`, `track_b`.
  - Exemples : `track_b_request.v0.schema.json`,
    `track_b_response.v0.schema.json`.
- **Statut** : tant que l'équipe ne l'a pas accepté, la `description` du
  schéma contient « **vN — proposition, à valider** ». La même version figure
  dans les messages eux-mêmes (ex. `"contract_version": "track_b.v0"`).
- **Versionnement** : un changement **incompatible** crée une **nouvelle
  version**, c'est-à-dire un nouveau fichier `.v<N+1>`. L'ancien reste en
  place tant qu'un rôle l'utilise. Exemples de changements incompatibles :
  champ supprimé ou renommé, type modifié, champ rendu obligatoire, valeur
  retirée d'un `enum`.
- **Validation** : chaque rôle valide les messages qu'il reçoit et ceux qu'il
  émet contre le schéma.

## Emplacement actuel

Aucun schéma n'est encore rangé ici. Ceux de Track B se trouvent aujourd'hui
dans [`data/mock_cards/schemas/`](../../../data/mock_cards/schemas/), où son
code les lit. Leur emplacement définitif (ici ou dans `data/mock_cards/`)
reste à décider en équipe. D'ici là, les deux emplacements suivent la même
convention de nommage.
