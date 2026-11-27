"""Etape A : un numero cite dans une note n'est un avenant que si la note le dit.

POURQUOI CE TEST EXISTE. Les notes de bas de page de l'archive citent des
avenants, des decrets et des lois sous la meme forme « عدد <n> » : seul le mot
qui precede dit ce que le numero designe. Un decret pris pour un avenant donne
une date fausse, et une date fausse accompagnee d'une citation d'article est le
pire cas pour un assistant juridique.

Le second risque est la date perimee : la date d'un avenant n'est celle du texte
courant que si rien d'inconnu ne l'a modifie ensuite. Perdre une date est
acceptable, en inventer une ne l'est pas ; et une date gardee malgre une
mention qu'on n'a pas su lire doit le dire dans son origine.

Aucun corpus n'est lu : chaque note est ecrite a la main.
"""

from __future__ import annotations

import json
import re
from datetime import date

import pytest

from src.legal_retrieval.corpus.ingest_archive import (
    avenants_cites,
    date_effet,
    lire_condense,
    releve_mentions,
)

CONVENTION = {"signed_date": "1977-03-01"}
INDEX = {n: {"effective_date": f"20{10 + n:02d}-05-01"} for n in range(1, 13)}
ARABE = re.compile(r"[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]")


# ------------------------------------------------- criteres A1 a A8

@pytest.mark.parametrize("notes, attendu", [
    (["نقح بالملحق التعديلي عدد 7"], [7]),                               # A1
    (["نقح بالملحق التعديلي عدد 7 ثم عدد 8 ثم عدد 9"], [7, 8, 9]),       # A2
    (["بالملحق التعديلي عدد4"], [4]),                                    # A3
    (["الملحق التعديلي عدد 3"], [3]),                                    # A4
    (["نقح بالمرسوم عدد 11"], []),                                       # A5
    (["نقح بالمرسوم عدد 11 ثم عدد 12"], []),                             # A6
    (["بالملحق التعديلي عدد 5 ثم بالمرسوم عدد 11"], [5]),                # A7
    (None, []),                                                          # A8
    ([], []),                                                            # A8
    (["ألغي هذا الفصل"], []),                                            # A8
    (["بالملحق التعديلي عدد 1 و عدد 3"], [1, 3]),
], ids=["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8-none", "A8-vide",
        "A8-sans-adad", "continuation-wa"])
def test_criteres_etape_a(notes, attendu):
    assert avenants_cites(notes) == attendu


# ---------------------------------------- graphies relevees sur la livraison

# Une par forme relevee dans la livraison. La regle (graphie de ملحق suivie de la racine
# تعديل) doit les engendrer sans liste de cas particuliers.
@pytest.mark.parametrize("note", [
    "نقح بالمحلق التعديلي عدد 6",
    "نقح بالملاحق التعديلية عدد 6",
    "نقح بالملحق لتعديلي عدد 6",
    "نقح بالملحقين التعديليين عدد 6",
    "بمقتضى الملحقين التعديليين عدد 6",
    "نقح بالملحقات التعديلية عدد 6",
    "نقح بالملحق التعديل عدد 6",
    "نقح بالقرار التحكيمي وبالملحق التعديلي عدد 6",
    "نقح وبالملحق التعديلي عدد 6",
    "نقح بالمحق التعديلي عدد 6",
    "نقح بالملح التعديلي عدد 6",
    "نقح باملحق التعديلي عدد 6",
])
def test_graphies_engendrees_par_la_regle(note):
    assert avenants_cites([note]) == [6]


def test_taadil_sans_mulhaq_non_retenu_et_signale():
    """تعديل seul ne fait pas un avenant : l'alarme signale une graphie inconnue."""
    assert avenants_cites(["نقح بالقرار التعديلي عدد 6"]) == []
    [m] = releve_mentions(["نقح بالقرار التعديلي عدد 6"])
    assert (m.nature, m.alarme, m.mulhaq, m.taadil) == (
        "non_reconnue", "taadil_sans_mulhaq", False, True)


def test_annexe_sans_taadil_non_retenue_et_signalee():
    """ملحق non suivi de تعديل designe une annexe, pas un avenant : « الملحق عدد 4 »
    de la grille du BTP est l'annexe n° 4."""
    assert avenants_cites(["نقح بالملحق عدد 4"]) == []
    [m] = releve_mentions(["نقح بالملحق عدد 4"])
    assert (m.nature, m.alarme, m.mulhaq, m.taadil) == (
        "non_reconnue", "mulhaq_sans_taadil", True, False)


