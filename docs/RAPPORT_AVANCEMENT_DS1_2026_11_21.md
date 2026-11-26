# Rapport d'avancement DS1 du 21 novembre 2026

La livraison DS1 est préparée sur `codex/ds1-delivery-2026-11-21`, à partir de
`main` actualisé au commit `b8799ef`. Elle réunit la nouvelle
interface, l'intégration DS4 v1 et le scénario complet DS3/DS2/DS4 avec revue
utilisateur. La validation juridique et certaines données sources restent
à fournir avant de considérer les scénarios métier définitivement validés.

## Changements livrés

| Périmètre | Résultat |
|---|---|
| Performance DS3 | Cache retiré du diff DS1 et transféré sur `codex/ds3-extraction-cache` pour revue séparée par Hadil |
| Interface DS1 | Mise en page responsive, débordement des champs corrigé, étapes de revue et résultats préparatoires affichés explicitement |
| DS4 v1 | Livraison source `52c5384` importée avec ses tests et contrats, adaptateur officiel v0/v1 et planner DS1 raccordés |
| Schémas DS4 | Métadonnées v0 résiduelles du schéma d'entrée v1 corrigées ; chargement du schéma de réponse indépendant du dossier courant |
| Scénario complet | DS3 live → revue des faits et du lien document/personne/pièce → DS2 live → DS4 v1 ; modes mock bloqués, audit et confirmations idempotentes |
| Migration D21 | Détection sans premier alias arbitraire, ambiguïtés FR/AR et outil de réception du vocabulaire ; 56 secteurs synthétiques testés, livraison officielle encore attendue |
| Tests documentaires | Fiche 02 et champs null vérifiés en live ; catégorie 2B reconnue comme test négatif volontaire ; parcours positif fiche 01 exécuté |

La livraison DS4 est attribuée à sa branche et à son commit d'origine ; elle
ne constitue pas une nouvelle validation juridique du contenu importé.

## Mesures et validation fonctionnelle

- Benchmark d'une même fiche : premier appel Gemini 30,533 s, répétition avec
  cache 0,012 s, dix citations conservées. Le cache accélère la répétition,
  pas le premier appel à un service distant.
- Fiche 02 live : 8,933 s ; les champs null restent indisponibles et ne sont
  ni confirmables ni transmis comme paramètres DS5. `2 b` est réellement
  imprimée et normalisée en `2B` ; refus attendu de la grille sélectionnée.
- Fiche 01 live : 4,720 s ; résultat technique DS5 `641.013 TND/mois` avec
  avertissement sur l'écart au salaire imprimé. Cela n'établit pas un salaire
  légal dû : la cohérence métier secteur/population/régime reste à confirmer.
- Scénario DS3/DS2/DS4 : trois faits monétaires et trois références, statut
  `insufficient_evidence`, conclusion juridique nulle, zéro citation finale.
  Les pages et dates d'effet DS2 manquantes sont signalées.
- Les confirmations des mesures CLI sont automatisées et identifiées comme
  tests techniques. La page comporte une revue utilisateur explicite avec
  cases non cochées par défaut.

## Vérification de livraison

La syntaxe JavaScript et les différences Git sont contrôlées. La validation
globale `python -m pytest -q src` est documentée dans la PR, avec les échecs de
données sources distingués des tests d'intégration. Les sources PDF et les
sorties temporaires ne sont pas publiées ; le fichier `.env` reste ignoré.

Résultat final après restauration D30 : **3973 tests réussis, 25 échecs,
3 ignorés** sur 4001 cas collectés.

| Module | Réussis | Échecs | Ignorés |
|---|---:|---:|---:|
| DS1 orchestrator | 223 | 0 | 0 |
| DS2 legal_retrieval | 207 | 0 | 1 |
| DS3 document_intelligence | 269 | 0 | 2 |
| DS4 track_a_legal | 322 | 0 | 0 |
| shared | 250 | 0 | 0 |
| DS5 track_b_accounting | 2702 | 25 | 0 |

