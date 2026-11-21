"""Transfer Learning vs Fine-Tuning sur arabic_PP-OCRv5_mobile_rec — une seule commande, graine fixée.

    .venv\\Scripts\\python experiments/ocr_transfer_finetune/run_experiment.py --seed 42

Étapes :
  1. génère les lignes FICTIVES (train / val / test / generic) avec bruit de scan ;
  2. charge le modèle pré-entraîné (poids officiels PaddleOCR, téléchargés une fois dans build/) ;
  3. baseline : modèle tel quel, sans entraînement ;
  4. Transfer Learning : backbone + encodeur gelés, seule la tête CTC est entraînée ;
  5. Fine-Tuning : tout le chemin CTC dégelé (statistiques BatchNorm du backbone gelées), learning rate
     faible (warmup + cosinus) ;
  6. CER / WER / lignes exactes sur le MÊME jeu de test (et sur un jeu « generic » pour l'oubli) ;
  7. écrit results.json, results.md, loss_curves.png (et les poids dans build/).
Pour chaque entraînement, on garde l'époque qui a le meilleur CER de validation (jamais le test).
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import platform
import random
import shutil
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

MAX_RESTARTS: Final = 3
"""Relances automatiques après un plantage natif de Paddle (erreur MKL « vsAdd », access violation)."""


def supervise(argv: list[str]) -> int:
    """Lance l'entraînement dans un sous-processus et le relance s'il plante.

    Paddle 3.3 sur CPU Windows plante parfois de façon aléatoire au milieu d'une époque (bug natif MKL,
    observé sur cette machine). Chaque relance repart des étapes terminées et du dernier point de sauvegarde.
    """
    code = 1
    for attempt in range(1, MAX_RESTARTS + 2):
        env = {**os.environ, "OCR_EXP_ATTEMPT": str(attempt)}
        cmd = [sys.executable, "-X", "faulthandler", str(Path(__file__).resolve()), *argv, "--worker"]
        code = subprocess.run(cmd, env=env, check=False).returncode
        if code == 0:
            return 0
        if attempt <= MAX_RESTARTS:
            print(f"\n!! Processus d'entraînement arrêté (code {code}) : relance {attempt}/{MAX_RESTARTS} "
                  "depuis le dernier point de sauvegarde…\n", flush=True)
    print(f"\n!! Abandon après {MAX_RESTARTS} relances (dernier code {code}).", flush=True)
    return code


if __name__ == "__main__" and "--worker" not in sys.argv:
    raise SystemExit(supervise(sys.argv[1:]))

import numpy as np

# Réglages de calcul CPU, fixés AVANT l'import de Paddle (voir ANALYSE.md, « difficultés ») :
# - oneDNN désactivé : l'inférence PP-OCRv5 plante avec oneDNN sous Windows (Paddle 3.3) ;
# - threads MKL laissés au réglage par défaut : limiter MKL à 1 thread (essayé contre le plantage MKL
#   « vsAdd ») rendait le calcul ~11 fois plus lent (92 min au lieu de ~8 pour une même étape). La protection
#   contre ce plantage aléatoire est la reprise automatique par point de sauvegarde (voir `supervise`).
os.environ["FLAGS_use_mkldnn"] = "0"

import paddle  # type: ignore[import-untyped]

HERE: Final = Path(__file__).resolve().parent
REPO_ROOT: Final = HERE.parents[1]
sys.path[:0] = [str(HERE), str(REPO_ROOT)]

import data_gen
import metrics
import model as m
from run_paths import run_paths

from src.document_intelligence.intermediate import detect_language as line_language

BUILD: Final = HERE / "build"
PPOCR_ROOT: Final = BUILD / "PaddleOCR"
PPOCR_TAG: Final = "v3.7.0"
WEIGHTS: Final = BUILD / "weights" / "arabic_PP-OCRv5_mobile_rec_pretrained.pdparams"
WEIGHTS_URL: Final = (
    "https://paddle-model-ecology.bj.bcebos.com/paddlex/official_pretrained_model/"
    "arabic_PP-OCRv5_mobile_rec_pretrained.pdparams"
)
SPARSE: Final = ("/ppocr/", "/tools/", "/configs/rec/PP-OCRv5/", "/requirements.txt")


# ---------------------------------------------------------------- préparation


def ensure_ppocr() -> None:
    """Code d'entraînement PaddleOCR (paquet ppocr), cloné une fois au tag figé, dans build/ (ignoré par git)."""
    if (PPOCR_ROOT / m.CONFIG_REL).exists():
        return
    BUILD.mkdir(parents=True, exist_ok=True)
    url = "https://github.com/PaddlePaddle/PaddleOCR.git"
    subprocess.run(["git", "clone", "--quiet", "--depth", "1", "--branch", PPOCR_TAG, "--filter=blob:none",
                    "--sparse", url, str(PPOCR_ROOT)], check=True)
    subprocess.run(["git", "-C", str(PPOCR_ROOT), "sparse-checkout", "set", "--no-cone", *SPARSE], check=True)


