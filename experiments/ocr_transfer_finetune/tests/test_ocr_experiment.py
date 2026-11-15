"""Tests rapides de l'expérience (sans Paddle) : métriques, ordre RTL, générateur déterministe."""

from __future__ import annotations

import random

import data_gen
import metrics
import numpy as np
import pytest
import vocab
from rtl import flip_rtl


def test_cer_and_wer_basic() -> None:
    assert metrics.cer(["abcd"], ["abcd"]) == 0.0
    assert metrics.cer(["abcd"], ["abxd"]) == pytest.approx(0.25)
    assert metrics.cer(["ab", "cd"], ["", "cd"]) == pytest.approx(0.5)  # corpus : 2 erreurs / 4 caractères
    assert metrics.wer(["Salaire de base 424.100"], ["Salaire de base 424.10"]) == pytest.approx(0.25)
    assert metrics.exact_match(["a", "b"], ["a", "c"]) == 0.5


def test_normalization_ignores_extra_spaces() -> None:
    assert metrics.cer(["الأجر الأساسي"], ["الأجر  الأساسي "]) == 0.0


def test_levenshtein() -> None:
    assert metrics.levenshtein("kitten", "sitting") == 3
    assert metrics.levenshtein("", "abc") == 3


@pytest.mark.parametrize(
    "text",
    ["الضريبة على الدخل : 2613.193 د", "الأجر الأساسي Prime de présence", "Salaire de base 424.100", "الصنف 2"],
)
def test_flip_rtl_is_an_involution(text: str) -> None:
    assert flip_rtl(flip_rtl(text)) == text


def test_flip_rtl_matches_visual_order_of_pretrained_model() -> None:
    # Sortie brute observée des poids pré-entraînés sur « الضريبة على الدخل » : « لخدلا ىلع ةبيرضلا ».
    assert flip_rtl("الضريبة على الدخل") == "لخدلا ىلع ةبيرضلا"
    # Les montants et les mots français restent des blocs lisibles de gauche à droite.
    assert flip_rtl("الصنف 3 : 424.100") == " 3 : 424.100فنصلا"
    assert "424.100" in flip_rtl("الأجر 424.100")
    assert flip_rtl("Catégorie 3") == "Catégorie 3"


def test_domain_lines_are_short_and_bilingual() -> None:
    rng = random.Random(0)
    lines = [vocab.domain_line(rng) for _ in range(300)]
    assert all(len(t) <= vocab.MAX_LEN for t in lines)
    assert any(any("؀" <= c <= "ۿ" for c in t) for t in lines)
    assert any(t.isascii() or "é" in t for t in lines)


def test_amount_format() -> None:
    rng = random.Random(1)
    for _ in range(50):
        integer, decimals = vocab.amount(rng).split(".")
        assert integer.isdigit() and len(decimals) == 3


def test_make_texts_is_deterministic_and_filters_unknown_chars() -> None:
    charset = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .:/-'éèàâôûçÉ")
    charset |= {chr(c) for c in range(0x0600, 0x0700)}
    sizes = {"train": 20, "val": 5, "test": 5, "generic": 4}
    a, rej_a = data_gen.make_texts(7, sizes, charset, ["arial.ttf"])
    b, rej_b = data_gen.make_texts(7, sizes, charset, ["arial.ttf"])
    assert a == b and rej_a == rej_b
    assert all(set(s.text) <= charset for s in a)
    assert [s.split for s in a].count("train") == 20
    tiny, rejected = data_gen.make_texts(7, {"train": 3}, charset - {"e"}, ["arial.ttf"])
    assert len(tiny) == 3 and all("e" not in s.text for s in tiny) and rejected >= 0


@pytest.mark.skipif(not (data_gen.FONT_DIR / "arial.ttf").exists(), reason="polices Windows absentes")
def test_rendering_is_deterministic() -> None:
    sample = data_gen.Sample("test", 3, "الأجر الأساسي 424.100", "arial.ttf")
    one, two = data_gen.render_sample(sample, 42), data_gen.render_sample(sample, 42)
    assert one.dtype == np.uint8 and one.ndim == 2 and one.shape[1] > one.shape[0]
    assert np.array_equal(one, two)
    other = data_gen.render_sample(data_gen.Sample("test", 4, sample.text, "arial.ttf"), 42)
    assert not np.array_equal(one, other) or one.shape != other.shape
