"""Modèle de reconnaissance arabic_PP-OCRv5_mobile_rec (PaddleOCR) : construction, gel, CTC.

Architecture (config officielle `configs/rec/PP-OCRv5/multi_language/arabic_PP-OCRv5_mobile_rec.yaml`) :
    image 48 x W -> backbone PPLCNetV3 (CNN) -> MultiHead
                                                 ├─ branche CTC : ctc_encoder (SVTR, 2 blocs) -> ctc_head (linéaire, 749 classes)
                                                 └─ branche NRTR (décodeur attentionnel, utilisée seulement à l'entraînement d'origine)
À l'inférence, PaddleOCR n'utilise que la branche CTC : on fait pareil, la branche NRTR est ignorée.

Ordre des caractères (vérifié sur nos images) : les poids PRÉ-ENTRAÎNÉS publiés pour l'entraînement
produisent l'arabe en ordre VISUEL (« لخدلاىلع ةبيرضلا » pour « الضريبة على الدخل »), alors que le modèle
d'inférence PaddleX (tâche 1) rend l'ordre logique. On suit donc la convention officielle de ces poids :
cibles d'entraînement en ordre visuel, sortie remise en ordre logique avant le calcul du CER
(`to_visual` / `to_logical`, une seule fonction involutive).
"""

from __future__ import annotations

import copy
import math
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any, Final, Literal

import cv2
import numpy as np
import paddle  # type: ignore[import-untyped]
import yaml  # type: ignore[import-untyped]
from numpy.typing import NDArray
from rtl import flip_rtl

IMG_H: Final = 48
MAX_W: Final = 640
CONFIG_REL: Final = Path("configs/rec/PP-OCRv5/multi_language/arabic_PP-OCRv5_mobile_rec.yaml")
DICT_REL: Final = Path("ppocr/utils/dict/ppocrv5_arabic_dict.txt")

Stage = Literal["baseline", "transfer", "finetune"]


to_visual = flip_rtl
to_logical = flip_rtl


class Charset:
    """Table des classes CTC : 0 = blank, puis le dictionnaire du modèle, puis l'espace."""

    def __init__(self, dict_path: Path) -> None:
        chars = [line.rstrip("\r\n") for line in dict_path.read_text(encoding="utf-8").splitlines()]
        self.chars: list[str] = ["<blank>", *chars, " "]
        self.index: dict[str, int] = {}
        for i, c in enumerate(self.chars):
            self.index.setdefault(c, i)  # premier indice si un caractère apparaît deux fois

    def __len__(self) -> int:
        return len(self.chars)

    @property
    def known(self) -> set[str]:
        return set(self.chars[1:])

    def encode(self, text: str) -> list[int]:
        """Texte logique -> indices CTC dans l'ordre de sortie du modèle (visuel pour l'arabe)."""
        return [self.index[c] for c in to_visual(text)]

    def greedy_decode(self, ids: Sequence[int]) -> str:
        """Décodage CTC glouton : on fusionne les répétitions puis on retire les blancs."""
        out: list[str] = []
        prev = -1
        for i in ids:
            if i != prev and i != 0:
                out.append(self.chars[i])
            prev = i
        return "".join(out)


def load_ppocr(ppocr_root: Path) -> None:
    if str(ppocr_root) not in sys.path:
        sys.path.insert(0, str(ppocr_root))


def build(ppocr_root: Path, weights: Path, charset: Charset) -> Any:
    """Construit le modèle à partir de la config officielle et charge les poids pré-entraînés."""
    load_ppocr(ppocr_root)
    from ppocr.modeling.architectures import build_model  # type: ignore[import-not-found]

    config = yaml.safe_load((ppocr_root / CONFIG_REL).read_text(encoding="utf-8"))
    arch = copy.deepcopy(config["Architecture"])
    arch["Head"]["out_channels_list"] = {"CTCLabelDecode": len(charset), "NRTRLabelDecode": len(charset) + 3}
    model = build_model(arch)
    state = paddle.load(str(weights))
    own = model.state_dict()
    loadable = {k: v for k, v in state.items() if k in own and list(v.shape) == list(own[k].shape)}
    ctc_keys = [k for k in own if not k.startswith(("head.gtc_head", "head.before_gtc"))]
    missing = [k for k in ctc_keys if k not in loadable]
    if missing:
        raise RuntimeError(f"Poids pré-entraînés incompatibles ({len(missing)} clés CTC manquantes, ex. {missing[:3]})")
    model.set_state_dict(loadable)
    return model


