# Scénario complet DS1 DS3 DS2 DS4

Le parcours technique fonctionne avec DS3 live, confirmation explicite des
faits documentaires, recherche DS2 live dans le corpus local, puis DS4 v1.
Le résultat live observé est `insufficient_evidence`, avec conclusion juridique
nulle et aucune citation finale. La validation juridique du fond reste ouverte.

## Dossier fictif

Configuration : `data/mock_cards/orchestrator_case_e2e_demo.json`.

- Carte : `case-e2e-payroll-001`, organisation fictive `org-demo`.
- Salarié : Ahmed Ben Salah ; employeur : Société Atlas Services SARL, fictive.
- Pièce : `paie_fictive_01_fr.pdf`, bulletin de mars 2026 déjà utilisé par DS3.
- Demande fictive : vérifier les éléments de paie, sans présumer d'irrégularité.
- Secteur gardiennage choisi explicitement comme hypothèse de test, non déduit
  de la fiche. À confirmer avec Ghofrane avant validation métier.
- Date de référence explicitement fixée au 31 mars 2026 pour le scénario.
- Recherche DS2 : `الأجر الأساسي منحة النقل`, secteur
  `gardiennage_securite_transport_fonds`, `top_k = 3`.

Le scénario remplace provisoirement le dossier de rupture envisagé : aucun
contrat ou courrier n'est présenté comme extrait par DS3 live. Ce choix permet
de tester immédiatement le périmètre effectivement supporté, une fiche de paie
PDF native. Une variante rupture devra être définie avec DS4.

## Parcours et garanties

1. DS1 vérifie l'autorisation de la Case Card et les métadonnées du document.
   La fiche fictive est stockée sous une référence liée à cette carte.
2. L'adaptateur officiel appelle DS3 en mode live. Les identifiants de requête,
   carte et document, le mode et le schéma de réponse sont vérifiés.
3. Les faits monétaires sont convertis via l'adaptateur livré par DS4. La
   liaison document/preuve/personne est déclarée, non inférée. La confiance
   et les citations originales sont conservées.
4. L'utilisateur sélectionne les faits, lit leurs citations et confirme la
   liaison à la personne et à la pièce. Aucune case n'est précochée. Une valeur
   insuffisamment fiable ou sans citation exploitable n'est pas confirmable.
5. Après confirmation seulement, DS1 appelle DS2 live. Une réponse mock,
   un refus ou une réponse de mauvaise identité ne permet pas de poursuivre.
6. DS4 reçoit uniquement les faits sélectionnés, marqués confirmés, et les
   sources récupérées sans certification juridique automatique. Les références
   et dates de DS2 ne sont pas inventées ou complétées par DS1.
7. La réponse passe par l'adaptateur DS1 officiel. Une conclusion non nulle
   est interdite. Les citations documentaires, de recherche et finales sont
   séparées. Les pages et dates d'effet manquantes sont signalées.

Les sessions sont en mémoire, liées à l'acteur et à la carte, limitées à 32
revues et expirent après 30 minutes. La confirmation revérifie la carte et les
permissions. Une double soumission avec la même sélection retourne le résultat
déjà obtenu ; une sélection différente après terminaison est rejetée.
L'audit conserve les étapes et identifiants, sans valeurs de paie ni requêtes.

## Validation observée

Commande : `python -m src.orchestrator.case_integration_demo --live-test`.
Le PDF peut être provisionné avec `--prepare-storage`. Le stockage de démo
doit être dans le workspace. Le script charge les paramètres locaux sans
afficher la clé API.

Premier test réel :

- DS3 live : environ 7,840 secondes ; trois faits monétaires exploitables.
- DS2 live : environ 196 millisecondes ; trois références renvoyées.
- DS4 : environ 7 millisecondes ; `analysis_status = insufficient_evidence`.
- `legal_conclusion = null` ; zéro citation finale.

La confirmation de ce test CLI est automatisée pour vérifier l'intégration,
explicitement marquée `automated_test_only`. Elle n'est ni une confirmation
humaine de la démo ni une approbation juridique.

