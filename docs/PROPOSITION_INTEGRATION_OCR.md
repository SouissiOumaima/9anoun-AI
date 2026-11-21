# Proposition : brancher l'OCR (partie A) dans le service DS3

**Statut : approuvée par Hadil le 2026-11-21 (décisions D41 et D42 ci-dessous). Appliquée en partie.**
- **Déjà fusionné (PR #44, Hadil)** : le pipeline et le service sont branchés avec l'**option B** : l'OCR ne tourne
  **dans le processus du service** que si `DS3_OCR_INPROCESS=1` (réservé aux démonstrations). Sans cette variable, un
  PDF est lu comme avant (zones en attente, avertissement) et une image reçoit le refus D41. Le contrôle passe par
  `pipeline.ocr_available()`. D41 est écrite dans `DECISIONS.md`.
- **À venir (D42)** : le backend en arrière-plan de la PR #46 (`reading/ocr_cache.py` : processus séparé, cache,
  verrou) **remplacera** l'option B : `ocr_backend` à la place de `DS3_OCR_INPROCESS` (diffs 4.1 et 4.2 ci-dessous).

Aucun fichier de la partie B, du pipeline ou du service n'a été modifié pour écrire ce document : Hadil applique
elle-même les diffs dans ses fichiers (section 8).

