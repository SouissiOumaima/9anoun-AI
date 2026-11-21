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

Les 25 échecs DS5 sont les 24 assertions de présence des PDF des vagues 1–4
et la comparaison exacte de baseline, dont le taux de citations valides dépend
des fichiers sources présents. Les montants et schémas de cette baseline
restent conformes ; les tests et le code DS5 sont inchangés par la livraison.
La PR reste en brouillon pour revue, avec ces limites de données explicites.

Les 7 sources D30 sont restaurables depuis le pack local historique et les
17 tests D30 passent avec ces fichiers. Un audit élargi des grilles DS5 a
identifié 24 autres PDF absents pour les vagues 1–4 ; la liste exacte est dans
`DS1_LIVRAISON_SOURCES_MANQUANTES_2026_11_21.json`. Leur absence empêche les
tests de présence correspondants et la reproduction exacte des citations de
la baseline DS5. Les calculs et schémas DS5 ne sont pas modifiés pour masquer
ces manques.

## Points attendus de l'équipe

| Responsable | Élément à fournir ou confirmer |
|---|---|
| Ghofrane | Revue de l'adaptation DS4 v1 et des corrections de contrat ; validation du dossier fictif, de l'applicabilité des sources et du Golden Set |
| Mouhib | D21 officiel des 56 secteurs, branche/commit et corpus/index associés ; cas de recette ; pages et dates d'effet des références du scénario |
| Oumaima | Cohérence de la fiche positive : PDF 208 h normalisé 48h, grille sélectionnée 42h ; pack des 24 PDF DS5 manquants pour une recette globale reproductible |
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