La page a également été vérifiée dans le navigateur : extraction DS3 live en
8,686 secondes, trois valeurs affichées avec leur citation de page 1 et leurs
cases non cochées. La confirmation du lien document/personne/pièce est également
non cochée. Cette revue est laissée disponible pour un essai utilisateur réel.

La validation finale DS1/DS3/DS4 compte 754 tests réussis, dont onze nouveaux
tests de ce parcours. Les tests de contrôle injectent des réponses de services
simulées et sont distincts du test live. La syntaxe JavaScript est vérifiée.
Les sept contrôles D30 déjà signalés restent dépendants des PDF sources absents.

## Références réellement renvoyées et manques

| Référence | Page | Date d'effet |
|---|---|---|
| CCS-GARDIENNAGE-ART-46-v1 | absente | absente |
| CCS-GARDIENNAGE-ART-47-v1 | absente | absente |
| CC-CADRE-ART-2-v1 | absente | absente |

DS2 signale `applicable_at_reference_date = true` pour ces résultats ; cette
indication ne remplace pas la preuve des dates ni la validation d'applicabilité
par DS4. DS1 conserve ces valeurs et affiche les limites plutôt que fabriquer
une page ou une date.

Demandes à Mouhib : compléter ou expliquer les pages originales, les dates
d'effet et métadonnées de version de ces trois références ; préciser si le
nouveau corpus des 56 conventions corrige ces champs et fournir la branche
correspondante. Indiquer les références indisponibles plutôt que les supposer.

Demandes à Ghofrane : valider ou remplacer le dossier de paie et son hypothèse
sectorielle, désigner les articles réellement attendus pour la demande, vérifier
les liens demande/source et confirmer les conditions permettant de sortir de
`insufficient_evidence`. La validation juridique humaine reste indispensable.

## Essai dans l'interface

Sur la page locale, ouvrir la section « Scénario complet DS2 + DS3 → DS4 ».
Cliquer « Extraire la fiche avec DS3 live », examiner les faits et citations,
sélectionner les valeurs vérifiées, confirmer le lien document/personne/pièce,
puis lancer « Confirmer et lancer DS2 live → DS4 ».

Les routes API sont `/api/case-integration/prepare` et
`/api/case-integration/complete`. Elles servent uniquement ce scénario local
avec identité fictive ; elles ne constituent pas une authentification production.

## Mail proposé

Objet : Scénario DS1 DS3 live DS2 live DS4 testé — données et validation restantes

Bonsoir Mouhib, bonsoir Ghofrane,

Le scénario technique complet est opérationnel localement : extraction DS3 live
d'une fiche de paie fictive, confirmation explicite des faits et de leur liaison
à la pièce/personne, recherche DS2 live, puis analyse DS4 v1. Les suites DS1,
DS3 et DS4 totalisent 754 tests réussis.

Le test live a transmis trois faits monétaires et trois références. DS4 retourne
`insufficient_evidence`, avec `legal_conclusion = null` et aucune citation finale.
La confirmation du test technique CLI est automatisée ; la page propose une
véritable étape de revue utilisateur avant l'appel DS2/DS4.

Mouhib : les références CCS-GARDIENNAGE-ART-46-v1,
CCS-GARDIENNAGE-ART-47-v1 et CC-CADRE-ART-2-v1 sont retournées sans page ni date
d'effet. Peux-tu fournir ces métadonnées, ou indiquer ce qui reste indisponible,
et confirmer si elles sont corrigées dans la migration des 56 conventions ?
Le marqueur d'applicabilité retourné vaut true ; nous avons besoin des éléments
permettant de vérifier cette applicabilité au 31 mars 2026.

Ghofrane : pour avancer dans le périmètre DS3 actuel, j'ai préparé un dossier
fictif de vérification de paie, au lieu de l'analyse de contrats et lettres non
encore supportée en live. Le secteur gardiennage est une hypothèse de test,
non déduite de la fiche. Peux-tu valider ou corriger ce scénario, préciser les
articles attendus et les contrôles juridiques nécessaires ?

Aucune source ni conclusion n'est considérée juridiquement validée à ce stade.
Les changements restent locaux, sans commit ni push.

Bien cordialement,
Achref
