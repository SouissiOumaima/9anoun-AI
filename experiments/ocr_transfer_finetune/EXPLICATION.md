# Explication complète : OCR (partie A) et expérience Transfer Learning vs Fine-Tuning

Document de préparation à la présentation. Français simple, phrases courtes.

**D'où viennent les chiffres.** Chaque chiffre porte sa source entre crochets :

| Code | Fichier |
|---|---|
| [R] | `experiments/ocr_transfer_finetune/results.md` |
| [J] | `experiments/ocr_transfer_finetune/results.json` |
| [A] | `experiments/ocr_transfer_finetune/ANALYSE.md` |
| [L:nom] | journal `experiments/ocr_transfer_finetune/build/nom` (ignoré par git) |
| [C:nom] | code source (fichier indiqué) |
| [T] | sortie de pytest pendant la session de travail (pas de fichier) |
| [S] | mesure faite pendant la session de travail sur la page A4 fictive (script temporaire, pas de fichier dans le dépôt) |
| [U] | résumé agrégé des vraies données, lancé par toi (`resume_agrege.json`, hors dépôt) |

---

## 0. Les mots à connaître

| Terme | Définition simple |
|---|---|
| OCR | Lecture automatique du texte dans une image. L'ordinateur « voit » des pixels et en tire des lettres. |
| Détection | Première étape de l'OCR : trouver **où** se trouve du texte dans l'image (des rectangles). |
| Reconnaissance | Deuxième étape : lire **quelles lettres** il y a dans chaque rectangle trouvé. |
| bbox | *Bounding box* : le rectangle autour d'un texte, donné par 4 nombres (x0, y0, x1, y1). |
| Confiance | Nombre entre 0 et 1 donné par l'OCR : à quel point il est sûr de sa lecture. Ce n'est **pas** une preuve que c'est juste. |
| CER | *Character Error Rate* : pourcentage de caractères faux (ajoutés, oubliés ou remplacés). Plus bas = mieux. |
| WER | *Word Error Rate* : pareil, mais compté en mots. Un seul caractère faux rend tout le mot faux. |
| CTC | Méthode qui permet d'apprendre à lire une ligne entière sans dire où commence chaque lettre. Le modèle sort une suite de symboles ; on fusionne les répétitions et on enlève les « blancs ». |
| Backbone | La première partie du réseau : un réseau de convolutions qui transforme l'image en « caractéristiques visuelles ». Ici : PPLCNetV3. |
| Encodeur | La partie du milieu : elle relie les caractéristiques entre elles le long de la ligne. Ici : SVTR, 2 blocs. |
| Tête | La dernière couche : elle transforme les caractéristiques en probabilités pour chaque caractère (749 classes). |
| BatchNorm | Couche qui « normalise » les valeurs internes du réseau. Elle a des paramètres (échelle, biais) et des statistiques (moyenne, variance). |
| Transfer Learning (TL) | On garde le modèle pré-entraîné **gelé** et on ré-entraîne seulement la fin (ici la tête). |
| Fine-Tuning (FT) | On ré-entraîne **presque tout** le modèle, doucement (learning rate faible). |
| Geler | Interdire à des poids de changer pendant l'entraînement. |
| Learning rate (LR) | La taille des pas d'apprentissage. Trop grand : le modèle « oublie » ou diverge. Trop petit : il apprend lentement. |
| Époque | Un passage complet sur toutes les données d'entraînement. |
| Graine (seed) | Nombre de départ du hasard. Même graine = mêmes données, mêmes résultats. Ici : 42. |
| train / val / test | Trois jeux séparés. **train** : pour apprendre. **val** : pour choisir la meilleure époque. **test** : pour la note finale, utilisé une seule fois. |
| Baseline | Le point de départ : le modèle pré-entraîné, sans aucun entraînement de notre part. |
| Oubli catastrophique | Quand un modèle apprend une nouvelle tâche, il peut devenir mauvais sur ce qu'il savait déjà. |
| Checkpoint | Point de sauvegarde : on enregistre les poids et l'état de l'entraînement à la fin de chaque époque. |
| Superviseur | Petit programme qui lance l'entraînement dans un autre processus et le relance s'il plante. |
| oneDNN / MKL | Bibliothèques d'Intel qui accélèrent les calculs sur processeur. Elles ont causé des plantages ici. |
| RTL | *Right-To-Left* : l'arabe se lit de droite à gauche. |
| Ordre logique / visuel | Logique : l'ordre où on tape les lettres. Visuel : l'ordre où on les voit à l'écran, de gauche à droite. Pour l'arabe, les deux sont inversés. |
| ds3.inter.v1 | Le nom (la version) du format commun de la « représentation intermédiaire » d'un document dans DS3 [C:intermediate.py]. |
| IntermediateDocument | Le document dans ce format : liste de pages, chaque page a des lignes et des zones en attente [C:intermediate.py]. |
| PendingZone | Une « zone en attente » : un rectangle de la page que le lecteur PDF n'a pas pu lire (une image, un scan, ou du texte natif illisible) [C:intermediate.py]. |
| TextLine | Une ligne de texte lue, avec son identifiant (`p2_l5`), sa page, son texte, sa bbox, sa confiance, sa source (`natif` ou `ocr`) et sa langue [C:intermediate.py]. |
| Points PDF | L'unité de mesure d'un PDF : 72 points = 1 pouce. |
| DPI | Points par pouce : la résolution de l'image. 300 DPI = 300 pixels par pouce. |
| Citation ou silence | Règle du projet : on ne devine jamais un texte. Si on ne sait pas lire, on le dit. |

---

## 1. La vue d'ensemble : où se place mon OCR dans DS3

DS3 lit des documents (fiches de paie, conventions) et en extrait des informations avec des citations.

