"""Mesure le vrai CER de l'OCR sur des lignes réelles annotées à la main, SANS afficher leur contenu.

À lancer par la personne qui détient les données, après `scripts/annoter_lignes.py` et l'annotation manuelle :

    .venv\\Scripts\\python scripts/evaluer_cer_reel.py "<dossier hors dépôt>\\annotation.csv"

Lit `annotation.csv` (colonne `texte_correct` remplie à la main en regardant seulement l'image ; vide = ligne
sautée ; `#ILLISIBLE` = ligne illisible, comptée à part) et compare, sur les mêmes lignes :
- `ocr_production` : la lecture faite pendant la préparation par l'OCR du projet (détection + reconnaissance,
  langue « auto »), lue dans `lectures_ocr.json`, à côté du CSV, par id de ligne. Ce fichier est ouvert en UTF-8
  par le script, sans passer par Excel. Un ancien CSV qui contient encore la colonne `lecture_ocr` reste accepté,
  avec un avertissement : l'annotatrice a pu voir la lecture de l'OCR, et le CER risque d'être trop optimiste ;
- `pre_entraine` : le modèle de reconnaissance pré-entraîné (`arabic_PP-OCRv5_mobile_rec`), sur l'image de la ligne ;
- `fine_tune` : le même modèle après le Fine-Tuning de l'expérience (variante `bn_frozen`), sur l'image de la ligne.
`pre_entraine` et `fine_tune` sont mesurés exactement de la même façon (reconnaissance seule) : leur écart est
l'effet du Fine-Tuning sur des données réelles. Les deux modèles ne sont chargés que si l'expérience est prête
(code PaddleOCR et poids dans `experiments/ocr_transfer_finetune/build/`) ; sinon seule `ocr_production` est mesurée.

Comparaison équitable (si PaddleOCR est installé) : `ocr_production` lit des MORCEAUX (boîtes du détecteur) alors que
`pre_entraine` et `fine_tune` lisent la ligne ENTIÈRE ; ces témoins séparent l'effet de l'entrée de celui du modèle :
- `production_rec_seule` : le modèle d'inférence PaddleX `arabic_PP-OCRv5_mobile_rec`, en reconnaissance seule, sur
  les mêmes images de ligne entière que `pre_entraine` et `fine_tune` ;
- `production_relue` : le pipeline de production (`ocr.py` : détection + reconnaissance, langue « auto ») relancé sur
  l'image de la ligne. Ses boîtes sont les morceaux lus par les deux lignes suivantes ; proche de `ocr_production`,
  il montre que ces morceaux représentent bien ceux de la production (les boîtes d'origine ne sont pas gardées) ;
- `pre_entraine_morceaux`, `fine_tune_morceaux` : les modèles de l'expérience lisent chacun de ces morceaux, puis les
  morceaux sont assemblés comme en production (`clean_boxes`, puis `group_rows`, droite à gauche pour l'arabe).
À l'évaluation, la largeur des images n'est plus plafonnée à 640 px (valeur de l'entraînement) mais à 3200 px, comme
PaddleX : une longue ligne n'est plus comprimée. Le CER est aussi donné par tranche de longueur de la référence :
`<=44c` (44 caractères au plus, longueur maximale des lignes d'entraînement) et `>44c`.

N'affiche QUE des chiffres agrégés : CER, WER, part de lignes exactes, globalement, par langue et par tranche. Écrit
aussi `resultats_cer_reel.json` à côté du CSV (chiffres seulement). Aucun texte, aucun nom de fichier n'est affiché.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import importlib.util
import json
import math
import os
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

REPO_ROOT: Final = Path(__file__).resolve().parents[1]
EXP_DIR: Final = REPO_ROOT / "experiments" / "ocr_transfer_finetune"
for _p in (REPO_ROOT, EXP_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import metrics  # experiments/ocr_transfer_finetune/metrics.py : les mêmes CER / WER que l'expérience

from src.document_intelligence.intermediate import detect_language

BUILD: Final = EXP_DIR / "build"
PPOCR_ROOT: Final = BUILD / "PaddleOCR"
PRETRAINED: Final = BUILD / "weights" / "arabic_PP-OCRv5_mobile_rec_pretrained.pdparams"
FT_FILE: Final = "finetune_bn_frozen_best.pdparams"
ILLEGIBLE: Final = "#ILLISIBLE"
LECTURES_NAME: Final = "lectures_ocr.json"
LECTURES_FORMAT: Final = "ds3.lectures_ocr.v1"
"""Lectures de l'OCR écrites par `annoter_lignes.py`, à part du CSV pour annoter sans les voir."""
LEGACY_COLUMN: Final = "lecture_ocr"
"""Colonne des anciens CSV (avant la séparation) : encore acceptée, avec un avertissement."""
RESULTS_NAME: Final = "resultats_cer_reel.json"
LANGS: Final = ("fr", "ar", "mixte", "inconnu")
"""Langue de la référence ; « inconnu » = ligne sans lettres (montants, dates seuls). Les portées par langue
couvrent donc toutes les lignes : leurs totaux s'additionnent pour donner le global."""
RESULTS_FORMAT: Final = "ds3.cer_reel.v2"
"""Format du fichier de résultats (v2 : avec les totaux nécessaires pour combiner plusieurs annotatrices)."""
EVAL_MAX_W: Final = 3200
"""Largeur maximale d'une image à l'évaluation (comme `max_imgW` de PaddleX) ; l'entraînement plafonnait à 640 px."""
TRANCHE_CHARS: Final = 44
"""Limite des tranches de longueur : `vocab.MAX_LEN` de l'expérience (lignes d'entraînement de 44 caractères au plus)."""
TRANCHES: Final = ("<=44c", ">44c")
PIECES_SUFFIX: Final = "_morceaux"

