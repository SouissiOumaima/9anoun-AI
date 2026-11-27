# Préparation DS1 pour la migration des 56 secteurs

La détection DS1 vers DS2 ne choisit plus le premier alias correspondant.
La partie DS1 est préparée et testée ; la migration réelle reste conditionnée
au vocabulaire et au corpus de Mouhib. Le D21 installé contient encore 7 secteurs.
Les changements sont locaux, sans commit ni push.

## Réalisation DS1

- Collecte des secteurs explicites sans dépendre de l'ordre des entrées D21.
- Reconnaissance des codes, identifiants de source, libellés et alias FR/AR
  aux limites de mots ; normalisation casse, diacritiques, espaces et tirets.
- Une désignation précise masque seulement les alias plus courts inclus dans
  la même expression. Les mentions distinctes et alias partagés restent ambigus.
- Lecture des règles `sector_ambiguities` : format historique `alias` séparé
  par `/`, ou liste `aliases`. Clarification FR/AR avec les vrais choix.
- Aucun appel DS2 en cas d'ambiguïté ; aucun code inventé pour un secteur inconnu.
- Protection des expressions sécurité sociale, assurance maladie/sociale/santé
  et variantes arabes contre les faux secteurs assurance/gardiennage.
- D30 et l'activation DS5 restent indépendantes. Une convention dans D21 ne
  rend pas automatiquement sa grille DS5 disponible.

Les variantes linguistiques non livrées dans les alias ne sont pas devinées.

## Filtre DS2 et sources générales

DS1 transmet `sector` lorsqu'il est explicite et univoque. Une recherche
thématique n'est pas restreinte artificiellement à un unique `source_id`.
Le routage d'une demande explicite d'article conserve sa référence précise.

Le filtre DS2 actuel conserve le secteur demandé et les sources dont
`sector = null`. Le test DS1/DS2 utilise le vrai ingesteur et handler sur trois
sources synthétiques : banques et convention-cadre sont rendues, BTP exclu.
Cela valide le filtre, pas la couverture de toutes les sources juridiquement
applicables. Classement, `top_k` et rappel multi-sources restent à évaluer sur
le corpus officiel migré avec des attendus fournis par DS2/DS4.

## Réception de la livraison

```text
python -m src.orchestrator.sector_vocabulary_audit chemin/vers/vocabulaire.json --expected-sectors 56
```

Contrôle en lecture seule : schéma D21, nombre de secteurs, codes uniques,
alias non vides après normalisation et références des ambiguïtés. Les alias
partagés sont signalés pour clarification, sans choisir selon leur ordre.
Sans argument, le contrôle examine le fichier installé : 7 secteurs, zéro erreur.
Redémarrer DS1/DS2 après remplacement du vocabulaire mis en cache.

## Validation

- 45 nouveaux cas : FR/AR, ambiguïtés, mots partiels, désignations précises,
  inversion de l'ordre, séparation D21/D30, recette et intégration DS1/DS2.
- Le vocabulaire à 56 secteurs des tests est synthétique, injecté en mémoire.
  Il ne remplace pas la livraison officielle et ne valide pas ses 56 conventions.
- 825 tests réussis DS1/DS3/DS4 et DS2 vocabulaire/recherche ; un test HTTP DS2
  bloqué en sandbox a été isolé puis réussi hors sandbox. Total : 826 succès.
- Les sept contrôles D30 de présence des PDF sources restent dépendants des
  fichiers absents du poste, comme signalé précédemment ; non inclus ici.

## Éléments attendus de Mouhib

1. Branche/commit du D21 officiel complet : codes stables, sources, libellés
   FR/AR et alias. Documenter les renommages/suppressions de codes existants.
2. Ambiguïtés et exemples FR/AR de recette, avec secteurs et sources attendus,
   notamment commerce de gros/matériaux et boissons gazeuses/alcoolisées.
3. Corpus/index associé, procédure d'installation et sources générales
   représentées par `sector = null`. Fournir des attendus multi-sources.
4. D30 actualisée seulement pour les liens DS2/DS5 prouvés sur un même PDF,
   avec statut des grilles, en coordination avec Oumaima.

Préférence : recevoir les 56 ensemble sur une branche dédiée et les activer
après contrôle, tests sur alias réels et recette du corpus.

## Mail proposé

Objet : DS1 préparé pour les 56 secteurs — livraison D21 et recette DS2 attendues

Bonjour Mouhib,

J'ai terminé la préparation côté DS1. Le détecteur ne retient plus le premier
alias : il identifie les correspondances multiples, privilégie les désignations
précises dans une même expression et demande une clarification FR/AR quand le
secteur reste ambigu. Les protections sécurité sociale/assurance maladie sont
conservées.

Pour répondre à tes trois questions :

1. D21 est consommé par `legal_retrieval_prompt.py` pour DS2.
   `sector_mapping.py` utilise séparément D30 pour les grilles DS5.
2. Je préfère recevoir les 56 secteurs ensemble sur une branche dédiée, avec
   codes stables et changements documentés, puis les activer après recette.
3. DS1 transmet déjà le secteur explicite et univoque. Le filtre DS2 actuel
   conserve ce secteur et les sources générales avec `sector = null`.
   Ce comportement est testé ; la couverture complète reste à mesurer sur
   le corpus migré.

Peux-tu me transmettre la branche et le commit du vocabulaire D21 officiel,
les règles d'ambiguïté, des exemples FR/AR avec secteurs et sources attendus,
ainsi que la version du corpus/index associée ? Merci également de préciser
les sources générales à conserver et de coordonner avec Oumaima la D30 pour
les seuls liens réellement prouvés avec ses grilles.

La préparation comprend 45 cas de migration, dont un vocabulaire synthétique
de 56 secteurs. La validation élargie totalise 826 succès. Le D21 réel installé
contient encore 7 secteurs : la migration officielle n'est donc pas encore
validée. Dès réception, je pourrai tester tes alias réels et le parcours DS1/DS2
avant activation. Les changements DS1 restent locaux, sans commit ni push.

Bien cordialement,
Achref