Les résultats de la table précédente décrivent l’exécution historique du 21 novembre, avant récupération des PDF partagés. Ils ne décrivent plus un blocage actuel. Au contrôle du 22 novembre, les 24 sources auparavant manquantes sont toutes suivies dans main et présentes localement. L’inventaire JSON associé est mis à jour avec zéro source manquante et la liste des sources résolues. Les résultats de la nouvelle recette sont ajoutés ci-dessous après exécution.

## Points attendus de l'équipe

| Responsable | Élément à fournir ou confirmer |
|---|---|
| Ghofrane | Revue de l'adaptation DS4 v1 et des corrections de contrat ; validation du dossier fictif, de l'applicabilité des sources et du Golden Set |
| Mouhib | D21 officiel des 56 secteurs, branche/commit et corpus/index associés ; cas de recette ; pages et dates d'effet des références du scénario |
| Oumaima | Cohérence de la fiche positive : PDF 208 h normalisé 48h, grille sélectionnée 42h ; les sources PDF sont désormais disponibles dans main |
| Hadil / Wiem | Revue du cache DS3 et de son isolation ; confirmer les exigences avant un éventuel branchement OCR au flux live |

Aucune conclusion juridique n'est considérée validée avant revue humaine.
Les contrôles techniques ne remplacent pas la vérification des sources originales.

## Scan et OCR

Le module OCR livré dans la PR #40 est désormais dans `main` et cette branche.
Il n'est toutefois pas raccordé à la pipeline d'extraction live actuellement
utilisée par DS1. Les images et PDF sans texte natif ne doivent donc pas être
présentés comme un parcours d'analyse live validé. Son activation ferait l'objet
d'un scénario séparé avec DS3 : contrat, dépendances, confiance, citations et
tests de refus, après accord sur le périmètre.

## Commits de réalisation

- `2c6faf0` : cache DS3 initial, retiré de DS1 par `b099f9f` et transféré sur la branche DS3 dédiée.
- `d219286` : import de la livraison DS4 v1 et corrections de contrat.
- `ef09e6e` : orchestration DS1, design, scénario complet et préparation secteurs.
- `3a1e85b` : synchronisation de la branche avec `main`.

Les rapports détaillés des étapes précédentes restent historiques. Le présent
rapport décrit le périmètre de la livraison à revoir dans la PR, sans annoncer
la migration officielle des 56 secteurs ni une validation métier finale.


## Suite à la revue de PR #47

- Cache Gemini sorti du diff DS1 sans réécriture de l’historique Git. Branche dédiée : `codex/ds3-extraction-cache`, revue Hadil attendue.
- Les erreurs DS3 valides, de provenance vérifiée, avec `retryable=true` donnent `retry_later` et un bouton Réessayer. Aucun fait n’est confirmé et DS2/DS4 ne sont pas lancés à cette étape.
- Messages DS3 français/arabe conservés, refus permanents bloquants. Une nouvelle tentative nécessite une action utilisateur et une nouvelle confirmation des faits.
- Confiance affichée avec une décimale arrondie vers le bas : 0,896 apparaît 89,6 %, 0,89999 apparaît 89,9 %.
- Validation : 230 tests DS1 réussis. Branche cache : 7 tests cache réussis (dont isolation du pipeline par utilisateur/carte), mypy du cache et ruff des deux fichiers corrigés réussis. Suite DS3 : 272 réussis, 2 ignorés, 3 échecs liés au fichier `scripts/evaluer_donnees_reelles.py` absent du main utilisé ; aucun appel Gemini réel dans ces tests.


### Relecture DS3 Hadil : stockage et provenance

- `.gitignore` limité aux copies locales de `cards/case-e2e-payroll-001/` ; le dossier de démo DS3 partagé et les futures cartes ne sont plus ignorés globalement.
- `is_usable_document_response` refuse déjà tout mode autre que `live`. Le test existant `test_ds3_provenance_boundary.py` caractérise également la limite : des métadonnées déclarées ne prouvent pas l’authenticité. DS1 vérifie séparément la provenance et le contexte de l’appel.
- Tests supplémentaires au niveau conversion DS4 v1 : modes mock/absent/vide rejetés ; confiances 0,896 et 0,89999 conservées à l’affichage mais non éligibles même après confirmation.
- Validation : 557 tests DS1/DS4 réussis. Suggestions d’évolution de l’unité monétaire et de séparation de la livraison DS4 laissées à coordonner avec sa propriétaire, sans changement du contrat DS4 dans ce correctif.