Recognizer = Callable[[list[Path]], list[str]]
"""Lit une liste d'images de lignes et renvoie un texte par image (remplaçable dans les tests)."""
PieceRecognizer = Callable[[list[Any]], list[str]]
"""Lit une liste de morceaux d'image (tableaux numpy en niveaux de gris, H x W) et renvoie un texte par morceau."""
Detector = Callable[[list[Path]], list[list[Any]]]
"""Pipeline de production sur chaque image de ligne : la liste de ses boîtes (`ocr.OcrBox`, pixels de l'image)."""


@dataclass(frozen=True)
class Row:
    image: Path
    lecture_ocr: str
    reference: str


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def read_lectures(path: Path) -> dict[str, str]:
    """Lectures de l'OCR par id de ligne, depuis `lectures_ocr.json`.

    Ouvert directement en UTF-8 (`utf-8-sig` accepte aussi un BOM éventuel), jamais via Excel. Les messages
    d'erreur ne citent aucun texte.
    """
    if not path.is_file():
        raise ValueError(f"{LECTURES_NAME} introuvable à côté du CSV (il est écrit par annoter_lignes.py).")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):  # UnicodeDecodeError et JSONDecodeError sont des ValueError
        raise ValueError(f"{LECTURES_NAME} illisible (JSON en UTF-8 attendu).") from None
    lectures = data.get("lectures") if isinstance(data, dict) and data.get("format") == LECTURES_FORMAT else None
    if not isinstance(lectures, dict) or not all(isinstance(k, str) and isinstance(v, str)
                                                 for k, v in lectures.items()):
        raise ValueError(f"{LECTURES_NAME} : format non reconnu (attendu : {LECTURES_FORMAT}).")
    by_id = {normalize_id(k): v for k, v in lectures.items()}
    if len(by_id) != len(lectures):
        raise ValueError(f"{LECTURES_NAME} : {len(lectures) - len(by_id)} id en double.")
    return by_id


def normalize_id(value: str | None) -> str:
    """Id de ligne comparable entre le CSV et `lectures_ocr.json`, sans dépendre des zéros de tête.

    Excel enregistre « 0001 » comme le nombre 1 : un id fait seulement de chiffres est donc comparé comme un
    nombre (« 0001 », « 001 » et « 1 » donnent « 1 »). Un autre id est seulement débarrassé de ses espaces.
    """
    text = (value or "").strip()
    return str(int(text)) if text.isascii() and text.isdigit() else text


