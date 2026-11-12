
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