def ctc_logits(model: Any, images: Any) -> Any:
    """Passe avant de la seule branche CTC ; renvoie des logits [N, T, C]."""
    feats = model.backbone(images)
    enc = model.head.ctc_encoder(feats)
    head = model.head.ctc_head
    out = head.fc(enc) if hasattr(head, "fc") else head(enc)
    return out


def ctc_modules(model: Any) -> dict[str, Any]:
    return {"backbone": model.backbone, "encoder": model.head.ctc_encoder, "head": model.head.ctc_head}


FtVariant = Literal["bn_frozen", "partial"]
FT_VARIANTS: Final[dict[str, str]] = {
    "bn_frozen": "tout dégelé sauf BatchNorm (paramètres et statistiques gelés)",
    "partial": "partiel : dernier étage du backbone (blocks6) + encodeur + tête, BatchNorm gelée",
}


def batchnorm_layers(model: Any) -> list[Any]:
    """Couches BatchNorm du chemin CTC (backbone + encodeur ; la tête n'en a pas)."""
    mods = ctc_modules(model)
    layers = mods["backbone"].sublayers() + mods["encoder"].sublayers()
    return [layer for layer in layers if "BatchNorm" in type(layer).__name__]


def configure_stage(model: Any, stage: Stage, ft_variant: FtVariant = "bn_frozen") -> list[Any]:
    """Gèle / dégèle selon l'étape ; renvoie les paramètres à entraîner.

    - transfer : backbone et encodeur gelés (poids ET statistiques BatchNorm), seule la tête entraînée ;
    - finetune « bn_frozen » : tout le chemin CTC entraînable sauf les BatchNorm (échelle, biais et statistiques
      gelés). Raison : le plantage natif de Paddle (MKL « vsAdd », access violation dans batch_norm) n'est
      apparu que quand le backbone recevait des gradients ;
    - finetune « partial » (plan B) : seulement le dernier étage du backbone, l'encodeur et la tête, BatchNorm
      gelée.
    """
    mods = ctc_modules(model)
    for p in model.parameters():
        p.stop_gradient = True
    if stage == "transfer":
        groups = [mods["head"]]
    elif stage == "finetune":
        first = mods["backbone"] if ft_variant == "bn_frozen" else mods["backbone"].blocks6
        groups = [first, mods["encoder"], mods["head"]]
    else:
        groups = []
    frozen_bn = {id(p) for layer in batchnorm_layers(model) for p in layer.parameters()} if stage == "finetune" else set()
    params: list[Any] = []
    for group in groups:
        for p in group.parameters():
            if id(p) in frozen_bn:
                continue
            p.stop_gradient = False
            params.append(p)
    return params


def set_train_mode(model: Any, stage: Stage) -> None:
    """Modes train/eval des blocs pendant l'entraînement.

    Le backbone reste TOUJOURS en mode évaluation, même en Fine-Tuning (ses poids reçoivent quand même
    les gradients) : en mode « train », PPLCNetV3 force la sortie à 40 pas de temps
    (`adaptive_avg_pool2d(x, [1, 40])`), donc au plus ~40 caractères et une géométrie différente de
    l'inférence. En mode évaluation : même pooling qu'à l'inférence, et statistiques BatchNorm gelées
    (pratique courante en fine-tuning avec peu de données et de petits lots).
    """
    model.eval()
    mods = ctc_modules(model)
    if stage == "transfer":
        mods["head"].train()
    elif stage == "finetune":
        mods["encoder"].train()
        mods["head"].train()
        for layer in batchnorm_layers(model):  # statistiques BatchNorm gelées (encodeur compris)
            layer.eval()


