"""D74 : un pointeur vers une grille de salaires n'est jamais citable.

POURQUOI CE TEST EXISTE. Les barèmes de salaires ne sont pas transcrits dans la
livraison Tradrly : les 256 tables n'y figurent que par leur titre et leur page.
Or « combien dois-je gagner » est la question la plus fréquente d'un
travailleur, et un corpus muet sur ce point mais riche en articles parlant
d'indemnités est dangereux : le moteur trouve quelque chose, et ce quelque
chose est faux.

D74 range donc ces tables comme des POINTEURS : indexables pour être trouvées,
jamais citables comme source d'un montant. Ce test vérifie que la garantie tient
dans le modèle lui-même, et pas seulement dans la bonne volonté de l'appelant.

Aucun corpus n'est lu : les objets sont construits à la main.
"""

from __future__ import annotations

import pytest

from src.legal_retrieval.corpus.models import ArticleStatus, DocumentKind, LegalArticle


def _document(**surcharges) -> LegalArticle:
    """Un document minimal valide ; les tests ne surchargent que ce qui les concerne."""
    base = {
        "article_id": "CCS-TEST-ART-1-v1",
        "source_id": "CCS-TEST",
        "article_number": 1,
        "article_label": "test",
        "text": "texte",
        "text_normalized": "texte",
        "hierarchy_path": "test",
    }
    return LegalArticle(**{**base, **surcharges})


# ------------------------------------------------------- la garantie centrale

def test_un_pointeur_est_toujours_non_citable() -> None:
    doc = _document(doc_kind=DocumentKind.POINTEUR)
    assert doc.citable is False


def test_un_pointeur_reste_non_citable_meme_si_on_demande_le_contraire() -> None:
    """Le cas qui compte : un appelant distrait ne peut pas rendre un pointeur citable."""
    doc = _document(doc_kind=DocumentKind.POINTEUR, citable=True)
    assert doc.citable is False


@pytest.mark.parametrize("kind", [DocumentKind.ARTICLE, DocumentKind.ANNEXE,
                                  DocumentKind.SECTION])
def test_les_autres_natures_restent_citables_par_defaut(kind: DocumentKind) -> None:
    """Un article, une annexe et une section sont du droit : on les cite."""
    assert _document(doc_kind=kind).citable is True


def test_un_document_ordinaire_peut_etre_rendu_non_citable() -> None:
    """L'interdiction doit rester disponible hors du cas des pointeurs.

    Par exemple un article abrogé que l'on garde pour l'historique mais que l'on
    ne veut pas voir cité comme règle en vigueur.
    """
    doc = _document(doc_kind=DocumentKind.ARTICLE, citable=False,
                    status=ArticleStatus.ABROGE)
    assert doc.citable is False


# ------------------------------------------------- les champs ajoutés par D73/D74

def test_la_nature_par_defaut_est_un_article() -> None:
    """Les documents déjà produits par l'ancien chemin restent des articles."""
    assert _document().doc_kind is DocumentKind.ARTICLE


def test_un_document_peut_couvrir_plusieurs_pages() -> None:
    """CC-CADRE-ART-2 s'étend sur les pages 3 et 4 (signalé par DS1)."""
    doc = _document(page_start=3, page_end=4)
    assert (doc.page_start, doc.page_end) == (3, 4)


def test_l_origine_de_la_date_est_conservee() -> None:
    """La date d'effet ne vient pas de la même place selon l'article.

    DS4 doit pouvoir dire « depuis cette date, par l'avenant n° 7 » plutôt
    qu'afficher une date sans provenance.
    """
    doc = _document(effective_from_origin="avenant:7")
    assert doc.effective_from_origin == "avenant:7"


def test_l_empreinte_de_la_source_est_conservee() -> None:
    """L'archive est confidentielle et hors dépôt : l'empreinte est ce qui reste
    pour relier un corpus committé à une livraison précise (D75)."""
    empreinte = "0" * 64
    assert _document(source_digest_sha256=empreinte).source_digest_sha256 == empreinte


def test_les_champs_nouveaux_sont_absents_par_defaut() -> None:
    """Rien n'est inventé pour les documents de l'ancien chemin d'ingestion."""
    doc = _document()
    assert doc.page_end is None
    assert doc.effective_from_origin is None
    assert doc.source_digest_sha256 is None
    assert doc.citable is True