@pytest.mark.parametrize("note, nature", [
    ("نقح بالمرسوم عدد 11", "decret"),
    ("المؤرخ في 2011 مرسوم عدد 11", "decret"),
    ("بالقرار والمرسوم عدد 11", "decret"),
    ("نقح هذا الفصل بالقانون عدد 11", "loi"),
    ("من الفصل الرابع من القانون عدد 11", "loi"),
])
def test_decrets_et_lois_reconnus_puis_exclus(note, nature):
    assert avenants_cites([note]) == []
    assert [m.nature for m in releve_mentions([note])] == [nature]   # reconnue, pas comptee


def test_marqueur_le_plus_proche_l_emporte():
    assert avenants_cites(["نقح بالمرسوم المؤرخ ثم بالملحق التعديلي عدد 5"]) == [5]
    assert avenants_cites(["نقح بالملحق التعديلي المصادق عليه بالقانون عدد 5"]) == []


# ------------------------------------------------------- continuations

def test_continuation_en_tete_de_note_sans_marqueur_non_reconnue():
    """Le type courant ne traverse pas d'une note a l'autre."""
    assert avenants_cites(["بالملحق التعديلي عدد 1", "ثم عدد 2"]) == [1]
    m = releve_mentions(["بالملحق التعديلي عدد 1", "ثم عدد 2"])[1]
    assert (m.nature, m.suite, m.mulhaq) == ("non_reconnue", True, False)


@pytest.mark.parametrize("note", [
    "نقح بالملحق التعديلي ثم عدد 6",
    "نقح بالملحق التعديلي و عدد 6",
])
def test_continuation_dont_le_segment_porte_un_marqueur(note):
    """Le marqueur du segment decide ; l'heritage ne vaut que sans marqueur."""
    assert avenants_cites([note]) == [6]
    [m] = releve_mentions([note])
    assert (m.nature, m.suite) == ("avenant", True)


def test_continuation_sans_marqueur_herite_du_decret():
    """A6 : le segment du 12 est « ثم » seul, il herite donc du decret."""
    assert [(m.nature, m.suite) for m in releve_mentions(["نقح بالمرسوم عدد 11 ثم عدد 12"])] == [
        ("decret", False), ("decret", True)]


def test_marqueur_au_milieu_de_la_note_requalifie_la_continuation():
    mentions = releve_mentions(["بالملحق التعديلي عدد 5 المصادق عليه بالقانون ثم عدد 6"])
    assert [(m.numero, m.nature, m.suite) for m in mentions] == [
        (5, "avenant", False), (6, "loi", True)]


def test_continuations_non_reconnues_typees():
    mentions = releve_mentions(["نقح بالملحق عدد 4 ثم عدد 5 و عدد 6"])
    assert [(m.nature, m.suite) for m in mentions] == [
        ("non_reconnue", False), ("non_reconnue", True), ("non_reconnue", True)]


def test_une_mention_ne_porte_aucun_texte():
    """Le rapport est versionne : seuls des nombres, des booleens et des codes
    ASCII peuvent en sortir."""
    for m in releve_mentions(["كلمات اولى ثاني ثالث رابع خامس نقح بالملحق عدد 4 ثم عدد 5"]):
        for valeur in m:
            assert valeur is None or isinstance(valeur, (bool, int)) or (
                isinstance(valeur, str) and valeur.isascii())


# ------------------------------------------------------- critere de surete

def test_mentions_toutes_non_reconnues_ne_donnent_pas_la_date_de_convention():
    assert date_effet(["نقح بالملحق عدد 4 ثم عدد 5"], INDEX, CONVENTION) == (
        None, "mentions_non_reconnues")


@pytest.mark.parametrize("notes", [None, [], ["ألغي هذا الفصل"]])
def test_note_sans_mention_donne_la_date_de_convention(notes):
    assert date_effet(notes, INDEX, CONVENTION) == (date(1977, 3, 1), "convention")


@pytest.mark.parametrize("note, origine", [
    ("نقح بالمرسوم عدد 11", "decret"),                     # A5
    ("نقح بالمرسوم عدد 11 ثم عدد 12", "decret"),           # A6
    ("نقح هذا الفصل بالقانون عدد 11", "loi"),
])
def test_decret_ou_loi_seul_ne_donne_pas_la_date_de_convention(note, origine):
    assert date_effet([note], INDEX, CONVENTION) == (None, origine)


