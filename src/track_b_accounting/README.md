# Track B — module comptable (DS5)

Calcule, avec du code Python testé, le **salaire de base conventionnel**, les **primes à montant fixe** et le
**SMIG/SMAG**, à partir des grilles vérifiées de `data/processed/`. Chaque montant est renvoyé avec ses
citations (PDF, page, article, entrée de `docs/DECISIONS.md`) ; sans source vérifiée, le module refuse
(« Citation ou Silence »). Le contrat d'échange est décrit dans `docs/CONTRACT_TRACK_B.md`.

```
src/track_b_accounting/
  calc/                 calculs : salaire_base, prime, smig (aucune donnée saisie ici)
  contract/             interface JSON track_b.v0 : handler (handle) et ligne de commande (cli)
  demo.py               démo du contrat : 122 échanges orchestrateur → Track B → Track A (fictifs)
  evaluation/           jeu de référence (201 cas lus dans les PDF), banc de mesure et baseline
  tests/                tests unitaires et de bout en bout du module
  tools/                outils de contrôle des PDF et de l'OCR
  requirements.txt      dépendances d'exécution et de test
  requirements-dev.txt  dépendances de développement (contrôle des types et du style)
  mypy.ini, ruff.toml   réglages de ces contrôles
```

## Installation

Depuis la racine du dépôt (Python 3.11 ou plus récent) :

```
python -m pip install -r src/track_b_accounting/requirements-dev.txt
```

## Commande unique de mesure

Depuis la racine du dépôt :

```
python src/track_b_accounting/evaluation/metrics_harness/run_eval.py --date AAAA-MM-JJ
```

Elle évalue le module sur les 201 cas du jeu de référence, écrit le rapport dans
`evaluation/results/eval_<date>.json` et `.md`, et compare automatiquement chaque métrique à la baseline
(`evaluation/results/baseline.json`). Code de sortie : **1** en cas de faux montant ou d'exception, **2** si au
moins deux métriques baissent par rapport à la baseline, **0** sinon. Détails : `evaluation/README.md`.

## Autres commandes

Toutes depuis la racine du dépôt :

| Objet | Commande |
|---|---|
| Tests du module | `python -m pytest -q src/track_b_accounting/tests` |
| Tests avec couverture | `python -m pytest -q src/track_b_accounting/tests --cov=src/track_b_accounting` |
| Types | `python -m mypy --config-file src/track_b_accounting/mypy.ini` |
| Style (règles de base) | `python -m ruff check src/track_b_accounting` |
| Format | `python -m ruff format --check src/track_b_accounting` |
| Démo du contrat | `python -m src.track_b_accounting.demo` |
| Une requête JSON | `python -m src.track_b_accounting.contract.cli <fichier.json>` |

## Reste à faire

- **mypy strict** sur `calc/` et `contract/` : les contrôles actuels utilisent les réglages par défaut de mypy et
  les seules règles de base de ruff. Le mode strict (types `dict` paramétrés, aucune fonction sans annotation)
  n'est pas encore appliqué.
