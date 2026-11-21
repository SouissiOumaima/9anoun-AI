"""Lecteur de l'archive Tradrly « اتفاقيات قطاعية محينة » : 56 conventions (D73, D74).

CE QUE CE MODULE REMPLACE. L'ancien chemin (`ingest_sections`, D20) découpait
des sections OCR par heuristique. La nouvelle livraison est une transcription
page à page vérifiée, qui porte ses propres métadonnées : pages, dates d'effet,
références JORT, statut d'abrogation. Il n'y a plus rien à deviner.

LES QUATRE CLASSES DE DOCUMENTS (D74) :

  articles               -> `-ART-`  73,4 % du texte
  annexes                -> `-ANX-`  24,8 % du texte, dont les tableaux de
                                     classification professionnelle
  other_sections         -> `-SEC-`  sauf liste d'exclusion, voir `_section_exclue`
  excluded_salary_tables -> `-PTR-`  pointeurs : indexables pour etre TROUVES,
                                     jamais citables comme source d'un montant

CE QUI EST PRESERVE DE L'ANCIEN CORPUS. `SMIG-GRILLE` est un decret, pas une
convention collective : l'archive ne le contient pas. La regle appliquee est
generale et non un cas particulier — toute source presente dans l'ancien chemin
et absente de la table de l'archive est reprise telle quelle.

CE QUE L'ARCHIVE NE CONTIENT PAS. Le texte des versions anciennes : un article
modifie ne porte que son texte courant, plus une note citant les avenants. D'ou
`previous_version_available = False` pour ces articles (R6, D17).

Usage, depuis la racine du depot :
    python -m src.legal_retrieval.corpus.ingest_archive --archive "<...>\\json"
    python -m src.legal_retrieval.corpus.ingest_archive --archive "<...>" --output out_test
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from .models import ArticleStatus, DocumentKind, LegalArticle, LegalSource, SourceType
from .normalize import normalize_arabic

_ICI = Path(__file__).resolve().parent
TABLE = _ICI / "archive_sources.v0.json"
SORTIE = Path("data/processed/legal_corpus")
ANCIEN_INPUT = Path("data/raw/txt")
ANCIEN_PDF = Path("data/raw/pdf")

# Suffixes ordinaux rencontres dans l'archive. Les quatre derniers manquaient a
# search/text.py avant la PR #39 : une question citant « الفصل 51 ثالثا »
# renvoyait l'article 51, donc le mauvais, avec un score de 1,0.
SUFFIXES = {"مكرر": "BIS", "مثلث": "TER", "ثالثا": "TER",
            "رابعا": "QUATER", "مربع": "QUATER",
            "خامسا": "QUINQUIES", "سادسا": "SEXIES"}

# « 32 مكرر » | « 54-5 » | « 46 - 3 » | « 50– 5 » | « 39 مكرر (1) » | « 1 مكرّر »
_NUM = re.compile(r"^\s*(\d+)\s*(?:[-–]\s*(\d+))?\s*([^\s(]+)?\s*(?:\((\d+)\))?\s*$")

# « نقح بالملحق التعديلي عدد 7 ثم عدد 8 » : seuls les nombres qui suivent « عدد »
# sont des numeros d'avenant, ce qui ecarte le numero d'appel de note.
_AVENANT_CITE = re.compile(r"عدد\s*(\d+)")


# --------------------------------------------------------------------- outils

def _sha256(chemin: Path) -> str:
    """Empreinte du condense. L'archive etant hors depot, c'est ce qui relie un
    corpus committe a une livraison precise (D75)."""
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def _date(valeur: Any) -> date | None:
    try:
        return date.fromisoformat(str(valeur))
    except (TypeError, ValueError):
        return None


def parse_number(brut: Any) -> tuple[int | None, str]:
    """« 32 مكرر » -> (32, '32BIS'). (None, brut) si illisible.

    La normalisation retire la chadda, donc « مكرّر » devient « مكرر ».
    """
    m = _NUM.match(normalize_arabic(str(brut)))
    if not m:
        return None, str(brut)
    numero, sous, mot, paren = m.group(1), m.group(2), m.group(3), m.group(4)
    suffixe = SUFFIXES.get(normalize_arabic(mot or ""), "")
    cle = numero + (f"-{sous}" if sous else "") + suffixe + (f"-{paren}" if paren else "")
    return int(numero), cle


def avenants_cites(notes: list[str] | None) -> list[int]:
    """Numeros d'avenants cites par les notes, dans l'ordre du texte."""
    numeros: list[int] = []
    for note in notes or []:
        for n in _AVENANT_CITE.findall(str(note)):
            if int(n) not in numeros:
                numeros.append(int(n))
    return numeros


def date_effet(notes: list[str] | None, index: dict[int, dict[str, Any]],
               convention: dict[str, Any]) -> tuple[date | None, str | None]:
    """Depuis quand le texte COURANT s'applique, et d'ou vient cette date.

    Article jamais modifie -> date de signature de la convention.
    Article modifie        -> date d'effet du DERNIER avenant cite ; a defaut sa
                              date de publication au JORT ; a defaut None.

    La provenance est renvoyee avec la date : DS4 doit pouvoir dire « depuis le
    1er mai 2011, par l'avenant n° 7 » plutot qu'afficher une date orpheline.
    """
    cites = avenants_cites(notes)
    if not cites:
        d = _date(convention.get("signed_date")) or _date(
            (convention.get("jort") or {}).get("date"))
        return d, ("convention" if d else None)
    dernier = cites[-1]
    avenant = index.get(dernier)
    if avenant is None:
        return None, f"avenant:{dernier}:introuvable"
    d = _date(avenant.get("effective_date"))
    if d:
        return d, f"avenant:{dernier}"
    d = _date((avenant.get("jort") or {}).get("date"))
    return d, (f"avenant:{dernier}:jort" if d else f"avenant:{dernier}:sans_date")


# Titres de `other_sections` a ne PAS ingerer. La liste est fermee : un titre
# inconnu est INGERE et signale, parce qu'omettre du droit est plus grave
# qu'indexer du bruit (D74).
def _section_exclue(titre: str) -> str | None:
    """Motif d'exclusion, ou None si la section doit entrer dans le corpus."""
    n = normalize_arabic(titre or "")
    if n == normalize_arabic("التوقيعات"):
        return "signatures"
    if normalize_arabic("معلومات حول") in n:
        return "note editoriale de la livraison"
    if normalize_arabic("غلاف") in n or n.startswith(normalize_arabic("العنوان")) \
            or n.startswith(normalize_arabic("عنوان")):
        return "couverture ou titre de page"
    if normalize_arabic("اعادة ترقيم الفصول") in n:
        return "note de renumerotation, conservee en metadonnee"
    return None