def ensure_weights() -> None:
    if WEIGHTS.exists() and WEIGHTS.stat().st_size > 1_000_000:
        return
    WEIGHTS.parent.mkdir(parents=True, exist_ok=True)
    print("Téléchargement des poids pré-entraînés (71 Mo)…")
    urllib.request.urlretrieve(WEIGHTS_URL, WEIGHTS)


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    paddle.seed(seed)


# ---------------------------------------------------------------- données en mémoire


@dataclass
class Split:
    images: list[Any]
    texts: list[str]
    labels: list[list[int]] = field(default_factory=list)


def load(data_dir: Path, name: str, charset: m.Charset) -> Split:
    rows = data_gen.load_split(data_dir, name)
    images = [m.preprocess(m.read_gray(p)) for p, _ in rows]
    texts = [t for _, t in rows]
    return Split(images, texts, [charset.encode(t) for t in texts])


# ---------------------------------------------------------------- évaluation


def evaluate(model: Any, split: Split, charset: m.Charset) -> dict[str, Any]:
    hyps = m.predict(model, split.images, charset)
    out: dict[str, Any] = {
        "cer": metrics.cer(split.texts, hyps),
        "wer": metrics.wer(split.texts, hyps),
        "exact": metrics.exact_match(split.texts, hyps),
        "n": len(split.texts),
    }
    for lang in ("fr", "ar", "mixte"):
        idx = [i for i, t in enumerate(split.texts) if line_language(t) == lang]
        if idx:
            refs = [split.texts[i] for i in idx]
            sub = [hyps[i] for i in idx]
            out[f"cer_{lang}"] = metrics.cer(refs, sub)
            out[f"wer_{lang}"] = metrics.wer(refs, sub)
            out[f"n_{lang}"] = len(idx)
    out["examples"] = [{"ref": split.texts[i], "hyp": hyps[i]} for i in range(min(8, len(hyps)))]
    return out


def min_ctc_steps(label: list[int]) -> int:
    """Pas de temps minimum pour qu'un alignement CTC existe (un blanc entre deux symboles répétés)."""
    return len(label) + sum(1 for a, b in itertools.pairwise(label) if a == b)


def forward(model: Any, split: Split, idx: list[int], feats: list[Any] | None) -> tuple[Any, list[int]]:
    """Logits [N, T, C] et longueurs utiles. Avec `feats` (Transfer Learning), seule la tête est calculée."""
    if feats is not None:
        lengths = [len(feats[i]) for i in idx]
        x = np.zeros((len(idx), max(lengths), feats[idx[0]].shape[1]), dtype=np.float32)
        for k, i in enumerate(idx):
            x[k, : lengths[k]] = feats[i]
        return model.head.ctc_head.fc(paddle.to_tensor(x)), lengths
    images = [split.images[i] for i in idx]
    return m.ctc_logits(model, paddle.to_tensor(m.make_batch(images))), [m.seq_len(im) for im in images]


def ctc_loss(logits: Any, lengths: list[int], labels: list[list[int]], ctc: Any) -> Any:
    max_len = max(len(lab) for lab in labels)
    padded = np.zeros((len(labels), max_len), dtype=np.int32)
    for k, lab in enumerate(labels):
        padded[k, : len(lab)] = lab
    log_probs = logits.transpose([1, 0, 2])  # [T, N, C] ; le softmax est appliqué dans la perte (warpctc)
    t = paddle.to_tensor(np.array(lengths, dtype=np.int64))
    n = paddle.to_tensor(np.array([len(lab) for lab in labels], dtype=np.int64))
    return ctc(log_probs, paddle.to_tensor(padded), t, n).mean()


