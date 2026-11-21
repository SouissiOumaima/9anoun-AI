
# DS4 — Lawyer Track v1
## Document de conception

**Projet :** 9anoun-AI  
**Branche :** DS4_Lawyer_Track_v1  
**Statut :** En préparation — contrat technique non finalisé

## 1. Objectif

Faire évoluer DS4 de track_a.v0 vers track_a.v1 afin de permettre une analyse juridique plus structurée, traçable et prudente.

DS4 doit distinguer :
- Les faits vérifiés.
- Les déclarations non vérifiées.
- Les informations manquantes.

DS4 ne doit jamais inventer de faits, de preuves, de dates, de citations ou de conclusions juridiques.

## 2. Architecture validée

- DS1 reste l'unique orchestrateur.
- DS4 reçoit les informations nécessaires via DS1.
- Le champ `legal_sources` sera optionnel.
- DS4 ne recalcule pas les résultats de DS5.
- Si DS4 cite un calcul DS5, il conserve la réponse et les citations telles que transmises via DS1.

## 3. Règles documentaires proposées par DS3

### 3.1 Fait vérifié
Une valeur peut être considérée comme vérifiée si :
- Elle possède une citation documentaire.
- Sa confiance atteint le seuil applicable.
- Elle a été confirmée par l'utilisateur dans DS1.

Le seuil DS4 reste à valider.

### 3.2 Déclaration non vérifiée
Une valeur citée mais insuffisamment fiable ou non confirmée reste non vérifiée.

### 3.3 Information manquante
Une valeur `null` n'est jamais un fait.

Raisons possibles :
- `absent_du_document`
- `zone_illisible`
- `valeur_incoherente`

### 3.4 Données fictives
Une réponse DS3 avec `mode = "mock"` ne doit jamais être utilisée comme preuve dans une analyse réelle.

## 4. Points en attente d'Achref

- Structure JSON exacte de `track_a.v1`.
- Champs obligatoires et optionnels.
- Représentation des confirmations utilisateur.
- Seuil de confiance applicable à DS4.
- Traitement des dates inconnues.
- Règles de validation et codes d'erreur.
- Transmission des citations et avertissements DS3.

Aucune modification du contrat v0 avant clarification des règles v1.


## 5. Intégration du contrat DS3 v2

### 5.1 Contrat de référence

Le contrat documentaire de référence est `ds3.v2`.

DS4 reçoit les données documentaires via DS1, qui reste l'unique orchestrateur.

La structure de référence est définie dans :
- `data/mock_cards/schemas/document_intelligence_response.v2.schema.json`
- `docs/CONTRACT_DOCUMENT_INTELLIGENCE_V2.md`

### 5.2 Validation des réponses

Avant d'exploiter une réponse DS3, vérifier :
- La version du contrat : `ds3.v2`.
- Le statut : `ok`, `refus` ou `erreur`.
- Le mode : `mock` ou `live`.
- La présence et la validité des citations utilisées.
- Les avertissements disponibles.

Une réponse `refus` ou `erreur` ne fournit pas de preuve exploitable.

Le mode `mock` est réservé aux tests et ne doit jamais servir de preuve dans un dossier réel.

Le mode `live` ne suffit pas, à lui seul, à établir qu'un fait est vérifié.

### 5.3 Validation des champs extraits

Pour chaque champ documentaire utilisé :
- `value` contient une chaîne ou `null`.
- `confidence` est compris entre 0 et 1.
- `citation_id` identifie une citation ou vaut `null`.
- `unreadable_reason` peut indiquer une information absente, illisible ou incohérente.

Une valeur `null` ne doit jamais être considérée comme un fait établi.

Le champ `result.complete = true` ne garantit pas que toutes les informations nécessaires à l'analyse juridique sont disponibles.

### 5.4 Traçabilité des citations

Une citation documentaire contient :
- `citation_id`
- `document_id`
- `page`
- `bbox`
- `excerpt`

DS4 devra vérifier que chaque `citation_id` exploité correspond à une citation présente dans la réponse.

Une citation documentaire atteste la provenance d'une extraction, mais ne constitue pas automatiquement une preuve juridique suffisante.

### 5.5 Règles en attente de validation

Les points suivants doivent être confirmés avec DS1 / Achref :
- Le seuil de confiance applicable à DS4.
- La structure des confirmations utilisateur.
- Le format de transmission des résultats DS3 vers DS4.
- La correspondance entre les citations DS3 et les preuves DS4.
- Le comportement exact de `track_a.v1` en cas de données insuffisantes.

Aucun changement du contrat `track_a.v0` avant validation.

## 6. Etat actuel de l'integration DS1

### 6.1 Orchestration existante

L'analyse du code de la branche DS1_Live_Integration montre que :

- DS1 reste l'unique orchestrateur.
- Le Planner selectionne actuellement un agent specialise par requete.
- Une demande CASE_ANALYSIS est dirigee vers track_a_legal.analyze_case.
- DS1 construit actuellement une requete track_a.v0 depuis la Case Card.
- Aucun chainage automatique DS2 -> DS3 -> DS4 n'a ete identifie dans les modules examines.

### 6.2 Validation documentaire existante

L'interface DS1 implemente deja une revue humaine des champs DS3 pour DS5.

Les tests couvrent notamment :
- Le refus des champs documentaires inutilisables.
- Le refus des champs sous le seuil de confiance DS5.
- Le blocage des calculs DS5 si le mode documentaire n'est pas live.
- L'obligation de confirmer les champs avant leur utilisation par DS5.

Ces protections ne constituent pas encore une integration DS3 -> DS4.

Le seuil 0.90 utilise par DS5 ne doit pas etre applique automatiquement a DS4.

### 6.3 Integration juridique a definir

Le contrat DS2 legal_retrieval.v0 fournit des articles et des citations.

Le format de transmission de ces informations vers legal_sources dans
track_a.v1 reste a definir avec DS1 et DS2.

Les reponses DS2 en mode mock ne doivent pas constituer des preuves
juridiques reelles.

### 6.4 Decisions en attente

Avant l'implementation de track_a.v1, confirmer avec Achref :

- Le schema exact de la requete DS4 v1.
- Le parcours de transmission DS2 et DS3 vers DS4.
- La representation des confirmations humaines.
- Le seuil de confiance documentaire applicable a DS4.
- Les controles de provenance et de citations.
- Les comportements de refus et les codes d'erreur.

Aucune modification du contrat track_a.v0 sans validation.