def _hierarchie(condense: dict[str, Any], feuille: str) -> str:
    """« اتفاقية مشتركة قطاعية > البنوك > الفصل 14 »."""
    racine = ("الاتفاقية المشتركة الإطارية"
              if condense.get("type") == "framework_convention"
              else "اتفاقية مشتركة قطاعية")
    return " > ".join(p for p in (racine, condense.get("sector"), feuille) if p)


# ------------------------------------------------------- lecture d'un condense

def lire_condense(chemin: Path, entree: dict[str, Any],
                  ) -> tuple[LegalSource, list[LegalArticle], dict[str, Any], dict[str, Any]]:
    """Un condense -> sa source, ses documents, son historique, son rapport."""
    condense = json.loads(chemin.read_text(encoding="utf-8"))
    source_id = entree["source_id"]
    empreinte = _sha256(chemin)
    convention = condense.get("original_convention") or {}

    index: dict[int, dict[str, Any]] = {}
    for avenant in condense.get("amendments") or []:
        try:
            index[int(avenant.get("number"))] = avenant
        except (TypeError, ValueError):
            continue

    rapport: dict[str, Any] = {
        "source_id": source_id, "digest": chemin.stem, "sha256": empreinte,
        "articles": 0, "annexes": 0, "sections": 0, "pointeurs": 0,
        "abroges": 0, "modifies": 0,
        "texte_vide": [], "numero_illisible": [], "sans_page": [], "sans_date": [],
        "doublons": [], "sections_exclues": Counter(), "sections_inconnues": [],
        "avenants": len(index), "avenants_sans_date_effet": [],
    }
    documents: list[LegalArticle] = []
    vus: Counter = Counter()        # pour la regle -DUP sur les numeros repetes

    commun = {"source_id": source_id, "sector": condense.get("sector"),
              "text_source": "page_image_transcription", "origin": "archive",
              "source_digest_sha256": empreinte}

    # ---------------------------------------------------------------- articles
    for brut in condense.get("articles") or []:
        numero, cle = parse_number(brut.get("number"))
        texte = (brut.get("text") or "").strip()
        pages = brut.get("pages") or []
        statut = brut.get("status")

        if numero is None:
            rapport["numero_illisible"].append(str(brut.get("number")))
        if not texte:
            rapport["texte_vide"].append(f"article {brut.get('number')}")
            continue                      # un document sans texte ne s'indexe pas
        if not pages:
            rapport["sans_page"].append(f"article {brut.get('number')}")

        # Deux conventions portent reellement deux fois le meme numero. Le
        # suffixe -DUP existe deja dans store.find_by_number : on le reutilise
        # plutot que d'ecraser silencieusement la premiere occurrence.
        vus[cle] += 1
        base = f"{source_id}-ART-{cle}" + (f"-DUP{vus[cle]}" if vus[cle] > 1 else "")
        if vus[cle] > 1:
            rapport["doublons"].append(f"{brut.get('number')} -> {base}")

        modifie = statut == "جديد"
        depuis, origine = date_effet(brut.get("footnotes"), index, convention)
        if depuis is None:
            rapport["sans_date"].append(f"article {brut.get('number')}")
        cites = avenants_cites(brut.get("footnotes"))

        documents.append(LegalArticle(
            article_id=f"{base}-v1", article_number=numero,
            article_label=f"الفصل {brut.get('number')}",
            text=texte, text_normalized=normalize_arabic(texte),
            hierarchy_path=_hierarchie(condense, f"الفصل {brut.get('number')}"),
            page_start=pages[0] if pages else None,
            page_end=pages[-1] if len(pages) > 1 else None,
            effective_from=depuis, effective_from_origin=origine,
            status=ArticleStatus.ABROGE if statut == "ملغى" else ArticleStatus.EN_VIGUEUR,
            doc_kind=DocumentKind.ARTICLE,
            modified=modifie,
            amended_by=f"{source_id}-AVENANT-{cites[-1]}" if cites else None,
            previous_version_available=not modifie,   # texte d'avant absent (R6, D17)
            **commun))
        rapport["articles"] += 1
        rapport["abroges"] += int(statut == "ملغى")
        rapport["modifies"] += int(modifie)

    # ----------------------------------------------------------------- annexes
    for rang, brut in enumerate(condense.get("annexes") or [], start=1):
        texte = (brut.get("text") or "").strip()
        if not texte:
            rapport["texte_vide"].append(f"annexe {rang}")
            continue
        pages = brut.get("pages") or []
        depuis, origine = date_effet(brut.get("footnotes"), index, convention)
        titre = (brut.get("title") or f"ملحق {rang}").strip()
        documents.append(LegalArticle(
            article_id=f"{source_id}-ANX-{rang}-v1", article_number=None,
            article_label=titre,
            text=texte, text_normalized=normalize_arabic(texte),
            hierarchy_path=_hierarchie(condense, titre),
            page_start=pages[0] if pages else None,
            page_end=pages[-1] if len(pages) > 1 else None,
            effective_from=depuis, effective_from_origin=origine,
            doc_kind=DocumentKind.ANNEXE, **commun))
        rapport["annexes"] += 1

    # ---------------------------------------------------------------- sections
    rang = 0
    for brut in condense.get("other_sections") or []:
        titre = (brut.get("title") or "").strip()
        motif = _section_exclue(titre)
        if motif:
            rapport["sections_exclues"][motif] += 1
            continue
        texte = (brut.get("text") or "").strip()
        if not texte:
            rapport["texte_vide"].append(f"section « {titre[:40]} »")
            continue
        rapport["sections_inconnues"].append(titre[:60])   # a relire : liste fermee
        rang += 1
        pages = brut.get("pages") or []
        depuis, origine = date_effet(brut.get("footnotes"), index, convention)
        documents.append(LegalArticle(
            article_id=f"{source_id}-SEC-{rang}-v1", article_number=None,
            article_label=titre,
            text=texte, text_normalized=normalize_arabic(texte),
            hierarchy_path=_hierarchie(condense, titre),
            page_start=pages[0] if pages else None,
            page_end=pages[-1] if len(pages) > 1 else None,
            effective_from=depuis, effective_from_origin=origine,
            doc_kind=DocumentKind.SECTION, **commun))
        rapport["sections"] += 1

    # --------------------------------------------------------------- pointeurs
    # Le barème n'est pas transcrit. Le pointeur porte son TITRE comme texte,
    # pour etre trouve par une question sur un salaire, et `citable` est force a
    # False par le modele : il ne peut jamais etre presente comme la source d'un
    # montant (D74).
    for rang, brut in enumerate(condense.get("excluded_salary_tables") or [], start=1):
        titre = (brut.get("title") or "").strip()
        if not titre:
            continue
        pages = brut.get("pages") or []
        documents.append(LegalArticle(
            article_id=f"{source_id}-PTR-{rang}-v1", article_number=None,
            article_label=titre,
            text=titre, text_normalized=normalize_arabic(titre),
            hierarchy_path=_hierarchie(condense, titre),
            page_start=pages[0] if pages else None,
            page_end=pages[-1] if len(pages) > 1 else None,
            doc_kind=DocumentKind.POINTEUR, **commun))
        rapport["pointeurs"] += 1

    # ------------------------------------------------------ source et historique
    jort = convention.get("jort") or {}
    source = LegalSource(
        source_id=source_id,
        title_ar=condense.get("title") or chemin.stem,
        source_type=(SourceType.CONVENTION_CADRE
                     if condense.get("type") == "framework_convention"
                     else SourceType.CONVENTION_SECTORIELLE),
        sector=condense.get("sector"),
        official_reference=jort.get("reference") or jort.get("number"),
        publication_date=_date(jort.get("date")),
        effective_date=_date(convention.get("signed_date")),
        file_name=condense.get("source_file") or chemin.name)

    historique = {
        "source_id": source_id,
        "signed_on": _iso(convention.get("signed_date")),
        "approved_on": _iso(jort.get("date")),
        "avenants": [],
    }
    for numero in sorted(index):
        avenant = index[numero]
        if not avenant.get("effective_date"):
            rapport["avenants_sans_date_effet"].append(numero)
        historique["avenants"].append({
            "avenant_id": f"{source_id}-AVENANT-{numero}",
            "number": numero,
            "signed_on": _iso(avenant.get("signed_date")),
            "approved_on": _iso((avenant.get("jort") or {}).get("date")),
            # champ ajoute par l'archive : l'ancien chemin ne l'avait pas
            "effective_on": _iso(avenant.get("effective_date")),
        })

    rapport["sections_exclues"] = dict(rapport["sections_exclues"])
    return source, documents, historique, rapport


