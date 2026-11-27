# Validation live des documents et restauration des sources D30

Les deux fiches de démonstration ont été rejouées avec DS3 live, suivies de
tests automatisés de confirmation et de calcul DS5. Les sept PDF manquants
pour D30 ont été retrouvés localement et restaurés. Aucun champ extrait ni
aucune grille de salaire n'a été modifié pour faire passer ces tests.

## Fiche 02 avec pièges

La carte `doc-company-payslip-02` correspond au fichier
`paie_fictive_04_pieges.pdf`, et non au document de référence DS3 numéro 02.
La copie en stockage DS3 est identique au PDF du golden set (SHA-256 comparé).

- Extraction réelle Gemini réussie en 8,933 secondes, mode `live`.
- Les dates de période sont 2024-02-01 et 2024-02-29.
- `hire_date`, `employment_status` et `work_hours_regime` restent null et
  `unavailable`, conformément aux pièges du document et à ses attendus.
- Une tentative de confirmation des champs null retourne
  `unconfirmed_or_unusable_field`.
- Les champs null sont absents des paramètres de calcul DS5.
- Catégorie imprimée : `2 b`, correctement normalisée en `2B`.
- DS5 refuse cette catégorie pour la grille configurée
  `METALLURGIE_BATIMENT`, population `admin_tech`, avec `PARAM_INVALIDE`.
  Les catégories acceptées sont `1A`, `1B`, puis `2` à `18` ; pas `2B`.
- La date d'entrée imprimée sur deux chiffres ne permet pas non plus de
  proposer une ancienneté fiable. La population et l'ancienneté restent à
  compléter, sans valeur inventée.

Conclusion technique : c'est un scénario négatif volontaire, pas une erreur
DS3 à corriger. Il ne faut ni remplacer `2B` par `2`, ni ajouter cette catégorie
à la grille sans source. Aucun travail DS3 n'est requis pour ces trois champs.
Si un scénario positif avec une vraie catégorie `2B` est souhaité, Oumaima doit
identifier la convention/population qui la couvre, et fournir la source ; DS1
ne peut pas déduire cela du seul nom d'entreprise fictif.

## Fiche 01 et parcours positif

`doc-company-payslip-01` utilise `paie_fictive_01_fr.pdf`. La copie en stockage
est identique au golden set. Extraction live réussie en 4,720 secondes.

Après confirmation des champs utilisables et, pour ce test technique,
confirmation automatique de l'ancienneté proposée de 6,495890 ans :

- secteur configuré : `METALLURGIE_BATIMENT` ; population : `admin_tech` ;
- catégorie extraite : `3` ; date : 2026-03-01 ;
- calcul DS5 réussi : `641.013 TND/mois` ;
- table `BM_T_2024-01-01`, degré 4, source PDF page 34 ;
- citations documentaires et citations de calcul séparées ;
- avertissement conservé sur la différence avec le salaire imprimé `424.100`.

Ce succès valide l'exécution sur les paramètres fictifs configurés, pas une
conclusion sur un salaire légal dû. La fiche indique un régime normalisé 48h,
tandis que le détail de la grille DS5 annonce 42h : l'applicabilité de cette
combinaison doit être revue avec Oumaima si le cas doit devenir une référence
métier. Le scénario de paie reste explicitement fictif.

## Sources D30 restaurées

Les sources D30 sont maintenant suivies dans `main`, sous `data/raw/pdf/`. Aucun chemin personnel ni pack externe n’est requis. Avec un clone partiel, inclure ce dossier avant de lancer les tests. Les 24 autres PDF DS5 précédemment signalés manquants sont également présents dans `main` au contrôle du 22 novembre 2026.

Contrôles : ouverture PDF, nombre de pages, titre de couverture vérifié
visuellement, correspondance du registre DS2 et SHA-256 identique avant/après
copie. Il ne s'agit pas d'une nouvelle vérification de chaque cellule des grilles.

| Secteur D30 | Pages du PDF restauré |
|---|---:|
| gardiennage_securite_transport_fonds | 21 |
| construction_metallique | 35 |
| btp | 25 |
| associations | 29 |
| assurance | 21 |
| enseignement_prive | 27 |
| banques | 23 |

Commande rejouée :
`python -m pytest -q src/shared/tests/test_sectors_table.py`.
Résultat : **17 tests réussis**, dont les sept qui échouaient sur les PDF absents.
La table D30 et ses assertions ne sont pas modifiées.

Les rapports antérieurs mentionnant sept sources locales manquantes décrivent
donc un état historique résolu dans le dépôt partagé. La migration D21 vers les 56 secteurs
reste un chantier distinct.

## Suite et demandes éventuelles

- Fiche 02 : contrôle live des nulls terminé ; aucun correctif DS3 requis.
- `2B` : cause identifiée, refus attendu ; ne plus la traiter comme un bug
  d'extraction ni comme le scénario de succès salaire de base.
- D30 : fichiers restaurés et tests réussis ; aucune demande de renvoi de ces
  sept PDF n'est nécessaire au groupe à ce stade.
- Oumaima : si validation métier demandée, confirmer la compatibilité de la
  fiche fictive positive avec secteur/population/régime et les résultats attendus.
  Un cas positif `2B` nécessiterait un autre jeu de paramètres validé et sourcé.

Les confirmations utilisées pour ces mesures live sont automatisées pour le
test technique. Elles ne remplacent pas une revue humaine juridique ou comptable.
Les détails de l'exécution sont disponibles localement dans
`tmp/document_live_validation_2026_11_21.json` et le manifeste des copies dans
`tmp/d30_restore_manifest.json`.


## Contrôle actualisé du 22 novembre 2026

Après actualisation sur main `34d8bec` et récupération des dossiers suivis nécessaires au clone partiel (`data/raw/pdf`, `scripts`, `experiments`), la suite globale donne **5227 tests réussis, 4 ignorés, aucun échec**. Les 24 PDF DS5 autrefois manquants sont tous disponibles dans le dépôt ; aucune demande de pack externe n’est nécessaire. Les mesures live du 21 novembre ci-dessus restent historiques et ne sont pas une recette live de la fiche modifiée de #56.