def read_annotations(csv_path: Path) -> tuple[list[Row], dict[str, int]]:
    """Lignes annotées (texte_correct rempli) et décompte des lignes sautées ou illisibles.

    La lecture de l'OCR vient de `lectures_ocr.json` (par id de ligne). Un ancien CSV avec la colonne
    `lecture_ocr` est encore lu, avec un avertissement (annotation peut-être influencée par cette lecture).
    """
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        columns = set(reader.fieldnames or [])
        legacy = LEGACY_COLUMN in columns
        missing = {"image", "texte_correct"} - columns if legacy else {"id", "image", "texte_correct"} - columns
        if missing:
            raise ValueError(f"colonnes manquantes dans le CSV : {sorted(missing)}")
        raw = list(reader)
    if legacy:
        print(f"Avertissement : ancien CSV avec la colonne {LEGACY_COLUMN} (lecture de l'OCR visible pendant "
              "l'annotation) : le CER risque d'être trop optimiste. Pour les prochaines annotations, préparez les "
              f"lignes avec la nouvelle version d'annoter_lignes.py (lecture dans {LECTURES_NAME}).")
        lectures: dict[str, str] = {}
    else:
        lectures = read_lectures(csv_path.parent / LECTURES_NAME)
    if "id" in columns:
        seen = Counter(normalize_id(record.get("id")) for record in raw)
        duplicated = sum(1 for line_id, count in seen.items() if line_id and count > 1)
        if duplicated:
            raise ValueError(f"{duplicated} id en double dans le CSV : chaque ligne doit garder son id d'origine.")
    rows: list[Row] = []
    illegible = skipped = without_reading = without_image = 0
    for record in raw:
        reference = (record.get("texte_correct") or "").strip()
        image = (record.get("image") or "").strip()
        if not reference:
            skipped += 1
        elif reference.upper() == ILLEGIBLE:
            illegible += 1
        elif not image:
            without_image += 1
        elif legacy:
            rows.append(Row(csv_path.parent / image, record.get(LEGACY_COLUMN) or "", reference))
        elif (line_id := normalize_id(record.get("id"))) in lectures:
            rows.append(Row(csv_path.parent / image, lectures[line_id], reference))
        else:
            without_reading += 1
    if without_image:
        raise ValueError(f"{without_image} ligne(s) annotée(s) sans image (colonne image vide) : remettez le nom "
                         "de l'image de chaque ligne, sans rien deviner.")
    if without_reading:  # jamais deviner : une ligne sans lecture fausserait la comparaison
        raise ValueError(f"{without_reading} ligne(s) annotée(s) sans lecture dans {LECTURES_NAME} "
                         "(CSV et fichier de lectures de deux préparations différentes ?).")
    return rows, {"lignes_dans_le_csv": len(raw), "lignes_annotees": len(rows), "lignes_illisibles": illegible,
                  "lignes_non_annotees": skipped}


def scores(refs: Sequence[str], hyps: Sequence[str]) -> dict[str, float | int]:
    """Taux (CER, WER, part de lignes exactes) et totaux qui permettent de combiner plusieurs fichiers.

    Les totaux sont des nombres seulement (aucun texte) : caractères et mots de référence, erreurs (distance
    d'édition) en caractères et en mots, lignes exactes. CER = erreurs_caracteres / caracteres_reference, etc.
    """
    norm_refs = [metrics.normalize(r) for r in refs]
    norm_hyps = [metrics.normalize(h) for h in hyps]
    chars = sum(len(r) for r in norm_refs)
    words = sum(len(r.split()) for r in norm_refs)
    char_errors = sum(metrics.levenshtein(r, h) for r, h in zip(norm_refs, norm_hyps, strict=True))
    word_errors = sum(metrics.levenshtein(r.split(), h.split()) for r, h in zip(norm_refs, norm_hyps, strict=True))
    exact = sum(r == h for r, h in zip(norm_refs, norm_hyps, strict=True))
    return {
        "n": len(refs),
        "cer": round(char_errors / chars, 4) if chars else 0.0,
        "wer": round(word_errors / words, 4) if words else 0.0,
        "lignes_exactes": round(exact / len(refs), 4) if refs else 0.0,
        "caracteres_reference": chars,
        "erreurs_caracteres": char_errors,
        "mots_reference": words,
        "erreurs_mots": word_errors,
        "nb_lignes_exactes": exact,
    }