@pytest.mark.parametrize("notes", [
    ["نقح بالملحق التعديلي عدد 3 ثم بالملحق عدد 5"],
    ["نقح بالملحق التعديلي عدد 3 عدد 5"],
    ["بالملحق التعديلي عدد 3", "ثم عدد 5"],                # dans la note suivante
    ["بالملحق التعديلي عدد 3 ثم بالمرسوم عدد 11 ثم بالملحق عدد 5"],
])
def test_mention_non_reconnue_apres_le_dernier_avenant_retire_la_date(notes):
    """On ignore ce qui a modifie l'article apres l'avenant 3 : sa date est perimee."""
    assert date_effet(notes, INDEX, CONVENTION) == (None, "mention_non_reconnue_posterieure")


def test_mention_non_reconnue_avant_le_dernier_avenant_garde_la_date_marquee():
    """Un avenant reconnu plus loin, meme dans une autre note, fixe la date. Mais
    l'ordre du texte n'est pas l'ordre chronologique : la mention qu'on n'a pas su
    lire peut designer un avenant plus recent, donc la date ne sort pas nue."""
    assert date_effet(["بالملحق عدد 4 ثم عدد 5", "بالملحق التعديلي عدد 9"],
                      INDEX, CONVENTION) == (date(2019, 5, 1), "avenant:9:mention_non_reconnue")


@pytest.mark.parametrize("notes", [
    ["بالملحق التعديلي عدد 5 ثم بالمرسوم عدد 11"],                 # A7
    ["بالملحق التعديلي عدد 5 المصادق عليه بالقانون ثم عدد 6"],
    ["نقح بالمرسوم عدد 11 ثم بالملحق التعديلي عدد 5"],              # avant l'avenant
])
def test_decret_ou_loi_garde_la_date_et_la_marque(notes):
    """Un decret ou une loi cite par le document, avant ou apres l'avenant, garde la
    date de l'avenant et l'origine porte l'incertitude : provisoire, en attente de
    la juriste."""
    assert date_effet(notes, INDEX, CONVENTION) == (date(2015, 5, 1), "avenant:5:decret_ou_loi")


def test_suffixe_conserve_la_provenance_jort():
    index = {5: {"jort": {"date": "2015-06-01"}}}
    assert date_effet(["بالملحق التعديلي عدد 5 ثم بالمرسوم عدد 11"], index, CONVENTION) == (
        date(2015, 6, 1), "avenant:5:jort:decret_ou_loi")


@pytest.mark.parametrize("index, attendu", [
    ({}, "avenant:5:introuvable:nombre_orphelin:decret_ou_loi"),
    ({5: {}}, "avenant:5:sans_date:nombre_orphelin:decret_ou_loi"),
])
def test_suffixe_conserve_dans_les_branches_sans_date(index, attendu):
    """Le jour ou la date manquante est fournie, l'incertitude doit encore se voir."""
    assert date_effet(["بالملحق التعديلي عدد 5 ثم 6 ثم بالمرسوم عدد 11"], index, CONVENTION) == (
        None, attendu)


def test_suffixes_cumules_dans_un_ordre_fixe():
    assert date_effet(["بالملحق عدد 4", "بالملحق التعديلي عدد 7 ثم 8 ثم بالمرسوم عدد 11"],
                      INDEX, CONVENTION) == (
        date(2017, 5, 1), "avenant:7:mention_non_reconnue:nombre_orphelin:decret_ou_loi")


def test_numero_sans_adad_mesure_mais_non_retenu():
    mentions = releve_mentions(["نقح بالملحق التعديلي عدد 7 ثم 8"])
    assert [m.numero for m in mentions] == [7]
    assert mentions[0].orpheline_apres is True


@pytest.mark.parametrize("note, attendu", [
    ("نقح بالملحق التعديلي عدد 7 ثم 8", (date(2017, 5, 1), "avenant:7:nombre_orphelin")),
    ("بالملحق التعديلي عدد 7 ثم 8 ثم بالمرسوم عدد 11",
     (date(2017, 5, 1), "avenant:7:nombre_orphelin:decret_ou_loi")),
    # l'orphelin suit le 7 et non le dernier avenant : il est marque quand meme,
    # sa position ne dit rien de sa date
    ("بالملحق التعديلي عدد 7 ثم 8 ثم عدد 9", (date(2019, 5, 1), "avenant:9:nombre_orphelin")),
])
def test_numero_sans_adad_marque_l_origine(note, attendu):
    """« عدد 7 ثم 8 » : le 8 est tres probablement un autre avenant. Le reconnaitre
    attend la juriste ; la date est gardee, l'incertitude marquee."""
    assert date_effet([note], INDEX, CONVENTION) == attendu


# ------------------------------------------------ lecture d'un condense

