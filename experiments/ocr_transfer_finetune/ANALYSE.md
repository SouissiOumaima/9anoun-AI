# Analyse critique : Transfer Learning vs Fine-Tuning (OCR arabe / français)

Les chiffres viennent de [`results.md`](results.md) (graine 42, données fictives, CPU). Ce document les interprète et
dit ce qu'ils ne prouvent pas.

## 1. Ce qui a été comparé

| Méthode | Entraîné | Paramètres entraînés | CER test | WER test | CER AR | CER generic |
|---|---|---|---|---|---|---|
| Baseline | rien | 0 | 13.68 % | 24.74 % | 24.93 % | 0.65 % |
| Transfer Learning | tête CTC seule (backbone + encodeur gelés) | 90 629 | 3.24 % | 19.38 % | 5.92 % | 0.43 % |
| Fine-Tuning, variante `bn_frozen` | tout le chemin CTC sauf les BatchNorm, LR 1e-4 | 5 478 185 | **1.20 %** | **7.06 %** | 1.91 % | 0.35 % |

Modèle : `arabic_PP-OCRv5_mobile_rec`, le même que l'OCR de production (`reading/ocr.py`). Pour chaque méthode,
on garde l'époque qui a le meilleur CER de validation (TL : époque 8 sur 15 ; FT : époque 3 sur 4). Le test ne sert
qu'à la mesure finale.

**Le chiffre de Fine-Tuning vient de la variante `bn_frozen`** : tous les poids sont dégelés, sauf l'échelle, le biais et
les statistiques des 151 couches BatchNorm (section 3.1). Le Fine-Tuning « tout dégelé » au sens strict n'a jamais pu
aller au bout sur cette machine.

## 2. Lecture des résultats

- **Le français était déjà presque parfait** (CER FR de la baseline : 0.57 %). Presque tout le gain vient de l'arabe
  (24.93 % → 5.92 % → 1.91 %) et des lignes mixtes arabe + chiffres (46.97 % → 11.04 % → 6.28 %).
- **L'erreur principale de la baseline : les chiffres dans les lignes arabes disparaissent** (exemple :
  « الضريبة على الدخل : 2613.193 د » lu « الضريبة علىالدخل »). Le modèle d'inférence de la tâche 1 a le même défaut.
  Le TL le corrige en partie ; le FT le corrige presque entièrement.
- **Le Transfer Learning plafonne vite** : son CER de validation se stabilise vers 2.8 % dès l'époque 8. Avec 90 k
  paramètres, la tête apprend à mieux utiliser les caractéristiques existantes, mais elle ne peut pas les modifier.
  Les espaces manquent souvent (« علىالدخل »), d'où un WER encore élevé (19.38 %) malgré un CER faible.
- **Le Fine-Tuning adapte aussi les caractéristiques visuelles** : en une époque, il dépasse le TL après 15 époques. Il
  coûte beaucoup plus cher : 5,5 M paramètres et 154 min d'entraînement contre 17 min.
- **Le WER montre la vraie différence pour le projet** : 79.5 % de lignes exactes avec le FT contre 58.5 % avec le TL.
  Pour extraire un montant ou un échelon, une ligne exacte compte plus qu'un CER moyen.

## 3. Difficultés rencontrées

### 3.1 Plantage natif de Paddle pendant le Fine-Tuning (bug principal)

- **Symptôme** : le processus meurt sans exception Python, avec le code `3221225477` (0xC0000005,
  *access violation*). Le traceback `faulthandler` pointe toujours vers `paddle.nn.functional.batch_norm`, dans le
  backbone PPLCNetV3, au milieu d'une époque. Le crash est aléatoire : il ne survient pas au même lot d'une fois à
  l'autre.
- **Cause probable** : un bug du noyau CPU de Paddle 3.3.1 sous Windows. La pile native montre Intel MKL (`vsAdd`)
  dans le BatchNorm. Il n'apparaît que lorsque le backbone reçoit des gradients ; le TL (backbone gelé) n'a jamais
  planté. Ce n'est pas un manque de RAM : rien ne l'indiquait, et une erreur mémoire Python aurait été levée.
