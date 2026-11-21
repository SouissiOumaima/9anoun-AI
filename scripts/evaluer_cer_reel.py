"""Mesure le vrai CER de l'OCR sur des lignes réelles annotées à la main, SANS afficher leur contenu.

À lancer par la personne qui détient les données, après `scripts/annoter_lignes.py` et l'annotation manuelle :

    .venv\\Scripts\\python scripts/evaluer_cer_reel.py "<dossier hors dépôt>\\annotation.csv"

Lit `annotation.csv` (colonne `texte_correct` remplie à la main ; vide = ligne sautée ; `#ILLISIBLE` = ligne
illisible, comptée à part) et compare, sur les mêmes lignes :
- `ocr_production` : la lecture faite pendant l'annotation par l'OCR du projet (détection + reconnaissance,
  langue « auto »), colonne `lecture_ocr` ;
- `pre_entraine` : le modèle de reconnaissance pré-entraîné (`arabic_PP-OCRv5_mobile_rec`), sur l'image de la ligne ;
- `fine_tune` : le même modèle après le Fine-Tuning de l'expérience (variante `bn_frozen`), sur l'image de la ligne.
`pre_entraine` et `fine_tune` sont mesurés exactement de la même façon (reconnaissance seule) : leur écart est
l'effet du Fine-Tuning sur des données réelles. Les deux modèles ne sont chargés que si l'expérience est prête
(code PaddleOCR et poids dans `experiments/ocr_transfer_finetune/build/`) ; sinon seule `ocr_production` est mesurée.

N'affiche QUE des chiffres agrégés : CER, WER, part de lignes exactes, globalement et par langue. Écrit aussi
`resultats_cer_reel.json` à côté du CSV (chiffres seulement). Aucun texte, aucun nom de fichier n'est affiché.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import os
import sys
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
RESULTS_NAME: Final = "resultats_cer_reel.json"
LANGS: Final = ("fr", "ar", "mixte", "inconnu")
"""Langue de la référence ; « inconnu » = ligne sans lettres (montants, dates seuls). Les portées par langue
couvrent donc toutes les lignes : leurs totaux s'additionnent pour donner le global."""
RESULTS_FORMAT: Final = "ds3.cer_reel.v2"
"""Format du fichier de résultats (v2 : avec les totaux nécessaires pour combiner plusieurs annotatrices)."""

Recognizer = Callable[[list[Path]], list[str]]
"""Lit une liste d'images de lignes et renvoie un texte par image (remplaçable dans les tests)."""


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


def read_annotations(csv_path: Path) -> tuple[list[Row], dict[str, int]]:
    """Lignes annotées (texte_correct rempli) et décompte des lignes sautées ou illisibles."""
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        missing = {"image", "lecture_ocr", "texte_correct"} - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"colonnes manquantes dans le CSV : {sorted(missing)}")
        raw = list(reader)
    rows: list[Row] = []
    illegible = skipped = 0
    for record in raw:
        reference = (record.get("texte_correct") or "").strip()
        if not reference:
            skipped += 1
        elif reference.upper() == ILLEGIBLE:
            illegible += 1
        else:
            rows.append(Row(csv_path.parent / record["image"], record.get("lecture_ocr") or "", reference))
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


def evaluate(rows: Sequence[Row], recognizers: dict[str, Recognizer]) -> dict[str, dict[str, Any]]:
    """CER / WER / lignes exactes par méthode, globalement et par langue (langue de la référence)."""
    refs = [row.reference for row in rows]
    langs = [detect_language(ref) for ref in refs]
    hyps_by_method: dict[str, list[str]] = {"ocr_production": [row.lecture_ocr for row in rows]}
    images = [row.image for row in rows]
    for name, recognize in recognizers.items():
        hyps_by_method[name] = recognize(images) if images else []
    results: dict[str, dict[str, Any]] = {}
    for name, hyps in hyps_by_method.items():
        entry: dict[str, Any] = {"global": scores(refs, hyps)}
        for lang in LANGS:
            idx = [i for i, value in enumerate(langs) if value == lang]
            if idx:
                entry[lang] = scores([refs[i] for i in idx], [hyps[i] for i in idx])
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


def experiment_recognizers(ft_weights: Path | None) -> dict[str, Recognizer]:  # pragma: no cover - charge Paddle
    """Modèle pré-entraîné et, si `ft_weights`, modèle fine-tuné, avec le code de l'expérience (Paddle)."""
    os.environ.setdefault("FLAGS_use_mkldnn", "0")  # oneDNN plante sous Windows (voir ANALYSE.md)
    model: Any = importlib.import_module("model")  # experiments/ocr_transfer_finetune/model.py
    paddle: Any = importlib.import_module("paddle")
    charset = model.Charset(PPOCR_ROOT / model.DICT_REL)

    def make(weights: Path | None) -> Recognizer:
        net = model.build(PPOCR_ROOT, PRETRAINED, charset)
        if weights is not None:
            net.set_state_dict(paddle.load(str(weights)))

        def recognize(paths: list[Path]) -> list[str]:
            images = [model.preprocess(model.read_gray(p)) for p in paths]
            return list(model.predict(net, images, charset))

        return recognize

    recognizers = {"pre_entraine": make(None)}
    if ft_weights is not None:
        recognizers["fine_tune"] = make(ft_weights)
    return recognizers


def print_results(counts: dict[str, int], results: dict[str, dict[str, Any]]) -> None:
    print("\nLignes :")
    for key, value in counts.items():
        print(f"  {key:<22} {value}")
    print("\nRésultats (CER et WER : plus bas = mieux) :")
    print(f"  {'méthode':<16} {'portée':<8} {'n':>5} {'CER':>8} {'WER':>8} {'exactes':>8}")
    for name, entry in results.items():
        for scope, s in entry.items():
            print(f"  {name:<16} {scope:<8} {s['n']:>5} {s['cer']:>8.2%} {s['wer']:>8.2%} {s['lignes_exactes']:>8.2%}")


def main(argv: list[str] | None = None, recognizers: dict[str, Recognizer] | None = None) -> int:
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
        recognizers = {}
        if not args.sans_modeles:
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
                recognizers = experiment_recognizers(ft)
            else:
                print("Note : expérience non préparée (build/PaddleOCR ou poids absents) : seule la lecture de "
                      "production est mesurée.")

    results = evaluate(rows, recognizers)
    print_results(counts, results)
    payload = {"format": RESULTS_FORMAT, "lignes": counts, "resultats": results,
               "lancement_fine_tune": run_info}  # graine + identifiant, jamais de chemin ; None sans fine-tuné
    (args.csv.parent / RESULTS_NAME).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nChiffres écrits dans {RESULTS_NAME}, à côté du CSV.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
