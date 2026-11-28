# Évaluation — DS5 Comptable Track (Track B)

Ce dossier contient le **jeu de référence** (golden set) et les **métriques**
du Track B. Comme pour les autres rôles, l'évaluation n'est pas un rôle à
part : DS5 évalue son propre module.

```
evaluation/
  README.md                                ce fichier
  golden_sets/track_b_golden.v0.json       514 cas, valeurs attendues lues dans les PDF
  golden_sets/track_b_hors_perimetre.v0.json  48 cas hors périmètre (refus attendus, D110)
  golden_sets/track_b_livrable.v0.json     12 cas du rapport de conformité (D108, D109), évalués à part
  metrics_harness/run_eval.py              script : appelle le handler, calcule les métriques
  results/baseline.json, baseline.md       rapport de référence (seuls résultats versionnés)
  results/eval_<date>.json, .md            rapports des relances (ignorés par git)
  results/eval_<date>_comparaison.json     écarts à la baseline, métrique par métrique (ignoré par git)
```

## Méthode

**Indépendance.** Les valeurs attendues viennent **des PDF de `data/raw/pdf/`**,
lus visuellement (rendu à 100-300 dpi), **jamais** de `data/processed/` ni du
code. Les tests unitaires (`../tests/`) vérifient le code contre nos propres
données ; cette évaluation vérifie le module contre la source.

**Chaque cas** contient :
- `requete` : opération, paramètres et langue, envoyés tels quels au handler ;
- `attendu` : `ok` avec montant, unité et citations attendues (PDF et page),
  ou `refus` avec son code (et, pour certains cas, les messages FR et AR attendus) ;
- `justification` : PDF, page et emplacement (tableau, ligne, colonne, ou
  article et texte lu), pour vérifier le cas sur le document ;
- `certitude` : **L** (lu directement), **C** (calculé à la main à partir de
  cellules lues), **I** (interprétation) ; `decision` donne l'entrée de
  `docs/DECISIONS.md` (D6, D9, D10, D23, D29, D38, D46, D47, D49 à D72, D75, D78 à D89, D91 à D100) qui
  fonde un cas I ou C ;
- `verification_humaine` : `true` quand DS5 a vérifié le cas sur le PDF.

Convention des colonnes : le numéro de colonne est le degré ; le degré 1 est
la colonne la plus à droite (en-tête « 2/0 » en métallurgie, « 0-2 » au BTP, « 1 » / « 2 » dans les grilles
des associations pour personnes handicapées).

**Répartition (514 cas, dont 503 vérifiés par DS5 sur le PDF : `verification_humaine = true` ; 41 cas en contrat v1).**

| Catégorie | Cas | Contenu |
|---|---|---|
| `ok` | 302 | Salaires de base (une ou plusieurs populations et dates par secteur), primes à montant fixe, SMIG |
| `art13` | 6 | Article 13 au-delà du dernier degré : métallurgie (calculés à la main) et BTP (table de correspondance p.8) |
| `refus` | 199 | Bornes exactes, ancienneté hors grille, catégories ou populations inconnues ou non couvertes, primes non couvertes, CNSS, conversion d'unité, secteur non transcrit |
| `piege` | 7 | Date antérieure à la première grille ou au décret SMIG, sous-catégorie manquante, ancienneté pour un occasionnel, alias non admis (messages FR et AR attendus) |

Par certitude : 240 cas **L**, 8 cas **C**, 266 cas **I**. Par opération :
354 `salaire_base`, 156 `prime`, 3 `smig`, 1 `cotisation_cnss` (refus).