```
 PDF
  │
  ▼
 Lecteur PDF natif (partie B, pdf_natif.py, Hadil)
  │   lit le texte « natif » du PDF
  ├──► TextLine (source = "natif")
  └──► PendingZone   (images, scans, arabe illisible)
          │
          ▼
 Mon OCR (partie A, reading/ocr.py) : ocr_pending_zones()
  │   rend chaque zone en image à 300 DPI, la lit avec PaddleOCR
  ├──► TextLine (source = "ocr", confiance réelle)
  └──► zone gardée en PendingZone + avertissement si rien n'est lu
          │
          ▼
 IntermediateDocument (format ds3.inter.v1)
          │
          ▼
 Gemini (extraction/gemini.py) → vérification → réponse avec citations (line_id)
```

**Point important pour le jury :** aujourd'hui, la chaîne `extraction/pipeline.py` appelle `read_pdf` puis
Gemini [C:pipeline.py]. Elle n'appelle **pas encore** mon OCR. Le branchement reste à faire (section 10).

---

## 2. La partie A : `src/document_intelligence/reading/ocr.py`

### 2.1 Les briques

| Élément | Ce qu'il fait |
|---|---|
| `OcrBox` | Un morceau de texte lu : texte, score (confiance), bbox en **pixels**. |
| `OcrEngine` | Un « contrat » (Protocol) : tout moteur d'OCR doit avoir une méthode `recognize(image, lang)`. Les tests utilisent un **faux moteur** : pas besoin de télécharger de modèle. |
| `PaddleEngine` | Le vrai moteur : PaddleOCR 3.x. Un pipeline par langue, créé à la première utilisation puis gardé. |
| `default_engine()` | Le moteur partagé. Les modèles ne sont chargés qu'une fois par processus. |
| `REC_MODELS` | Modèle de reconnaissance par langue : `arabic_PP-OCRv5_mobile_rec` (ar) et `latin_PP-OCRv5_mobile_rec` (fr). |
| `DET_MODEL` | Modèle de détection : `PP-OCRv5_mobile_det` (voir 2.7). |

Réglages de `PaddleEngine` [C:ocr.py] :
- `device="cpu"` ;
- `enable_mkldnn=False` (oneDNN désactivé, voir 5.3) ;
- pas de redressement de document ni de classification d'orientation : les zones viennent de PDF déjà droits.

