"""Évalue l'OCR (partie A) sur les PDF réels, SANS jamais afficher leur contenu.

À lancer par la personne qui détient les données (elles restent en dehors du dépôt) :

    .venv\\Scripts\\python scripts/evaluer_donnees_reelles.py "<dossier des PDF>" --out "<dossier de sortie>" --limit 5

- lit chaque PDF : texte natif (partie B) puis OCR des zones en attente (partie A) ;
- écrit, pour chaque document, la représentation intermédiaire complète dans `--out`
  (`doc_001.json`, `doc_002.json`… : les noms de fichiers d'origine ne sont pas repris) ;
- `--out` doit être EN DEHORS du dépôt (le script refuse sinon) ;
- n'affiche QUE des chiffres agrégés : documents, pages, zones, lignes, confiance moyenne, durée.
  Aucun texte, aucun nom de fichier n'est affiché.

Options de mesure de la vitesse :
- `--max-pages N` : seulement les N premières pages de chaque PDF ;
- `--profile` : durées par étape (lecture native, chargement des modèles, rendu, détection,
  reconnaissance) et compteurs (zones, appels OCR par langue, boîtes, taille des images en pixels),
  zone par zone. Toujours aucun texte ni nom de fichier.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.document_intelligence.intermediate import IntermediateDocument, PendingZone
from src.document_intelligence.reading import ocr
from src.document_intelligence.reading.ocr import Image3, OcrBox, OcrEngine, OcrLang
from src.document_intelligence.reading.pdf_natif import read_pdf


@dataclass
class Totals:
    documents: int = 0
    documents_en_echec: int = 0
    pages: int = 0
    zones_a_lire: int = 0
    zones_lues: int = 0
    zones_restees_en_attente: int = 0
    lignes_natives: int = 0
    lignes_ocr: int = 0
    lignes_ocr_ar: int = 0
    lignes_ocr_fr: int = 0
    lignes_ocr_mixte_ou_inconnu: int = 0
    confiances_ocr: list[float] = field(default_factory=list)
    duree_s: float = 0.0

    def summary(self) -> dict[str, float | int]:
        conf = sorted(self.confiances_ocr)
        out: dict[str, float | int] = {k: v for k, v in asdict(self).items() if k != "confiances_ocr"}
        out["duree_s"] = round(self.duree_s, 1)
        out["confiance_ocr_moyenne"] = round(sum(conf) / len(conf), 4) if conf else 0.0
        out["confiance_ocr_mediane"] = round(conf[len(conf) // 2], 4) if conf else 0.0
        out["lignes_ocr_confiance_sous_0_90"] = sum(1 for c in conf if c < 0.90)
        out["part_zones_lues"] = round(self.zones_lues / self.zones_a_lire, 4) if self.zones_a_lire else 0.0
        return out


# ---------------------------------------------------------------- profilage (chiffres seulement)


@dataclass
class ZoneProfile:
    largeur_px: int = 0
    hauteur_px: int = 0
    rendu_s: float = 0.0
    appels: list[str] = field(default_factory=list)  # langue de chaque passe : "ar", "fr"
    ocr_s: float = 0.0
    boites: int = 0


@dataclass
class Profile:
    lecture_native_s: float = 0.0
    chargement_modeles_s: float = 0.0
    rendu_s: float = 0.0
    detection_s: float = 0.0
    reconnaissance_s: float = 0.0
    ocr_total_s: float = 0.0
    zones: list[ZoneProfile] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        calls = Counter(lang for z in self.zones for lang in z.appels)
        pixels = [z.largeur_px * z.hauteur_px for z in self.zones]
        return {
            "lecture_native_s": round(self.lecture_native_s, 1),
            "chargement_modeles_s": round(self.chargement_modeles_s, 1),
            "rendu_s": round(self.rendu_s, 1),
            "detection_s": round(self.detection_s, 1),
            "reconnaissance_s": round(self.reconnaissance_s, 1),
            "reste_ocr_s (decoupe, post-traitement)": round(
                max(0.0, self.ocr_total_s - self.detection_s - self.reconnaissance_s), 1),
            "ocr_total_s (sans chargement des modeles)": round(self.ocr_total_s, 1),
            "zones": len(self.zones),
            "appels_ocr_ar": calls["ar"],
            "appels_ocr_fr": calls["fr"],
            "zones_lues_deux_fois": sum(1 for z in self.zones if len(z.appels) > 1),
            "boites_total": sum(z.boites for z in self.zones),
            "pixels_total_millions": round(sum(pixels) / 1e6, 2),
            "plus_grande_image_px": max((f"{z.largeur_px}x{z.hauteur_px}" for z in self.zones),
                                        key=lambda s: int(s.split("x")[0]) * int(s.split("x")[1]), default="-"),
        }


class ProfilingEngine:
    """Enveloppe un moteur d'OCR : compte les appels, la langue, la taille des images et les boîtes."""

    def __init__(self, inner: OcrEngine, profile: Profile) -> None:
        self.inner = inner
        self.profile = profile
        self.name = inner.name

    def recognize(self, image: Image3, lang: OcrLang) -> list[OcrBox]:
        start, loading_before = time.perf_counter(), self.profile.chargement_modeles_s
        boxes = self.inner.recognize(image, lang)
        # le premier appel d'une langue charge le modèle : ce temps est compté à part
        elapsed = time.perf_counter() - start - (self.profile.chargement_modeles_s - loading_before)
        if not self.profile.zones:  # appel hors rendu de zone (ne devrait pas arriver)
            self.profile.zones.append(ZoneProfile(largeur_px=image.shape[1], hauteur_px=image.shape[0]))
        zone = self.profile.zones[-1]
        zone.appels.append(lang)
        zone.ocr_s += elapsed
        zone.boites += len(boxes)
        self.profile.ocr_total_s += elapsed
        return boxes


