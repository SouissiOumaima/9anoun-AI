# Proposition : brancher l'OCR (partie A) dans le service DS3

**Statut : proposition, rien n'est appliqué.** À relire par Hadil (pipeline et service) et Wiem (OCR) avant toute
modification. Aucun fichier de la partie B, du pipeline ou du service n'a été modifié pour écrire ce document.

Branche de la proposition : `DS3_ocr_integration` (à partir de `DS3_ocr_vitesse`). L'OCR lui-même
(`src/document_intelligence/reading/ocr.py`) est sur `DS3_ocr` (PR #40).

---

## 1. Aujourd'hui

```
service.handle_request ──► extraction/pipeline.analyze_payslip_pdf
                              1. read_pdf (texte natif)
                              2. aucune ligne ? → refus SOURCE_MANQUANTE (UNREADABLE_DOCUMENT)
                              3. ask_gemini → vérification → réponse ds3.v2
```

- `pipeline.py` le dit lui-même (docstring) : « L'OCR (partie A) n'est pas encore branché : une page sans texte
  natif donne un refus SOURCE_MANQUANTE ».
- Les zones que `read_pdf` ne sait pas lire (images, scans, arabe en Private Use) restent dans `pending_zones`.
  `full_text()` les envoie à Gemini sous la forme `[p1_z1] <zone image non lue, en attente d'OCR>` : leur contenu est
  perdu.
- `service.py` refuse tout ce qui n'est pas `.pdf` (`LIVE_EXTENSIONS = {".pdf"}` → `UNSUPPORTED_FORMAT`).

## 2. Ce qui est proposé

```
service.handle_request ──► pipeline.analyze_payslip_pdf (accepte aussi PNG / JPG)
                              1. PDF   : read_pdf, puis ocr_pending_zones s'il reste des zones en attente
                                 image : read_image (OCR de toute l'image)
                              2. aucune ligne, ni native ni OCR ? → refus SOURCE_MANQUANTE (inchangé)
                              3. ask_gemini → vérification → réponse ds3.v2 (inchangé)
```

### 2.1 Où appeler `ocr_pending_zones`

**Entre `read_pdf` et le test « aucune ligne »**, donc avant Gemini :
- l'OCR n'est appelé **que s'il reste des zones en attente**. Un PDF entièrement natif ne paie aucun temps d'OCR ;
- le test « aucune ligne » reste en place et voit les lignes OCR : un scan lisible part à Gemini, une page où l'OCR
  ne lit rien donne toujours `SOURCE_MANQUANTE` (« citation ou silence ») ;
- `ocr_pending_zones` ne modifie pas le document d'entrée, garde dans `pending_zones` les zones qu'il n'a pas pu lire
  (avec un avertissement) et ne lève pas d'exception si le moteur échoue sur une zone.

### 2.2 Import paresseux : ne pas casser le service sans Paddle

`ocr.py` importe `numpy` et `Pillow` au chargement. Ni l'un ni l'autre n'est dans `requirements.txt` : ils viennent
de `requirements-ocr.txt`. Un `from ...reading.ocr import ...` en tête de `pipeline.py` ferait échouer **tout** le
service DS3 chez quelqu'un qui n'a pas installé les dépendances OCR.

Proposition : importer l'OCR **dans la fonction**, et si l'import échoue, garder le comportement d'aujourd'hui
(zones non lues, refus `SOURCE_MANQUANTE` si rien d'autre n'est lisible) avec un avertissement clair. PaddleOCR
lui-même est déjà chargé paresseusement par `ocr.py` (au premier appel).

### 2.3 Accepter PNG et JPG

- `service.py` : `LIVE_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}`.
- `pipeline.py` : si l'extension est une image, `read_image(path, document_id=...)` au lieu de `read_pdf`.
  `read_image` produit le même `IntermediateDocument` (une page `kind="image"`, une zone lue par l'OCR).
- **Unité des `bbox`** : pour une image, la page mesure `pixels × 72 / dpi` points (DPI lu dans le fichier, 300 par
  défaut). Les citations restent donc en « points », comme pour un PDF, mais sur une page virtuelle. À écrire dans le
  contrat (section 4).
- Image illisible (fichier tronqué, faux PNG) : `read_image` lève une exception, attrapée comme aujourd'hui pour
  `read_pdf` → `FILE_EMPTY_OR_CORRUPTED`.
- **Image alors que l'OCR n'est pas installé sur le serveur** (recommandation) : refus clair `HORS_SCOPE`
  (`UNSUPPORTED_FORMAT`), décidé dans `service.py` **avant** toute lecture, avec un message qui dit pourquoi :
  « La lecture des images (OCR) n'est pas installée sur ce serveur : envoyez un PDF avec du texte ». C'est
  honnête pour l'utilisateur et cohérent avec « format non pris en charge en live ». Le test se fait sans charger
  Paddle : `importlib.util.find_spec("paddleocr") is not None`.
- `mime_type` n'est pas vérifié aujourd'hui (seule l'extension compte). La proposition ne change pas ce point.

### 2.4 Rendre l'OCR remplaçable dans les tests

Comme `client` pour Gemini, `handle_request` et `analyze_payslip_pdf` reçoivent un paramètre facultatif
`ocr_engine` (un objet qui respecte `OcrEngine` : `recognize(image, lang)`). `None` = PaddleOCR par défaut. Les tests
passent un faux moteur : aucun modèle n'est chargé, les tests restent rapides et ne dépendent pas de Paddle.

## 3. Refus du contrat ds3.v2 qui changent

Les **codes** ne changent pas (`ds3_code`, `refus.code` et leur correspondance restent ceux du contrat). Ce qui
change, c'est **quand** ils sont renvoyés :

| Cas | Aujourd'hui | Après intégration |
|---|---|---|
| PDF entièrement natif | lu, envoyé à Gemini | **inchangé** (l'OCR n'est pas appelé) |
| PDF avec quelques zones image | zones perdues (« en attente d'OCR » dans le texte envoyé à Gemini) | zones lues par l'OCR ; lignes `source="ocr"` citables |
| Page scannée lisible | `refus` `SOURCE_MANQUANTE` (`UNREADABLE_DOCUMENT`) | **lue par l'OCR → `ok`** (ou `complete = false` si des champs manquent) |
| Page scannée où l'OCR ne lit rien | `refus` `SOURCE_MANQUANTE` | `refus` `SOURCE_MANQUANTE` (inchangé ; avertissement « rien n'est deviné ») |
| OCR non installé ou en panne | — | comme aujourd'hui (`SOURCE_MANQUANTE` si rien d'autre n'est lisible), avec un avertissement |
| Fichier `.png`, `.jpg`, `.jpeg` | `refus` `HORS_SCOPE` (`UNSUPPORTED_FORMAT`) | **lu par l'OCR** |
| Image alors que l'OCR n'est pas installé | `refus` `HORS_SCOPE` | `refus` `HORS_SCOPE` (`UNSUPPORTED_FORMAT`), message « OCR non installé sur ce serveur » |
| Image corrompue | — | `refus` `PARAM_INVALIDE` (`FILE_EMPTY_OR_CORRUPTED`) |
| Autres formats (`.docx`, `.tiff`, `.zip`…) | `refus` `HORS_SCOPE` | `refus` `HORS_SCOPE` (inchangé) |

**Confiance.** La confiance d'un champ est celle de sa ligne (D32 : 1,0 en natif, valeur de l'OCR sinon). DS3
n'applique aucun seuil (D39) ; DS1 exige 0,90. Conséquence attendue : des champs lus par l'OCR sous 0,90 passent
« à confirmer » côté DS1. Ordre de grandeur sur 1 vrai PDF de 5 pages : 24 lignes OCR sur 174 sous 0,90.

**Chiffres perdus en arabe.** Le modèle pré-entraîné perd parfois des chiffres dans les lignes arabes (voir
`experiments/ocr_transfer_finetune/ANALYSE.md`). `verify.py` vérifie que la valeur figure dans la ligne citée : une
valeur incomplète n'est donc pas vérifiée et le champ devient `null`. Le risque est un résultat **moins complet**,
pas une valeur fausse.

## 4. Diff proposé

> Ces diffs sont à appliquer par la propriétaire de chaque fichier, après relecture. Ils ne sont pas appliqués.

### 4.1 `src/document_intelligence/extraction/pipeline.py`

```diff
-"""Chaîne complète DS3 pour une fiche de paie en PDF : lecture -> Gemini -> vérification -> réponse ds3.v2.
+"""Chaîne complète DS3 pour une fiche de paie (PDF, PNG ou JPG) : lecture -> Gemini -> vérification -> ds3.v2.
 
-    1. lecture du PDF (texte natif) ............ reading/pdf_natif.py
+    1. lecture : texte natif du PDF ............ reading/pdf_natif.py
+       puis OCR des zones en attente / image .. reading/ocr.py (partie A)
     2. Gemini : où se trouve chaque valeur ...... extraction/gemini.py
     3. vérification contre le document .......... extraction/verify.py
     4. normalisation au format du contrat ....... extraction/normalize.py
     5. réponse ds3.v2 avec citations ............ extraction/assemble.py
 
 Ne lève jamais d'exception : un problème devient une réponse « refus » ou « erreur ».
-L'OCR (partie A) n'est pas encore branché : une page sans texte natif donne un refus SOURCE_MANQUANTE.
+L'OCR n'est appelé que s'il reste des zones en attente ; si rien n'est lisible, même après OCR : SOURCE_MANQUANTE.
 """
 
 from __future__ import annotations
 
 import logging
 import time
 from pathlib import Path
 from typing import Any
 
 from src.document_intelligence.contract.v2.models import DS3Request, DS3Response, Erreur, Refus, ResponseMeta
 from src.document_intelligence.extraction.assemble import (
     COMPUTED_BY,
     PIPELINE_VERSION,
     build_payslip_response,
 )
 from src.document_intelligence.extraction.gemini import GeminiError, ask_gemini
+from src.document_intelligence.intermediate import IntermediateDocument
 from src.document_intelligence.reading.pdf_natif import read_pdf
 
 log = logging.getLogger(__name__)
 
+IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg"})
+
 
@@
+def _read_document(path: Path, document_id: str, ocr_engine: Any | None) -> IntermediateDocument:
+    """Texte natif du PDF, puis OCR des zones en attente ; image : OCR de toute l'image.
+
+    L'OCR est importé ici et non en tête du module : sans les dépendances de requirements-ocr.txt, le service
+    continue de fonctionner comme avant (zones non lues, avertissement).
+    """
+    is_image = path.suffix.lower() in IMAGE_EXTENSIONS
+    try:
+        from src.document_intelligence.reading.ocr import ocr_pending_zones, read_image
+    except ImportError:
+        if is_image:
+            raise
+        doc = read_pdf(path, document_id=document_id)
+        if any(page.pending_zones for page in doc.pages):
+            doc.warnings.append("OCR non installé (requirements-ocr.txt) : les zones en attente ne sont pas lues.")
+        return doc
+    if is_image:
+        return read_image(path, engine=ocr_engine, document_id=document_id)
+    doc = read_pdf(path, document_id=document_id)
+    if any(page.pending_zones for page in doc.pages):
+        doc = ocr_pending_zones(doc, path, engine=ocr_engine)
+    return doc
+
+
 def analyze_payslip_pdf(pdf_path: Path, req: DS3Request, client: Any | None = None,
-                        model: str | None = None) -> dict[str, Any]:
-    """Analyse une fiche de paie en PDF et renvoie la réponse ds3.v2 (dict JSON)."""
+                        model: str | None = None, ocr_engine: Any | None = None) -> dict[str, Any]:
+    """Analyse une fiche de paie (PDF, PNG ou JPG) et renvoie la réponse ds3.v2 (dict JSON).
+
+    `ocr_engine` permet aux tests de remplacer PaddleOCR (même rôle que `client` pour Gemini).
+    """
     started = time.perf_counter()
     try:
-        doc = read_pdf(pdf_path, document_id=req.document.document_id)
+        doc = _read_document(pdf_path, req.document.document_id, ocr_engine)
     except Exception:
         log.exception("Lecture impossible : %s", pdf_path.name)
         return DS3Response(
@@
     if not any(page.lines for page in doc.pages):
         return DS3Response(
             **_envelope(req, started), status="refus", ds3_code="UNREADABLE_DOCUMENT",
             refus=Refus(code="SOURCE_MANQUANTE",
                         message_fr="Aucun texte lisible dans ce document : rien n'est extrait.",
                         message_ar="لا يوجد أي نص مقروء في هذه الوثيقة."),
-            warnings=[*doc.warnings, "Aucun texte natif : le document doit passer par l'OCR (partie A)."],
+            warnings=[*doc.warnings, "Aucun texte lu, ni dans la couche texte du PDF ni par l'OCR."],
         ).to_json()
```

Remarques :
- `ocr_engine: Any` évite d'importer `OcrEngine` en tête du module (même raison que l'import paresseux). Si Hadil
  préfère un type exact : `if TYPE_CHECKING: from ...reading.ocr import OcrEngine`.
- `_read_document` attrape seulement `ImportError`. Les autres erreurs (fichier corrompu) remontent au `try` existant
  et donnent `FILE_EMPTY_OR_CORRUPTED`, comme aujourd'hui.
- Le nom `analyze_payslip_pdf` est gardé pour ne rien casser chez les appelants ; seul le docstring dit qu'il
  accepte aussi les images. Un renommage peut venir plus tard.

### 4.2 `src/document_intelligence/service.py`

```diff
+import importlib.util
@@
-LIVE_EXTENSIONS: Final = {".pdf"}
+IMAGE_EXTENSIONS: Final = {".png", ".jpg", ".jpeg"}
+LIVE_EXTENSIONS: Final = {".pdf", *IMAGE_EXTENSIONS}
@@
 def handle_request(request: dict[str, Any], *, storage_root_dir: Path | str | None = None,
-                   client: Any | None = None, model: str | None = None) -> dict[str, Any]:
+                   client: Any | None = None, model: str | None = None,
+                   ocr_engine: Any | None = None) -> dict[str, Any]:
     """Point d'entrée unique DS3 en live. Reçoit et renvoie du JSON (dict), jamais d'exception.
 
-    `client` et `model` permettent aux tests de remplacer Gemini (aucun appel réseau).
+    `client` et `model` permettent aux tests de remplacer Gemini (aucun appel réseau) ;
+    `ocr_engine` permet de remplacer PaddleOCR (aucun modèle chargé).
     """
     started = time.perf_counter()
     try:
-        return _handle(request, storage_root_dir, client, model, started)
+        return _handle(request, storage_root_dir, client, model, ocr_engine, started)
@@
-def _handle(request: dict[str, Any], root_dir: Path | str | None, client: Any | None, model: str | None,
-            started: float) -> dict[str, Any]:
+def _handle(request: dict[str, Any], root_dir: Path | str | None, client: Any | None, model: str | None,
+            ocr_engine: Any | None, started: float) -> dict[str, Any]:
@@
-    if PurePosixPath(req.document.file_name).suffix.lower() not in LIVE_EXTENSIONS:
+    suffix = PurePosixPath(req.document.file_name).suffix.lower()
+    if suffix not in LIVE_EXTENSIONS:
         return _refus(env, "UNSUPPORTED_FORMAT",
-                      live_fr="Format pas encore pris en charge en live : seuls les PDF le sont pour l'instant.",
-                      live_ar="هذه الصيغة غير مدعومة بعد في الخدمة الفعلية: ملفات PDF فقط حاليا.")
+                      live_fr="Format pas encore pris en charge en live : seuls les PDF, PNG et JPG le sont.",
+                      live_ar="هذه الصيغة غير مدعومة بعد في الخدمة الفعلية: ملفات PDF وPNG وJPG فقط حاليا.")
+    if suffix in IMAGE_EXTENSIONS and importlib.util.find_spec("paddleocr") is None:
+        return _refus(env, "UNSUPPORTED_FORMAT",
+                      live_fr="La lecture des images (OCR) n'est pas installée sur ce serveur : "
+                      "envoyez un PDF avec du texte.",
+                      live_ar="قراءة الصور (OCR) غير مثبتة على هذا الخادم: أرسل ملف PDF يحتوي على نص.")
@@
-    return analyze_payslip_pdf(path, req, client=client, model=model)
+    return analyze_payslip_pdf(path, req, client=client, model=model, ocr_engine=ocr_engine)
```

Le message arabe est à faire relire par une personne arabophone de l'équipe avant de l'appliquer.

### 4.3 `docs/CONTRACT_DOCUMENT_INTELLIGENCE_V2.md` (section « Service réel »)

```diff
-**Disponible en live aujourd'hui :** `analyze_document` sur une **fiche de paie en PDF** (texte natif).
+**Disponible en live aujourd'hui :** `analyze_document` sur une **fiche de paie en PDF, PNG ou JPG**. Le texte natif
+du PDF est lu d'abord ; les zones image, les pages scannées et les images sont lues par l'OCR (PaddleOCR PP-OCRv5,
+arabe et français). Une ligne lue par l'OCR porte sa confiance réelle ; pour une image, les `bbox` sont en points
+d'une page virtuelle de `pixels × 72 / dpi` points (300 DPI par défaut).
 Le reste donne un refus clair, en français et en arabe :
@@
-| fichier autre que PDF | `refus` `HORS_SCOPE` (`UNSUPPORTED_FORMAT`) |
+| fichier autre que PDF, PNG, JPG | `refus` `HORS_SCOPE` (`UNSUPPORTED_FORMAT`) |
 | `expected_type` autre que `fiche_de_paie` | `refus` `HORS_SCOPE` (`UNSUPPORTED_FORMAT`) |
-| page scannée sans texte | `refus` `SOURCE_MANQUANTE` (en attente de l'OCR de la partie A) |
+| document où ni la couche texte ni l'OCR ne lisent rien | `refus` `SOURCE_MANQUANTE` |
```

### 4.4 `docs/DECISIONS.md`

Une nouvelle décision **D41** (D41 à D45 sont réservés à DS3 d'après D40 ; à revérifier avec `git fetch origin`
au moment du merge) : « OCR branché dans le service live : seulement s'il reste des zones en attente, import
paresseux, images PNG/JPG acceptées, confiance OCR transmise telle quelle ». D40 garde son historique ; la ligne
« page scannée : SOURCE_MANQUANTE en attendant l'OCR » est marquée « remplacé par D41 ».

### 4.5 `docs/CONTRACT_DOCUMENT_INTELLIGENCE_V2.md` (exemples) et mock

Le mock v2 ne change pas : il simule déjà un document lisible ou non par son nom de fichier. Les exemples générés
(`generate_examples.py`) n'ont pas besoin d'être régénérés.

## 5. Tests à ajouter ou à adapter

Tous avec un **faux moteur d'OCR** (comme `FakeEngine` dans `test_document_intelligence_ocr.py`) et le faux client
Gemini existant : aucun modèle, aucun réseau.

**À adapter (deviennent faux après l'intégration) :**

| Test | Fichier | Pourquoi | Adaptation proposée |
|---|---|---|---|
| `test_scanned_page_is_not_sent_to_gemini` | `test_document_intelligence_gemini.py` | sur un poste avec Paddle, DS3-03 serait lu par l'OCR puis envoyé à Gemini | passer un faux moteur qui ne lit **rien** : le refus et « aucun appel Gemini » restent vrais ; le message d'avertissement contient toujours « OCR » |
| `NEEDS_OCR = {"DS3-03"}` | `test_document_intelligence_golden.py` | le cas scanné peut maintenant être évalué | garder l'exclusion du test 100 % natif, et ajouter le test OCR ci-dessous |

**À ajouter :**

1. **Pipeline, scan lisible** : DS3-03 + faux moteur qui renvoie les lignes de la fiche → `status = "ok"`, les
   citations pointent vers des lignes `source="ocr"`, la confiance des champs est celle donnée par le moteur.
2. **Pipeline, PDF natif** : DS3-01 + faux moteur → `engine.calls == []` (aucun temps d'OCR sur un PDF natif).
3. **Pipeline, moteur en panne** : faux moteur qui lève une exception → `refus` `SOURCE_MANQUANTE`, avertissement
   « échec de lecture », aucune exception.
4. **OCR non installé** : simuler l'absence (monkeypatch de `importlib.util.find_spec` et de `sys.modules`) →
   PDF : même réponse qu'aujourd'hui ; image : `refus` `HORS_SCOPE` (`UNSUPPORTED_FORMAT`) avec le message
   « OCR non installé », sans lire le fichier.
5. **Service, image** : `paie.png` dans le stockage (`local://`), faux moteur, faux Gemini → `status = "ok"`,
   `mode = "live"`, `DS3Response.model_validate` passe.
6. **Service, formats** : `.tiff` → `UNSUPPORTED_FORMAT` ; `.png` corrompu → `FILE_EMPTY_OR_CORRUPTED`.
7. **Service, paramètre** : `handle_request(..., ocr_engine=fake)` transmet bien le moteur au pipeline.
8. **Intégration réelle (facultatif, `skipif` sans paddleocr)** : un PDF scanné fictif lu par le vrai PaddleOCR de
   bout en bout, avec un faux Gemini.
9. **Processus séparé (section 7.2)** : un faux OCR qui sort avec un code d'erreur (comme un plantage natif) ou
   dépasse le délai → le service répond quand même ; les zones restent en attente avec un avertissement ; aucune
   exception.
10. **Cache du téléversement (section 7.1)** : si le résultat de l'OCR est déjà en cache pour ce fichier, le
    pipeline ne relance pas l'OCR (`engine.calls == []`) ; si le cache n'est pas prêt, la réponse suit l'option
    choisie (`TIMEOUT` réessayable recommandé).

Tous les tests existants doivent continuer à passer, sur un poste **avec** et **sans** `requirements-ocr.txt`.

## 6. Risques et points à décider

| Risque | Détail | Mesure proposée |
|---|---|---|
| **Temps de réponse** | La spécification vise **20 s (P95)**. L'OCR prend environ 27 s par page sur CPU (mesuré sur 1 vrai PDF de 5 pages), plus environ 8,5 s de chargement des modèles. Un scan d'une seule page dépasse déjà la cible ; 5 pages ≈ 2 min 30. | **OCR au téléversement, pas à la question** (section 7.1). |
| **Plantage natif de Paddle** | Paddle peut mourir sans exception Python (access violation, vu à l'entraînement, et à l'inférence avec `server_det` avant le passage à `mobile_det`). Un `try/except` ne l'attrape pas : **tout le processus du service tomberait**. Aucun plantage observé à l'inférence depuis `mobile_det`, mais le risque reste. | **OCR dans un processus séparé** (section 7.2). |
| **Conflit torch / paddle** | Sous Windows, importer `torch` **après** `paddle` dans le même processus fait échouer le chargement de `shm.dll`. Aucun module de `src/` n'importe `torch` aujourd'hui. | Si DS1 regroupe plusieurs DS dans un seul processus et qu'un module importe `torch`, importer `torch` **avant** l'OCR, ou séparer les processus. À signaler à DS1. |
| **Dépendances lourdes** | `paddlepaddle`, `paddleocr`, `paddlex` (plusieurs centaines de Mo) + modèles téléchargés au premier appel (cache `~/.paddlex`). | `requirements-ocr.txt` reste séparé ; l'import paresseux garde le service utilisable sans lui. Pré-télécharger les modèles sur la machine de démo. |
| **Mémoire / processeur** | Une page A4 à 300 DPI = environ 8,7 millions de pixels ; l'OCR occupe le CPU pendant ~30 s. | Une requête OCR à la fois au début. Ne pas appeler l'OCR en parallèle tant que la sûreté des threads de PaddleOCR n'est pas vérifiée. |
| **Qualité réelle inconnue** | Pas de CER mesuré sur des vraies lignes (pas de texte de référence). Chiffres parfois perdus dans les lignes arabes. | Étape suivante : jeu réel annoté (scripts `annoter_lignes.py` et `evaluer_cer_reel.py`). La vérification `verify.py` empêche une valeur incomplète d'être renvoyée. |
| **Image sans OCR installé** | Accepter `.png` dans le service sans Paddle donnerait un refus peu clair. | **Recommandé** : refus `HORS_SCOPE` (`UNSUPPORTED_FORMAT`) décidé avant la lecture, avec le message « La lecture des images (OCR) n'est pas installée sur ce serveur » (sections 2.3 et 4.2). |
| **`bbox` des images** | Points d'une page virtuelle, pas d'un PDF. | Écrit dans le contrat (section 4.3) ; l'écran de revue DS1 doit afficher l'image à la même échelle. |

## 7. Tenir les 20 s et survivre à un plantage de Paddle

### 7.1 Lancer l'OCR au téléversement, pas au moment de la question

**Problème.** La spécification vise un délai de réponse de **20 s (P95)**. L'OCR prend environ **27 s par page** :
une seule page scannée dépasse déjà la cible si l'OCR est fait quand l'utilisateur pose sa question.

**Proposition.** Faire l'OCR **dès que le document est téléversé**, pendant que l'utilisateur fait autre chose, et
garder le résultat :

```
téléversement ─► DS3 : lecture native + OCR (processus séparé, 7.2) ─► cache : IntermediateDocument (JSON)
question      ─► DS3 : lit le cache ─► Gemini ─► vérification ─► réponse ds3.v2   (plus d'OCR ici)
```

- **Cache** : le `IntermediateDocument` complet (lignes natives et OCR) en JSON, rangé dans le stockage DS3 à côté
  du document, nommé par l'empreinte SHA-256 du fichier et la version du lecteur (`reader`, par ex.
  `pdf_natif-0.3+ocr_paddle-0.1`). Un fichier modifié ou un nouveau lecteur donne une autre empreinte, donc une
  nouvelle lecture : jamais de résultat périmé.
- **À la question** : `analyze_payslip_pdf` lit le cache s'il existe. Le temps de réponse redevient celui du texte
  natif + Gemini, quel que soit le nombre de pages.
- **Si le cache n'est pas encore prêt** (question posée juste après le téléversement), deux options à décider avec
  DS1 :
  - (a) faire l'OCR tout de suite (réponse lente, mais complète) ;
  - (b) **recommandé** : répondre `erreur` `TIMEOUT` avec `retryable = true` et le message « Lecture du document en
    cours, réessayez dans quelques instants ». Le code existe déjà dans le contrat ; DS1 sait déjà proposer de
    réessayer.
- **Déclencheur** : le contrat ds3.v2 n'a pas d'opération « document téléversé ». Deux possibilités :
  - une **nouvelle opération** `prepare_document` (même requête, réponse sans `result`) appelée par DS1 au
    téléversement. C'est un **changement de contrat** : à valider avec DS1 et à écrire dans une décision (D41) ;
  - ou, sans toucher au contrat, un **petit service de fond** DS3 qui surveille le dossier de stockage et traite
    chaque nouveau fichier. Plus simple à démarrer, mais DS1 ne sait pas quand la lecture est finie.
- **Confidentialité** : le cache contient le texte du document. Il reste dans le stockage DS3, avec les mêmes droits
  que le fichier d'origine, et il est supprimé avec lui.

### 7.2 Exécuter l'OCR dans un processus séparé

**Problème.** Un plantage natif de Paddle (access violation) tue le processus qui l'a appelé, sans exception
Python. Si l'OCR tourne dans le processus du service, **tout le service DS3 tombe**, y compris pour les autres
utilisateurs.

**Proposition.** Le service ne charge jamais Paddle lui-même. Il lance l'OCR dans un **processus séparé**, attend
son résultat avec un délai maximal, et lit un JSON :

```python
# esquisse, dans reading/ (fichier de Wiem) ; appelée par le pipeline ou par le travail de téléversement
def ocr_in_subprocess(path: Path, document_id: str, timeout_s: float) -> IntermediateDocument | None:
    out = <fichier temporaire .json dans le stockage DS3>
    proc = subprocess.run(
        [sys.executable, "-m", "src.document_intelligence.reading.ocr", str(path), "--json", str(out)],
        capture_output=True, timeout=timeout_s, check=False,
    )   # stdout contient le texte du document : jamais journalisé
    if proc.returncode != 0 or not out.exists():
        return None                       # plantage natif, délai dépassé ou erreur : rien n'est deviné
    return IntermediateDocument.model_validate_json(out.read_text(encoding="utf-8"))
```

- La commande `python -m src.document_intelligence.reading.ocr fichier --json sortie.json` **existe déjà** (CLI de
  `ocr.py`) : elle fait la lecture native puis l'OCR et écrit le `IntermediateDocument` complet.
- **Si le processus plante** (code de sortie ≠ 0, comme `3221225477` sous Windows) ou dépasse le délai : le service
  garde la lecture native, les zones restent dans `pending_zones` avec un avertissement « OCR interrompu », et la
  suite est la même qu'aujourd'hui (`SOURCE_MANQUANTE` si rien n'est lisible). **Le service, lui, continue.**
- `document_id` : à remettre sur le document lu (la CLI utilise le nom du fichier), ou à passer en option de la CLI
  (petite modification de `ocr.py`, côté Wiem).
- **Coût** : chaque processus recharge les modèles (environ 8,5 s mesurés). Acceptable au téléversement (7.1).
  Version suivante si besoin : un **processus OCR permanent** qui garde les modèles en mémoire et reçoit les
  fichiers un par un ; s'il plante, le service le relance (même idée que le superviseur de l'expérience).
- **Bonus** : le conflit de DLL torch / paddle disparaît, puisque Paddle n'est plus jamais chargé dans le processus
  du service.

Avec 7.2, le paramètre `ocr_engine` (section 2.4) reste utile pour les tests du pipeline. La fonction
`ocr_in_subprocess` est testée à part (test 9 de la section 5).

## 8. Ordre proposé

1. Merger la PR #40 (`DS3_ocr`) : l'OCR et ses tests arrivent sur `main` sans rien brancher.
2. Relire ce document avec Hadil ; décider du déclencheur du téléversement et du comportement quand le cache
   n'est pas prêt (section 7.1), puis valider avec DS1.
3. Wiem ajoute `ocr_in_subprocess` et le cache dans `reading/` (ses fichiers), avec leurs tests.
4. Hadil applique 4.1 et 4.2 (ses fichiers), avec l'OCR en processus séparé et la lecture du cache, et les tests
   de la section 5 ; Wiem relit.
5. Mettre à jour le contrat (4.3) et `DECISIONS.md` (4.4), puis prévenir DS1 : nouveaux formats, OCR au
   téléversement, `TIMEOUT` réessayable pendant la lecture, champs OCR « à confirmer » plus fréquents.