def eval_pass(model: Any, split: Split, charset: m.Charset, ctc: Any, feats: list[Any] | None,
              batch_size: int = 64) -> tuple[float, list[str]]:
    """Une seule passe sur un split : perte CTC moyenne et textes reconnus (ordre logique)."""
    model.eval()
    hyps = [""] * len(split.texts)
    total = 0.0
    order = sorted(range(len(split.texts)), key=lambda i: split.images[i].shape[2])
    with paddle.no_grad():
        for s in range(0, len(order), batch_size):
            idx = order[s : s + batch_size]
            logits, lengths = forward(model, split, idx, feats)
            total += float(ctc_loss(logits, lengths, [split.labels[i] for i in idx], ctc)) * len(idx)
            ids = logits.argmax(axis=2).numpy()
            for k, i in enumerate(idx):
                hyps[i] = m.to_logical(charset.greedy_decode(ids[k][: lengths[k]].tolist()))
    return total / max(1, len(order)), hyps


# ---------------------------------------------------------------- entraînement


def _opt_name_map(model: Any) -> dict[str, str]:
    """Nom interne Paddle d'un paramètre (« conv2d_131.w_0 », change d'un processus à l'autre) -> nom
    structurel (« backbone.conv1.conv.weight », stable)."""
    return {p.name: name for name, p in model.named_parameters()}


def opt_state_portable(opt: Any, model: Any) -> dict[str, Any]:
    """État de l'optimiseur avec des clés stables, rechargeable dans un autre processus."""
    names = sorted(_opt_name_map(model).items(), key=lambda kv: -len(kv[0]))
    out: dict[str, Any] = {}
    for key, value in opt.state_dict().items():
        for internal, structural in names:
            if key.startswith(internal + "_"):
                out["@" + structural + key[len(internal):]] = value
                break
        else:
            out[key] = value  # ex. LR_Scheduler
    return out


def opt_state_local(state: dict[str, Any], model: Any) -> dict[str, Any]:
    """Inverse de `opt_state_portable` pour le modèle de ce processus."""
    names = sorted(((s, i) for i, s in _opt_name_map(model).items()), key=lambda kv: -len(kv[0]))
    out: dict[str, Any] = {}
    for key, value in state.items():
        if key.startswith("@"):
            for structural, internal in names:
                if key[1:].startswith(structural + "_"):
                    out[internal + key[1 + len(structural):]] = value
                    break
            else:
                raise KeyError(f"Paramètre inconnu dans le point de sauvegarde : {key}")
        else:
            out[key] = value
    return out


def stage_label(stage: str, ft_variant: str) -> str:
    """« transfer », ou « finetune_bn_frozen » / « finetune_partial » : chaque variante a ses propres fichiers."""
    return f"{stage}_{ft_variant}" if stage == "finetune" else stage