- **Historique** :
  1. Premier lancement : plantage après l'époque 1 du FT (val CER 3.85 %). Rien n'était sauvegardé par époque.
  2. Ajout d'un **superviseur** : le script se relance lui-même dans un sous-processus, jusqu'à 3 fois. Ajout aussi de
     **points de sauvegarde à chaque époque** (poids, état de l'optimiseur et du scheduler, historique) et de résultats
     enregistrés par étape. La baseline et le TL ne sont plus jamais recalculés. La première reprise a échoué parce que
     l'état de l'optimiseur était indexé par des noms de tenseurs générés automatiquement (`conv2d_131.w_0_moment1_0`),
     qui changent d'un processus à l'autre. Correction : remappage sur les noms structurels des paramètres.
  3. Essai `MKL_NUM_THREADS=1` : 11 fois plus lent (92 min rien que pour une étape qui prenait environ 8 min).
     Abandonné.
  4. Relance avec reprise, tout dégelé : 4 plantages d'affilée, le superviseur abandonne.
- **Correction retenue (variante `bn_frozen`)** : les paramètres BatchNorm (échelle, biais) ont `stop_gradient=True`,
  et les couches BatchNorm restent en mode évaluation, donc leurs statistiques sont gelées. Tout le reste est entraîné.
  C'est une pratique courante en fine-tuning avec peu de données et de petits lots.
- **Effet mesuré** :
  - sur l'essai rapide : aucun plantage, et une époque passe de 182 s à environ 70 s ;
  - sur l'expérience complète : **1 seul plantage en 4 époques** (après l'époque 1), contre 4 plantages consécutifs
    avant. La reprise automatique a repris depuis l'époque 1, et l'entraînement est allé au bout.
  - La correction **réduit le problème sans le supprimer**. C'est l'ensemble « BatchNorm gelée + points de sauvegarde
    + superviseur » qui rend l'expérience reproductible.
  - Le plan B (`--ft-variant partial` : seulement le dernier étage du backbone, l'encodeur et la tête) n'a pas été
    nécessaire. Il reste disponible.
- **Constat non expliqué** : après la reprise, les époques 2 à 4 ont duré environ 2 700 s, contre 852 s pour l'époque
  1, avec le même code. La charge de la machine (mise en veille, autre programme, température) pourrait jouer, mais
  rien ne le prouve. Les durées de `results.md` sont donc des durées réelles, pas un coût normal.

### 3.2 Autres difficultés

- **Plantage oneDNN à l'inférence** (`ConvertPirAttribute2RuntimeAttribute`) : corrigé avec `enable_mkldnn=False`
  dans `ocr.py` et `FLAGS_use_mkldnn=0` dans l'expérience.
- **Ordre visuel de l'arabe** : les poids d'entraînement publiés sortent l'arabe en ordre visuel, alors que le modèle
  d'inférence PaddleX le sort en ordre logique. Sans correction, la baseline donnait 38.9 % de CER, une erreur de
  mesure et pas du modèle. Les cibles sont donc passées en ordre visuel, puis la sortie est remise en ordre logique
  (`rtl.py`, fonction involutive testée).
- **Pas de temps CTC** : en mode « train », PPLCNetV3 force 40 pas de temps, ce qui fait planter warpctc dès qu'une
  ligne dépasse 40 caractères. Le backbone reste donc en mode évaluation, même en FT : ses poids reçoivent quand même
  les gradients.
- **Conflit de DLL torch / paddle** (`shm.dll`) si torch est importé après paddle dans le même processus. Il est évité
  dans les scripts et n'apparaît pas dans la suite de tests.
- **Taille des données réduite pour le CPU** : 1 200 lignes d'entraînement au lieu des 3 000 prévues, et 4 époques de
  FT seulement.
- **Le TL précalcule les caractéristiques de l'encodeur gelé** une seule fois : c'est ce qui le rend aussi rapide.

## 4. Limites : ce que ces chiffres ne prouvent pas

- **Données fictives ≠ données réelles.** Les lignes sont rendues par ordinateur, avec 4 polices Windows et un bruit
  de scan simulé. Les vrais scans ont des tampons, des signatures, des tableaux, du papier plié, des polices variées
  et parfois de l'écriture manuscrite. Le CER réel sera plus élevé. Il faut le mesurer avec
  `scripts/evaluer_donnees_reelles.py`. Pour l'instant, ce script ne donne que des agrégats (pas de vérité terrain),
  donc il ne donne pas de CER.
- **Train et test se ressemblent beaucoup.** Les deux viennent du même générateur, donc des mêmes gabarits de phrases
  et du même vocabulaire. Seuls les montants, les dates et le rendu changent. Le FT a pu apprendre en partie le
  vocabulaire du domaine. Le CER de 1.20 % mesure donc surtout l'adaptation à ce rendu et à ce vocabulaire, pas une
  généralisation à des fiches inconnues.
- **Peu de données.** Avec 1 200 lignes, le FT de 5,5 M paramètres risque le sur-apprentissage. Le CER de validation
  remonte d'ailleurs légèrement à l'époque 4 (1.05 % → 1.07 %). Une seule graine a été lancée, donc pas d'écart-type :
  la différence entre TL et FT est nette, mais sa taille exacte reste incertaine.
- **Oubli catastrophique : pas observé, mais mal mesuré.** Le CER sur le jeu « generic » baisse même avec le FT
  (0.65 % → 0.35 %). Ce jeu ne contient que 20 phrases distinctes, rendues avec les mêmes polices et le même bruit
  que l'entraînement. Le modèle s'améliore sur ce rendu, quel que soit le sujet. Un vrai test d'oubli demanderait
  d'autres polices, des images naturelles ou des documents d'un autre type. La BatchNorm gelée et le LR faible
  limitent probablement l'oubli, sans le garantir.
- **Arabe RTL.** Le CER est calculé en ordre logique, après normalisation NFC. Il ne mesure pas les erreurs de
  segmentation en lignes ni d'ordre des lignes dans une page : c'est le travail de `ocr.py`, testé à part.
- **Changement de générateur aléatoire entre deux lancements.** L'ordre des lots dépend maintenant de
  `default_rng([graine, époque])`, ce qui rend les reprises reproductibles. Les chiffres du tout premier lancement
  (avant ce changement) ne sont donc pas strictement comparables. Seuls ceux de `results.md` comptent.

## 5. Recommandation pour le projet

1. Garder pour l'instant le modèle pré-entraîné dans `ocr.py`. Il est fiable en français, et le résultat du FT reste
   à confirmer sur des données réelles.
2. Constituer un petit jeu réel annoté de quelques centaines de lignes, en respectant la confidentialité (hors dépôt).
   Mesurer la baseline dessus, puis refaire le FT `bn_frozen` sur un mélange réel + fictif.
3. Si le CPU reste la seule machine : garder le TL comme solution rapide (17 min, gain déjà important sur l'arabe) et
   réserver le FT à une machine plus stable, ou à un GPU.