def _timed(fn: Callable[..., Any], add: Callable[[float], None]) -> Callable[..., Any]:
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            add(time.perf_counter() - start)

    return wrapper


def _instrument_paddle(engine: ocr.PaddleEngine, profile: Profile) -> None:
    """Chronomètre le chargement des modèles, puis la détection et la reconnaissance de PaddleOCR.

    PaddleX appelle `predictor.process(...)` pour chaque lot : on remplace cette méthode sur l'instance.
    Si la structure interne change, seules les durées détection / reconnaissance restent à 0.
    """
    original = engine._pipeline

    def add_det(dt: float) -> None:
        profile.detection_s += dt

    def add_rec(dt: float) -> None:
        profile.reconnaissance_s += dt

    def pipeline(lang: OcrLang) -> Any:
        if lang in engine._pipelines:
            return original(lang)
        start = time.perf_counter()
        pipe = original(lang)
        profile.chargement_modeles_s += time.perf_counter() - start
        inner: Any = getattr(pipe, "paddlex_pipeline", pipe)
        for _ in range(3):
            inner = getattr(inner, "_pipeline", inner)
        for attr, add in (("text_det_model", add_det), ("text_rec_model", add_rec)):
            predictor = getattr(inner, attr, None)
            if predictor is not None and hasattr(predictor, "process"):
                predictor.process = _timed(predictor.process, add)
        return pipe

    engine._pipeline = pipeline  # type: ignore[method-assign]


def _install_render_probe(profile: Profile) -> Callable[[], None]:
    """Chronomètre le rendu de chaque zone et note sa taille en pixels. Renvoie la fonction qui annule."""
    original = ocr.render_zone

    def render(page: Any, zone: PendingZone, dpi: int = ocr.OCR_DPI) -> Image3:
        start = time.perf_counter()
        image = original(page, zone, dpi)
        elapsed = time.perf_counter() - start
        profile.rendu_s += elapsed
        profile.zones.append(ZoneProfile(largeur_px=image.shape[1], hauteur_px=image.shape[0], rendu_s=elapsed))
        return image

    ocr.render_zone = render  # type: ignore[assignment]

    def restore() -> None:
        ocr.render_zone = original

    return restore


# ---------------------------------------------------------------- évaluation


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _first_pages(doc: IntermediateDocument, max_pages: int | None) -> IntermediateDocument:
    """Garde seulement les `max_pages` premières pages (les autres ne passent pas à l'OCR)."""
    if max_pages is None or len(doc.pages) <= max_pages:
        return doc
    return doc.model_copy(update={"pages": doc.pages[:max_pages]})