Branche de la proposition : `DS3_ocr_integration` (à partir de `DS3_ocr_vitesse`). L'OCR lui-même
(`src/document_intelligence/reading/ocr.py`) est sur `DS3_ocr` (PR #40).

## Décisions validées

| N° | Décision |
|---|---|
| **D41** | Une image (PNG, JPG) envoyée alors que l'OCR **n'est pas disponible** sur le serveur reçoit un **refus `HORS_SCOPE`** (`ds3_code` `UNSUPPORTED_FORMAT`), décidé avant toute lecture, avec le message « La lecture des images n'est pas possible : l'OCR n'est pas installé ou pas activé sur ce serveur. Envoyez un PDF avec du texte. ». « Disponible » se vérifie avec `ocr_available()`, plus seulement avec `find_spec("paddleocr")` (section 2.3). |
| **D42** | **Pas de changement de contrat pour l'instant.** À la première question sur un document qui demande l'OCR, l'OCR est lancé **en arrière-plan** et le service répond `erreur` **`TIMEOUT` réessayable** (`retryable = true`, « lecture en cours »). **Chaque nouvel essai** répond de même **`TIMEOUT` réessayable tant que la lecture n'est pas terminée** ; le résultat en cache n'est servi **qu'une fois la lecture achevée** (jamais de résultat partiel). Le déclenchement au téléversement (`prepare_document`) viendra plus tard, après accord d'Achref (DS1) (section 7.1). |

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

## 2. Ce qui change

```
service.handle_request ──► pipeline.analyze_payslip_pdf (accepte aussi PNG / JPG)
                              1. PDF : read_pdf ; plus de zone en attente → étape 3 directement (pas d'OCR)
                              2. zones en attente, ou image :
                                   cache prêt     → document lu (natif + OCR)
                                   pas de cache   → OCR lancé en arrière-plan → erreur TIMEOUT réessayable (D42)
                                   OCR en cours   → erreur TIMEOUT réessayable
                                   OCR en échec   → lecture native seule, zones en attente + avertissement
                              3. aucune ligne, ni native ni OCR ? → refus SOURCE_MANQUANTE (inchangé)
                              4. ask_gemini → vérification → réponse ds3.v2 (inchangé)
```

### 2.1 Où brancher l'OCR

**Entre `read_pdf` et le test « aucune ligne »**, donc avant Gemini :
- l'OCR n'est utilisé **que s'il reste des zones en attente** (ou pour une image). Un PDF entièrement natif ne paie
  aucun temps d'OCR et ne passe pas par le cache ;
- le test « aucune ligne » reste en place et voit les lignes OCR : un scan lisible part à Gemini, une page où l'OCR
  ne lit rien donne toujours `SOURCE_MANQUANTE` (« citation ou silence ») ;
- `ocr_pending_zones` ne modifie pas le document d'entrée, garde dans `pending_zones` les zones qu'il n'a pas pu lire
  (avec un avertissement) et ne lève pas d'exception si le moteur échoue sur une zone ;
- l'OCR ne tourne jamais dans le processus du service : il tourne dans un processus séparé, en arrière-plan
  (sections 7.1 et 7.2).

### 2.2 Import paresseux : ne pas casser le service sans Paddle

`ocr.py` importe `numpy` et `Pillow` au chargement. Ni l'un ni l'autre n'est dans `requirements.txt` : ils viennent
de `requirements-ocr.txt`. Un `from ...reading.ocr import ...` en tête de `pipeline.py` ferait échouer **tout** le
service DS3 chez quelqu'un qui n'a pas installé les dépendances OCR.

Donc : l'OCR est importé **dans la fonction**. Si l'import échoue, le comportement est celui d'aujourd'hui (zones non
lues, refus `SOURCE_MANQUANTE` si rien d'autre n'est lisible), avec un avertissement clair. PaddleOCR lui-même n'est
chargé que dans le processus séparé.

### 2.3 Accepter PNG et JPG (D41)

- `service.py` : `LIVE_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}`.
- `pipeline.py` : une image passe par le même chemin que les zones en attente (cache, arrière-plan, D42). Dans le
  processus séparé, `read_image` produit le même `IntermediateDocument` (une page `kind="image"`, une zone lue par
  l'OCR).
- **Unité des `bbox`** : pour une image, la page mesure `pixels × 72 / dpi` points (DPI lu dans le fichier, 300 par
  défaut). Les citations restent donc en « points », comme pour un PDF, mais sur une page virtuelle. À écrire dans le
  contrat (section 4.3).
- **Image illisible** (fichier tronqué, faux PNG) : détectée **avant** l'OCR, en ouvrant l'image (voir 4.1) →
  `FILE_EMPTY_OR_CORRUPTED`. **Une image valide ne devient jamais `FILE_EMPTY_OR_CORRUPTED` parce que l'OCR manque** :
  si l'OCR n'est pas disponible, c'est le refus D41 (y compris quand PaddleOCR est installé mais que
  `DS3_CACHE_DIR` n'est pas défini, voir 4.1).
- **D41 — image alors que l'OCR n'est pas disponible sur le serveur** : refus `HORS_SCOPE` (`UNSUPPORTED_FORMAT`),
  décidé dans `service.py` **avant** toute lecture, avec le message « La lecture des images n'est pas possible :
  l'OCR n'est pas installé ou pas activé sur ce serveur. Envoyez un PDF avec du texte. ». Le contrôle passe par
  **`pipeline.ocr_available()`**, sans charger Paddle :
  - **aujourd'hui (PR #44)** : un moteur fourni (tests), ou PaddleOCR installé **et** `DS3_OCR_INPROCESS=1` ;
  - **avec D42** : un `ocr_backend` fourni (tests), ou `default_backend()` différent de `None` (PaddleOCR installé
    **et** `DS3_CACHE_DIR` défini).
  `find_spec("paddleocr")` seul ne suffit plus : PaddleOCR peut être installé sans que l'OCR soit activé.
- `mime_type` n'est pas vérifié aujourd'hui (seule l'extension compte). Ce point ne change pas.

### 2.4 Rendre l'OCR remplaçable dans les tests

Comme `client` pour Gemini, `handle_request` et `analyze_payslip_pdf` reçoivent un paramètre facultatif
`ocr_backend` : l'objet qui donne l'état de la lecture OCR d'un document (`pret` avec le document, `en_cours`,
`echec`) et qui lance l'OCR en arrière-plan. `None` = le vrai (cache + processus séparé). Les tests passent un faux
backend : aucun modèle n'est chargé, aucun processus n'est lancé, les tests restent rapides et ne dépendent pas de
Paddle.

## 3. Refus du contrat ds3.v2 qui changent

Les **codes** ne changent pas (`ds3_code`, `refus.code` et leur correspondance restent ceux du contrat). Ce qui
change, c'est **quand** ils sont renvoyés :

| Cas | Aujourd'hui | Après intégration |
|---|---|---|
| PDF entièrement natif | lu, envoyé à Gemini | **inchangé** (pas d'OCR, pas de cache) |
| PDF avec zones en attente, **première question** | zones perdues | `erreur` `TIMEOUT`, `retryable = true`, « lecture en cours » ; l'OCR démarre en arrière-plan (D42) |
| Même document, nouvel essai, **OCR pas encore terminé** | zones perdues | de nouveau `erreur` `TIMEOUT`, `retryable = true` ; l'OCR n'est pas relancé ; aucun résultat partiel |
| Même document, nouvel essai, OCR terminé | zones perdues | zones lues (cache, servi seulement une fois la lecture achevée) ; lignes `source="ocr"` citables ; `ok` ou `complete = false` |
| Page scannée lisible | `refus` `SOURCE_MANQUANTE` (`UNREADABLE_DOCUMENT`) | 1re question : `TIMEOUT` réessayable ; ensuite : **`ok`** (ou `complete = false`) |
| Page scannée où l'OCR ne lit rien | `refus` `SOURCE_MANQUANTE` | `refus` `SOURCE_MANQUANTE` (inchangé ; avertissement « rien n'est deviné ») |
| OCR en échec (plantage, délai dépassé) | — | lecture native seule ; `SOURCE_MANQUANTE` si rien n'est lisible ; avertissement « OCR interrompu » |
| OCR non installé, PDF | — | comme aujourd'hui, avec un avertissement |
| Fichier `.png`, `.jpg`, `.jpeg` | `refus` `HORS_SCOPE` (`UNSUPPORTED_FORMAT`) | **lu par l'OCR** (même chemin : `TIMEOUT` puis cache) |
| Image alors que l'OCR n'est pas disponible (D41) | `refus` `HORS_SCOPE` | `refus` `HORS_SCOPE` (`UNSUPPORTED_FORMAT`), message « l'OCR n'est pas installé ou pas activé sur ce serveur » ; jamais `FILE_EMPTY_OR_CORRUPTED` |
| Image corrompue | — | `refus` `PARAM_INVALIDE` (`FILE_EMPTY_OR_CORRUPTED`) |
| Autres formats (`.docx`, `.tiff`, `.zip`…) | `refus` `HORS_SCOPE` | `refus` `HORS_SCOPE` (inchangé) |

**Confiance.** La confiance d'un champ est celle de sa ligne (D32 : 1,0 en natif, valeur de l'OCR sinon). DS3
n'applique aucun seuil (D39) ; DS1 exige 0,90. Côté DS1 :
- **sous 0,90** : le champ reste **visible avec sa citation** (page, `bbox`), mais il **n'est pas sélectionnable
  pour un calcul, même après confirmation** par l'utilisateur ;
- **à 0,90 ou plus** : le champ n'entre dans un calcul qu'après **confirmation explicite** de l'utilisateur, qui
  voit la citation pour comparer à l'original.

Ordre de grandeur sur 1 vrai PDF de 5 pages : 24 lignes OCR sur 174 sous 0,90.

**Ce que la vérification protège, et ce qu'elle ne protège pas.**
- `verify.py` vérifie que la valeur renvoyée figure **dans la ligne citée**. Pour une ligne OCR, la ligne citée est
  **ce que l'OCR a lu**, pas ce qui est imprimé sur le papier.
- **Un chiffre manquant** (l'OCR perd parfois des chiffres dans les lignes arabes) : la valeur complète n'est pas
  dans la ligne lue, elle n'est pas vérifiée, et le champ devient `null`. Le résultat est **moins complet**, mais
  pas faux.
- **Un chiffre mal lu n'est PAS détecté.** Exemple : le papier porte `424,100`, l'OCR lit `424,700`. Gemini recopie
  `424,700`, qui figure bien dans la ligne lue : la vérification **passe**, et la valeur renvoyée est fausse.
- **La seule protection contre ce cas est en aval**, côté DS1 : sous 0,90, le champ reste visible avec sa citation
  mais n'est jamais utilisable dans un calcul, même confirmé ; à 0,90 ou plus, l'utilisateur doit le **confirmer**
  sur l'écran de revue en voyant la citation (page, `bbox`) pour comparer à l'original. Une confiance au-dessus de
  0,90 ne garantit pas qu'un chiffre est juste : c'est la confirmation qui protège.
- C'est écrit dans le contrat (section 4.3) pour que DS1 et DS5 le sachent.

## 4. Diff proposé

> Ces diffs sont à appliquer par la propriétaire de chaque fichier, après relecture. Ils ne sont pas appliqués.
> `reading/` (Wiem) fournit le backend OCR (cache + processus séparé, sections 7.1 et 7.2) ; le pipeline et le
> service (Hadil) l'utilisent.

### 4.1 `src/document_intelligence/extraction/pipeline.py`

```diff
-"""Chaîne complète DS3 pour une fiche de paie en PDF : lecture -> Gemini -> vérification -> réponse ds3.v2.
+"""Chaîne complète DS3 pour une fiche de paie (PDF, PNG ou JPG) : lecture -> Gemini -> vérification -> ds3.v2.
 
-    1. lecture du PDF (texte natif) ............ reading/pdf_natif.py
+    1. lecture : texte natif du PDF ............ reading/pdf_natif.py
+       puis OCR des zones en attente / image .. reading/ocr.py (partie A), en arrière-plan, résultat en cache
     2. Gemini : où se trouve chaque valeur ...... extraction/gemini.py
     3. vérification contre le document .......... extraction/verify.py
     4. normalisation au format du contrat ....... extraction/normalize.py
     5. réponse ds3.v2 avec citations ............ extraction/assemble.py
 
 Ne lève jamais d'exception : un problème devient une réponse « refus » ou « erreur ».
-L'OCR (partie A) n'est pas encore branché : une page sans texte natif donne un refus SOURCE_MANQUANTE.
+OCR (D42) : première question → OCR lancé en arrière-plan, réponse TIMEOUT réessayable ; ensuite, lecture du cache.
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
+
+class _OcrPending(Exception):
+    """La lecture OCR du document est en cours (lancée par cette question ou une précédente)."""
+
+
+class _OcrFailed(Exception):
+    """L'OCR d'une image valide a échoué (plantage, délai dépassé) : rien n'a été lu."""
+
 
@@
+def _read_document(path: Path, req: DS3Request, ocr_backend: Any | None) -> IntermediateDocument:
+    """Texte natif du PDF ; s'il reste des zones en attente (ou pour une image) : lecture OCR depuis le cache.
+
+    L'OCR est importé ici et non en tête du module : sans requirements-ocr.txt, le service continue de
+    fonctionner comme avant. Lève _OcrPending si la lecture OCR n'est pas encore prête (D42).
+    """
+    is_image = path.suffix.lower() in IMAGE_EXTENSIONS
+    doc = None if is_image else read_pdf(path, document_id=req.document.document_id)
+    if doc is not None and not any(page.pending_zones for page in doc.pages):
+        return doc  # PDF entièrement natif : ni OCR ni cache
+    backend = ocr_backend
+    if backend is None:
+        try:
+            from src.document_intelligence.reading.ocr_cache import default_backend
+        except ImportError:  # dépendances de requirements-ocr.txt absentes
+            default_backend = None
+        backend = default_backend() if default_backend is not None else None
+    if backend is None:  # DS3_CACHE_DIR non défini, ou PaddleOCR non installé : pas d'OCR disponible
+        if doc is None:  # image : refus D41 (HORS_SCOPE), jamais FILE_EMPTY_OR_CORRUPTED
+            raise OcrUnavailable(OCR_UNAVAILABLE_WARNING)  # le service l'a normalement déjà refusée avant
+        doc.warnings.append(OCR_UNAVAILABLE_WARNING)  # PDF : lecture native seule, comme aujourd'hui
+        return doc
+    if is_image:  # image vraiment corrompue : erreur ici, AVANT l'OCR -> FILE_EMPTY_OR_CORRUPTED (try existant)
+        from PIL import Image
+        with Image.open(path) as image:
+            image.verify()
+    state = backend.lookup_or_start(path, card_id=req.context.card_id, document_id=req.document.document_id)
+    if state.status == "pret":
+        return state.document
+    if state.status == "en_cours":
+        raise _OcrPending()
+    if doc is None:  # image valide dont l'OCR a échoué : rien d'autre à lire -> SOURCE_MANQUANTE
+        raise _OcrFailed()
+    doc.warnings.append("OCR interrompu : les zones en attente ne sont pas lues (rien n'est deviné).")
+    return doc
+
+
 def analyze_payslip_pdf(pdf_path: Path, req: DS3Request, client: Any | None = None,
-                        model: str | None = None) -> dict[str, Any]:
-    """Analyse une fiche de paie en PDF et renvoie la réponse ds3.v2 (dict JSON)."""
+                        model: str | None = None, ocr_backend: Any | None = None) -> dict[str, Any]:
+    """Analyse une fiche de paie (PDF, PNG ou JPG) et renvoie la réponse ds3.v2 (dict JSON).
+
+    `ocr_backend` permet aux tests de remplacer le cache et le processus OCR (même rôle que `client` pour Gemini).
+    """
     started = time.perf_counter()
     try:
-        doc = read_pdf(pdf_path, document_id=req.document.document_id)
+        doc = _read_document(pdf_path, req, ocr_backend)
+    except OcrUnavailable:  # image sans OCR disponible (D41), déjà présent depuis la PR #44
+        return DS3Response(
+            **_envelope(req, started), status="refus", ds3_code="UNSUPPORTED_FORMAT",
+            refus=Refus(code="HORS_SCOPE", message_fr=OCR_IMAGE_FR, message_ar=OCR_IMAGE_AR),
+        ).to_json()
+    except _OcrFailed:  # image valide, OCR en échec : jamais FILE_EMPTY_OR_CORRUPTED (tableau section 3)
+        return DS3Response(
+            **_envelope(req, started), status="refus", ds3_code="UNREADABLE_DOCUMENT",
+            refus=Refus(code="SOURCE_MANQUANTE",
+                        message_fr="Aucun texte lisible dans ce document : rien n'est extrait.",
+                        message_ar="لا يوجد أي نص مقروء في هذه الوثيقة."),
+            warnings=["OCR interrompu : l'image n'a pas pu être lue (rien n'est deviné)."],
+        ).to_json()
+    except _OcrPending:
+        return DS3Response(
+            **_envelope(req, started), status="erreur", refus=None, ds3_code="TIMEOUT", retryable=True,
+            erreur=Erreur(type="TIMEOUT",
+                          message_fr="Lecture du document en cours : réessayez dans quelques instants.",
+                          message_ar="قراءة الوثيقة جارية: أعد المحاولة بعد لحظات."),
+        ).to_json()
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
- `ocr_backend: Any` évite d'importer le backend en tête du module (même raison que l'import paresseux). Si Hadil
  préfère un type exact : `if TYPE_CHECKING: from ...reading.ocr_cache import OcrBackend`.
- `reading/ocr_cache.py` est le **module de Wiem** (backend, cache, processus séparé), écrit sur la branche
  `DS3_ocr_cache`. Il expose `OcrCache.lookup_or_start(...)` (états `pret`, `en_cours`, `echec`) et
  `default_backend()`, qui renvoie **`None`** quand `DS3_CACHE_DIR` n'est pas défini ou que PaddleOCR n'est pas
  installé. Le pipeline teste donc `if backend is None:` :
  - **PDF** : lecture native seule, avec un avertissement, exactement comme aujourd'hui ;
  - **image** : `OcrUnavailable` → refus **`HORS_SCOPE`** (`UNSUPPORTED_FORMAT`) avec le message D41 « l'OCR n'est
    pas installé ou pas activé sur ce serveur ». C'est le cas **PaddleOCR installé mais `DS3_CACHE_DIR` absent** :
    une image valide ne doit **jamais** devenir `FILE_EMPTY_OR_CORRUPTED`. Test dédié : n° 5 bis (section 5).
  Le `except ImportError` reste seulement pour un poste sans les dépendances de `requirements-ocr.txt`.
- `OcrUnavailable`, `OCR_UNAVAILABLE_WARNING`, `OCR_IMAGE_FR` et `OCR_IMAGE_AR` **existent déjà** dans
  `pipeline.py` depuis la PR #44 (option B) ; D42 les réutilise tels quels.
- **Image valide dont l'OCR échoue** (état `echec` : plantage, délai dépassé) : `_OcrFailed` → `refus`
  **`SOURCE_MANQUANTE`** (`ds3_code` `UNREADABLE_DOCUMENT`), avertissement « OCR interrompu », Gemini pas appelé.
  C'est le code du tableau de la section 3, et le contrat fait déjà correspondre `UNREADABLE_DOCUMENT` à
  `SOURCE_MANQUANTE` : une image valide ne devient **jamais** `FILE_EMPTY_OR_CORRUPTED`. Test dédié : n° 4 bis.
- **Image vraiment corrompue** (fichier tronqué, faux PNG) : `Image.open(...).verify()` échoue **avant** le
  lancement de l'OCR ; l'erreur remonte au `try` existant et donne `FILE_EMPTY_OR_CORRUPTED`, comme dans le
  tableau de la section 3 et le contrat. Pillow est toujours là quand le backend existe (dépendance de PaddleOCR).
- Les autres erreurs (PDF corrompu) remontent au `try` existant et donnent `FILE_EMPTY_OR_CORRUPTED`, comme
  aujourd'hui.
- Le nom `analyze_payslip_pdf` est gardé pour ne rien casser chez les appelants ; seul le docstring dit qu'il
  accepte aussi les images.

### 4.2 `src/document_intelligence/service.py`

```diff
-LIVE_EXTENSIONS: Final = {".pdf"}
+IMAGE_EXTENSIONS: Final = {".png", ".jpg", ".jpeg"}
+LIVE_EXTENSIONS: Final = {".pdf", *IMAGE_EXTENSIONS}
@@
 def handle_request(request: dict[str, Any], *, storage_root_dir: Path | str | None = None,
-                   client: Any | None = None, model: str | None = None) -> dict[str, Any]:
+                   client: Any | None = None, model: str | None = None,
+                   ocr_backend: Any | None = None) -> dict[str, Any]:
     """Point d'entrée unique DS3 en live. Reçoit et renvoie du JSON (dict), jamais d'exception.
 
-    `client` et `model` permettent aux tests de remplacer Gemini (aucun appel réseau).
+    `client` et `model` permettent aux tests de remplacer Gemini (aucun appel réseau) ;
+    `ocr_backend` permet de remplacer le cache et le processus OCR (aucun modèle chargé).
     """
     started = time.perf_counter()
     try:
-        return _handle(request, storage_root_dir, client, model, started)
+        return _handle(request, storage_root_dir, client, model, ocr_backend, started)
@@
-def _handle(request: dict[str, Any], root_dir: Path | str | None, client: Any | None, model: str | None,
-            started: float) -> dict[str, Any]:
+def _handle(request: dict[str, Any], root_dir: Path | str | None, client: Any | None, model: str | None,
+            ocr_backend: Any | None, started: float) -> dict[str, Any]:
@@
-    if PurePosixPath(req.document.file_name).suffix.lower() not in LIVE_EXTENSIONS:
+    suffix = PurePosixPath(req.document.file_name).suffix.lower()
+    if suffix not in LIVE_EXTENSIONS:
         return _refus(env, "UNSUPPORTED_FORMAT",
-                      live_fr="Format pas encore pris en charge en live : seuls les PDF le sont pour l'instant.",
-                      live_ar="هذه الصيغة غير مدعومة بعد في الخدمة الفعلية: ملفات PDF فقط حاليا.")
+                      live_fr="Format pas encore pris en charge en live : seuls les PDF, PNG et JPG le sont.",
+                      live_ar="هذه الصيغة غير مدعومة بعد في الخدمة الفعلية: ملفات PDF وPNG وJPG فقط حاليا.")
+    if suffix in IMAGE_EXTENSIONS and not pipeline.ocr_available(ocr_backend):
+        # D41 : refus clair, décidé avant toute lecture du fichier (messages déjà dans pipeline.py, PR #44)
+        return _refus(env, "UNSUPPORTED_FORMAT", live_fr=OCR_IMAGE_FR, live_ar=OCR_IMAGE_AR)
@@
-    return analyze_payslip_pdf(path, req, client=client, model=model)
+    return analyze_payslip_pdf(path, req, client=client, model=model, ocr_backend=ocr_backend)
```

**Contrôle D41 : `pipeline.ocr_available()`**, plus seulement `find_spec("paddleocr")` (PaddleOCR peut être installé
sans que l'OCR soit activé). Il existe déjà depuis la PR #44 : `ocr_engine is not None or (paddle_installed() and
DS3_OCR_INPROCESS=1)`. Avec D42, il devient : `ocr_backend is not None or default_backend() is not None`
(PaddleOCR installé **et** `DS3_CACHE_DIR` défini). Le service et le pipeline appellent la **même** fonction, donc ils
ne peuvent pas être en désaccord : une image acceptée par le service a toujours un OCR pour la lire.

**Les messages arabes** (format, `TIMEOUT` « lecture en cours » en 4.1) sont relus par Hadil avant application ; le
message arabe D41 (`OCR_IMAGE_AR`) l'a déjà été dans la PR #44.

### 4.3 `docs/CONTRACT_DOCUMENT_INTELLIGENCE_V2.md` (section « Service réel »)

```diff
-**Disponible en live aujourd'hui :** `analyze_document` sur une **fiche de paie en PDF** (texte natif).
+**Disponible en live aujourd'hui :** `analyze_document` sur une **fiche de paie en PDF, PNG ou JPG**. Le texte natif
+du PDF est lu d'abord ; les zones image, les pages scannées et les images sont lues par l'OCR (PaddleOCR PP-OCRv5,
+arabe et français). Une ligne lue par l'OCR porte sa confiance réelle ; pour une image, les `bbox` sont en points
+d'une page virtuelle de `pixels × 72 / dpi` points (300 DPI par défaut).
+
+**Lecture OCR en arrière-plan (D42).** À la première question sur un document qui demande l'OCR, la réponse est
+`erreur` `TIMEOUT` avec `retryable = true` (« lecture en cours ») : l'OCR tourne en arrière-plan (environ 30 s par
+page sur CPU). DS1 repose la question plus tard. **Tant que la lecture n'est pas terminée, chaque nouvel essai
+reçoit la même réponse `TIMEOUT` réessayable** (l'OCR n'est pas relancé). Le résultat gardé en cache n'est servi
+**qu'une fois la lecture achevée** : jamais de résultat partiel.
+
+**Limite de la vérification sur les lignes OCR.** DS3 vérifie que la valeur figure dans la ligne citée, c'est-à-dire
+dans ce que l'OCR a lu. Un chiffre **mal lu** par l'OCR (par exemple `424,700` au lieu de `424,100` imprimé) passe
+donc cette vérification. La protection est côté DS1 :
+- **confiance sous 0,90** : le champ reste visible avec sa citation, mais il **n'est pas sélectionnable pour un
+  calcul, même après confirmation** ;
+- **confiance de 0,90 ou plus** : l'utilisateur **confirme** le champ en voyant la citation (page, `bbox`) pour
+  comparer à l'original.
 Le reste donne un refus clair, en français et en arabe :