def tranche(reference: str) -> str:
    """Tranche de longueur de la référence normalisée : `<=44c` ou `>44c`."""
    return TRANCHES[0] if len(metrics.normalize(reference)) <= TRANCHE_CHARS else TRANCHES[1]


def crop_pieces(image: Path, boxes: Sequence[Any]) -> list[Any]:
    """Morceaux de l'image de ligne (niveaux de gris), un par boîte ; une boîte hors de l'image ou vide donne un
    morceau vide (0 x 0), qui sera lu comme un texte vide."""
    import numpy as np
    from PIL import Image

    with Image.open(image) as img:
        gray = np.asarray(img.convert("L"), dtype=np.uint8)
    height, width = gray.shape
    pieces: list[Any] = []
    for box in boxes:
        x0, y0, x1, y1 = box.bbox
        left, top = max(0, math.floor(x0)), max(0, math.floor(y0))
        right, bottom = min(width, math.ceil(x1)), min(height, math.ceil(y1))
        usable = x1 > x0 and y1 > y0 and right > left and bottom > top  # boîte dégénérée ou hors de l'image : vide
        pieces.append(gray[top:bottom, left:right].copy() if usable else np.zeros((0, 0), dtype=np.uint8))
    return pieces


def assemble(boxes: Sequence[Any]) -> str:
    """Texte d'une image de ligne à partir de ses morceaux lus, comme en production : `clean_boxes` puis
    `group_rows` (morceaux de droite à gauche si la ligne est surtout arabe), lignes visuelles jointes par un espace."""
    from src.document_intelligence.reading import ocr

    return " ".join(row.text for row in ocr.group_rows(ocr.clean_boxes(boxes)))


def read_pieces(rows_boxes: Sequence[Sequence[Any]], images: Sequence[Path],
                recognize: PieceRecognizer) -> list[str]:
    """Lit tous les morceaux de toutes les lignes en un seul appel, puis assemble chaque ligne."""
    from src.document_intelligence.reading.ocr import OcrBox

    crops = [crop_pieces(image, boxes) for image, boxes in zip(images, rows_boxes, strict=True)]
    flat = [piece for line in crops for piece in line if piece.size]
    texts = iter(recognize(flat) if flat else [])
    out: list[str] = []
    for boxes, line in zip(rows_boxes, crops, strict=True):
        read = [OcrBox(next(texts) if piece.size else "", box.score, box.bbox) for box, piece in zip(boxes, line,
                                                                                                   strict=True)]
        out.append(assemble(read))
    return out


def evaluate(rows: Sequence[Row], recognizers: dict[str, Recognizer], *, detector: Detector | None = None,
             piece_recognizers: dict[str, PieceRecognizer] | None = None) -> dict[str, dict[str, Any]]:
    """CER / WER / lignes exactes par méthode : globalement, par langue (langue de la référence) et par tranche de
    longueur. Avec `detector`, ajoute `production_relue` et, pour chaque `piece_recognizers`, `<nom>_morceaux`."""
    refs = [row.reference for row in rows]
    langs = [detect_language(ref) for ref in refs]
    tranches = [tranche(ref) for ref in refs]
    hyps_by_method: dict[str, list[str]] = {"ocr_production": [row.lecture_ocr for row in rows]}
    images = [row.image for row in rows]
    for name, recognize in recognizers.items():
        hyps_by_method[name] = recognize(images) if images else []
    if detector is not None and images:
        from src.document_intelligence.reading import ocr

        rows_boxes = [ocr.clean_boxes(boxes) for boxes in detector(images)]  # comme en production : sans doublons
        hyps_by_method["production_relue"] = [assemble(boxes) for boxes in rows_boxes]
        for name, recognize_pieces in (piece_recognizers or {}).items():
            hyps_by_method[f"{name}{PIECES_SUFFIX}"] = read_pieces(rows_boxes, images, recognize_pieces)
    results: dict[str, dict[str, Any]] = {}
    for name, hyps in hyps_by_method.items():
        entry: dict[str, Any] = {"global": scores(refs, hyps)}
        # portées par langue, puis par tranche : chacune couvre toutes les lignes (ses totaux donnent le global)
        for keys, values in ((LANGS, langs), (TRANCHES, tranches)):
            for key in keys:
                idx = [i for i, value in enumerate(values) if value == key]
                if idx:
                    entry[key] = scores([refs[i] for i in idx], [hyps[i] for i in idx])
        results[name] = entry
    return results


