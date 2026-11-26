# DS4 - Lawyer Track A v1

## 1. Objectif

Livraison technique du module DS4 Lawyer Track A v1
pour integration dans l'orchestrateur DS1 de 9anoun-AI.

Le module produit une analyse juridique preparatoire,
sans conclusion juridique definitive automatique.

## 2. Contrats et livrables

| Fichier | Description |
|---|---|
| [track_a_request.v1.schema.json](../../data/mock_cards/schemas/track_a_request.v1.schema.json) | Contrat d'entree |
| [track_a_response.v1.schema.json](../../data/mock_cards/schemas/track_a_response.v1.schema.json) | Contrat de sortie |
| example_request_v1.json | Requete fictive |
| example_response_v1.json | Reponse preparatoire |
| example_refusal_v1.json | Exemple de refus |
| VALIDATION_REPORT.md | Rapport de validation technique |

Les schemas canoniques sont centralises dans
data/mock_cards/schemas/.

## 3. Architecture et fonctionnalites

- Handler officiel : src.track_a_legal.v1_handler.handle_v1.
- Routage DS1 compatible avec Track A v0 et v1.
- Integration DS2 et preservation des versions juridiques.
- Integration des faits documentaires DS3.
- Validation des references et coherence temporelle.
- Analyse preparatoire selon les cinq piliers.
- Livrables S7 et rapport juridique preparatoire S8.
- Protocole et validation structurelle des revues humaines S9.
- Diagnostics officiels dedupliques dans uncertain_information.
- Verification documentaire PDF optionnelle.
- Preservation optionnelle de la provenance documentaire DS3.

Les faits DS3 ne sont jamais automatiquement confirmes.
Le filtrage TND a la frontiere v1 est implemente sans
conversion monetaire. La politique collective reste a confirmer.

## 4. Validation technique au 26 novembre 2026

| Perimetre | Tests reussis | Tests ignores |
|---|---:|---:|
| DS4 avec diagnostics, commit a33821e | 463 | 0 |
| Suite globale, commit a33821e | 5293 | 1 |
| DS4, PR #65, commit e0238ac | 472 | 0 |
| Suite globale, PR #65 | 5302 | 1 |
| Integration combinee DS1/DS4, selon Achref | 5364 | 4 |

Aucun echec rapporte dans ces executions.

Les resultats correspondent a des revisions distinctes
et ne doivent pas etre additionnes.

## 5. Etat de l'integration

- PR #59 : integree dans la livraison DS4.
- PR #64 : integree par le merge e45a421.
- Correctif DS1 des dates inconnues : 9342e87.
- Restitution des diagnostics dans DS1 : 73e7df5.
- PR #47 : integration finale en attente.
- PR #65 : raccordement PDF optionnel soumis a revue.
- PR #53 : revue technique finale en cours.

La verification PDF et la provenance optionnelle ne sont
pas activees implicitement dans DS1.

## 6. Garanties et limites

- Preservation des donnees d'entree.
- Absence de conclusion juridique definitive automatique.
- Absence de citations finales injustifiees dans les scenarios testes.
- Conservation des incertitudes et des references.
- Les relectures de reponses DS2 LIVE sauvegardees ne constituent
  pas de nouveaux appels LIVE.
- La verification textuelle PDF ne garantit ni authenticite,
  ni pertinence, ni applicabilite juridique.
- Le dossier Ahmed Ben Salah reste en attente de confirmation
  sectorielle, documentaire et juridique.
- La validation humaine S6/S9 reste a realiser.
- Les 42 decisions humaines S9 restent en attente.

## 7. Commande de validation

Depuis la racine du depot :

    python -m pytest src/track_a_legal/tests -q

## 8. Statut de livraison

**TECHNICAL REVIEW IN PROGRESS - LEGAL VALIDATION PENDING**

La validation technique ne constitue pas une validation
juridique humaine ni une autorisation de fusion dans main.