@@
-| fichier autre que PDF | `refus` `HORS_SCOPE` (`UNSUPPORTED_FORMAT`) |
+| fichier autre que PDF, PNG, JPG | `refus` `HORS_SCOPE` (`UNSUPPORTED_FORMAT`) |
+| image alors que l'OCR n'est pas disponible sur le serveur | `refus` `HORS_SCOPE` (`UNSUPPORTED_FORMAT`), « l'OCR n'est pas installé ou pas activé sur ce serveur » (D41) |
 | `expected_type` autre que `fiche_de_paie` | `refus` `HORS_SCOPE` (`UNSUPPORTED_FORMAT`) |
-| page scannée sans texte | `refus` `SOURCE_MANQUANTE` (en attente de l'OCR de la partie A) |
+| lecture OCR en cours (première question et chaque nouvel essai tant qu'elle n'est pas terminée) | `erreur` `TIMEOUT`, `retryable = true` (D42) |
+| document où ni la couche texte ni l'OCR ne lisent rien | `refus` `SOURCE_MANQUANTE` |
```

Aucun nouveau code ni nouvelle opération : `TIMEOUT` existe déjà dans la correspondance des codes du contrat.

### 4.4 `docs/DECISIONS.md`

Deux décisions dans les numéros réservés à DS3 par D40 :
- **D41** (**déjà écrite** dans `DECISIONS.md` par la PR #44) : refus `HORS_SCOPE` « l'OCR n'est pas installé ou pas
  activé sur ce serveur » pour une image quand `ocr_available()` est faux. Avec D42, seule la définition de
  `ocr_available()` change (4.2) ;
- **D42** (à écrire avec la PR #46) : OCR lancé en arrière-plan à la première question ; réponse `TIMEOUT`
  réessayable à chaque essai tant que la lecture n'est pas terminée ; cache servi seulement une fois la lecture
  achevée ; remplace l'option B (`DS3_OCR_INPROCESS`) ; pas de changement de contrat ; `prepare_document` plus tard,
  après accord d'Achref.

D40 garde son historique ; la ligne « page scannée : SOURCE_MANQUANTE en attendant l'OCR » est marquée « remplacé par
D41 et D42 ».

### 4.5 Mock et exemples

Le mock v2 ne change pas : il simule déjà un document lisible ou non par son nom de fichier, et `TIMEOUT`
(nom contenant `timeout`). Les exemples générés (`generate_examples.py`) n'ont pas besoin d'être régénérés.

## 5. Tests à ajouter ou à adapter

Tous avec un **faux backend OCR** (états `pret` / `en_cours` / `echec`, documents fictifs) et le faux client Gemini
existant : aucun modèle, aucun processus, aucun réseau.

**À adapter (deviennent faux après l'intégration) :**

| Test | Fichier | Pourquoi | Adaptation proposée |
|---|---|---|---|
| `test_scanned_page_is_not_sent_to_gemini` | `test_document_intelligence_gemini.py` | DS3-03 ne donne plus directement `SOURCE_MANQUANTE` | passer un faux backend `pret` avec un document **sans** ligne lue : le refus et « aucun appel Gemini » restent vrais ; l'avertissement contient toujours « OCR » |
| `NEEDS_OCR = {"DS3-03"}` | `test_document_intelligence_golden.py` | le cas scanné peut maintenant être évalué | garder l'exclusion du test 100 % natif, et ajouter le test 1 ci-dessous |

**À ajouter :**

1. **Pipeline, scan lisible** : DS3-03 + faux backend `pret` avec les lignes OCR de la fiche → `status = "ok"`, les
   citations pointent vers des lignes `source="ocr"`, la confiance des champs est celle des lignes OCR.
2. **Pipeline, PDF natif** : DS3-01 + faux backend → le backend n'est jamais appelé (ni OCR ni cache).
3. **Pipeline, première question et nouveaux essais (D42)** : faux backend `en_cours` → `status = "erreur"`,
   `ds3_code = "TIMEOUT"`, `retryable = true`, message « lecture en cours », Gemini pas appelé. Deux essais de suite
   avec un backend encore `en_cours` → deux fois `TIMEOUT` ; le backend passe ensuite à `pret` → réponse `ok` tirée du
   cache.
4. **Pipeline, OCR en échec** : faux backend `echec` → lecture native seule, avertissement « OCR interrompu »,
   `SOURCE_MANQUANTE` si rien d'autre n'est lisible, aucune exception.
4 bis. **Pipeline, image valide dont l'OCR échoue** : PNG valide + faux backend `echec` → `refus`
   `SOURCE_MANQUANTE` (`ds3_code = "UNREADABLE_DOCUMENT"`), avertissement « OCR interrompu », Gemini pas appelé,
   **jamais** `FILE_EMPTY_OR_CORRUPTED`. En contrôle : un faux PNG (octets au hasard) + faux backend → toujours
   `FILE_EMPTY_OR_CORRUPTED`, et le backend n'est **pas** appelé.
5. **OCR non disponible** : `ocr_available()` faux (monkeypatch de `default_backend` qui renvoie `None`, aucun
   `ocr_backend` passé) → PDF : même réponse qu'aujourd'hui ; image : `refus` `HORS_SCOPE` (`UNSUPPORTED_FORMAT`)
   avec « l'OCR n'est pas installé ou pas activé sur ce serveur », sans lire le fichier (D41).
5 bis. **PaddleOCR installé mais `DS3_CACHE_DIR` absent** (test dédié, demandé par Achraf) : `paddle_installed()`
   forcé à vrai, `DS3_CACHE_DIR` retiré de l'environnement (`monkeypatch.delenv`), image PNG **valide** →
   - au service : `refus` `HORS_SCOPE` (`UNSUPPORTED_FORMAT`), message D41 ;
   - au pipeline appelé directement (sans passer par le service) : même refus, via `OcrUnavailable` ;
   - dans les deux cas, **jamais** `FILE_EMPTY_OR_CORRUPTED` et aucun processus OCR lancé.
6. **Service, image** : `paie.png` dans le stockage (`local://`), faux backend `pret`, faux Gemini →
   `status = "ok"`, `mode = "live"`, `DS3Response.model_validate` passe.
7. **Service, formats** : `.tiff` → `UNSUPPORTED_FORMAT` ; `.png` corrompu → `FILE_EMPTY_OR_CORRUPTED`.
8. **Service, paramètre** : `handle_request(..., ocr_backend=fake)` transmet bien le backend au pipeline.
9. **Backend, processus séparé (Wiem, 7.2)** : un faux programme OCR qui sort avec un code d'erreur (comme un
   plantage natif) ou dépasse le délai → état `echec`, le processus appelant continue, aucune exception.
