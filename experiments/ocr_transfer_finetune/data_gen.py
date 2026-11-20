"""Génère les images de lignes de texte FICTIVES (FR / AR) avec un bruit de scan, graine fixée.

- rendu par pymupdf (`insert_htmlbox`, mise en forme arabe et bidi par HarfBuzz) avec des polices
  Windows qui ont des glyphes arabes et latins (Arial, Tahoma, Times New Roman, Segoe UI) ;
- bruit de scan : résolution variable, légère rotation (±2°), flou, bruit gaussien, contraste, JPEG ;
- découpage fixe : train / val / test (domaine) + « generic » (hors domaine, pour mesurer l'oubli) ;
- chaque image dépend seulement de (graine, split, index) : régénérer donne exactement les mêmes images.

Sortie : `<out>/<split>/<index>.png` et `<out>/<split>/labels.jsonl` ({"file", "text", "font"}).
"""

from __future__ import annotations

import html
import json
import random
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import cv2
import numpy as np
import pymupdf
from numpy.typing import NDArray
from vocab import domain_line, generic_line

FONT_DIR: Final = Path("C:/Windows/Fonts")
FONTS: Final = ("arial.ttf", "tahoma.ttf", "times.ttf", "segoeui.ttf")
SPLITS: Final = ("train", "val", "test", "generic")
_SPLIT_ID: Final = {name: i for i, name in enumerate(SPLITS)}

Gray = NDArray[np.uint8]


@dataclass(frozen=True)
class Sample:
    split: str
    index: int
    text: str
    font: str


def available_fonts(font_dir: Path = FONT_DIR) -> list[str]:
    fonts = [f for f in FONTS if (font_dir / f).exists()]
    if not fonts:
        raise FileNotFoundError(f"Aucune police arabe/latine trouvée dans {font_dir} (attendu : {FONTS}).")
    return fonts


def make_texts(seed: int, sizes: dict[str, int], charset: set[str], fonts: list[str]) -> tuple[list[Sample], int]:
    """Tire les textes de chaque split. Les lignes contenant un caractère inconnu du modèle sont
    retirées (et comptées), pour que le CER ne mesure que ce que le modèle peut écrire."""
    samples: list[Sample] = []
    rejected = 0
    for split in SPLITS:
        rng = random.Random(seed * 1000 + _SPLIT_ID[split])
        n = 0
        while n < sizes.get(split, 0):
            text = generic_line(rng) if split == "generic" else domain_line(rng)
            if not set(text) <= charset:
                rejected += 1
                continue
            samples.append(Sample(split, n, text, rng.choice(fonts)))
            n += 1
    return samples, rejected


_ARCHIVES: dict[str, pymupdf.Archive] = {}


def render_text(text: str, font: str, dpi: int, font_dir: Path = FONT_DIR) -> Gray:
    """Rend une ligne en niveaux de gris, recadrée autour de l'encre (marge de quelques pixels)."""
    key = str(font_dir)
    if key not in _ARCHIVES:
        _ARCHIVES[key] = pymupdf.Archive(key)
    css = f"@font-face {{font-family: f; src: url({font});}} p {{font-family: f; font-size: 20px; margin: 0;}}"
    is_rtl = any("\u0600" <= ch <= "\u06ff" for ch in text)
    body = f"<p dir='rtl'>{html.escape(text)}</p>" if is_rtl else f"<p>{html.escape(text)}</p>"
    doc = pymupdf.open()
    page = doc.new_page(width=900, height=50)
    page.insert_htmlbox(pymupdf.Rect(5, 5, 895, 45), body, css=css, archive=_ARCHIVES[key])
    pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY, alpha=False)
    doc.close()
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).copy()
    ys, xs = np.where(img < 200)
    if len(xs) == 0:
        return img
    m = max(2, dpi // 30)
    y0, y1 = max(0, ys.min() - m), min(img.shape[0], ys.max() + m + 1)
    x0, x1 = max(0, xs.min() - m), min(img.shape[1], xs.max() + m + 1)
    return img[y0:y1, x0:x1]


def scan_noise(img: Gray, rng: np.random.Generator) -> Gray:
    """Bruit de scan léger et réaliste."""
    out: NDArray[Any] = img.astype(np.float32)
    # contraste / luminosité (encre pas tout à fait noire, papier pas tout à fait blanc)
    ink, paper = rng.uniform(0, 70), rng.uniform(200, 255)
    out = ink + (out / 255.0) * (paper - ink)
    # légère rotation
    angle = float(rng.uniform(-2.0, 2.0))
    h, w = out.shape
    mat = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    out = cv2.warpAffine(out, mat, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                         borderValue=(float(paper),))
    # flou
    if rng.random() < 0.7:
        sigma = float(rng.uniform(0.3, 1.2))
        out = cv2.GaussianBlur(out, (0, 0), sigma)
    # bruit gaussien
    out = out + rng.normal(0.0, rng.uniform(2.0, 12.0), out.shape)
    noisy: NDArray[Any] = np.clip(out, 0, 255).astype(np.uint8)
    # compression JPEG
    if rng.random() < 0.5:
        ok, buf = cv2.imencode(".jpg", noisy, [cv2.IMWRITE_JPEG_QUALITY, int(rng.integers(40, 90))])
        if ok:
            noisy = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)
    return np.asarray(noisy, dtype=np.uint8)


def render_sample(sample: Sample, seed: int) -> Gray:
    rng = np.random.default_rng([seed, _SPLIT_ID[sample.split], sample.index])
    dpi = int(rng.integers(110, 171))
    return scan_noise(render_text(sample.text, sample.font, dpi), rng)


def generate(out_dir: Path, seed: int, sizes: dict[str, int], charset: set[str]) -> dict[str, object]:
    """Génère (ou réutilise si déjà présent avec la même configuration) le jeu de données."""
    fonts = available_fonts()
    config = {"seed": seed, "sizes": sizes, "fonts": fonts, "version": 1}
    manifest_path = out_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("config") == config:
            return dict(manifest)
    samples, rejected = make_texts(seed, sizes, charset, fonts)
    counts: dict[str, int] = {}
    for split in SPLITS:
        split_dir = out_dir / split
        split_dir.mkdir(parents=True, exist_ok=True)
        rows = []
        for s in (x for x in samples if x.split == split):
            name = f"{s.index:05d}.png"
            ok, png = cv2.imencode(".png", render_sample(s, seed))
            if not ok:
                raise RuntimeError(f"Encodage PNG impossible : {split}/{name}")
            (split_dir / name).write_bytes(png.tobytes())
            rows.append({"file": name, "text": s.text, "font": s.font})
        (split_dir / "labels.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
        )
        counts[split] = len(rows)
    manifest = {"config": config, "counts": counts, "rejected_out_of_charset": rejected}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def load_split(out_dir: Path, split: str) -> list[tuple[Path, str]]:
    rows: Iterable[str] = (out_dir / split / "labels.jsonl").read_text(encoding="utf-8").splitlines()
    return [(out_dir / split / r["file"], r["text"]) for r in map(json.loads, rows)]
