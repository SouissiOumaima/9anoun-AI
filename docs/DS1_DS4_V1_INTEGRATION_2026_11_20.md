# Intégration DS1 vers DS4 Track A v1

Le parcours officiel DS1 vers DS4 v1 fonctionne sur la Case Card fictive du
dépôt. La réponse est une analyse préparatoire, sans conclusion juridique
validée. Les changements sont locaux et ne sont pas publiés sur GitHub.

## Source et périmètre

Livraison importée depuis `DS4_Lawyer_Track_v1`, commit `52c5384`.
L'archive fournie contient les schémas, exemples et rapports, mais pas les
modules Python : ceux-ci proviennent du commit Git.

Import ciblé des sources/tests DS4 et de ses données, schémas et documents.
Les différences de la branche concernant DS1, DS2, DS3, DS5, D30 et les fichiers
partagés ne sont pas reprises. Les modifications locales de performance DS3
et de design DS1 sont conservées.

## Raccordement officiel

- Le planner utilise `track_a.v1` pour l'analyse de la Case Card autorisée.
- Le constructeur conserve son mode v0 par défaut pour les anciens appelants.
- La conversion v1 conserve les liens `event_ids` et `evidence_ids` des demandes
  et des événements. Les sources des pièces restent des références de la carte.
- `TrackAAdapter` délègue les requêtes v1 à `DS1TrackAV1Adapter`. Les requêtes
  v0 gardent l'adaptateur existant ; les versions inconnues sont rejetées.
- L'identité de requête, la carte de type case et le mode lecture seule sont
  vérifiés à la frontière v1. Les entrées ne sont pas modifiées.
- Une réponse préparatoire valide peut avoir zéro citation finale. Cela
  n'autorise aucune conclusion juridique ; une réponse avec une conclusion
  non nulle est rejetée.
- L'interface affiche le statut préparatoire, la chronologie déclarée, les
  informations à vérifier et un avertissement FR/AR de revue humaine.

## Ajustements à communiquer à DS4

1. Le schéma d'entrée v1 livré avait encore `$id`, titre et description v0.
   Ces métadonnées sont corrigées dans le schéma opérationnel et sa copie
   documentaire. Les contraintes métier sont inchangées. Cette correction
   modifie nécessairement le SHA-256 de ces deux fichiers livrés.
2. Le handler v1 chargeait le schéma de réponse relativement au dossier courant.
   Il utilise désormais un chemin fondé sur `__file__`.
3. La frontière DS1 v0 exigeait au moins une citation pour tout succès. La
   frontière v1 utilise le contrat DS4 préparatoire, autorisant zéro citation
   avec `legal_conclusion = null`, sans assouplir le comportement v0.

## Validation

- Les 322 tests DS4 livrés passent dans le dépôt DS1.
- La validation finale ciblée DS1/DS4/DS3 réussit : 743 tests. La syntaxe
  JavaScript de l'interface est vérifiée avec `node --check`.
- Dix nouveaux tests DS1 couvrent le parcours réel FR/AR, la non-mutation,
  la mauvaise carte, l'écriture interdite, une version inconnue, une conclusion
  non autorisée et les trois exemples de livraison.
- La validation élargie DS1/DS4/DS3/shared a produit 986 succès et 7 échecs.
  Ces sept échecs sont les contrôles D30 de présence des PDF sources dans
  `data/raw/pdf/`, absents de ce poste. La table et ces tests ne sont pas modifiés.
- Test HTTP sur `/api/chat` avec `case-demo-001` : succès,
  route `track_a_legal.analyze_case`, réponse `case_preparatory`,
  `analysis_status = preparatory`, `legal_conclusion = null`, zéro citation finale.

## Limites et scénario suivant

Le test de la démo utilise les faits structurés fictifs de la Case Card. Il
ne constitue pas une extraction live de contrats ou lettres de licenciement.
DS3 live conserve son périmètre actuel de fiches de paie PDF.

Les adaptateurs et pipelines DS2/DS3 livrés sont importés et testés avec la
suite DS4. La démo n'enchaîne pas automatiquement une recherche DS2 et une
extraction DS3 live à chaque analyse de dossier : le planner transmet la carte
structurée disponible, sans fabriquer de sources ni de confirmations.

Le prochain scénario doit préciser la requête DS2, la fiche de paie fictive,
les liens document/preuve/personne, les confirmations utilisateur et les
références juridiques vérifiées. La validation humaine des sources et du Golden
Set reste à effectuer côté DS4. Les dates partielles de Case Card restent
refusées par le constructeur actuel plutôt que converties arbitrairement.

Une étape ultérieure de ce travail a ajouté un parcours E2E distinct avec
extraction DS3 live, confirmation explicite, recherche DS2 live et DS4.
Le parcours de chat décrit ci-dessus reste inchangé. Le scénario E2E et ses
limites sont documentés dans `DS1_DS2_DS3_DS4_SCENARIO_2026_11_20.md`.

## Essai dans la démo

Choisir « Affaire Démo — case », puis envoyer « Analyse les preuves de ce
dossier ». En arabe : « حلل أدلة هذه القضية. ». Le résultat doit être présenté
comme préparatoire et ne doit afficher aucune conclusion juridique définitive.