10. **Backend, cache (Wiem, 7.1)** : deuxième appel pour le même fichier → `pret` sans relancer l'OCR ; fichier
    modifié (autre SHA-256) → nouvelle lecture ; `card_id` ou `document_id` avec `..` ou `/` → refusé ; chemin
    résolu hors de `DS3_CACHE_DIR` → refusé.
11. **Backend, JSON temporaire supprimé (Wiem, 7.2, remarque 4)** : le fichier `.part` écrit par le processus séparé
    n'existe plus après lecture, **dans les trois cas** : succès (le cache final existe, le `.part` non), plantage du
    processus (code ≠ 0) et JSON invalide (`model_validate_json` échoue). Vérifier aussi qu'aucun texte du document
    n'apparaît dans les journaux.
12. **Intégration réelle (facultatif, `skipif` sans paddleocr)** : un PDF scanné fictif lu par le vrai PaddleOCR de
    bout en bout (`TIMEOUT` puis `ok`), avec un faux Gemini.

Tous les tests existants doivent continuer à passer, sur un poste **avec** et **sans** `requirements-ocr.txt`.

## 6. Risques et limites connues

| Risque | Détail | Mesure |
|---|---|---|
| **Temps de réponse** | La spécification vise **20 s (P95)**. L'OCR prend environ 27 s par page sur CPU (mesuré sur 1 vrai PDF de 5 pages), plus environ 8,5 s de chargement des modèles. | **D42** : OCR en arrière-plan, `TIMEOUT` réessayable, cache (section 7.1). Plus tard : `prepare_document` au téléversement. |
| **Plantage natif de Paddle** | Paddle peut mourir sans exception Python (access violation). Un `try/except` ne l'attrape pas : dans le processus du service, **tout le service tomberait**. | OCR **toujours dans un processus séparé** (section 7.2). |
| **Chiffre mal lu** | Un chiffre mal lu par l'OCR passe la vérification « la valeur est dans la ligne citée » (section 3). | Confiance (0,90, DS1) et confirmation par l'utilisateur ; écrit dans le contrat (4.3). |
| **Lignes natives relues en double** (limite connue) | Le lecteur natif envoie une page **entière** à l'OCR quand au moins la moitié de ses lignes sont cassées (D35). Les lignes natives **lisibles** de cette page sont alors relues par l'OCR : la même information apparaît deux fois (une ligne `natif`, confiance 1,0, et une ligne `ocr`), avec deux `line_id`. Gemini peut citer l'une ou l'autre. | Accepté pour l'instant (aucune valeur inventée ; au pire une citation OCR à la place de la native). Amélioration possible plus tard : ignorer une ligne OCR qui recouvre une ligne native lisible. |
| **Conflit torch / paddle** | Sous Windows, importer `torch` **après** `paddle` dans le même processus fait échouer `shm.dll`. Aucun module de `src/` n'importe `torch` aujourd'hui. | Disparaît avec le processus séparé : Paddle n'est jamais chargé dans le processus du service. |
| **Dépendances lourdes** | `paddlepaddle`, `paddleocr`, `paddlex` (plusieurs centaines de Mo) + modèles téléchargés au premier appel (cache `~/.paddlex`). | `requirements-ocr.txt` reste séparé ; import paresseux ; pré-télécharger les modèles sur la machine de démo. |
| **Mémoire / processeur** | Une page A4 à 300 DPI = environ 8,7 millions de pixels ; l'OCR occupe le CPU pendant ~30 s. | Un seul OCR en arrière-plan à la fois au début (file d'attente simple). |
| **Qualité réelle inconnue** | Pas de CER mesuré sur des vraies lignes (pas de texte de référence). | Jeu réel annoté (scripts `annoter_lignes.py` et `evaluer_cer_reel.py`, à venir). |
| **`bbox` des images** | Points d'une page virtuelle, pas d'un PDF. | Écrit dans le contrat (4.3) ; l'écran de revue DS1 doit afficher l'image à la même échelle. |