@dataclass(frozen=True)
class FinetunedRun:
    """Lancement de l'expérience dont viennent les poids fine-tunés."""

    weights: Path
    run_id: str
    """Nom du dossier d'état (`seed<graine>_<empreinte de la configuration>`) : un identifiant, pas un chemin."""
    seed: int | None

    def describe(self) -> dict[str, Any]:
        """Ce qui peut être affiché et écrit dans le JSON : graine et identifiant, jamais de chemin."""
        return {"graine": self.seed, "identifiant": self.run_id}


def find_finetuned_run(build: Path = BUILD) -> FinetunedRun | None:
    """Lancement le plus récent de l'expérience COMPLÈTE qui a des poids fine-tunés (jamais l'essai rapide).

    Depuis la PR #50, l'essai rapide (`--quick`) écrit tout sous `build/quick/` et n'écrit plus dans
    `build/<étape>_best.pdparams`. Par précaution, on ne lit **jamais** `build/*_best.pdparams` (un ancien essai
    rapide a pu l'écraser) : on prend le meilleur état gardé dans le dossier d'état d'un lancement non rapide.
    """
    found: list[FinetunedRun] = []
    for run_info in (build / "state").glob("*/run.json"):
        try:
            config = json.loads(run_info.read_text(encoding="utf-8"))["config"]
        except (OSError, ValueError, KeyError):
            continue
        weights = run_info.parent / FT_FILE
        if not config.get("quick", False) and weights.exists():
            seed = config.get("seed")
            found.append(FinetunedRun(weights, run_info.parent.name, seed if isinstance(seed, int) else None))
    return max(found, key=lambda run: run.weights.stat().st_mtime) if found else None


def experiment_models(ft_weights: Path | None) -> tuple[dict[str, Recognizer], dict[str, PieceRecognizer]]:
    """Modèle pré-entraîné et, si `ft_weights`, modèle fine-tuné, avec le code de l'expérience (Paddle).

    Renvoie les lecteurs de lignes entières et les lecteurs de morceaux (mêmes réseaux, chargés une fois). La largeur
    maximale des images passe de 640 px (entraînement) à `EVAL_MAX_W` : une longue ligne n'est plus comprimée.
    """
    os.environ.setdefault("FLAGS_use_mkldnn", "0")  # oneDNN plante sous Windows (voir ANALYSE.md)
    model: Any = importlib.import_module("model")  # experiments/ocr_transfer_finetune/model.py
    paddle: Any = importlib.import_module("paddle")
    model.MAX_W = EVAL_MAX_W  # lu par model.preprocess à chaque appel
    charset = model.Charset(PPOCR_ROOT / model.DICT_REL)

    def make(weights: Path | None) -> PieceRecognizer:
        net = model.build(PPOCR_ROOT, PRETRAINED, charset)
        if weights is not None:
            net.set_state_dict(paddle.load(str(weights)))

        def recognize(grays: list[Any]) -> list[str]:
            return list(model.predict(net, [model.preprocess(g) for g in grays], charset))

        return recognize

    def on_lines(read: PieceRecognizer) -> Recognizer:
        return lambda paths: read([model.read_gray(p) for p in paths])

    pieces = {"pre_entraine": make(None)}
    if ft_weights is not None:
        pieces["fine_tune"] = make(ft_weights)
    return {name: on_lines(read) for name, read in pieces.items()}, pieces


def paddleocr_available() -> bool:
    return importlib.util.find_spec("paddleocr") is not None


def production_models() -> tuple[Recognizer, Detector]:
    """Modèle d'inférence PaddleX en reconnaissance seule (`production_rec_seule`) et pipeline de production
    (`ocr.read_zone` : détection + reconnaissance, langue « auto », boîtes nettoyées), sur chaque image de ligne."""
    import numpy as np
    from PIL import Image

    from src.document_intelligence.reading import ocr

    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    paddleocr: Any = importlib.import_module("paddleocr")
    rec = paddleocr.TextRecognition(model_name=ocr.REC_MODELS["ar"], device="cpu", enable_mkldnn=False)

    def recognize(paths: list[Path]) -> list[str]:
        return [str(result["rec_text"]) for result in rec.predict([str(p) for p in paths], batch_size=1)]

    def detect(paths: list[Path]) -> list[list[Any]]:
        engine = ocr.default_engine()
        out: list[list[Any]] = []
        for path in paths:
            with Image.open(path) as img:
                bgr = np.ascontiguousarray(np.asarray(img.convert("RGB"), dtype=np.uint8)[:, :, ::-1])
            out.append(ocr.read_zone(engine, bgr, "auto")[0])
        return out

    return recognize, detect


