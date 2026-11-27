"""Releve reproductible d'une source du corpus archive, en lecture seule.

Usage :
    python tools/ds2_releves/releve_source.py --source-id CCS-CONSTRUCTION-METALLIQUE \
        --input <dossier out_*>

Le releve sert de piece de controle partageable : il doit pouvoir etre colle
dans une fiche, compare d'une execution a l'autre et relu sans editeur
capable d'afficher l'arabe. D'ou deux partis pris : aucune donnee textuelle
du corpus n'est imprimee, et la sortie est en ASCII strict.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Le registre n'est pas encore sur main : il est arrive avec 7cb7e6e (D73/D74).
# On le lit dans ce commit plutot que sur le disque pour que le releve ne
# depende pas de la branche extraite ni d'une copie locale modifiee.
REGISTRE_REV = "7cb7e6e"
REGISTRE_CHEMIN = "src/legal_retrieval/corpus/archive_sources.v0.json"

# Champs exclus d'office : ce sont le contenu juridique lui-meme. Le releve
# decrit la structure du corpus, il ne doit jamais en devenir un extrait.
CHAMPS_TEXTE = {"text", "text_normalized"}

# Ordre fixe des types de documents : les totaux reperes doivent toujours
# afficher les trois lignes, meme a zero, pour qu'un type disparu se voie.
DOC_KINDS_REPERES = ("article", "annexe", "pointeur")


def emettre(ligne: str = "") -> None:
    # Garde-fou central : toute sortie passe ici. Si un caractere non-ASCII
    # arrive jusqu'ici, c'est qu'un champ a echappe au masquage ; on prefere
    # interrompre le releve plutot que de laisser fuir du texte du corpus.
    # Le message d'erreur donne la position, jamais le caractere lui-meme.
    if not ligne.isascii():
        pos = next(i for i, c in enumerate(ligne) if not c.isascii())
        raise ValueError(f"caractere non-ASCII en position {pos} d'une ligne de sortie")
    print(ligne)


def masquer(valeur) -> str:
    # Les champs en arabe (libelles, nom du PDF, secteur) sont utiles pour
    # verifier qu'ils n'ont pas change, pas pour etre lus ici : longueur et
    # empreinte suffisent a comparer deux releves sans rien en extraire.
    if valeur is None:
        return "null"
    s = valeur if isinstance(valeur, str) else json.dumps(valeur, ensure_ascii=False)
    if s.isascii():
        return s
    empreinte = hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]
    return f"<non-ASCII, {len(s)} car., sha256:{empreinte}>"


def empreinte_fichier(chemin: Path) -> str:
    # L'empreinte des entrees rend le releve opposable : deux releves ne
    # se comparent que s'ils portent sur les memes octets.
    h = hashlib.sha256()
    with chemin.open("rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def charger_registre(chemin_local: str | None) -> tuple[dict, str]:
    if chemin_local:
        p = Path(chemin_local)
        return json.loads(p.read_text(encoding="utf-8")), f"fichier {masquer(str(p))}"
    brut = subprocess.run(
        ["git", "show", f"{REGISTRE_REV}:{REGISTRE_CHEMIN}"],
        check=True, capture_output=True,
    ).stdout
    return json.loads(brut.decode("utf-8")), f"git {REGISTRE_REV}:{REGISTRE_CHEMIN}"


def numero_avenant(avenant_id) -> int:
    # Tri numerique : un tri lexical placerait AVENANT-11 avant AVENANT-4.
    if not avenant_id:
        return -1
    try:
        return int(str(avenant_id).rsplit("-", 1)[-1])
    except ValueError:
        return 10**6


def court(avenant_id) -> str:
    # L'identifiant complet repete le source_id sur chaque ligne et rend les
    # tables illisibles ; le numero suffit puisque la source est fixee.
    if avenant_id is None:
        return "-"
    n = numero_avenant(avenant_id)
    return f"AV-{n}" if 0 <= n < 10**6 else masquer(avenant_id)


def table(entetes: list[str], lignes: list[list[str]]) -> None:
    largeurs = [max(len(e), *(len(l[i]) for l in lignes)) if lignes else len(e)
                for i, e in enumerate(entetes)]
    fmt = "  ".join(f"{{:<{w}}}" for w in largeurs)
    emettre(fmt.format(*entetes))
    emettre(fmt.format(*("-" * w for w in largeurs)))
    for l in lignes:
        emettre(fmt.format(*l))


def compte(c: Counter) -> str:
    return ", ".join(f"{masquer(k)}={v}" for k, v in sorted(c.items(), key=lambda kv: str(kv[0])))


def titre(nom: str) -> None:
    emettre()
    emettre("=" * 72)
    emettre(nom)
    emettre("=" * 72)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source-id", required=True)
    ap.add_argument("--input", required=True, help="dossier out_* contenant legal_articles.jsonl et avenants.json")
    ap.add_argument("--registre", help=f"chemin local du registre (par defaut : git {REGISTRE_REV})")
    args = ap.parse_args()

    # Seconde barriere : meme un print() oublie hors de emettre() echouerait.
    sys.stdout.reconfigure(encoding="ascii", errors="strict")

    dossier = Path(args.input)
    f_articles = dossier / "legal_articles.jsonl"
    f_avenants = dossier / "avenants.json"

    registre, origine_registre = charger_registre(args.registre)
    fiche = next((s for s in registre.get("sources", []) if s.get("source_id") == args.source_id), None)

    docs = []
    with f_articles.open(encoding="utf-8") as f:
        for ligne in f:
            if ligne.strip():
                d = json.loads(ligne)
                if d.get("source_id") == args.source_id:
                    # Le texte est retire des la lecture : ce qui n'est pas
                    # garde en memoire ne peut pas etre imprime par erreur.
                    for k in CHAMPS_TEXTE:
                        d.pop(k, None)
                    docs.append(d)

    index_brut = json.loads(f_avenants.read_text(encoding="utf-8"))
    entree = next((e for e in index_brut if e.get("source_id") == args.source_id), None)
    avenants = sorted((entree or {}).get("avenants", []), key=lambda a: a.get("number") or 0)
    par_id = {a.get("avenant_id"): a for a in avenants}

    # ------------------------------------------------------------------
    titre("IDENTIFICATION")
    emettre(f"source_id                : {masquer(args.source_id)}")
    emettre(f"dossier d'entree         : {masquer(str(dossier))}")
    emettre(f"sha256 legal_articles    : {empreinte_fichier(f_articles)}")
    emettre(f"sha256 avenants          : {empreinte_fichier(f_avenants)}")
    emettre(f"registre                 : {origine_registre}")
    emettre(f"registre.schema          : {masquer(registre.get('schema'))}")
    emettre(f"registre.decision_ref    : {masquer(registre.get('decision_ref'))}")
    if fiche is None:
        emettre("fiche registre           : ABSENTE")
    else:
        for k in fiche:
            emettre(f"registre.{k:<16}: {masquer(fiche[k])}")
    kinds = Counter(d.get("doc_kind") for d in docs)
    emettre()
    emettre("Totaux reperes")
    emettre(f"  total documents        : {len(docs)}")
    for k in DOC_KINDS_REPERES:
        emettre(f"  {'doc_kind=' + k:<23}: {kinds.get(k, 0)}")
    # Un type hors des trois attendus doit se voir ici, pas seulement en table.
    for k in sorted(set(kinds) - set(DOC_KINDS_REPERES), key=str):
        emettre(f"  {'doc_kind=' + masquer(k):<23}: {kinds[k]}  (type inattendu)")
    if fiche is not None:
        emettre(f"  articles declares      : {masquer(fiche.get('articles'))}")

    # ------------------------------------------------------------------
    titre("DOCUMENTS")
    groupes = defaultdict(list)
    for d in docs:
        groupes[(d.get("doc_kind"), d.get("amended_by"))].append(d)
    ordre_kind = {k: i for i, k in enumerate(DOC_KINDS_REPERES)}
    lignes = []
    for (kind, av), g in sorted(groupes.items(),
                                key=lambda kv: (ordre_kind.get(kv[0][0], 99), numero_avenant(kv[0][1]))):
        pages = [p for d in g for p in (d.get("page_start"), d.get("page_end")) if isinstance(p, int)]
        lignes.append([
            masquer(kind), court(av), str(len(g)),
            f"{min(pages)}-{max(pages)}" if pages else "-",
            str(sum(1 for d in g if d.get("citable"))),
            str(sum(1 for d in g if d.get("modified"))),
            compte(Counter(d.get("status") for d in g)),
        ])
    table(["doc_kind", "amended_by", "n", "pages", "citable", "modified", "status"], lignes)
    # Les champs qui ne varient pas sont sortis de la table : une colonne
    # constante masque les rares cas ou elle cesse de l'etre, une ligne non.
    emettre()
    emettre("Valeurs par champ (toute la source)")
    for k in ("origin", "part", "version", "text_source", "language", "sector",
              "previous_version_available", "numbers_unverified", "effective_to"):
        emettre(f"  {k:<27}: {compte(Counter(d.get(k) for d in docs))}")
    digests = Counter(d.get("source_digest_sha256") for d in docs)
    emettre(f"  {'source_digest_sha256':<27}: {len(digests)} valeur(s) distincte(s)")
    for v, n in sorted(digests.items(), key=lambda kv: str(kv[0])):
        emettre(f"    {masquer(v)} x{n}")

    # ------------------------------------------------------------------
    titre("INDEX AVENANTS")
    if entree is None:
        emettre("entree absente de avenants.json")
    else:
        for k, v in entree.items():
            if k != "avenants":
                emettre(f"{k:<12}: {masquer(v)}")
        emettre(f"avenants    : {len(avenants)}")
        if avenants:
            cles = list(dict.fromkeys(k for a in avenants for k in a))
            table(cles, [[court(a.get(k)) if k == "avenant_id" else masquer(a.get(k)) for k in cles]
                         for a in avenants])

    # ------------------------------------------------------------------
    titre("RECONCILIATION")
    # On met cote a cote la date portee par chaque article et celle de
    # l'index sans trancher : un ecart peut etre voulu (date JORT, effet
    # retroactif), c'est au lecteur de la fiche d'en decider.
    par_amended = defaultdict(Counter)
    for d in docs:
        par_amended[d.get("amended_by")][(d.get("effective_from"), d.get("effective_from_origin"))] += 1
    lignes = []
    for av in sorted(par_amended, key=numero_avenant):
        idx = par_id.get(av)
        eff_idx = idx.get("effective_on") if idx else None
        for (ef, orig), n in sorted(par_amended[av].items(), key=lambda kv: str(kv[0])):
            if av is None:
                marque = "-"
            elif idx is None:
                marque = "hors index"
            else:
                marque = "=" if ef == eff_idx else "!="
            lignes.append([court(av), masquer(ef), masquer(orig), str(n),
                           masquer(eff_idx) if av else "-", marque])
    table(["amended_by", "effective_from", "effective_from_origin", "n",
           "index.effective_on", "vs index"], lignes)

    # ------------------------------------------------------------------
    titre("MANQUANT")
    cites = {d.get("amended_by") for d in docs if d.get("amended_by")}
    hors_index = sorted(cites - set(par_id), key=numero_avenant)
    non_cites = sorted(set(par_id) - cites, key=numero_avenant)
    emettre(f"amended_by absents de l'index      : {', '.join(court(a) for a in hors_index) or 'aucun'}")
    emettre(f"avenants indexes non references    : {', '.join(court(a) for a in non_cites) or 'aucun'}")
    if fiche is not None:
        decl = fiche.get("articles")
        emettre(f"articles declares / doc_kind=article / total : "
                f"{masquer(decl)} / {kinds.get('article', 0)} / {len(docs)}")
    emettre("champs nuls ou vides (effectif sur la source) :")
    champs = sorted({k for d in docs for k in d})
    vides = [(k, sum(1 for d in docs if d.get(k) in (None, "", [], {}))) for k in champs]
    vides = [(k, n) for k, n in vides if n]
    if not vides:
        emettre("  aucun")
    for k, n in vides:
        emettre(f"  {k:<27}: {n}/{len(docs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