## 7. Tenir les 20 s et survivre à un plantage de Paddle

### 7.1 D42 : OCR en arrière-plan à la première question, puis cache

**Problème.** La spécification vise **20 s (P95)**. L'OCR prend environ **27 s par page** : une seule page scannée
dépasse déjà la cible si l'OCR est fait pendant la question.

**Décision (D42, sans changement de contrat).**

```
1re question ──────► pas de cache ─► lance l'OCR en arrière-plan (processus séparé, 7.2) ─► erreur TIMEOUT réessayable
nouvel essai ──────► OCR pas terminé ─► (rien n'est relancé) ─────────────────────────────► erreur TIMEOUT réessayable
   … (autant d'essais que nécessaire, même réponse tant que la lecture n'est pas terminée)
nouvel essai ──────► lecture achevée, cache prêt ─► document lu (natif + OCR) ─► Gemini ─► vérification ─► ds3.v2
```

- **Réponse pendant la lecture** : `status = "erreur"`, `ds3_code = "TIMEOUT"`, `retryable = true`, message
  « Lecture du document en cours : réessayez dans quelques instants. ». Le code existe déjà dans le contrat, et DS1
  sait déjà proposer de réessayer.
- **Chaque nouvel essai répond `TIMEOUT` (`retryable = true`) tant que l'OCR n'est pas terminé.** L'OCR n'est pas
  relancé (verrou ci-dessous), et DS1 peut réessayer autant de fois que nécessaire.