## Découpage DS4 / DS1 après revue

- PR DS4 #53 : `codex/ds4-track-a-v1-delivery` vers `main`, commit `922784b`, 116 fichiers DS4 extraits de la livraison existante avec attribution au commit source `52c5384`. 327 tests DS4 réussis indépendamment de DS1. Les évolutions ultérieures de la branche de Ghofrane ne sont pas incluses implicitement.
- PR DS1 #47 : base temporaire `codex/ds4-track-a-v1-delivery`, 23 fichiers DS1 uniquement ; l'historique existant est conservé. Branche actualisée avec main `ebe87ba` ; 557 tests DS1/DS4 réussis.
- Ordre : revue DS4 par Ghofrane (notamment devise, schémas et routage), fusion de #53 dans main, actualisation de la branche DS1 avec main puis retour de la base de #47 à main et nouvelle vérification du diff/tests. Ne pas fusionner #47 dans la branche DS4. Cette actualisation est importante également si #53 est fusionnée par squash.
- Cache DS3 #48 indépendant. Aucune fusion dans main effectuée pendant ce découpage. Validation juridique humaine inchangée.


## Actualisation après relecture Oumaima du 22 novembre 2026

- Main actualisé au commit `34d8bec`. Les 24 sources DS5 auparavant absentes sont toutes suivies et présentes ; inventaire mis à jour avec zéro manque. Aucun chemin personnel de téléchargement dans la documentation de validation.
- Schémas DS4 v1 canoniques uniquement dans `data/mock_cards/schemas/` ; README de livraison et tests des exemples raccordés à ces fichiers. Sept fiches de revue avocat réencodées en UTF-8 avec accents corrigés.
- Tests synthétiques à 56 secteurs indépendants de la taille du D21 réel. Message de refus OCR aligné D41. Erreurs inattendues journalisées avec type et emplacements de pile, sans message d’exception ni lignes de code susceptibles de contenir des données ; test de non-divulgation réussi.
- Nouvelle suite globale `python -m pytest -q src` : **5227 réussis, 4 ignorés, aucun échec**. Services distants injectés dans les tests ; cela ne constitue pas une nouvelle revue juridique ni une recette Gemini réelle.
- Suite DS4 indépendante : **339 réussis**. Les 14 rapports préparatoires S7/S8 sont conservés comme instantané pour la revue, explicitement sans validation juridique. Les tests de contrat DS3 conservés dans DS4 documentent la frontière du consommateur.
- Partie DS4 isolée dans #53 ; sa revue et son accord par Ghofrane restent requis. #47 garde sa base temporaire DS4. Après fusion #53 : actualiser DS1 avec main, remettre la base sur main et refaire les vérifications. Fusion squash proposée par Oumaima ; aucune fusion ni fermeture de #38 effectuée ici.


## Synchronisation DS4 du 26 novembre 2026

- PR #59 intégrée dans la branche de livraison de #53, sans fusion dans main : merge `f3db81c`. Les 13 commits DS4 et leur attribution sont conservés.
- Défaut S9 signalé par Graphify confirmé puis corrigé dans `00b0981` : des entrées de revue non objets, sans identifiants, avec identifiants vides ou non textuels sont refusées par ValueError ; neuf cas de régression ajoutés.
- DS4 indépendant : **452 tests réussis**. Combinaison exacte avec DS1 : **5340 réussis, 4 ignorés, aucun échec**. L’arbre de la branche DS1 après intégration est identique à celui testé, avant cette mise à jour documentaire.
- Schémas, routage v0/v1, mapping Case Card, temporalité et provenance testés. Le filtre v1 accepte seulement TND faute de champ devise dans le contrat, sans conversion ; politique collective encore à confirmer. La provenance détaillée et la vérification PDF sont optionnelles et ne sont pas activées implicitement dans DS1.
- Une citation retrouvée dans un PDF ne certifie ni l’authenticité officielle ni l’applicabilité juridique. Aucun nouvel accord juridique ni changement des schémas partagés n’est déclaré par ces tests.
- #47 reste une PR de 23 fichiers DS1, basée temporairement sur la livraison DS4. La consolidation finale de #53, puis son intégration à main, restent séparées de cette fusion #59. Ne pas intégrer #47 à la branche DS4.


