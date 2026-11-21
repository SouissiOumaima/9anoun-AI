"""L'essai rapide (--quick) ne doit jamais écraser les poids ni l'état de l'expérience complète (sans Paddle)."""

from __future__ import annotations

from pathlib import Path

from run_paths import run_paths

HERE = Path(__file__).resolve().parents[1]


def test_quick_run_writes_everything_under_build_quick(tmp_path: Path) -> None:
    build = tmp_path / "build"
    quick = run_paths(build, quick=True, seed=42, tag="q1", out=HERE)
    for path in (quick.work, quick.state, quick.data, quick.out):
        assert path.is_relative_to(build / "quick"), path
    full = run_paths(build, quick=False, seed=42, tag="f1", out=HERE)
    # les meilleurs poids de l'essai rapide ne tombent jamais sur ceux de l'expérience complète
    label = "finetune_bn_frozen_best.pdparams"
    assert quick.work / label != full.work / label
    assert not quick.state.is_relative_to(build / "state")
    assert not quick.data.is_relative_to(full.data)


def test_full_run_keeps_its_former_paths_so_finished_steps_are_reused(tmp_path: Path) -> None:
    build = tmp_path / "build"
    full = run_paths(build, quick=False, seed=42, tag="f14bc986b9", out=HERE)
    assert full.work == build
    assert full.state == build / "state" / "seed42_f14bc986b9"
    assert full.data == build / "data" / "seed42"
    assert full.out == HERE


def test_run_experiment_never_writes_best_weights_straight_into_build() -> None:
    source = (HERE / "run_experiment.py").read_text(encoding="utf-8")
    assert 'BUILD / f"{label}_best' not in source  # ancien chemin, partagé avec --quick
    assert 'best_dir / f"{label}_best' in source and "best_dir=dirs.work" in source
    assert "state_dir = dirs.state" in source and "data_dir = dirs.data" in source
