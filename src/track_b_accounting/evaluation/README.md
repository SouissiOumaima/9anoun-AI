# Évaluation — DS5 Comptable Track (Track B)

Ce dossier contient le **jeu de référence** (golden set) et les **métriques**
du Track B. Comme pour les autres rôles, l'évaluation n'est pas un rôle à
part : DS5 évalue son propre module.

```
evaluation/
  README.md                                ce fichier
  golden_sets/track_b_golden.v0.json       244 cas, valeurs attendues lues dans les PDF
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
  `docs/DECISIONS.md` (D6, D9, D10, D23, D29, D38, D46, D47, D49 à D66) qui
  fonde un cas I ou C ;
- `verification_humaine` : `true` quand DS5 a vérifié le cas sur le PDF.

Convention des colonnes : le numéro de colonne est le degré ; le degré 1 est
la colonne la plus à droite (en-tête « 2/0 » en métallurgie, « 0-2 » au BTP, « 1 » / « 2 » dans les grilles
des associations pour personnes handicapées).

**Répartition (244 cas, dont 234 vérifiés par DS5 sur le PDF : `verification_humaine = true`).**

| Catégorie | Cas | Contenu |
|---|---|---|
| `ok` | 129 | Salaires de base (une ou plusieurs populations et dates par secteur), primes à montant fixe, SMIG |
| `art13` | 6 | Article 13 au-delà du dernier degré : métallurgie (calculés à la main) et BTP (table de correspondance p.8) |
| `refus` | 103 | Bornes exactes, ancienneté hors grille, catégories ou populations inconnues ou non couvertes, primes non couvertes, CNSS, conversion d'unité, secteur non transcrit |
| `piege` | 6 | Date antérieure à la première grille ou au décret SMIG, sous-catégorie manquante, ancienneté pour un occasionnel, alias non admis (messages FR et AR attendus) |

Par certitude : 145 cas **L**, 7 cas **C**, 92 cas **I**. Par opération :
177 `salaire_base`, 63 `prime`, 3 `smig`, 1 `cotisation_cnss` (refus).

Secteurs couverts (nombre de cas) : métallurgie et bâtiment 22, BTP 20,
enseignement privé 18, associations pour personnes handicapées 16, assurance
16, banques 14, gardiennage 14, confiserie 8, cosmétiques 7, savonnerie 7,
commerce du pétrole 7, boissons gazeuses 7, torréfaction du café 6, pâtes 6,
plasturgie 6, minoteries 6, teintureries 6, gestion des déchets 8, commerce de gros et de détail 8, mécanique et
stations-service 7, boissons alcoolisées 7, bois et ameublement 7, habillement 6, agences de voyages 5, hôtels 5 ;
SMIG 4 ; secteur fictif non supporté 1.

## Métriques

| Métrique | Définition | Cible |
|---|---|---|
| **Faux montants** (critique) | Montant ou unité faux pour un `ok` attendu, **et** `ok` renvoyé alors qu'un refus est attendu : la règle « Citation ou Silence » est violée | **0** |
| Exactitude des montants | `ok` attendu : même montant au millime et même unité | 100 % |
| Silence excessif | `ok` attendu, refus renvoyé (perte de couverture, pas de faux montant) | 0 |
| Refus corrects | Refus attendu : statut `refus` **et** même code ; si le cas fixe `message_fr` ou `message_ar`, même texte | 100 % |
| Citations valides | Pour un `ok` : nombre de citations, nom du PDF et page égaux à ceux du golden set ; `source_file` et `data_file` existent ; `decision_ref` est un titre `### Dn` de `docs/DECISIONS.md` | 100 % |
| Conformité aux schémas | Réponse valide contre `track_b_response.v0` et contre le schéma commun (`src/shared/schemas/common.v0.schema.json`) | 100 % |
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
- Code de sortie :
  - **1** s'il y a au moins un faux montant ou une exception ;
  - **2** sinon, si **au moins deux métriques baissent** par rapport à la
    baseline (règle de régression : le changement est bloqué) ;
  - **0** sinon.
- `--baseline` réécrit le rapport de référence (`results/baseline.*`) sans
  comparer, à faire seulement quand le golden set ou le module change
  volontairement.
- Le banc lui-même est testé : `../tests/test_run_eval.py` (verdicts,
  métriques, comparaison, codes de sortie, et relance complète identique à la
  baseline versionnée).

## Limites

- **Indépendance partielle tant que `verification_humaine` n'est pas à
  `true`.** Les valeurs ont été lues dans les PDF par la même personne qui a
  transcrit les grilles ; une erreur de lecture systématique pourrait se
  retrouver dans les deux. Seuls les cas vérifiés par DS5 sur le PDF sont une
  vérification réellement indépendante : le rapport donne leur nombre et leurs
  métriques à part.
- **Les cas I traduisent nos décisions** (D6, D9, D10, D23), pas le texte seul :
  ils mesurent la conformité du module à ces décisions, pas leur justesse.
- **244 cas sur plus de 10 000 cellules transcrites** : c'est un échantillon. La couverture
  exhaustive des grilles repose sur la double lecture et les contrôles
  automatiques (`../tests/test_grid_bm.py`, `../tests/test_grid_btp.py`,
  `../tests/test_grid_associations.py`).
- Les scans des pages 30 à 35 de la métallurgie sont bruités ; les cas dont un
  chiffre est peu net portent une `note`.