## Correction DS1 des dates inconnues du 26 novembre 2026

Le mapper officiel `build_track_a_request_from_case_card` réserve désormais le contrôle strict de date à Track A v0. Pour v1, il conserve explicitement `date=None`, `date_precision=unknown` et le motif fourni, puis valide toute la requête contre le schéma officiel v1 avec contrôle des formats. Aucun motif ni date ne sont fabriqués. Une date inconnue sans métadonnées conformes et une date exacte invalide sont refusées.

Le schéma Case Card propre à DS1 accepte maintenant le champ optionnel `date_reason` ; le schéma partagé Track A v1 reste inchangé. Tests de non-régression v0/v1, motifs FR/AR, absence de mutation et dates invalides : 28 tests ciblés réussis. Suites DS1, DS4 et shared : **1033 tests réussis, aucun échec**. Correctif livré uniquement côté DS1 dans #47.


## Restitution des diagnostics du 26 novembre 2026

- PR #64 intégrée dans la branche de livraison de #53 par merge `e45a421`, sans fusion dans main. Les changements se limitent aux diagnostics officiels DS4 ; le commit de configuration PDF `02cce48` reste hors périmètre.
- DS1 préservait déjà uncertain_information dans la réponse du chat. L’affichage du résultat du parcours complet DS3 puis DS2 puis DS4 le restitue désormais aussi, avec échappement HTML des identifiants et raisons.
- Tests d’intégration : informations manquantes et contradictions déclarées atteignent la réponse du chat ; diagnostics du parcours complet non vides et sans doublons ; conclusion juridique toujours null et absence de citations injustifiées conservées.
- Combinaison avec la dernière correction des dates inconnues DS1 : **5364 tests réussis, 4 ignorés, aucun échec**. Tests ciblés diagnostics et parcours : **53 réussis**. Syntaxe JavaScript et échappement du rendu vérifiés.
- Les essais sur réponses DS2 LIVE sauvegardées restent des relectures de données sauvegardées, sans nouvel appel LIVE. Aucun contrôle PDF ni traitement de provenance optionnel n’est activé implicitement. Revue finale de #53, politique TND et validation humaine S6/S9 restent distinctes.


## Vérification PDF optionnelle du 26 novembre 2026

- PR #65 revue puis intégrée uniquement dans la branche de livraison de #53, merge `42af1e9`. Le raccordement des adaptateurs DS4 transmet un pdf_root explicite de configuration serveur ; aucun chemin n’est extrait de l’enveloppe client.
- Le véritable adaptateur DS1 reste sans activation implicite. Deux tests supplémentaires vérifient qu’un pdf_root placé dans params ou context par le client n’est pas transmis au handler. La configuration réelle du serveur reste à valider conjointement avant toute activation.
- Tests ciblés adaptateurs PDF et frontière DS1 : **55 réussis**. Combinaison globale avec DS1 : **5375 réussis, 4 ignorés, aucun échec**. Les PDF utilisés dans ces essais sont synthétiques ; aucune authenticité officielle ni applicabilité juridique certifiée.
- Les trois anomalies de formatage du document de conception sont corrigées dans #53 par `91be72a` ; git diff --check sur le diff complet de livraison ne signale plus d’anomalie.
- Aucun merge dans main. La revue finale de Ghofrane, la politique TND et les validations humaines S6/S9 restent ouvertes ; le dossier Ahmed attend les références DS2 confirmées.