- **Le résultat en cache n'est servi qu'une fois la lecture achevée.** Le JSON est écrit dans un fichier temporaire
  puis renommé d'un seul coup à la fin : tant qu'il n'existe pas en entier, l'état reste `en_cours`. Aucun résultat
  partiel (quelques pages seulement) n'est jamais renvoyé.
- **Une seule lecture par document** : un fichier verrou (`<sha256[:24]>_<code version>.lock`, PR #46, créé de façon atomique, avec
  l'heure de départ) empêche de lancer deux
  fois l'OCR du même fichier. Un verrou plus vieux que le délai maximal (par exemple 10 min, réglable) est considéré
  comme un échec (processus mort sans nettoyer).
- **Échec** (plantage, délai dépassé) : un marqueur `echec` (sans aucun texte) est écrit. Les questions suivantes
  répondent avec la lecture native seule (zones en attente, avertissement « OCR interrompu »), sans relancer l'OCR en
  boucle. Un nouvel essai a lieu seulement si le fichier change (autre empreinte).
- **Plus tard** : le déclenchement **au téléversement** (`prepare_document`, nouvelle opération) supprimera le premier
  `TIMEOUT`. C'est un changement de contrat : il attend l'accord d'Achref (DS1).

**Cache (remarque 2).**
- **Dossier propre à DS3**, donné par la variable d'environnement **`DS3_CACHE_DIR`**, distinct du dossier de
  stockage des documents. Sans `DS3_CACHE_DIR`, pas de cache : `default_backend()` renvoie `None`, l'OCR n'est
  pas lancé, même si PaddleOCR est installé. Un PDF garde la lecture native, avec un avertissement ; une image
  reçoit le refus D41 (`HORS_SCOPE`), jamais `FILE_EMPTY_OR_CORRUPTED` (4.1, test 5 bis).
- **Rangement par carte et par document** :
  `<DS3_CACHE_DIR>/cards/<card_id>/documents/<document_id>/<sha256[:24]>_<code version>.json` (PR #46,
  `reading/ocr_cache.py`, fonction `cache_key`) : les 24 premiers caractères du SHA-256 du fichier, puis un code de
  **8 caractères** tiré du SHA-256 de la version du lecteur (`CACHE_VERSION`, par ex.
  `pdf_natif-0.3+ocr_paddle-0.1`). Ce nom court évite de dépasser la limite de longueur des chemins sous Windows.
  Un fichier modifié ou un nouveau lecteur donne un autre nom : jamais de résultat périmé.
- **Mêmes contrôles d'accès que le stockage** (`resolve_storage_ref`, D40) : le cache n'est lu ou écrit que pour la
  carte active (`req.context.card_id`, déjà vérifiée égale à la carte du document) ; `card_id` et `document_id`
  doivent être de simples noms (pas de `/`, `\`, `..`) ; le chemin résolu doit rester dans `DS3_CACHE_DIR`. Une
  requête d'une autre carte ne peut donc jamais lire le cache d'un document qui n'est pas le sien.
- **Confidentialité** : le cache contient le texte du document. Il ne sort jamais de `DS3_CACHE_DIR`, n'est jamais
  journalisé, et doit être supprimé avec le document (à prévoir avec le backend, comme le stockage, D40).
- **Écriture atomique** : le résultat est écrit dans un fichier `.part`, vérifié, puis renommé ; un lecteur ne voit
  jamais un cache à moitié écrit.

### 7.2 Exécuter l'OCR dans un processus séparé

**Problème.** Un plantage natif de Paddle (access violation) tue le processus qui l'a appelé, sans exception
Python. Si l'OCR tourne dans le processus du service, **tout le service DS3 tombe**, y compris pour les autres
utilisateurs.

**Proposition.** Le service ne charge jamais Paddle. Le backend lance l'OCR dans un **processus séparé** (en
arrière-plan pour D42), avec un délai maximal, et lit un JSON :

```python
# esquisse, dans reading/ocr_cache.py (Wiem) ; exécutée par le travail d'arrière-plan
def run_ocr_process(path: Path, document_id: str, final: Path, timeout_s: float) -> bool:
    part = final.with_suffix(".part")          # dans DS3_CACHE_DIR, jamais dans un dossier temporaire partagé
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "src.document_intelligence.reading.ocr", str(path), "--json", str(part)],
            capture_output=True, timeout=timeout_s, check=False,
        )   # stdout contient le texte du document : jamais journalisé, jeté
        if proc.returncode != 0 or not part.exists():
            return False                       # plantage natif ou erreur : rien n'est deviné
        doc = IntermediateDocument.model_validate_json(part.read_text(encoding="utf-8"))
        doc.document_id = document_id
        write_atomically(final, doc.model_dump_json())
        return True
    except (subprocess.TimeoutExpired, ValueError, OSError):
        return False
    finally:
        part.unlink(missing_ok=True)           # remarque 4 : le JSON temporaire contient le texte, toujours supprimé