def train_stage(
    stage: m.Stage, model: Any, train: Split, val: Split, charset: m.Charset, *, epochs: int, lr: float,
    batch_size: int, seed: int, warmup_epochs: int, budget_s: float, ckpt_dir: Path, best_dir: Path,
    ft_variant: m.FtVariant = "bn_frozen",
) -> dict[str, Any]:
    """Transfer Learning (tête seule, sur les sorties pré-calculées de l'encodeur gelé) ou Fine-Tuning.

    Point de sauvegarde à la fin de chaque époque (poids, optimiseur, scheduler, meilleur état, historique) :
    après un plantage de Paddle, la relance repart de la dernière époque terminée. L'ordre des lots dépend
    seulement de (graine, époque), donc une époque reprise est identique à une époque non interrompue.
    """
    start = time.perf_counter()
    label = stage_label(stage, ft_variant)  # nom des fichiers de sauvegarde et des messages
    params = m.configure_stage(model, stage, ft_variant)
    feats_train = feats_val = None
    if stage == "transfer":
        # L'encodeur est gelé et en mode évaluation : ses sorties ne changent pas pendant l'entraînement.
        # Les calculer une fois donne exactement le même résultat, beaucoup plus vite sur CPU.
        print("  calcul des sorties de l'encodeur gelé (une seule fois)…", flush=True)
        feats_train = m.encoder_features(model, train.images)
        feats_val = m.encoder_features(model, val.images)
    steps = [len(lab) for lab in train.labels]
    usable = [i for i in range(len(train.texts))
              if min_ctc_steps(train.labels[i]) <= m.seq_len(train.images[i]) and steps[i] > 0]
    steps_per_epoch = max(1, (len(usable) + batch_size - 1) // batch_size)
    sched: Any = paddle.optimizer.lr.CosineAnnealingDecay(learning_rate=lr, T_max=max(1, epochs * steps_per_epoch))
    if warmup_epochs > 0:
        sched = paddle.optimizer.lr.LinearWarmup(sched, warmup_steps=warmup_epochs * steps_per_epoch,
                                                start_lr=lr / 10, end_lr=lr)
    opt = paddle.optimizer.Adam(learning_rate=sched, parameters=params)
    ctc = paddle.nn.CTCLoss(blank=0, reduction="none")
    sub_images = [train.images[i] for i in usable]

    ckpt_dir.mkdir(parents=True, exist_ok=True)
    progress_path = ckpt_dir / f"{label}_progress.json"
    last_model, last_opt, best_path = (ckpt_dir / f"{label}_last.pdparams", ckpt_dir / f"{label}_last.pdopt",
                                       ckpt_dir / f"{label}_best.pdparams")
    history: dict[str, list[float]]
    if progress_path.exists() and last_model.exists() and last_opt.exists():
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
        history, first_epoch = progress["history"], progress["epoch"] + 1
        best_cer, best_epoch, elapsed_before = progress["best_cer"], progress["best_epoch"], progress["elapsed_s"]
        model.set_state_dict(paddle.load(str(last_model)))
        opt_state = paddle.load(str(last_opt))
        opt.set_state_dict(opt_state_local(opt_state["optimizer"], model))
        sched.set_state_dict(opt_state["scheduler"])
        print(f"  [{label}] reprise après l'époque {progress['epoch']} (point de sauvegarde)", flush=True)
    else:
        history = {"train_loss": [], "val_loss": [], "val_cer": [], "epoch_s": []}
        v_loss, v_hyps = eval_pass(model, val, charset, ctc, feats_val)
        history["epoch0_val_loss"] = [v_loss]
        history["epoch0_val_cer"] = [metrics.cer(val.texts, v_hyps)]
        best_cer, best_epoch, first_epoch, elapsed_before = history["epoch0_val_cer"][0], 0, 1, 0.0
        paddle.save(model.state_dict(), str(best_path))  # meilleur état initial : les poids pré-entraînés
    for epoch in range(first_epoch, epochs + 1):
        if elapsed_before + time.perf_counter() - start > budget_s:
            print(f"  [{label}] budget de temps atteint avant l'époque {epoch} : arrêt.", flush=True)
            break
        t0 = time.perf_counter()
        m.set_train_mode(model, stage)
        losses = []
        rng = np.random.default_rng([seed, epoch])
        for group in m.width_batches(sub_images, batch_size, rng):
            idx = [usable[j] for j in group]
            logits, lengths = forward(model, train, idx, feats_train)
            loss = ctc_loss(logits, lengths, [train.labels[i] for i in idx], ctc)
            loss.backward()
            opt.step()
            opt.clear_grad()
            sched.step()
            losses.append(float(loss))
        v_loss, v_hyps = eval_pass(model, val, charset, ctc, feats_val)
        cer = metrics.cer(val.texts, v_hyps)
        history["train_loss"].append(float(np.mean(losses)))
        history["val_loss"].append(v_loss)
        history["val_cer"].append(cer)
        history["epoch_s"].append(time.perf_counter() - t0)
        print(f"  [{label}] époque {epoch}/{epochs}  loss {history['train_loss'][-1]:.3f}  "
              f"val_loss {v_loss:.3f}  val_CER {cer:.4f}  ({history['epoch_s'][-1]:.0f} s)", flush=True)
        if cer < best_cer:
            best_cer, best_epoch = cer, epoch
            paddle.save(model.state_dict(), str(best_path))
        # point de sauvegarde (écrit d'abord les poids, puis le fichier de progression qui les valide)
        paddle.save(model.state_dict(), str(last_model))
        paddle.save({"optimizer": opt_state_portable(opt, model), "scheduler": sched.state_dict()}, str(last_opt))
        progress_path.write_text(json.dumps({
            "epoch": epoch, "history": history, "best_cer": best_cer, "best_epoch": best_epoch,
            "elapsed_s": elapsed_before + time.perf_counter() - start,
        }), encoding="utf-8")
    model.set_state_dict(paddle.load(str(best_path)))
    paddle.save(model.state_dict(), str(best_dir / f"{label}_best.pdparams"))  # build/quick/ pour --quick
    return {
        "history": history, "best_epoch": best_epoch, "best_val_cer": best_cer,
        "trainable_params": m.count_params(params), "lr": lr, "epochs_run": len(history["train_loss"]),
        "train_lines_used": len(usable), "train_s": elapsed_before + time.perf_counter() - start,
    }


# ---------------------------------------------------------------- sorties


def plot(results: dict[str, Any], out: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"transfer": "#2a78d6", "finetune": "#eb6834"}  # palette catégorielle validée, emplacements 1 et 2
    names = {"transfer": "Transfer Learning (tête seule)",
             "finetune": f"Fine-Tuning ({results['finetune'].get('variant', '?')}, LR faible)"}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), facecolor="#fcfcfb")
    for ax in axes:
        ax.set_facecolor("#fcfcfb")
        ax.grid(True, color="#e5e4e0", linewidth=0.8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines[["left", "bottom"]].set_color("#9a9994")
        ax.tick_params(colors="#52514e")
    for stage in ("transfer", "finetune"):
        h = results[stage]["history"]
        ep = list(range(1, len(h["train_loss"]) + 1))
        axes[0].plot(ep, h["train_loss"], color=colors[stage], linewidth=2, marker="o", markersize=5,
                     label=f"{names[stage]} — train")
        axes[0].plot(ep, h["val_loss"], color=colors[stage], linewidth=2, linestyle="--",
                     label=f"{names[stage]} — validation")
        cer_curve = h["epoch0_val_cer"] + h["val_cer"]  # époque 0 = avant entraînement
        axes[1].plot(list(range(len(cer_curve))), [100 * c for c in cer_curve], color=colors[stage], linewidth=2,
                     marker="o", markersize=5, label=names[stage])
    axes[1].axhline(100 * results["baseline"]["val"]["cer"], color="#7a7974", linewidth=1.5, linestyle=":",
                    label="Baseline (sans entraînement)")
    axes[0].set_title("Perte CTC par époque", color="#0b0b0b", loc="left")
    axes[1].set_title("CER de validation (%) par époque", color="#0b0b0b", loc="left")
    for ax in axes:
        ax.set_xlabel("Époque", color="#52514e")
        ax.legend(frameon=False, fontsize=8, labelcolor="#0b0b0b")
    axes[0].set_ylabel("Perte CTC", color="#52514e")
    axes[1].set_ylabel("CER (%)", color="#52514e")
    axes[1].set_ylim(bottom=0)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def pct(x: float) -> str:
    return f"{100 * x:.2f} %"


def write_markdown(results: dict[str, Any], out: Path) -> None:
    variant = results["finetune"].get("variant", "?")
    variant_text = results["finetune"].get("variant_description", variant)
    rows = [("Baseline (pré-entraîné, sans entraînement)", "baseline"),
            ("Transfer Learning (encodeur gelé, tête entraînée)", "transfer"),
            (f"Fine-Tuning, variante `{variant}` (LR faible)", "finetune")]
    cfg = results["config"]
    lines = [
        "# Résultats : Transfer Learning vs Fine-Tuning (arabic_PP-OCRv5_mobile_rec)",
        "",
        "Fichier généré automatiquement par `run_experiment.py` : uniquement des chiffres mesurés.",
        "",
        (
            f"- Données FICTIVES : train {cfg['sizes']['train']}, val {cfg['sizes']['val']}, "
            f"test {cfg['sizes']['test']}, generic (hors domaine) {cfg['sizes']['generic']} lignes ; "
            f"graine {cfg['seed']}."
        ),
        (
            f"- Machine : {cfg['machine']}, CPU seulement ; durée totale {results['total_s'] / 60:.1f} min "
            "(reprises après plantage comprises)."
        ),
        (
            f"- **Variante de Fine-Tuning qui a produit le chiffre : `{variant}`** — {variant_text}. "
            "Voir ANALYSE.md (plantage natif de Paddle pendant le Fine-Tuning complet)."
        ),
        "",
        "## Jeu de test (domaine : fiches de paie et conventions, FR + AR)",
        "",
        "| Méthode | CER | WER | Lignes exactes | CER FR | CER AR | CER mixte | Paramètres entraînés | Époques (meilleure) | Durée |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for label, key in rows:
        r = results[key]["test"]
        info = results.get(key, {})
        params = f"{info['trainable_params']:,}".replace(",", " ") if "trainable_params" in info else "0"
        epochs = f"{info['epochs_run']} ({info['best_epoch']})" if "epochs_run" in info else "—"
        dur = f"{info['train_s'] / 60:.1f} min" if "train_s" in info else "—"
        lines.append(
            f"| {label} | {pct(r['cer'])} | {pct(r['wer'])} | {pct(r['exact'])} | {pct(r.get('cer_fr', 0))} | "
            f"{pct(r.get('cer_ar', 0))} | {pct(r.get('cer_mixte', 0))} | {params} | {epochs} | {dur} |"
        )
    lines += [
        "",
        "## Oubli : jeu « generic » (phrases hors domaine, jamais vues à l'entraînement)",
        "",
        "| Méthode | CER generic | WER generic |",
        "|---|---|---|",
    ]
    for label, key in rows:
        g = results[key]["generic"]
        lines.append(f"| {label} | {pct(g['cer'])} | {pct(g['wer'])} |")
    lines += ["", "## Exemples (test)", "", "| Référence | Baseline | Transfer | Fine-Tuning |", "|---|---|---|---|"]
    for i in range(len(results["baseline"]["test"]["examples"])):
        cells = [results["baseline"]["test"]["examples"][i]["ref"]] + [
            results[k]["test"]["examples"][i]["hyp"] for k in ("baseline", "transfer", "finetune")
        ]
        lines.append("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")
    lines += ["", "Courbes : `loss_curves.png`. Détails complets : `results.json`.", ""]
    out.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seed", type=int, default=42)
    # Tailles choisies pour le CPU : le backbone PPLCNetV3 de Paddle met ~12 s par lot de 32 images
    # (mesuré, avec ou sans oneDNN). Le Fine-Tuning, qui recalcule le backbone à chaque pas, fixe le budget.
    p.add_argument("--n-train", type=int, default=1200)
    p.add_argument("--n-val", type=int, default=200)
    p.add_argument("--n-test", type=int, default=400)
    p.add_argument("--n-generic", type=int, default=150)
    p.add_argument("--epochs-tl", type=int, default=15)
    p.add_argument("--epochs-ft", type=int, default=4)
    p.add_argument("--lr-tl", type=float, default=1e-3)
    p.add_argument("--lr-ft", type=float, default=1e-4)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--budget-min", type=float, default=150.0, help="Budget total d'entraînement (minutes).")
    p.add_argument("--out", type=Path, default=HERE, help="Dossier où écrire results.* et loss_curves.png.")
    p.add_argument("--quick", action="store_true", help="Essai rapide (petits jeux, 1 époque) pour vérifier la chaîne.")
    p.add_argument("--fresh", action="store_true", help="Ignore les étapes déjà terminées et recommence tout.")
    p.add_argument("--ft-variant", choices=sorted(m.FT_VARIANTS), default="bn_frozen",
                   help="Variante de Fine-Tuning : bn_frozen (tout dégelé sauf BatchNorm) ou partial (plan B).")
    p.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)  # processus lancé par le superviseur
    a = p.parse_args(argv)
    if a.quick:
        a.n_train, a.n_val, a.n_test, a.n_generic, a.epochs_tl, a.epochs_ft = 64, 32, 32, 16, 2, 2

    # Dossier d'état propre à cette configuration : résultats de chaque étape terminée + points de sauvegarde.
    # La variante de Fine-Tuning n'entre pas dans la clé : baseline et Transfer Learning restent partagés,
    # et chaque variante a ses propres fichiers (finetune_<variante>_*).
    key = {k: v for k, v in vars(a).items() if k not in ("out", "worker", "fresh", "budget_min", "ft_variant")}
    tag = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()[:10]
    # --quick écrit tout dans build/quick/ : il n'écrase jamais l'état ni les poids de l'expérience complète.
    dirs = run_paths(BUILD, quick=a.quick, seed=a.seed, tag=tag, out=a.out)
    a.out = dirs.out
    a.out.mkdir(parents=True, exist_ok=True)
    dirs.work.mkdir(parents=True, exist_ok=True)
    state_dir = dirs.state
    # --fresh : on efface l'état à la première tentative seulement ; une relance après plantage doit reprendre.
    if a.fresh and state_dir.exists() and os.environ.get("OCR_EXP_ATTEMPT", "1") == "1":
        shutil.rmtree(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    run_info_path = state_dir / "run.json"
    if not run_info_path.exists():
        run_info_path.write_text(json.dumps({"started_at": time.time(), "config": key}), encoding="utf-8")
    started_at = float(json.loads(run_info_path.read_text(encoding="utf-8"))["started_at"])

    def saved(stage: str) -> dict[str, Any] | None:
        path = state_dir / f"{stage}_result.json"
        return dict(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else None

    def save(stage: str, info: dict[str, Any]) -> None:
        (state_dir / f"{stage}_result.json").write_text(json.dumps(info, ensure_ascii=False, default=str),
                                                        encoding="utf-8")

    paddle.set_device("cpu")
    set_seed(a.seed)
    ensure_ppocr()
    ensure_weights()
    charset = m.Charset(PPOCR_ROOT / m.DICT_REL)

    sizes = {"train": a.n_train, "val": a.n_val, "test": a.n_test, "generic": a.n_generic}
    data_dir = dirs.data
    print("1/5 Génération des données fictives…", flush=True)
    manifest = data_gen.generate(data_dir, a.seed, sizes, charset.known)
    splits = {name: load(data_dir, name, charset) for name in data_gen.SPLITS}

    results: dict[str, Any] = {
        "config": {**vars(a), "out": str(a.out), "sizes": sizes, "manifest": manifest,
                   "machine": f"{platform.processor() or platform.machine()} ({os.cpu_count()} threads)",
                   "paddle": paddle.__version__, "ppocr_tag": PPOCR_TAG, "model": "arabic_PP-OCRv5_mobile_rec",
                   "cpu_flags": {k: os.environ.get(k, "défaut") for k in ("FLAGS_use_mkldnn", "MKL_NUM_THREADS",
                                                                         "OMP_NUM_THREADS")}},
    }

    print("2/5 Baseline (modèle pré-entraîné, sans entraînement)…", flush=True)
    done = saved("baseline")
    if done is None:
        base = m.build(PPOCR_ROOT, WEIGHTS, charset)
        done = {k: evaluate(base, splits[k], charset) for k in ("val", "test", "generic")}
        save("baseline", done)
        del base
    else:
        print("  (déjà mesurée : résultat repris)", flush=True)
    results["baseline"] = done
    print(f"  baseline : CER test {pct(results['baseline']['test']['cer'])}", flush=True)
    budget_s = a.budget_min * 60

    plan: list[tuple[m.Stage, int, float, int]] = [
        ("transfer", a.epochs_tl, a.lr_tl, 0),
        ("finetune", a.epochs_ft, a.lr_ft, 1),
    ]
    for stage, epochs, lr, warmup in plan:
        step = "3/5 Transfer Learning" if stage == "transfer" else "4/5 Fine-Tuning"
        print(f"{step}…", flush=True)
        label = stage_label(stage, a.ft_variant)
        info = saved(label)
        if info is None:
            set_seed(a.seed)
            net = m.build(PPOCR_ROOT, WEIGHTS, charset)  # chaque méthode repart des poids pré-entraînés
            # budget : temps d'entraînement de cette étape (reprises comprises)
            stage_budget = budget_s * (0.25 if stage == "transfer" else 0.75)
            info = train_stage(stage, net, splits["train"], splits["val"], charset, epochs=epochs, lr=lr,
                               batch_size=a.batch_size, seed=a.seed, warmup_epochs=warmup,
                               budget_s=max(60.0, stage_budget), ckpt_dir=state_dir, best_dir=dirs.work,
                               ft_variant=a.ft_variant)
            info.update({k: evaluate(net, splits[k], charset) for k in ("val", "test", "generic")})
            if stage == "finetune":
                info["variant"] = a.ft_variant
                info["variant_description"] = m.FT_VARIANTS[a.ft_variant]
            save(label, info)
            del net
        else:
            print("  (déjà entraîné et évalué : résultat repris)", flush=True)
        results[stage] = info
        print(f"  {stage} : CER test {pct(info['test']['cer'])}", flush=True)

    print("5/5 Écriture des résultats…", flush=True)
    results["total_s"] = time.time() - started_at  # durée réelle, reprises après plantage comprises
    results["restarts"] = int(os.environ.get("OCR_EXP_ATTEMPT", "1")) - 1
    (a.out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str),
                                        encoding="utf-8")
    write_markdown(results, a.out / "results.md")
    plot(results, a.out / "loss_curves.png")
    print(f"Terminé en {results['total_s'] / 60:.1f} min -> {a.out / 'results.md'}")


if __name__ == "__main__":
    main()