Les noms des deux modèles sont donnés **explicitement**. Quand on nomme le détecteur, PaddleOCR ignore `lang`
et prendrait son modèle par défaut (PP-OCRv6, qui ne lit pas l'arabe) [C:ocr.py, commentaire de `REC_MODELS`].

### 2.2 Les étapes, dans l'ordre

1. **`ocr_pending_zones(doc, pdf_path)`**, la fonction principale.
   - Elle travaille sur une **copie** du document (`model_copy(deep=True)`) : l'entrée n'est jamais modifiée.
   - S'il n'y a aucune zone en attente, elle rend la copie telle quelle.
   - Sinon, elle ouvre le PDF et passe chaque zone au cœur commun `_ocr_pages`.
   - À la fin, elle ajoute `+ocr_paddle-0.1` au nom du lecteur (`reader`), pour qu'on sache que l'OCR est passé.
2. **`render_zone`** : rend la zone (et seulement elle, avec `clip`) en image, à **300 DPI**. Couleurs RGB
   converties en BGR (l'ordre attendu par PaddleOCR).
3. **`read_zone_boxes`** : lit l'image (voir 2.6 pour `lang="auto"`).
4. **`clean_boxes`** : enlève les textes vides et les doublons. Une boîte qui est à **80 %** ou plus dans une
   boîte plus grande est ignorée (exemple : une hamza « ء » détectée à part au-dessus d'un mot déjà lu)
   [C:ocr.py, `CONTAINED_RATIO = 0.8`].
5. **`group_rows`** : regroupe les boîtes en lignes visuelles (voir 2.5).
6. **`to_pdf_bbox`** : convertit les pixels en points PDF (voir 2.3).
7. **Création des `TextLine`** : `source="ocr"`, langue détectée par `detect_language`, confiance réelle
   (bornée entre 0 et 1, arrondie à 4 décimales).
8. **Avertissements** ajoutés au document : un bilan (« N zone(s) lue(s), M ligne(s) ajoutée(s) »), et la liste
   des zones vides ou en échec.

Autres fonctions publiques :
- **`read_image(path)`** : lit une image PNG ou JPG comme une page entière.
  - Le DPI est lu dans le fichier (300 par défaut).
  - La taille de la page en points vaut `pixels × 72 / dpi`, pour que les bbox soient dans la même unité qu'un PDF.
  - La page est de type `kind="image"`, avec une seule zone `p1_z1`.
- **`read_document(path)`** : PDF → `read_pdf` (texte natif) puis `ocr_pending_zones` ; image → `read_image`.
- **CLI** : `python -m src.document_intelligence.reading.ocr fichier [--lang auto|ar|fr] [--json sortie.json]`.

### 2.3 La conversion des bbox (pixels → points PDF)

L'OCR travaille sur l'image de la **zone**, pas de la page. Ses bbox sont en pixels, et comptées depuis le coin
de la zone. Il faut donc deux choses :
- **changer d'unité** : 1 pixel à 300 DPI = 72 / 300 = 0,24 point ;
- **ajouter le décalage de la zone** : sa position (x0, y0) sur la page.

```
x_page = zone.x0 + x_pixel × 72 / dpi
y_page = zone.y0 + y_pixel × 72 / dpi
```

Exemple : une zone commence à (100, 200) points. L'OCR trouve un mot au pixel (300, 50) à 300 DPI. Le mot est
donc à (100 + 300 × 0,24 ; 200 + 50 × 0,24) = **(172, 212) points** sur la page. Le résultat est arrondi à
0,1 point [C:ocr.py, `to_pdf_bbox`].

### 2.4 La numérotation des `line_id`

- Le format est `p{page}_l{n}`, par exemple `p1_l3`.
- La page a peut-être déjà des lignes natives (`p1_l1`, `p1_l2`). `_next_line_number` cherche le plus grand `n`
  existant sur la page et commence à **n + 1**.
- On ajoute ensuite 1 à chaque nouvelle ligne.
- Résultat : **jamais deux lignes avec le même identifiant**. C'est vital, parce que Gemini cite les lignes par
  leur `line_id`.
- Les zones sont traitées de haut en bas (tri sur y, puis x).

### 2.5 L'ordre de lecture droite-à-gauche (RTL)

Le détecteur découpe souvent une ligne en plusieurs morceaux (des mots). Il faut les remettre dans le bon ordre.
- Deux boîtes sont sur la même ligne si elles se recouvrent assez en hauteur. Le seuil `SAME_ROW_OVERLAP` est
  repris de `pdf_natif.py`, pour avoir la même règle que le lecteur natif.
- Dans une ligne, si les morceaux **arabes** sont plus nombreux que les morceaux **français**, on trie de **droite
  à gauche** (x décroissant). Sinon, de gauche à droite. Les montants (sans lettres) ne comptent pas.
- La confiance d'une ligne fusionnée est le **minimum** de ses morceaux. C'est un choix prudent : une ligne n'est
  pas plus sûre que son morceau le moins sûr.

### 2.6 « Citation ou silence » et le choix `lang="auto"`

**Citation ou silence :**
- Une zone où l'OCR ne lit **rien** reste dans `pending_zones`, avec l'avertissement « aucun texte lu… rien n'est
  deviné ». **Aucune ligne n'est inventée.**
- Si l'OCR **plante** sur une zone, la zone reste aussi en attente. Le reste du document continue.
- **Aucun seuil de confiance** n'est appliqué : la vraie confiance est transmise. C'est le consommateur (Gemini
  et la vérification) qui décide (décision D39 citée dans [C:ocr.py]).

**`lang="auto"` (par défaut) :**
1. On lit d'abord avec le modèle **arabe**. Il connaît aussi les lettres latines et les chiffres.
2. Si le texte lu est surtout **latin**, on relit avec le modèle **latin**, qui connaît mieux les accents
   français.
3. On garde la lecture qui a la meilleure **confiance moyenne**.

Conséquence : une zone en français est lue **deux fois**, donc elle prend plus de temps.

### 2.7 Le détecteur `mobile_det`, et pourquoi

- Au départ, le détecteur était `PP-OCRv5_server_det`.
- Sur une vraie page A4 entière à 300 DPI, il plantait (access violation) dans la détection.
- Je l'ai reproduit sur une page A4 **fictive** dense : 2480 × 3508 pixels, arabe, montants, dates, un tableau.
  Le plantage arrive 2 fois sur 2 [S].
- La raison probable : par défaut, la détection ne réduit pas une grande image (`limit_type=min`,
  `side_len=64`). La page entre donc en taille réelle [S, valeurs lues dans le pipeline PaddleOCR].
- Les essais, dans l'ordre :

| Essai | Résultat [S] |
|---|---|
| Vérifier que oneDNN est bien désactivé pour la détection | Oui (`run_mode='paddle'`) : ce n'était pas la cause. |
| `PP-OCRv5_mobile_det` | Pas de plantage (2 fois sur 2), environ 30 à 40 s pour la page, 19 nombres sur 48 retrouvés. |
| `server_det` limité à 2000 px | Pas de plantage, mais 213 à 294 s pour la page, et **les mêmes** 19 nombres sur 48. |

- Choix : **`mobile_det`**. C'est la solution la plus simple (un seul nom à changer), elle ne plante pas, elle est
  la plus rapide, et elle donne la même qualité sur ce test.
- Les nombres manquants ne viennent pas du détecteur : c'est le défaut connu du modèle arabe, qui perd des chiffres
  dans les lignes arabes (voir 4.2).
- Un test reproduit ce cas : `test_paddle_full_a4_page_at_300_dpi_does_not_crash`. Il tourne dans un
  sous-processus, sinon un plantage ferait tomber toute la suite de tests.

---

## 3. L'expérience Transfer Learning vs Fine-Tuning, étape par étape

Dossier : `experiments/ocr_transfer_finetune/`. Une seule commande lance tout : `run_experiment.py`.

### 3.1 Choix du modèle

**Quoi :** `arabic_PP-OCRv5_mobile_rec` (PaddleOCR), uniquement la partie reconnaissance.

**Pourquoi** [README.md de l'expérience] :
- c'est **le même modèle que l'OCR de production** (`ocr.py`) : ce qu'on apprend sert directement le projet ;
- il lit déjà l'arabe, et son dictionnaire (747 caractères) contient aussi les lettres latines, les accents et les
  chiffres. La baseline a donc un sens ;
- il est petit, donc entraînable sur CPU ;
- les poids d'entraînement officiels sont publics, et le code d'entraînement vient du dépôt PaddleOCR au tag figé
  `v3.7.0`.

**Alternatives écartées** (d'après le code, pas de mesure comparative) :
- le modèle **latin** `latin_PP-OCRv5_mobile_rec` ne lit pas l'arabe ;
- le modèle par défaut **PP-OCRv6** n'est pas arabe [C:ocr.py] ;
- un autre outil d'OCR casserait le lien avec l'OCR de production. Aucun autre modèle n'a été mesuré dans cette
  expérience.

**Architecture** [C:model.py] :

```
image 48 x W ─> backbone PPLCNetV3 ─> encodeur SVTR (2 blocs) ─> tête CTC (linéaire, 749 classes)
```

- Les 749 classes sont : 1 « blanc » CTC + 747 caractères du dictionnaire + l'espace.
- Le modèle d'origine a aussi une branche NRTR (décodeur attentionnel). PaddleOCR ne l'utilise pas à l'inférence,
  donc on l'ignore aussi.

### 3.2 Génération des données fictives

**Quoi** [C:vocab.py, data_gen.py] :
- **Texte** : lignes inventées de fiches de paie et de conventions, en français et en arabe (salaire de base,
  CNSS, catégorie, échelon, الأجر الأساسي, الصنف, الدرجة…), des montants au format `424.100`, des dates, et des
  lignes bilingues. Une ligne fait au plus 44 caractères (`MAX_LEN`).
- **Rendu** : pymupdf, qui met correctement en forme l'arabe (lettres liées, sens droite-à-gauche). 4 polices
  Windows : Arial, Tahoma, Times New Roman, Segoe UI. Résolution tirée entre 110 et 170 DPI.
- **Bruit de scan** :
  - encre pas tout à fait noire (0 à 70) et papier pas tout à fait blanc (200 à 255) ;
  - rotation de ±2° ;
  - flou dans 70 % des cas ;
  - bruit gaussien ;
  - compression JPEG (qualité 40 à 89) dans 50 % des cas.
- Les lignes qui contiennent un caractère inconnu du modèle sont retirées. Ici : 0 ligne retirée [J,
  `rejected_out_of_charset`].

**Pourquoi :** les vraies données sont confidentielles et hors du dépôt. On ne peut pas entraîner dessus ici.

### 3.3 Découpage

**Quoi :** quatre jeux fixes, avec la graine 42 [R] :
- train : 1 200 lignes ;
- val : 200 ;
- test : 400 ;
- generic : 150.

Chaque jeu a son propre générateur aléatoire, et chaque image est dérivée de (graine, jeu, numéro). Même graine =
mêmes images.

Le jeu **generic** contient des phrases de la vie courante, **hors domaine**. Il sert à mesurer l'oubli. Il ne
contient que 20 phrases distinctes [A].

Composition du test : 193 lignes FR, 192 AR, 15 mixtes [J].

### 3.4 Baseline

**Quoi :** le modèle pré-entraîné, sans entraînement, évalué sur val, test et generic.

**Pourquoi :** c'est la référence. Sans elle, on ne sait pas ce que l'adaptation apporte.

**Résultat :** CER test **13,68 %**, WER 24,74 % [R]. CER val 12,92 % [J].

### 3.5 Transfer Learning

**Quoi** [C:model.py, `configure_stage`] :
- **gelés** : le backbone et l'encodeur (poids et statistiques BatchNorm) ;
- **entraînée** : seulement la tête CTC, soit **90 629 paramètres** [R].
- LR 1e-3, optimiseur Adam, décroissance cosinus, lots de 32, 15 époques [J, `config`].
- Astuce : comme l'encodeur est gelé, ses sorties ne changent jamais. On les calcule **une seule fois**. Une époque
  prend alors environ 2,5 s [J, `epoch_s`].

**Pourquoi :** c'est la méthode la moins chère et la moins risquée pour l'oubli.

**Résultat :**
- meilleure époque sur val : **8** (CER val 2,76 %) [J] ;
- CER test **3,24 %**, WER 19,38 % [R] ;
- durée : 17,1 min, calcul des sorties de l'encodeur compris [R].

### 3.6 Fine-Tuning, variante `bn_frozen`

**Quoi** [C:model.py] :
- **entraînés** : backbone, encodeur et tête, **sauf** les couches BatchNorm ;
- **gelées** : les 151 couches BatchNorm. Leurs paramètres (échelle, biais) et leurs statistiques ne bougent pas [A].
- **5 478 185 paramètres** entraînés [R].
- LR **1e-4** (10 fois plus petit qu'en TL), avec 1 époque d'échauffement (le LR monte de 1e-5 à 1e-4), puis
  décroissance cosinus. Adam, lots de 32, 4 époques [J ; C:run_experiment.py].
- Le backbone reste en mode « évaluation », même s'il reçoit des gradients (voir 5.5).
- Le FT repart des poids **pré-entraînés**, pas des poids du TL.

**Pourquoi geler les BatchNorm :**
1. Le Fine-Tuning « tout dégelé » plantait toujours dans `batch_norm` (voir 5.1). Geler les BatchNorm a réduit
   les plantages : 1 en 4 époques, contre 4 d'affilée avant [A ; L:run_full3.log ; L:run_full_bnfrozen.log].
2. C'est une pratique courante quand on a peu de données et de petits lots : les statistiques calculées sur 32
   images sont peu fiables.

**Résultat :**
- meilleure époque sur val : **3** (CER val 1,05 %) [J] ;
- CER test **1,20 %**, WER 7,06 % [R] ;
- durée d'entraînement : 153,9 min [R].

**Plan B, non utilisé :** `--ft-variant partial`. Seuls le dernier étage du backbone (`blocks6`), l'encodeur et la
tête sont entraînés, BatchNorm gelée [C:model.py].

### 3.7 Métriques

- **CER** et **WER**, calculés avec une distance de Levenshtein écrite et testée dans `metrics.py`, après
  normalisation (Unicode NFC, espaces).
- **Lignes exactes** : pourcentage de lignes lues sans aucune erreur.
- Détail **par langue** : FR / AR / mixte, avec `detect_language` sur le texte de référence.
- L'arabe est comparé en **ordre logique** (voir 5.4).

### 3.8 Sélection de l'époque sur val, mesure unique sur le test

- À chaque époque, on calcule le CER sur **val**. On garde les poids de la meilleure époque.
- L'état de départ (époque 0, les poids pré-entraînés) compte aussi : si l'entraînement n'apporte rien, on garde le
  modèle d'origine [C:run_experiment.py].
- Le **test** n'est utilisé **qu'une fois**, à la fin, avec les poids choisis. On ne choisit rien en regardant le
  test : sinon la note serait trop optimiste.

---

## 4. Les résultats

### 4.1 Le tableau final (jeu de test, 400 lignes) [R]

| Méthode | CER | WER | Lignes exactes | Paramètres entraînés | Époques (meilleure) | Durée |
|---|---|---|---|---|---|---|
| Baseline | 13,68 % | 24,74 % | 47,00 % | 0 | — | — |
| Transfer Learning | 3,24 % | 19,38 % | 58,50 % | 90 629 | 15 (8) | 17,1 min |
| Fine-Tuning `bn_frozen` | **1,20 %** | **7,06 %** | **79,50 %** | 5 478 185 | 4 (3) | 153,9 min |

Comment le lire :
- le CER est divisé par environ 4 avec le TL, et par environ 11 avec le FT, par rapport à la baseline ;
- le WER baisse peu avec le TL (24,74 % → 19,38 %), mais beaucoup avec le FT (7,06 %). La tête seule ne corrige
  pas bien les espaces entre les mots arabes [A] ;
- pour le projet, les **lignes exactes** comptent le plus : un montant à moitié juste ne sert à rien.

### 4.2 Le détail FR / AR [R ; J]

| Méthode | CER FR (193 lignes) | CER AR (192 lignes) | CER mixte (15 lignes) |
|---|---|---|---|
| Baseline | 0,57 % | 24,93 % | 46,97 % |
| Transfer Learning | 0,13 % | 5,92 % | 11,04 % |
| Fine-Tuning `bn_frozen` | 0,13 % | 1,91 % | 6,28 % |

Comment le lire :
- le **français** était déjà presque parfait ;
- **tout le gain vient de l'arabe** et des lignes mixtes ;
- la plus grosse erreur de la baseline : **les chiffres disparaissent dans les lignes arabes** [A, R] ;
- le jeu mixte n'a que 15 lignes : ce chiffre est fragile.

### 4.3 L'oubli : jeu « generic » [R ; J]

| Méthode | CER generic | WER generic | Lignes exactes |
|---|---|---|---|
| Baseline | 0,65 % | 3,59 % | 83,33 % |
| Transfer Learning | 0,43 % | 2,53 % | 85,33 % |
| Fine-Tuning `bn_frozen` | 0,35 % | 2,00 % | 88,00 % |

Comment le lire :
- s'il y avait de l'oubli, le CER generic **monterait**. Il **baisse**, donc pas d'oubli visible ;
- **mais** ce jeu est faible : seulement 20 phrases distinctes, avec les **mêmes polices et le même bruit** que
  l'entraînement. Le modèle s'améliore sur ce « style d'image », quel que soit le sujet ;
- conclusion honnête : **oubli non observé, mais mal mesuré** [A].

### 4.4 Les exemples [R]

| Référence | Baseline | Transfer | Fine-Tuning |
|---|---|---|---|
| الضريبة على الدخل : 2613.193 د | الضريبة علىالدخل | الضريبة علىالدخل 2613.193د | الضريبة على الدخل : 2613.193د |
| Catégorie 4 Échelon 5 | Catégorie 4 Echelon 5 | Catégorie 4 Échelon 5 | Catégorie 4 Échelon 5 |
| Qualification : Agent de maîtrise | … maïtrise | … maitrise | … maïtrise |

Comment les lire :
- **ligne arabe** : la baseline perd le montant et un espace. Le TL retrouve le montant, mais pas l'espace ni les
  deux-points. Le FT est presque parfait (il manque seulement l'espace avant « د ») ;
- **« Échelon »** : la baseline perd l'accent du É majuscule ;
- **« maîtrise »** : aucune méthode ne lit correctement le « î ». C'est une erreur qui reste.

### 4.5 Les courbes (`loss_curves.png`)

- **À gauche**, la perte CTC (train et val) baisse pour les deux méthodes. Celle du FT descend beaucoup plus bas.
- **À droite**, le CER de validation par époque :
  - le TL se stabilise vers 2,8 % à partir de l'époque 8 environ [J] ;
  - le FT passe sous le TL **dès la 1re époque** (2,69 % contre 6,06 %) [J] ;
  - la ligne pointillée grise est la baseline (12,92 % sur val) [J].

---

## 5. Les difficultés et leurs solutions

### 5.1 Plantage de Paddle pendant le Fine-Tuning

- **Symptôme** : le processus meurt sans message d'erreur Python. Code `3221225477`, c'est-à-dire *access
  violation*. Le traceback pointe vers `batch_norm` dans le backbone [L:run_full.log, L:run_full3.log].
- **Quand** : seulement quand le backbone reçoit des gradients (FT). Le TL n'a jamais planté.
- **Historique** :
  1. Premier lancement : plantage après l'époque 1 du FT (CER val 3,85 %, 826 s) [L:run_full.log].
  2. Après l'ajout de la reprise, relance « tout dégelé » : 4 plantages d'affilée, abandon après 3 relances
     [L:run_full3.log].
  3. Variante `bn_frozen` : 1 seul plantage (après l'époque 1). La reprise automatique a fini le travail
     [L:run_full_bnfrozen.log ; J, `restarts` = 1].
- **Essai abandonné** : limiter Intel MKL à 1 thread. C'était 11 fois plus lent [A].
- **Conclusion** : la correction **réduit** le problème sans le supprimer. C'est l'ensemble « BatchNorm gelée +
  checkpoints + superviseur » qui permet d'aller au bout.

### 5.2 La reprise automatique

- **Superviseur** : `run_experiment.py` se relance lui-même dans un sous-processus (option cachée `--worker`). Si
  le sous-processus plante, il le relance, **jusqu'à 3 fois** [C:run_experiment.py, `supervise`].
- **Checkpoint à chaque époque** : poids, état de l'optimiseur et du scheduler, meilleure époque, historique. La
  relance repart de la dernière époque terminée.
- **Résultats par étape** : la baseline et le TL sont enregistrés une fois finis. Ils ne sont **jamais recalculés**
  lors d'une relance.
- **Bug corrigé dans la reprise** : l'état de l'optimiseur utilisait des noms internes générés au hasard
  (`conv2d_131.w_0_moment1_0`), différents d'un processus à l'autre. Solution : les remplacer par les noms
  « structurels » des paramètres [A].
- L'ordre des lots dépend seulement de (graine, époque). Une époque reprise est donc identique à une époque non
  interrompue.

### 5.3 oneDNN

- À l'inférence, avec oneDNN activé, PaddleOCR plantait (`ConvertPirAttribute2RuntimeAttribute not support`) [A].
- Solution : `enable_mkldnn=False` dans `ocr.py`, et `FLAGS_use_mkldnn=0` dans l'expérience [J, `cpu_flags`].

### 5.4 Ordre visuel / logique de l'arabe

- Les poids **d'entraînement** publiés sortent l'arabe en **ordre visuel** (à l'envers). Le modèle **d'inférence**
  de PaddleX le sort en **ordre logique** [C:model.py].
- Sans correction, la baseline donnait 38,9 % de CER. C'était une **erreur de mesure**, pas une faiblesse du
  modèle [A].
- Solution (`rtl.py`) : les cibles d'entraînement sont mises en ordre visuel, et la sortie est remise en ordre
  logique avant le calcul du CER. C'est la même fonction dans les deux sens (une fonction « involutive »), et elle
  est testée.

### 5.5 Les 40 pas CTC

- En mode « train », le backbone PPLCNetV3 force la sortie à **40 pas de temps**. Il ne peut donc écrire qu'environ
  40 caractères, et le calcul CTC (warpctc) plantait sur les lignes plus longues [A ; C:model.py].
- Solution : le backbone reste **toujours en mode évaluation**, même en FT. Ses poids reçoivent quand même les
  gradients.
- La longueur réelle de chaque image est utilisée : largeur / 8 pas.

### 5.6 Conflit torch / paddle

- Si `torch` est importé **après** `paddle` dans le même programme, Windows refuse de charger une DLL (`shm.dll`)
  [A].
- Ce cas est évité dans les scripts, et il n'apparaît pas dans la suite de tests.

### 5.7 Plantage de `server_det` sur page A4, passage à `mobile_det`

Voir 2.7 : plantage reproduit sur une page A4 fictive, `mobile_det` ne plante pas et donne la même qualité [S].

### 5.8 Lenteur sur les vraies pages

- Sur tes vraies données : 5 pages en 4 563 s [U], soit environ **913 s (15 min) par page**.
- Sur la page A4 fictive, `mobile_det` met environ 30 à 40 s [S].
- **Pourquoi cet écart ? Je ne sais pas, ce n'est pas mesuré.** Pistes possibles, à vérifier :
  - une page réelle peut contenir **beaucoup de zones**, et chaque zone est un appel OCR séparé ;
  - en mode `auto`, une zone surtout française est lue **deux fois** ;
  - et il faut vérifier que ce lancement utilisait déjà `mobile_det`.

### 5.9 Autres contraintes

- CPU seulement : 1 200 lignes d'entraînement au lieu des 3 000 prévues, et 4 époques de FT [A].
- Les époques 2 à 4 du FT ont duré environ 2 600 à 2 800 s, contre 852 s pour l'époque 1, avec le même code [J].
  Ce n'est **pas expliqué**.

---

## 6. Les fichiers

`git diff --stat` est **vide** : **aucun fichier suivi par git n'a été modifié**. Tous les fichiers ci-dessous
sont **nouveaux** (non suivis, `??` dans `git status`). **Aucun fichier n'a été modifié hors de la liste
autorisée.** `requirements-ocr.txt` a été créé à ta demande.

### Code

| Chemin | Créé / modifié | Rôle | Fonctions ou options principales |
|---|---|---|---|
| `src/document_intelligence/reading/ocr.py` | créé | OCR partie A | `ocr_pending_zones`, `read_image`, `read_document`, `PaddleEngine`, `clean_boxes`, `group_rows`, `read_zone_boxes`, `to_pdf_bbox`, CLI `--lang --json` |

### Tests

| Chemin | Créé / modifié | Rôle | Contenu principal |
|---|---|---|---|
| `src/document_intelligence/tests/test_document_intelligence_ocr.py` | créé | tests de l'OCR | 17 tests [T] : faux moteur (bbox, numérotation, zone vide, échec, RTL, `auto`, `read_image`), intégration PaddleOCR, page A4 dense en sous-processus, détecteur par défaut |
| `experiments/ocr_transfer_finetune/tests/test_ocr_experiment.py` | créé | tests de l'expérience, sans Paddle | 12 tests : CER/WER, RTL, déterminisme du générateur |
| `experiments/ocr_transfer_finetune/tests/conftest.py` | créé | chemin d'import des tests | — |

### Scripts

| Chemin | Créé / modifié | Rôle | Options |
|---|---|---|---|
| `scripts/evaluer_donnees_reelles.py` | créé | OCR sur les vraies données, n'affiche que des agrégats | `source`, `--out` (obligatoire, refusé dans le dépôt), `--limit N` ; écrit `doc_###.json` et `resume_agrege.json` |

### Expérience (`experiments/ocr_transfer_finetune/`)

| Chemin | Créé / modifié | Rôle | Fonctions ou options principales |
|---|---|---|---|
| `run_experiment.py` | créé | la commande unique | `supervise`, `train_stage`, `evaluate`, `plot`, `write_markdown` ; options `--seed --quick --fresh --ft-variant --n-train --epochs-tl --epochs-ft --lr-tl --lr-ft --batch-size --budget-min --out` |
| `model.py` | créé | modèle, gel, CTC | `Charset`, `build`, `ctc_logits`, `configure_stage`, `set_train_mode`, `batchnorm_layers`, `predict`, `encoder_features` |
| `data_gen.py` | créé | rendu et bruit des images | `make_texts`, `render_text`, `scan_noise`, `generate`, `load_split` |
| `vocab.py` | créé | vocabulaire fictif | `domain_line`, `generic_line`, `amount`, `date` |
| `metrics.py` | créé | métriques | `cer`, `wer`, `exact_match`, `levenshtein`, `normalize` |
| `rtl.py` | créé | ordre logique ↔ visuel | `is_arabic`, `flip_rtl` |
| `README.md` | créé | installation et commande | — |
| `results.md`, `results.json` | créés (générés) | chiffres mesurés | — |
| `loss_curves.png` | créé (généré) | courbes | — |
| `ANALYSE.md` | créé | analyse critique | — |
| `EXPLICATION.md` | créé | ce document | — |

### Configuration

| Chemin | Créé / modifié | Rôle |
|---|---|---|
| `requirements-ocr.txt` (racine) | créé | dépendances OCR : paddlepaddle 3.3.1, paddleocr 3.7.0, paddlex 3.7.2, PyYAML, pymupdf, opencv-python, pillow, matplotlib, mypy |
| `requirements.txt`, `.gitignore` | **non modifiés** | — |

### Fichiers ignorés par git (`experiments/ocr_transfer_finetune/build/`)

Le dossier est ignoré par la règle `build/` déjà présente dans `.gitignore`. `.venv/` est ignoré aussi.

| Chemin | Rôle |
|---|---|
| `build/PaddleOCR/` | code d'entraînement PaddleOCR (tag `v3.7.0`) |
| `build/weights/` | poids pré-entraînés téléchargés |
| `build/data/`, `build/data_quick/` | images fictives générées |
| `build/state/` | résultats par étape et checkpoints (reprise) |
| `build/quick/` | résultats de l'essai rapide |
| `build/*_best.pdparams` | meilleurs poids TL et FT |
| `build/run_full*.log`, `build/quick*.log` | journaux des lancements |

---

## 7. Les commandes

Toutes se lancent depuis la racine `9anoun-AI`, dans PowerShell.

| But | Commande | Durée |
|---|---|---|
| Installer (une fois) | `python -m venv --system-site-packages .venv` puis `.venv\Scripts\python -m pip install -r requirements-ocr.txt` | non mesurée (téléchargements) |
| Expérience complète | `.venv\Scripts\python experiments/ocr_transfer_finetune/run_experiment.py --seed 42` | environ 3 h d'entraînement (17,1 + 153,9 min [R]), plus génération et évaluations. **Les étapes déjà faites sont reprises** : relancée telle quelle, elle se termine presque tout de suite. |
| Tout refaire depuis zéro | ajouter `--fresh` | comme ci-dessus, environ 3 h ou plus |
| Essai rapide | ajouter `--quick` (64/32/32/16 lignes, 2 époques ; résultats dans `build/quick/`) | quelques minutes. Les époques FT de l'essai ont duré 73 s et 67 s [L:quick_bnfrozen.log]. Le « Terminé en 204.4 min » du journal compte depuis le **premier** essai rapide : ce n'est pas la durée d'un essai. Le README annonce « 7 minutes » : ce chiffre n'est pas vérifié par un journal. |
| Plan B Fine-Tuning | ajouter `--ft-variant partial` | non mesuré |
| Tests DS3 + expérience | `.venv\Scripts\python -m pytest -q src/document_intelligence/tests experiments/ocr_transfer_finetune/tests` | 276 réussis, en 49 s à 250 s selon les lancements [T] |
| Tests OCR seuls | `.venv\Scripts\python -m pytest -q src/document_intelligence/tests/test_document_intelligence_ocr.py` | 17 réussis en 61,5 s [T] |
| Démo OCR | `.venv\Scripts\python -m src.document_intelligence.reading.ocr <fichier_fictif.pdf ou .png>` (ajouter `--json sortie.json` pour le détail) | environ 30 à 40 s pour une page A4 dense [S], plus le chargement des modèles |
| Vraies données (c'est **toi** qui lances) | `.venv\Scripts\python -X faulthandler scripts/evaluer_donnees_reelles.py "<dossier_pdf>" --out "<dossier_hors_depot>" --limit 1` | environ 15 min par page d'après le dernier lancement [U] |

Pour la démo, utilise **uniquement un fichier fictif**. Le test `test_paddle_reads_fictive_scanned_payslip`
fabrique lui-même un PDF fictif (une ligne française, une ligne arabe) : c'est une démo sûre.

---

## 8. Les vraies données

Résumé agrégé que tu as obtenu [U] :

| Mesure | Valeur |
|---|---|
| Documents | 1 |
| Pages | 5 |
| Lignes OCR | 174 |
| Confiance moyenne | 0,9378 |
| Lignes avec une confiance sous 0,90 | 24 (environ 14 % des 174) |
| Durée | 4 563 s (environ 76 min, environ 15 min par page) |

**Ce que ça montre :**
- la chaîne complète tourne sur un vrai document : lecteur PDF → zones → OCR → lignes, sans plantage ;
- l'OCR produit du texte sur les 5 pages ;
- le modèle est **en moyenne sûr de lui** (0,94) ;
- 24 lignes sont moins sûres : ce sont elles qu'il faudrait vérifier en priorité.

**Ce que ça ne prouve pas :**
- **La confiance n'est pas la justesse.** Un modèle peut être très sûr et se tromper (par exemple, perdre un
  chiffre). Sans texte de référence (vérité terrain), **on ne peut pas calculer de CER** sur ces données.
- **Un seul document** : impossible de généraliser aux 66 PDF.
- **Le CER de 1,20 % de l'expérience ne s'applique pas** à ces données. Il a été mesuré sur des lignes fictives,
  avec un modèle fine-tuné qui **n'est pas** celui utilisé par `ocr.py` (qui garde le modèle pré-entraîné).
- La durée est trop longue pour 66 PDF en l'état (section 10).

---

## 9. Les 10 questions les plus probables du jury

1. **Pourquoi PaddleOCR et ce modèle ?**
   Il lit l'arabe, le français et les chiffres. C'est le même modèle que l'OCR de production. Il est petit, donc
   entraînable sur CPU.

2. **Quelle différence entre Transfer Learning et Fine-Tuning ?**
   En TL, on gèle le modèle et on ré-entraîne seulement la tête (90 629 paramètres). En FT, on ré-entraîne presque
   tout (5 478 185 paramètres), avec un learning rate 10 fois plus petit [R].

3. **Quel est le résultat ?**
   CER test : 13,68 % pour la baseline, 3,24 % pour le TL, 1,20 % pour le FT [R]. Le gain vient presque entièrement
   de l'arabe.

4. **Pourquoi des données fictives ?**
   Les vraies données sont confidentielles et ne sortent pas de leur dossier. Le générateur imite des fiches de paie,
   avec un bruit de scan. C'est la principale limite de l'expérience.

5. **Comment évitez-vous de tricher avec le jeu de test ?**
   On choisit la meilleure époque sur la **validation**. Le test sert une seule fois, à la fin.

6. **Y a-t-il de l'oubli catastrophique ?**
   Pas observé : le CER generic baisse (0,65 % → 0,35 %) [R]. Mais le jeu generic est petit et ressemble à
   l'entraînement, donc la mesure est faible.

7. **Pourquoi geler les BatchNorm ?**
   Le FT complet plantait toujours dans `batch_norm` (bug de Paddle sous Windows). Les geler a réduit les plantages,
   et c'est une pratique courante avec peu de données et de petits lots.

8. **Pourquoi le TL plafonne-t-il ?**
   Il ne peut pas changer les caractéristiques visuelles, seulement la façon de les lire. Il oublie souvent les
   espaces entre les mots arabes, d'où un WER encore de 19,38 % [R ; A].

9. **Comment garantissez-vous « citation ou silence » ?**
   Une zone illisible n'est jamais remplie par une invention. Elle reste en attente, avec un avertissement. Chaque
   ligne garde sa vraie confiance et un identifiant unique, que Gemini cite.

10. **Ça marche sur les vraies données ?**
    La chaîne tourne sur 1 document réel de 5 pages : 174 lignes, confiance moyenne 0,9378 [U]. Mais sans texte de
    référence, on ne connaît pas la précision réelle. Et c'est lent : environ 15 min par page.

Questions bonus possibles :
- *Pourquoi 1,20 % n'est-il pas utilisé en production ?* Parce qu'il est mesuré sur des données fictives, très
  proches du train. Il faut d'abord le confirmer sur des vraies lignes annotées.
- *Pourquoi seulement 4 époques ?* À cause du temps CPU (environ 45 min par époque après la reprise) [J]. La
  meilleure époque est la 3e : la 4e n'améliore plus la validation (1,05 % → 1,07 %).
- *Une seule graine ?* Oui, donc pas d'écart-type. L'écart entre TL et FT est grand, mais sa taille exacte est
  incertaine.

---

## 10. Ce qui reste à faire après la validation

1. **Commit et pull request** : rien n'est encore commité. À faire seulement avec ton accord : branche `DS3_ocr`
   vers `main`.
2. **Intégration au service de Hadil** : `extraction/pipeline.py` appelle aujourd'hui `read_pdf` puis Gemini,
   sans OCR [C:pipeline.py]. Il faut ajouter l'appel `ocr_pending_zones(doc, pdf_path)` entre les deux. C'est un
   fichier de Hadil : à décider avec elle, puis à tester avec les tests du service.
3. **Jeu réel annoté** : quelques centaines de lignes réelles, avec leur texte exact, gardées hors du dépôt. Il
   permettra de mesurer le vrai CER de la baseline, puis de refaire le FT `bn_frozen` sur un mélange réel + fictif.
4. **Lenteur** : environ 15 min par page [U]. À faire :
   - mesurer où part le temps (nombre de zones par page, double lecture en mode `auto`) ;
   - vérifier que `mobile_det` était bien utilisé ;
   - essayer `--lang ar` pour éviter la double lecture ;
   - regrouper les zones par page.
5. **Les 66 PDF** : au rythme actuel, ce serait très long. Par exemple, 66 documents de 5 pages chacun, à 4 563 s
   par document, feraient environ 84 h. C'est une **estimation**, pas une mesure. Le nombre réel de pages n'est pas
   connu ici. Il faut d'abord régler la lenteur, puis lancer par lots avec `--limit`.
6. **Défaut des chiffres dans les lignes arabes** : le modèle pré-entraîné perd des chiffres. C'est grave pour des
   montants. Le FT le corrige sur les données fictives : c'est l'argument principal pour adopter un modèle
   fine-tuné, une fois validé sur des données réelles.
7. **Plantages Paddle** : surveiller. Si `mobile_det` plante sur certaines vraies pages, découper la page en
   bandes horizontales qui se chevauchent, avant la détection.