Secteurs couverts (nombre de cas) : métallurgie et bâtiment 22, BTP 20,
enseignement privé 18, associations pour personnes handicapées 16, assurance
16, banques 14, gardiennage 14, confiserie 8, cosmétiques 7, savonnerie 7,
commerce du pétrole 7, boissons gazeuses 7, torréfaction du café 6, pâtes 6,
plasturgie 6, minoteries 6, teintureries 6, gestion des déchets 8, commerce de gros et de détail 8, mécanique et
stations-service 7, boissons alcoolisées 7, bois et ameublement 7, habillement 6, imprimerie 8, matériel agricole 8,
fonderie 9, verre 7, boulangeries 7, textile 7, produits d'entretien 7, automobiles 8, matériaux de construction 8,
peintures 11, chaussure 9, cuirs 8, clercs d'avocats 8, pharmacies 7, conserveries 8, grossistes en médicaments 8,
cinéma 8, transport routier 9, jardins d'enfants 11, cliniques 8, location de voitures 9, commerce des matériaux 9,
cafés 11, ports 17, électricité et électronique 11, presse écrite 11, industrie laitière 10,
explosifs et artifices 10, agences de voyages 5, hôtels 5 ; cas v1 du contrat (D75 à D77) répartis dans leurs secteurs ;
SMIG 4 ; secteur fictif non supporté 1.

## Métriques

| Métrique | Définition | Cible |
|---|---|---|
| **Faux montants** (critique) | Montant ou unité faux pour un `ok` attendu, **et** `ok` renvoyé alors qu'un refus est attendu : la règle « Citation ou Silence » est violée | **0** |
| Exactitude des montants | `ok` attendu : même montant au millime et même unité | 100 % |
| Silence excessif | `ok` attendu, refus renvoyé (perte de couverture, pas de faux montant) | 0 |
| Refus corrects | Refus attendu : statut `refus` **et** même code ; si le cas fixe `message_fr` ou `message_ar`, même texte | 100 % |
| Citations valides | Pour un `ok` : nombre de citations, nom du PDF et page égaux à ceux du golden set ; `source_file` et `data_file` existent ; `decision_ref` est un titre `### Dn` de `docs/DECISIONS.md` | 100 % |
| Conformité aux schémas | Réponse valide contre `track_b_response.v0` (ou `track_b_response.v1` pour un cas dont la requête porte `contract_version: track_b.v1`, D75) et contre le schéma commun (`src/shared/schemas/common.v0.schema.json`) | 100 % |
| Statut erreur, exceptions | Réponses `erreur` et exceptions levées par le handler | 0 |

Les métriques sont calculées **sur l'ensemble des cas et sur les seuls cas
vérifiés par DS5** (`verification_humaine = true`), puis ventilées par
certitude (L, C, I) et par catégorie. Un échec sur un cas L ou C est une
**erreur de lecture** (du golden set ou du code) ; un échec sur un cas I est
un **désaccord d'interprétation**, compté à part.

## Relancer

Depuis la racine du dépôt :
```
python src/track_b_accounting/evaluation/metrics_harness/run_eval.py --date AAAA-MM-JJ
```
- Le script appelle le handler en **Python direct**
  (`track_b_accounting.contract.handle`), comme l'orchestrateur ; chaque
  réponse passe par un aller-retour JSON, comme sur le réseau.
- Une **exception** du handler est enregistrée comme échec
  (`exception_inattendue`, type et message) et l'évaluation continue.
- Sorties : `results/eval_<date>.json` (clés triées) et `.md`. La date est
  passée en argument : à commit et date égaux, les fichiers sont identiques à
  l'octet près.
- **Comparaison automatique à la baseline** (sans `--baseline`) : les
  métriques de l'ensemble sont comparées à `results/baseline.json`. Le script
  affiche, pour chaque métrique, la valeur de la baseline, la valeur obtenue,
  l'écart et le statut (`stable`, `amélioration`, `baisse`, `non comparable`),
  et écrit le même détail dans `results/eval_<date>_comparaison.json`. Une
  métrique en taux est comparée sur son taux, un compteur sur son nombre.
- **Tranche hors périmètre (D110)** : `golden_sets/track_b_hors_perimetre.v0.json` (CNSS, IRPP,
  factures, dépenses, ratios, heures supplémentaires, congés, indemnités, conventions-cadres, secteurs
  sans grille, populations inexistantes, net à payer, simulation de hausse, conversion d'unité ; mêmes
  scénarios en v0 et en v1) est évaluée à part : les cas du jeu principal ne changent pas. Métrique
  `taux_refus_hors_perimetre` = refus avec le code attendu **et** le motif attendu
  (`message_fr_contient`) / cas hors périmètre ; affichée, comparée à la baseline, **seuil 85 %**
  (cahier des charges §8.4).