def _iso(valeur: Any) -> str | None:
    d = _date(valeur)
    return d.isoformat() if d else None


# ------------------------------------------------------------- heritage ancien

def heritage(table_sources: set[str], ancien_input: Path, ancien_pdf: Path) -> list[str]:
    """Lignes JSONL des sources que l'archive ne couvre pas (SMIG-GRILLE, D73).

    La regle est generale : tout ce que l'ancien chemin produit pour une source
    absente de la table est conserve tel quel, sans retraitement.
    """
    if not ancien_input.exists():
        return []
    from .ingest_sections import run as run_ancien      # import tardif : dependance lourde
    with tempfile.TemporaryDirectory() as tmp:
        run_ancien(ancien_input, Path(tmp), ancien_pdf if ancien_pdf.exists() else None)
        lignes = (Path(tmp) / "legal_articles.jsonl").read_text(
            encoding="utf-8").splitlines()
    return [ligne for ligne in lignes
            if json.loads(ligne).get("source_id") not in table_sources]


# ----------------------------------------------------------------------- run

def run(archive_dir: Path, output_dir: Path, table_path: Path = TABLE,
        ancien_input: Path = ANCIEN_INPUT, ancien_pdf: Path = ANCIEN_PDF,
        ) -> list[dict[str, Any]]:
    """Ingere les 56 condenses ; ecrit articles, sources, avenants, rapport."""
    table = json.loads(table_path.read_text(encoding="utf-8"))
    entrees = {e["digest"]: e for e in table["sources"]}
    ids_archive = {e["source_id"] for e in table["sources"]}

    output_dir.mkdir(parents=True, exist_ok=True)
    sources, historiques, rapports = [], [], []
    conserves = heritage(ids_archive, ancien_input, ancien_pdf)

    with (output_dir / "legal_articles.jsonl").open("w", encoding="utf-8") as out:
        for ligne in conserves:              # d'abord l'heritage, ordre stable
            out.write(ligne + "\n")
        for chemin in sorted(archive_dir.glob("*.json")):
            if chemin.stem.endswith(".verification"):
                continue                      # fichier de controle livre a cote
            entree = entrees.get(chemin.stem)
            if entree is None:
                raise SystemExit(f"condense hors table : {chemin.stem}")
            source, documents, historique, rapport = lire_condense(chemin, entree)
            sources.append(source.model_dump(mode="json"))
            historiques.append(historique)
            rapports.append(rapport)
            for document in documents:        # un objet JSON par ligne
                out.write(document.model_dump_json() + "\n")

    for nom, charge in (("legal_sources.json", sources),
                        ("avenants.json", historiques),
                        ("ingestion_report.json", rapports)):
        (output_dir / nom).write_text(
            json.dumps(charge, ensure_ascii=False, indent=2), encoding="utf-8")
    return rapports


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestion de l'archive Tradrly (D73, D74)")
    parser.add_argument("--archive", type=Path, required=True,
                        help="dossier json/ de l'archive (hors depot, confidentiel)")
    parser.add_argument("--table", type=Path, default=TABLE)
    parser.add_argument("--output", type=Path, default=SORTIE)
    parser.add_argument("--ancien-input", type=Path, default=ANCIEN_INPUT)
    args = parser.parse_args()

    rapports = run(args.archive, args.output, args.table, args.ancien_input)
    for r in sorted(rapports, key=lambda x: x["source_id"]):
        print(f"{r['source_id']:<40} art={r['articles']:<3} anx={r['annexes']:<2} "
              f"sec={r['sections']:<2} ptr={r['pointeurs']:<3} "
              f"abroges={r['abroges']:<2} modifies={r['modifies']:<3} "
              f"vides={len(r['texte_vide'])} dup={len(r['doublons'])} "
              f"sans_date={len(r['sans_date'])}")

    totaux = Counter()
    for r in rapports:
        for cle in ("articles", "annexes", "sections", "pointeurs", "abroges", "modifies"):
            totaux[cle] += r[cle]
    print(f"\nTOTAL  articles={totaux['articles']}  annexes={totaux['annexes']}  "
          f"sections={totaux['sections']}  pointeurs={totaux['pointeurs']}")
    print(f"       abroges={totaux['abroges']}  modifies={totaux['modifies']}")

    exclues: Counter = Counter()
    for r in rapports:
        exclues.update(r["sections_exclues"])
    print(f"\nsections ecartees : {dict(exclues)}")

    inconnues = sorted({t for r in rapports for t in r["sections_inconnues"]})
    print(f"\nsections ingerees, titres distincts ({len(inconnues)}) — a relire :")
    for titre in inconnues:
        print(f"  {titre}")

    doublons = [d for r in rapports for d in r["doublons"]]
    vides = [(r["source_id"], v) for r in rapports for v in r["texte_vide"]]
    print(f"\ndoublons (-DUP) : {doublons or 'aucun'}")
    print(f"documents sans texte, ecartes : {vides or 'aucun'}")
    print(f"\n-> {args.output}")


if __name__ == "__main__":
    main()