def _condense(tmp_path, articles):
    """`articles` : couples (numero brut, notes)."""
    chemin = tmp_path / "test.json"
    chemin.write_text(json.dumps({
        "original_convention": CONVENTION,
        "amendments": [{"number": 5, "effective_date": "2015-05-01"}],
        "articles": [{"number": numero, "text": "نص", "pages": [1], "status": "جديد",
                      "footnotes": notes} for numero, notes in articles],
    }, ensure_ascii=False), encoding="utf-8")
    return lire_condense(chemin, {"source_id": "CCS-TEST"})


def test_article_modifie_sans_mention_reconnue_reste_sans_date(tmp_path):
    """Un article modifie dont aucune mention n'est reconnue ne recoit pas la date
    de signature de sa convention : ce serait la date de son texte d'origine."""
    _, documents, _, rapport = _condense(tmp_path, [("1", ["نقح بالملحق عدد 4"])])
    article = documents[0]
    assert article.modified is True
    assert (article.effective_from, article.effective_from_origin) == (
        None, "mentions_non_reconnues")
    assert article.amended_by is None
    assert rapport["sans_date"] == ["CCS-TEST-ART-1-v1"]


ARTICLES_RAPPORT = [
    ("1", ["بالملحق التعديلي عدد 5 ثم بالمرسوم عدد 11"]),   # date gardee, decret
    ("2", ["نقح بالملحق عدد 4 ثم عدد 6"]),                   # aucune mention reconnue
    ("3", ["نقح بالملحق التعديلي عدد 5 ثم 6"]),              # date gardee, orphelin
    ("4", ["نقح بالقرار التعديلي عدد 5"]),                   # aucune mention reconnue
    ("5", ["بالملحق التعديلي عدد 5", "ثم عدد 6"]),           # date retiree
    # numero brut en arabe, sans date : il entre dans sans_date
    ("5 مكرر", ["نقح بالملحق عدد 4"]),
    ("7", ["بالملحق عدد 4", "بالملحق التعديلي عدد 5"]),      # date gardee, non reconnue avant
]


def test_rapport_compte_les_mentions(tmp_path):
    _, documents, _, rapport = _condense(tmp_path, ARTICLES_RAPPORT)
    assert [d.effective_from_origin for d in documents] == [
        "avenant:5:decret_ou_loi", "mentions_non_reconnues",
        "avenant:5:nombre_orphelin", "mentions_non_reconnues",
        "mention_non_reconnue_posterieure", "mentions_non_reconnues",
        "avenant:5:mention_non_reconnue"]
    assert documents[0].amended_by == "CCS-TEST-AVENANT-5"
    assert rapport["sans_date"] == [
        "CCS-TEST-ART-2-v1", "CCS-TEST-ART-4-v1", "CCS-TEST-ART-5-v1", "CCS-TEST-ART-5BIS-v1"]
    assert rapport["mentions_non_reconnues"] == 6
    assert rapport["nombres_sans_adad"] == 1
    assert rapport["alarme_racine"] == {"mulhaq_sans_taadil": 3, "taadil_sans_mulhaq": 1}
    assert rapport["date_retiree_mention_posterieure"] == 1
    assert rapport["avenant_marque_mention_non_reconnue"] == 1
    assert rapport["avenant_marque_nombre_orphelin"] == 1
    assert rapport["avenant_marque_decret_ou_loi"] == 1
    assert rapport["formes_mentions"] == {
        "nature=avenant|suite=0|mulhaq=1|taadil=1|alarme=-": 4,
        "nature=decret|suite=0|mulhaq=0|taadil=0|alarme=-": 1,
        "nature=non_reconnue|suite=0|mulhaq=0|taadil=1|alarme=taadil_sans_mulhaq": 1,
        "nature=non_reconnue|suite=0|mulhaq=1|taadil=0|alarme=mulhaq_sans_taadil": 3,
        "nature=non_reconnue|suite=1|mulhaq=0|taadil=0|alarme=-": 2,
    }
    assert "exemples_non_reconnus" not in rapport


def test_rapport_ne_contient_aucun_caractere_arabe(tmp_path):
    """Des notes et un numero d'article en arabe en entree, aucune lettre arabe en
    sortie : le rapport part dans data/processed/legal_corpus/, qui est versionne."""
    _, _, _, rapport = _condense(tmp_path, ARTICLES_RAPPORT)
    assert "CCS-TEST-ART-5BIS-v1" in rapport["sans_date"]     # le cas est bien exerce
    sortie = json.dumps(rapport, ensure_ascii=False)
    assert not ARABE.search(sortie)