def evaluate(
    source: Path,
    out_dir: Path,
    limit: int | None,
    *,
    max_pages: int | None = None,
    profile: Profile | None = None,
    engine: OcrEngine | None = None,
) -> Totals:
    pdfs = sorted(p for p in source.iterdir() if p.suffix.lower() == ".pdf")
    if limit is not None:
        pdfs = pdfs[:limit]
    out_dir.mkdir(parents=True, exist_ok=True)
    totals = Totals()
    restore: Callable[[], None] | None = None
    if profile is not None:
        base = engine or ocr.default_engine()
        if isinstance(base, ocr.PaddleEngine):
            _instrument_paddle(base, profile)
        engine = ProfilingEngine(base, profile)
        restore = _install_render_probe(profile)
    start = time.perf_counter()
    try:
        for k, pdf in enumerate(pdfs, start=1):
            totals.documents += 1
            try:
                t0 = time.perf_counter()
                natif = _first_pages(read_pdf(pdf, document_id=f"doc_{k:03d}"), max_pages)
                if profile is not None:
                    profile.lecture_native_s += time.perf_counter() - t0
                doc = ocr.ocr_pending_zones(natif, pdf, engine=engine)
            except Exception:  # noqa: BLE001 — un document cassé ne doit pas arrêter l'évaluation
                totals.documents_en_echec += 1
                print(f"  document {k}/{len(pdfs)} : échec de lecture")
                continue
            before = sum(len(p.pending_zones) for p in natif.pages)
            after = sum(len(p.pending_zones) for p in doc.pages)
            lines = [line for page in doc.pages for line in page.lines]
            ocr_lines = [line for line in lines if line.source == "ocr"]
            totals.pages += len(doc.pages)
            totals.zones_a_lire += before
            totals.zones_restees_en_attente += after
            totals.zones_lues += before - after
            totals.lignes_natives += sum(1 for line in lines if line.source == "natif")
            totals.lignes_ocr += len(ocr_lines)
            totals.lignes_ocr_ar += sum(1 for line in ocr_lines if line.language == "ar")
            totals.lignes_ocr_fr += sum(1 for line in ocr_lines if line.language == "fr")
            totals.lignes_ocr_mixte_ou_inconnu += sum(1 for line in ocr_lines if line.language in ("mixte", "inconnu"))
            totals.confiances_ocr.extend(line.confidence for line in ocr_lines)
            (out_dir / f"doc_{k:03d}.json").write_text(doc.model_dump_json(indent=2), encoding="utf-8")
            print(f"  document {k}/{len(pdfs)} : {len(doc.pages)} page(s), {before - after}/{before} zone(s) lue(s), "
                  f"{len(ocr_lines)} ligne(s) OCR")
    finally:
        if restore is not None:
            restore()
    totals.duree_s = time.perf_counter() - start
    return totals


def print_profile(profile: Profile) -> None:
    print("\nProfil (durées en secondes, aucune donnée de contenu) :")
    for key, value in profile.summary().items():
        print(f"  {key:<48} {value}")
    print("\n  zone  taille_px     rendu_s  passes  ocr_s   boites")
    for i, z in enumerate(profile.zones, start=1):
        size = f"{z.largeur_px}x{z.hauteur_px}"
        print(f"  {i:>4}  {size:<12} {z.rendu_s:>7.2f}  {'+'.join(z.appels) or '-':<6}  {z.ocr_s:>6.1f}  {z.boites:>6}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Évaluation agrégée de l'OCR sur des PDF réels (aucun texte affiché).")
    parser.add_argument("source", type=Path, help="Dossier contenant les PDF réels (hors dépôt).")
    parser.add_argument("--out", type=Path, required=True, help="Dossier de sortie, EN DEHORS du dépôt.")
    parser.add_argument("--limit", type=int, default=None, help="Nombre maximal de PDF à traiter.")
    parser.add_argument("--max-pages", type=int, default=None, help="Seulement les N premières pages de chaque PDF.")
    parser.add_argument("--profile", action="store_true", help="Affiche les durées par étape (chiffres seulement).")
    args = parser.parse_args(argv)

    if not args.source.is_dir():
        print("Erreur : le dossier source n'existe pas.")
        return 2
    if _inside(args.out, REPO_ROOT):
        print("Erreur : --out doit être en dehors du dépôt 9anoun-AI (données confidentielles).")
        return 2
    for name in ("limit", "max_pages"):
        value = getattr(args, name)
        if value is not None and value < 1:
            print(f"Erreur : --{name.replace('_', '-')} doit être au moins 1.")
            return 2

    profile = Profile() if args.profile else None
    totals = evaluate(args.source, args.out, args.limit, max_pages=args.max_pages, profile=profile)
    summary = totals.summary()
    (args.out / "resume_agrege.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\nRésumé agrégé :")
    for key, value in summary.items():
        print(f"  {key:<32} {value}")
    if profile is not None:
        print_profile(profile)
        profil = {**profile.summary(), "zones_detail": [asdict(z) for z in profile.zones]}
        (args.out / "profil.json").write_text(json.dumps(profil, indent=2), encoding="utf-8")
    print(f"\nDétails écrits dans le dossier de sortie ({totals.documents - totals.documents_en_echec} JSON).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