def print_results(counts: dict[str, int], results: dict[str, dict[str, Any]]) -> None:
    print("\nLignes :")
    for key, value in counts.items():
        print(f"  {key:<22} {value}")
    print("\nRésultats (CER et WER : plus bas = mieux) :")
    print(f"  {'méthode':<22} {'portée':<8} {'n':>5} {'CER':>8} {'WER':>8} {'exactes':>8}")
    for name, entry in results.items():
        for scope, s in entry.items():
            print(f"  {name:<22} {scope:<8} {s['n']:>5} {s['cer']:>8.2%} {s['wer']:>8.2%} {s['lignes_exactes']:>8.2%}")


def main(argv: list[str] | None = None, recognizers: dict[str, Recognizer] | None = None, *,
         detector: Detector | None = None, piece_recognizers: dict[str, PieceRecognizer] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CER réel sur des lignes annotées (aucun texte affiché).")
    parser.add_argument("csv", type=Path, help="annotation.csv rempli à la main (hors dépôt).")
    parser.add_argument("--sans-modeles", action="store_true",
                        help="Ne mesure que la lecture de production (pas de chargement de Paddle).")
    parser.add_argument("--poids-finetune", type=Path, default=None,
                        help="Poids du modèle fine-tuné (par défaut : ceux de l'expérience complète).")
    args = parser.parse_args(argv)

    if not args.csv.is_file():
        print("Erreur : le fichier CSV n'existe pas.")
        return 2
    if _inside(args.csv, REPO_ROOT):
        print("Erreur : le CSV doit rester en dehors du dépôt 9anoun-AI (données confidentielles).")
        return 2
    try:
        rows, counts = read_annotations(args.csv)
    except ValueError as exc:
        print(f"Erreur : {exc}")
        return 2
    if not rows:
        print("Aucune ligne annotée : remplissez la colonne texte_correct.")
        return 1

    run_info: dict[str, Any] | None = None
    if recognizers is None:
        recognizers, piece_recognizers, detector = {}, {}, None
        if not args.sans_modeles:
            if paddleocr_available():
                recognizers["production_rec_seule"], detector = production_models()
            else:
                print("Note : PaddleOCR absent : témoins production_rec_seule et *_morceaux non mesurés.")
            if PPOCR_ROOT.is_dir() and PRETRAINED.is_file():
                ft: Path | None = args.poids_finetune
                if ft is not None:
                    run_info = {"graine": None, "identifiant": "poids fournis par --poids-finetune"}
                else:
                    run = find_finetuned_run()
                    if run is not None:
                        ft, run_info = run.weights, run.describe()
                if ft is None:
                    print("Note : poids du Fine-Tuning introuvables : seul le modèle pré-entraîné est mesuré.")
                else:
                    assert run_info is not None
                    print(f"Lancement du Fine-Tuning retenu : graine {run_info['graine']}, "
                          f"identifiant {run_info['identifiant']}.")
                lines, piece_recognizers = experiment_models(ft)
                recognizers.update(lines)
            else:
                print("Note : expérience non préparée (build/PaddleOCR ou poids absents) : les modèles de "
                      "l'expérience ne sont pas mesurés.")

    results = evaluate(rows, recognizers, detector=detector, piece_recognizers=piece_recognizers)
    print_results(counts, results)
    payload = {"format": RESULTS_FORMAT, "lignes": counts, "resultats": results,
               "parametres": {"largeur_max_px": EVAL_MAX_W, "tranche_caracteres": TRANCHE_CHARS},
               "lancement_fine_tune": run_info}  # graine + identifiant, jamais de chemin ; None sans fine-tuné
    (args.csv.parent / RESULTS_NAME).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nChiffres écrits dans {RESULTS_NAME}, à côté du CSV.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