def count_params(params: Sequence[Any]) -> int:
    return int(sum(math.prod(p.shape) for p in params))


# ---------------------------------------------------------------- images -> tenseurs


def read_gray(path: Path) -> NDArray[np.uint8]:
    img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(f"Image illisible : {path}")
    return np.asarray(img, dtype=np.uint8)


def preprocess(img: NDArray[np.uint8]) -> NDArray[np.float32]:
    """Comme PaddleX : hauteur 48, largeur proportionnelle, normalisation (x/255 - 0.5) / 0.5, 3 canaux."""
    h, w = img.shape[:2]
    new_w = max(8, min(MAX_W, math.ceil(IMG_H * w / h)))
    resized = cv2.resize(img, (new_w, IMG_H)).astype(np.float32)
    norm = (resized / 255.0 - 0.5) / 0.5
    return np.repeat(norm[None, :, :], 3, axis=0)


def make_batch(images: Sequence[NDArray[np.float32]]) -> NDArray[np.float32]:
    """Complète à droite avec 0 (gris moyen après normalisation, comme PaddleX) jusqu'à la largeur max."""
    width = max(im.shape[2] for im in images)
    width = int(math.ceil(width / 8) * 8)
    batch = np.zeros((len(images), 3, IMG_H, width), dtype=np.float32)
    for i, im in enumerate(images):
        batch[i, :, :, : im.shape[2]] = im
    return batch


def batches(n: int, batch_size: int, rng: np.random.Generator | None) -> Iterator[NDArray[np.int64]]:
    order = rng.permutation(n) if rng is not None else np.arange(n)
    for start in range(0, n, batch_size):
        yield order[start : start + batch_size]


def predict(model: Any, images: Sequence[NDArray[np.float32]], charset: Charset, batch_size: int = 64) -> list[str]:
    """Reconnaissance (décodage glouton) d'une liste d'images prétraitées."""
    model.eval()
    out: list[str] = [""] * len(images)
    # trier par largeur limite le remplissage et accélère l'inférence
    order = sorted(range(len(images)), key=lambda i: images[i].shape[2])
    with paddle.no_grad():
        for start in range(0, len(order), batch_size):
            idx = order[start : start + batch_size]
            logits = ctc_logits(model, paddle.to_tensor(make_batch([images[i] for i in idx])))
            ids = logits.argmax(axis=2).numpy()
            for k, i in enumerate(idx):
                out[i] = to_logical(charset.greedy_decode(ids[k][: seq_len(images[i])].tolist()))
    return out


def seq_len(image: NDArray[np.float32]) -> int:
    """Nombre de pas de temps CTC utiles d'une image (le backbone divise la largeur par 8)."""
    return max(1, math.ceil(image.shape[2] / 8))


def width_batches(images: Sequence[NDArray[np.float32]], batch_size: int,
                  rng: np.random.Generator) -> list[list[int]]:
    """Lots d'images de largeurs voisines (moins de remplissage, donc plus rapide), ordre des lots mélangé."""
    order = sorted(range(len(images)), key=lambda i: (images[i].shape[2], rng.random()))
    groups = [order[s : s + batch_size] for s in range(0, len(order), batch_size)]
    return [groups[j] for j in rng.permutation(len(groups))]


def encoder_features(model: Any, images: Sequence[NDArray[np.float32]], batch_size: int = 64) -> list[Any]:
    """Sorties de l'encodeur gelé (backbone + SVTR), calculées une fois : [T_i, 120] par image."""
    model.eval()
    feats: list[Any] = [None] * len(images)
    order = sorted(range(len(images)), key=lambda i: images[i].shape[2])
    with paddle.no_grad():
        for start in range(0, len(order), batch_size):
            idx = order[start : start + batch_size]
            enc = model.head.ctc_encoder(model.backbone(paddle.to_tensor(make_batch([images[i] for i in idx]))))
            arr = enc.numpy()
            for k, i in enumerate(idx):
                feats[i] = arr[k, : seq_len(images[i])].copy()
    return feats
