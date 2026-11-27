"""Recette d'une sortie d'ingestion, avant de remplacer le corpus livré.

POURQUOI. Le résumé de `ingest_archive` compte ce qu'il a écrit, pas ce qui
manque. Trois choses ne s'y voient pas, et chacune casserait quelque chose :

  1. `SMIG-GRILLE` a-t-il survécu ? C'est un décret, absent de l'archive, repris
     de l'ancien chemin. Le golden set le référence (question G25).
  2. Les identifiants sont-ils uniques, tous espaces confondus ? Deux documents
     partageant un `article_id` se masqueraient l'un l'autre dans le store.
  3. **Le golden set retrouve-t-il ses sources ?** C'est la question décisive :
     un identifiant attendu qui n'existe plus fait chuter le rappel sans aucun
     message d'erreur, la question étant simplement comptée comme manquée.

Ce script ne modifie rien. Il lit une sortie d'ingestion et le golden set.

Usage, depuis la racine du dépôt :
    python tools\\ds2_releves\\verifier_sortie_ingestion.py out_test
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

GOLDEN = Path("src/legal_retrieval/evaluation/golden_set_retrieval.v0.json")
_VERSION = re.compile(r"-v(\d+)$")
_PARTIE = re.compile(r"-P\d+-")


def groupe(article_id: str) -> str:
    """« CCS-BTP-ART-39-v1 » -> « CCS-BTP-ART-39 » (comme store.version_group)."""
    return _VERSION.sub("", article_id)


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    dossier = Path(sys.argv[1])
    lignes = (dossier / "legal_articles.jsonl").read_text(encoding="utf-8").splitlines()
    docs = [json.loads(ligne) for ligne in lignes if ligne.strip()]
    print(f"documents : {len(docs)}\n")

    # ------------------------------------------------------------ 1. volumes
    print("=== 1. Répartition ===")
    par_kind = Counter(d.get("doc_kind") for d in docs)
    for kind, n in par_kind.most_common():
        print(f"  {str(kind):<10} {n}")
    sources = Counter(d["source_id"] for d in docs)
    print(f"  sources distinctes : {len(sources)}")

    # ----------------------------------------------- 2. l'héritage a-t-il tenu
    print("\n=== 2. Sources héritées de l'ancien chemin ===")
    herite = {sid: n for sid, n in sources.items()
              if all(d.get("origin") != "archive"
                     for d in docs if d["source_id"] == sid)}
    print(f"  {herite or 'AUCUNE — le SMIG a disparu, vérifier --ancien-input'}")

    # -------------------------------------------------- 3. unicité et héritage
    print("\n=== 3. Unicité des identifiants ===")
    ids = Counter(d["article_id"] for d in docs)
    collisions = {i: n for i, n in ids.items() if n > 1}
    print(f"  article_id en double : {collisions or 'aucun'}")
    groupes = Counter(groupe(d["article_id"]) for d in docs)
    doubles = {g: n for g, n in groupes.items() if n > 1}
    print(f"  groupes de version portant plusieurs documents : {len(doubles)}")
    for g, n in list(doubles.items())[:5]:
        print(f"      {g} x{n}   (normal seulement si versions multiples)")

    print("\n=== 4. D73 : aucun numéro de partie ne subsiste ===")
    restants = [d["article_id"] for d in docs if _PARTIE.search(d["article_id"])]
    print(f"  identifiants portant -P<n>- : {restants or 'aucun'}")

    # --------------------------------------------- 5. la garantie des pointeurs
    print("\n=== 5. D74 : un pointeur n'est jamais citable ===")
    pointeurs = [d for d in docs if d.get("doc_kind") == "pointeur"]
    citables = [d["article_id"] for d in pointeurs if d.get("citable") is not False]
    print(f"  pointeurs : {len(pointeurs)}   citables à tort : {citables or 'aucun'}")
    sans_page = [d["article_id"] for d in pointeurs if d.get("page_start") is None]
    print(f"  pointeurs sans page : {len(sans_page)}")

    # ------------------------------------------------- 6. pages et dates servies
    print("\n=== 6. Complétude des champs que DS4 attend ===")
    citables_docs = [d for d in docs if d.get("citable") is not False]
    avec_page = sum(1 for d in citables_docs if d.get("page_start") is not None)
    avec_date = sum(1 for d in citables_docs if d.get("effective_from"))
    n = len(citables_docs) or 1
    print(f"  documents citables : {len(citables_docs)}")
    print(f"  avec page_start    : {avec_page} ({100 * avec_page / n:.1f} %)")
    print(f"  avec effective_from: {avec_date} ({100 * avec_date / n:.1f} %)")
    manquantes = Counter(d["source_id"] for d in citables_docs if not d.get("effective_from"))
    if manquantes:
        print("  sources où la date manque le plus :")
        for sid, k in manquantes.most_common(5):
            print(f"      {sid:<36} {k}")

    # ------------------------------------------- 7. LA question : le golden set
    print("\n=== 7. Le golden set retrouve-t-il ses sources ===")
    if not GOLDEN.exists():
        print(f"  NON TROUVÉ : {GOLDEN}")
        return
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    presents = {groupe(d["article_id"]) for d in docs}

    attendus_par_question: dict[str, list[str]] = {}
    for q in golden.get("questions") or []:
        for attendu in q.get("expected") or []:
            attendus_par_question.setdefault(q["id"], []).append(attendu)

    casses: dict[str, list[str]] = defaultdict(list)
    total_attendus = trouves = 0
    for qid, attendus in attendus_par_question.items():
        for attendu in attendus:
            total_attendus += 1
            if attendu in presents:
                trouves += 1
            else:
                casses[qid].append(attendu)

    print(f"  identifiants attendus : {total_attendus}   retrouvés : {trouves}")
    if not casses:
        print("  >> aucune question cassée : la migration préserve le jeu d'évaluation")
        return
    print(f"  >> {len(casses)} question(s) perdent au moins une source :\n")
    for qid, perdus in sorted(casses.items()):
        for perdu in perdus:
            # on cherche un remplaçant plausible : même source, même numéro
            sid = perdu.split("-ART-")[0].replace("-P2", "").replace("-P3", "")
            num = perdu.split("-ART-")[-1] if "-ART-" in perdu else ""
            candidat = f"{sid}-ART-{num}"
            remplacant = candidat if candidat in presents else None
            print(f"    {qid:<5} {perdu}")
            print(f"          -> {remplacant or 'AUCUN remplaçant évident'}")


if __name__ == "__main__":
    main()