- Code de sortie :
  - **1** s'il y a au moins un faux montant ou une exception (jeu principal,
    tranche hors périmètre ou livrable) ;
  - **2** sinon, si **au moins deux métriques baissent** par rapport à la
    baseline (règle de régression : le changement est bloqué) ;
  - **3** sinon, si `taux_refus_hors_perimetre` est sous 85 % ;
  - **0** sinon.
- `--baseline` réécrit le rapport de référence (`results/baseline.*`) sans
  comparer, à faire seulement quand le golden set ou le module change
  volontairement.
- Le banc lui-même est testé : `../tests/test_run_eval.py` (verdicts,
  métriques, comparaison, codes de sortie, et relance complète identique à la
  baseline versionnée).

## Jeu du livrable : rapport de conformité (D108, D109)

`golden_sets/track_b_livrable.v0.json` : 12 cas de l'opération `rapport_conformite` (contrat v1), tous à
`verification_humaine: true` (vérifiés par DS5 sur les images des PDF, D108). Ils sont évalués à part, dans le bloc
`livrable` du rapport ; les métriques de l'ensemble ne changent pas.

- **Attendu** : pour chaque ligne du rapport, dans l'ordre, `rubrique`, `code`, `statut`, `montant_convention`,
  `unite`, `difference`, code du `motif` et citations (PDF, page) ; puis la liste des documents manquants et le
  drapeau `aucune_ligne_verifiee`. Un refus attendu donne son code.
- **Montants attendus** : relus sur le PDF (couche texte, ou image rendue à 110 dpi), ou repris d'un cas déjà
  vérifié par DS5 (TB-05, TB-17). `justification.montants` dit où chacun a été lu.
- **Verdicts** : `correct`, `faux_montant` (montant de convention, unité ou différence différents, ou montant donné
  là où l'attendu n'en a pas), `lignes_differentes`, `statut_ligne_incorrect`, `documents_incorrects`, puis ceux du
  jeu principal (`montant_au_lieu_de_refus`, `silence_excessif`, `code_refus_incorrect`, `statut_erreur`,
  `exception_inattendue`).
- **Métriques** : cas corrects, lignes correctes, faux montants (lignes), statuts incorrects, refus corrects,
  citations valides, conformité au schéma de réponse du rapport, erreurs et exceptions. Elles sont comparées au bloc
  `livrable` de la baseline ; un faux montant du livrable donne aussi le code de sortie 1, et les baisses du livrable
  comptent avec celles de l'ensemble pour la règle des deux baisses.

## Limites

- **Indépendance partielle tant que `verification_humaine` n'est pas à
  `true`.** Les valeurs ont été lues dans les PDF par la même personne qui a
  transcrit les grilles ; une erreur de lecture systématique pourrait se
  retrouver dans les deux. Seuls les cas vérifiés par DS5 sur le PDF sont une
  vérification réellement indépendante : le rapport donne leur nombre et leurs
  métriques à part.
- **Les cas I traduisent nos décisions** (D6, D9, D10, D23), pas le texte seul :
  ils mesurent la conformité du module à ces décisions, pas leur justesse.
- **514 cas sur plus de 40 000 cellules transcrites** : c'est un échantillon. La couverture
  exhaustive des grilles repose sur la double lecture et les contrôles
  automatiques (`../tests/test_grid_bm.py`, `../tests/test_grid_btp.py`,
  `../tests/test_grid_associations.py`), dont le contrôle de hausse entre
  dates sur toutes les grilles à plusieurs tables (`../tests/test_controle_hausse.py`).
- Les scans des pages 30 à 35 de la métallurgie sont bruités ; les cas dont un
  chiffre est peu net portent une `note`.
