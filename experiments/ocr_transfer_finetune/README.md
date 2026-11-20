# Transfer Learning vs Fine-Tuning — reconnaissance de texte arabe / français (DS3, partie A)

Validation du module *Project Cognition & IA*. On part d'un modèle de reconnaissance de texte
pré-entraîné, on l'adapte à des lignes de fiches de paie et de conventions collectives tunisiennes
(données **fictives**), et on compare trois mesures sur le **même** jeu de test :

| Méthode | Ce qui est entraîné |
|---|---|
| Baseline | rien : le modèle pré-entraîné tel quel |
| Transfer Learning | la tête CTC seule (encodeur gelé) |
| Fine-Tuning | tout le chemin CTC sauf les BatchNorm (variante `bn_frozen`), avec un learning rate faible |

Résultats : [`results.md`](results.md) (fichier généré, uniquement des chiffres mesurés) et
[`loss_curves.png`](loss_curves.png). Analyse critique : [`ANALYSE.md`](ANALYSE.md).

## Modèle choisi : `arabic_PP-OCRv5_mobile_rec` (PaddleOCR)

- C'est **le même modèle que l'OCR de production** de la tâche 1 (`src/document_intelligence/reading/ocr.py`) :
  ce qu'on apprend ici sert directement le projet.
- Il lit déjà l'arabe, et son dictionnaire (747 caractères) contient aussi les lettres latines, les accents
  et les chiffres. La baseline a donc un sens : le modèle sait déjà lire, on mesure ce que l'adaptation apporte.
- Il est petit (backbone PPLCNetV3 + encodeur SVTR + tête CTC linéaire), donc entraînable sur CPU.
- Les poids officiels d'entraînement sont publics ; le code d'entraînement (`ppocr`) vient du dépôt
  PaddleOCR au tag figé `v3.7.0`.

```
image 48 x W ─> backbone PPLCNetV3 (CNN) ─> encodeur SVTR (2 blocs) ─> tête CTC (linéaire, 749 classes)
               └──────────── gelé en Transfer Learning ────────────┘     └ seule partie entraînée en TL
               └──────────────── tout entraîné en Fine-Tuning (LR faible) ───────────────┘
```

## Installation (une fois)

Depuis la racine du dépôt, sous Windows (Python 3.13) :

```powershell
python -m venv --system-site-packages .venv
.venv\Scripts\python -m pip install -r requirements-ocr.txt
```

`requirements-ocr.txt` (racine du dépôt) contient les dépendances de l'OCR : `paddlepaddle`, `paddleocr`,
`paddlex`, `mypy`, etc. Au premier lancement, le script clone le code d'entraînement PaddleOCR et
télécharge les poids pré-entraînés (71 Mo) dans `build/`, dossier ignoré par git.

## Relancer l'expérience (une commande)

```powershell
.venv\Scripts\python experiments/ocr_transfer_finetune/run_experiment.py --seed 42
```

- Durée sur CPU : environ 3 h, surtout pour le Fine-Tuning (voir `results.md`). Le script se relance tout seul
  depuis le dernier point de sauvegarde si Paddle plante (jusqu'à 3 fois), et ne refait jamais une étape déjà
  terminée. `--ft-variant bn_frozen` (par défaut) ou `partial` (plan B, voir `ANALYSE.md`). `--fresh` repart de
  zéro. Autres options utiles : `--n-train`, `--epochs-tl`, `--epochs-ft`,
  `--budget-min` (arrêt propre si le budget de temps est dépassé), `--quick` (petit essai pour
  vérifier la chaîne, résultats dans `build/quick/` ; durée mesurée avec `--quick --fresh` : 14,6 min sur CPU,
  dont 2 relances automatiques après plantage).
- Sorties : `results.json`, `results.md`, `loss_curves.png` dans ce dossier ; données générées et poids
  entraînés dans `build/`.
- Reproductible : graine fixe pour le texte, le rendu, le bruit, le découpage, l'ordre des lots et
  l'initialisation. Les données sont régénérées à l'identique (même graine = mêmes images).

Tests rapides (sans Paddle) : `.venv\Scripts\python -m pytest -q experiments/ocr_transfer_finetune/tests`.

## Données (fictives)

- `vocab.py` : vocabulaire inventé des fiches de paie et conventions (salaire de base, CNSS, catégorie,
  échelon / الأجر الأساسي، الصنف، الدرجة…), montants au format `424.100`, dates, lignes bilingues.
- `data_gen.py` : rendu par pymupdf (mise en forme arabe et bidi par HarfBuzz) avec Arial, Tahoma,
  Times New Roman et Segoe UI, puis bruit de scan (résolution variable, rotation ±2°, flou, bruit
  gaussien, contraste, JPEG).
- Découpage fixe : train / val / test (domaine) et un jeu `generic` (phrases de la vie courante, hors
  domaine) pour mesurer l'**oubli catastrophique**.
- Pour chaque méthode, on garde l'époque qui a le meilleur CER de **validation** ; le test ne sert
  qu'à la mesure finale.

## Fichiers

| Fichier | Rôle |
|---|---|
| `run_experiment.py` | la commande unique : données, baseline, TL, FT, résultats, courbes |
| `model.py` | construction du modèle, gel / dégel, passe CTC, décodage glouton |
| `rtl.py` | passage ordre logique ↔ ordre visuel des lignes arabes (convention des poids pré-entraînés) |
| `data_gen.py`, `vocab.py` | génération des lignes fictives |
| `metrics.py` | CER, WER, lignes exactes |
| `tests/` | tests rapides (métriques, RTL, déterminisme du générateur) |