```

- La commande `python -m src.document_intelligence.reading.ocr fichier --json sortie.json` **existe déjà** (CLI de
  `ocr.py`) : elle fait la lecture native puis l'OCR et écrit le `IntermediateDocument` complet.
- **Remarque 4 — JSON temporaire** : le fichier `.part` contient le texte du document. Il est **supprimé juste après
  lecture, même en cas d'erreur** (bloc `finally`), et il est écrit dans `DS3_CACHE_DIR` (mêmes droits que le cache),
  jamais dans le dossier temporaire du système. Testé par le test 11 (section 5).
- **Si le processus plante** (code de sortie ≠ 0, comme `3221225477` sous Windows) ou dépasse le délai : état
  `echec` (7.1). **Le service, lui, continue.**
- `document_id` : remis sur le document lu (la CLI utilise le nom du fichier), ou passé en option de la CLI (petite
  modification de `ocr.py`, côté Wiem).
- **Coût** : chaque processus recharge les modèles (environ 8,5 s mesurés), acceptable en arrière-plan. Version
  suivante si besoin : un **processus OCR permanent** qui garde les modèles en mémoire ; s'il plante, il est relancé
  (même idée que le superviseur de l'expérience).
- **Bonus** : le conflit de DLL torch / paddle disparaît.

## 8. Ordre convenu

1. ✅ **Fusion de la PR #40** (`DS3_ocr`) : l'OCR et ses tests arrivent sur `main`, sans rien brancher.
2. ✅ **PR #44 (Hadil, fusionnée)** : pipeline et service branchés avec l'**option B** : l'OCR tourne dans le
   processus du service **seulement si `DS3_OCR_INPROCESS=1`** (démonstrations). Elle apporte `ocr_available()`,
   `OcrUnavailable`, le refus D41 avec le message « l'OCR n'est pas installé ou pas activé sur ce serveur », et D41
   dans `DECISIONS.md`.
3. **PR #46 (Wiem, `DS3_ocr_cache`)** : le backend `reading/ocr_cache.py` (cache `DS3_CACHE_DIR`, verrou, processus
   séparé, suppression du JSON temporaire, tests 9 à 11), à relire par Hadil et à fusionner **avant** l'étape 4.
4. **Hadil applique D42** dans ses fichiers (`pipeline.py`, `service.py`) : le backend de la #46 **remplace**
   l'option B (`ocr_backend` à la place de `ocr_engine` et de `DS3_OCR_INPROCESS`), diffs 4.1 et 4.2, avec les
   tests 1 à 8 et 5 bis de la section 5, et elle **relit les messages arabes** nouveaux.
5. Mise à jour du contrat (4.3) et de `DECISIONS.md` (D42, 4.4).
6. Prévenir DS1 (Achref) : nouveaux formats ; `TIMEOUT` réessayable à chaque essai tant que la lecture n'est pas
   terminée ; champs OCR sous 0,90 visibles mais pas sélectionnables pour un calcul, même confirmés ; champs à 0,90
   ou plus à confirmer en voyant la citation ; limite de la vérification sur les chiffres mal lus. Proposer ensuite
   `prepare_document`.
