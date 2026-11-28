"""Rapport de conformité d'une fiche de paie (contrat v1, D108 ; documents manquants, D109).

Aucun montant de convention n'est calculé ici : chacun vient de calc/ (salaire_base, prime_v1, smig), avec ses
citations et ses hypothèses. Le rapport ajoute seulement la différence « imprimé − convention », arrondie au millime
(D6), et un statut par ligne : conforme (imprimé ≥ convention), écart (imprimé < convention), non vérifiable, ou
absente de la fiche. Un refus du moteur devient une ligne non vérifiable qui reprend son message. Seul un secteur
inconnu ou sans table transcrite fait refuser le rapport entier (Refus levé par calc/).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from .. import calc
from ..calc import Refus, Result
from ..calc.loaders import charger_grille, exiger_tables_transcrites
from ..calc.models import arrondi_millime
from ..calc.primes import _params_attendus
from . import documents as docs

CONFORME, ECART, NON_VERIFIABLE, ABSENTE = "conforme", "ecart", "non_verifiable", "absente_de_la_fiche"
STATUTS = (CONFORME, ECART, NON_VERIFIABLE, ABSENTE)

# Motifs propres au rapport ; les refus du moteur gardent leur code (SOURCE_MANQUANTE, PARAM_INVALIDE, HORS_SCOPE).
CHAMP_ABSENT = "CHAMP_ABSENT"
CONDITION_NON_VERIFIABLE = "CONDITION_NON_VERIFIABLE"
GROUPE_NON_LU = "GROUPE_NON_LU"
TRANSPORT_NON_LU = "TRANSPORT_NON_LU"
UNITE_DIFFERENTE = "UNITE_DIFFERENTE"
REGIME_DIFFERENT = "REGIME_DIFFERENT"
MOTIFS_RAPPORT = (
    CHAMP_ABSENT,
    CONDITION_NON_VERIFIABLE,
    GROUPE_NON_LU,
    TRANSPORT_NON_LU,
    UNITE_DIFFERENTE,
    REGIME_DIFFERENT,
)

# Motif court, pour la liste des documents manquants (FR, AR).
MOTIF_COURT: dict[str, tuple[str, str]] = {
    CONDITION_NON_VERIFIABLE: (
        "condition d'octroi non vérifiable sur la fiche",
        "شرط الإسناد غير قابل للتحقق من كشف الأجر",
    ),
    GROUPE_NON_LU: ("groupe non lu sur la fiche", "المجموعة غير مذكورة في كشف الأجر"),
    TRANSPORT_NON_LU: ("transport assuré non lu sur la fiche", "توفير النقل غير مذكور في كشف الأجر"),
    Refus.PARAM_INVALIDE: ("valeur refusée par le moteur", "قيمة رفضها المحرك"),
}

UNITES_PAIE = {"mensuel": "TND/mois", "horaire": "TND/heure"}
UNITE_PRIME_FICHE = "TND/mois"  # une prime imprimée est un montant du mois
_CLES_NON_GROUPE = {"effective_date", "au_titre_de", "montant"}


def fr(montant: str) -> str:
    """Montant écrit à la française : virgule décimale (aucun arrondi, aucun calcul)."""
    return montant.replace(".", ",")


def _ligne(rubrique: str, code: str | None, libelle_fr: str, libelle_ar: str) -> dict[str, Any]:
    return {
        "rubrique": rubrique,
        "code": code,
        "libelle_fr": libelle_fr,
        "libelle_ar": libelle_ar,
        "statut": NON_VERIFIABLE,
        "montant_convention": None,
        "unite": None,
        "montant_imprime": None,
        "difference": None,
        "citations": [],
        "hypotheses_fr": [],
        "hypotheses_ar": [],
        "motif": None,
        "observation": None,
        "documents": [],
    }


def _citations(r: Result) -> list[dict[str, Any]]:
    return [
        {
            "source_file": c.source_file,
            "page": c.page,
            "article": c.article,
            "data_file": c.data_file,
            "decision_ref": c.decision_ref,
        }
        for c in r.citations
    ]


def _ajouter_citations(ligne: dict, r: Result) -> None:
    for c in _citations(r):
        if c not in ligne["citations"]:
            ligne["citations"].append(c)


def _hypotheses(ligne: dict, r: Result) -> None:
    ligne["hypotheses_fr"] += [h for h in r.detail.get("hypotheses", []) if h not in ligne["hypotheses_fr"]]
    ligne["hypotheses_ar"] += [h for h in r.detail.get("hypotheses_ar", []) if h not in ligne["hypotheses_ar"]]


def _avec_resultat(ligne: dict, r: Result) -> None:
    ligne["montant_convention"], ligne["unite"] = str(r.montant), r.unite
    _ajouter_citations(ligne, r)
    _hypotheses(ligne, r)


def _motif(ligne: dict, code: str, message_fr: str, message_ar: str) -> None:
    ligne["statut"] = NON_VERIFIABLE
    ligne["motif"] = {"code": code, "message_fr": message_fr, "message_ar": message_ar}


def _refus(ligne: dict, e: Refus) -> None:
    _motif(ligne, e.code, e.message_fr, e.message_ar)


def _document(ligne: dict, *codes: str) -> None:
    for code in codes:
        if code not in ligne["documents"]:
            ligne["documents"].append(code)


def _difference(imprime: str, convention: Decimal) -> Decimal:
    return arrondi_millime(Decimal(imprime) - convention)


def _comparer(ligne: dict, imprime: str, r: Result) -> None:
    ligne["difference"] = str(_difference(imprime, r.montant))
    ligne["statut"] = CONFORME if Decimal(imprime) >= r.montant else ECART


def _illisibles(p: dict) -> dict[str, str]:
    return p.get("champs_illisibles") or {}


def raison_champ_fr(libelle: str, illisible: str | None) -> str:
    if illisible is not None:
        return f"champ « {libelle} » illisible ({illisible})"
    return f"champ « {libelle} » absent de la fiche"


def raison_champ_ar(libelle: str, illisible: str | None) -> str:
    if illisible is not None:
        return f"المعطى «{libelle}» غير مقروء ({illisible})"
    return f"المعطى «{libelle}» غير موجود في كشف الأجر"


def _champ_absent(ligne: dict, p: dict, champs: list[str]) -> None:
    """Motif CHAMP_ABSENT : chaque champ est nommé, avec la raison donnée par DS3 s'il est illisible."""
    ill = _illisibles(p)
    parties_fr, parties_ar = [], []
    for c in champs:
        lib_fr, lib_ar, document = docs.CHAMPS[c]
        raison = ill.get(c)
        parties_fr.append(raison_champ_fr(lib_fr, raison))
        parties_ar.append(raison_champ_ar(lib_ar, raison))
        _document(ligne, document)
    _motif(
        ligne,
        CHAMP_ABSENT,
        "Champ nécessaire non lu : " + " ; ".join(parties_fr) + ".",
        "معطى ضروري غير مقروء: " + "؛ ".join(parties_ar) + ".",
    )


def _absents(p: dict, champs: tuple[str, ...]) -> list[str]:
    return [c for c in champs if p.get(c) is None]


# --- 1. Salaire de base -------------------------------------------------------------------------------------------


def ligne_salaire(p: dict) -> dict:
    ligne = _ligne("salaire_base", None, "Salaire de base", "الأجر الأساسي")
    imprime = p.get("salaire_base_imprime")
    ligne["montant_imprime"] = imprime
    manquants = _absents(p, ("date", "categorie"))
    if manquants:
        _champ_absent(ligne, p, manquants)
        return ligne
    args = {k: p[k] for k in ("population", "categorie", "sous_categorie", "date") if p.get(k) is not None}
    anciennete, degre = p.get("anciennete_annees"), p.get("degre")
    if anciennete is not None:
        args["anciennete_annees"] = anciennete  # les deux donnés : l'ancienneté va au moteur, le degré est observé
    elif degre is not None:
        args["degre"] = degre
    try:
        r = calc.salaire_base(secteur=p["secteur"], **args)
    except Refus as e:
        _refus(ligne, e)
        if e.code == Refus.PARAM_INVALIDE:
            _document(ligne, *docs.DOCUMENTS_REFUS_SALAIRE)
        return ligne
    _avec_resultat(ligne, r)
    if anciennete is not None and degre is not None:
        deduit = r.detail.get("degre")
        deduit_txt = "—" if deduit is None else str(deduit)
        ligne["observation"] = {
            "degre_imprime": str(degre),
            "degre_deduit": deduit_txt,
            "message_fr": f"Degré imprimé sur la fiche : {degre} ; degré déduit de l'ancienneté : {deduit_txt}. "
            "L'échelon de la fiche peut ne pas correspondre au degré de la grille.",
            "message_ar": f"الدرجة المطبوعة في كشف الأجر: {degre}؛ الدرجة المستنتجة من الأقدمية: {deduit_txt}. "
            "قد لا تتطابق درجة كشف الأجر مع درجة جدول الأجور.",
        }
    if imprime is None:
        _champ_absent(ligne, p, ["salaire_base_imprime"])
        return ligne
    unite_fiche = UNITES_PAIE.get(p.get("mode_paie") or "")
    if unite_fiche is None:
        _champ_absent(ligne, p, ["mode_paie"])
        return ligne
    if r.unite != unite_fiche:
        _motif(
            ligne,
            UNITE_DIFFERENTE,
            f"La grille est en {r.unite}, le salaire imprimé en {unite_fiche} ; aucune conversion n'est faite (D6).",
            f"جدول الأجور بوحدة {r.unite} والأجر المطبوع بوحدة {unite_fiche}؛ لا يتم أي تحويل (D6).",
        )
        return ligne
    regime_grille, regime = r.detail.get("regime_hebdomadaire_heures"), p.get("regime_heures")
    if regime_grille is not None and regime is not None and regime != regime_grille:
        ligne["difference"] = str(_difference(imprime, r.montant))
        _motif(
            ligne,
            REGIME_DIFFERENT,
            f"La grille est établie pour {regime_grille} h, la fiche indique {regime} h ; "
            "aucune conversion n'est faite (D6).",
            f"جدول الأجور معدّ لنظام {regime_grille} ساعة، وكشف الأجر يذكر {regime} ساعة؛ لا يتم أي تحويل (D6).",
        )
        return ligne
    if regime_grille is not None and regime is None:
        ligne["hypotheses_fr"].append(
            f"Régime horaire de la fiche non lu : la grille est établie pour {regime_grille} h."
        )
        ligne["hypotheses_ar"].append(f"نظام العمل في كشف الأجر غير مقروء: جدول الأجور معدّ لنظام {regime_grille} ساعة.")
    _comparer(ligne, imprime, r)
    return ligne


# --- 2. Primes imprimées ------------------------------------------------------------------------------------------


def _entree_prime(grille: dict, code: str) -> dict | None:
    entree = next((x for x in grille.get("primes", []) if x["code"] == code), None)
    if entree is None:
        entree = grille.get("primes_non_couvertes", {}).get(code, {}).get("service_contrat_v1")
    return entree


def _groupes(entree: dict) -> list[str]:
    return sorted({k for ligne in entree.get("montants", []) for k in ligne if k not in _CLES_NON_GROUPE})


def ligne_prime(p: dict, grille: dict, imprimee: dict) -> dict:
    code = imprimee["code"]
    entree = _entree_prime(grille, code)
    ligne = _ligne(
        "prime",
        code,
        entree.get("label_fr", code) if entree else code,
        entree.get("label_ar", code) if entree else code,
    )
    ligne["montant_imprime"] = imprimee["montant"]
    if p.get("date") is None:
        _champ_absent(ligne, p, ["date"])
        return ligne
    params: dict[str, Any] = {k: imprimee[k] for k in ("groupe", "transport_assure", "variante") if k in imprimee}
    attendus = _params_attendus(entree) if entree else set()
    condition = "condition_remplie" in attendus
    if condition:
        params["condition_remplie"] = True  # seulement pour lire la condition et la citation ; jamais un montant dû
    secteur, date = p["secteur"], p["date"]

    if "groupe" in attendus and "groupe" not in params and entree is not None:
        montants_fr, montants_ar = [], []
        for g in _groupes(entree):
            try:
                r = calc.prime_v1(secteur, code, date, **params, groupe=g)
            except Refus:
                continue
            _ajouter_citations(ligne, r)
            lib_fr, lib_ar = r.detail.get("groupe_libelle", g), r.detail.get("groupe_libelle_ar", g)
            montants_fr.append(f"{fr(str(r.montant))} {r.unite} ({lib_fr})")
            montants_ar.append(f"{r.montant} {r.unite} ({lib_ar})")
        _motif(
            ligne,
            GROUPE_NON_LU,
            "Le groupe n'est pas indiqué sur la fiche ; montants de la convention selon le groupe : "
            + (", ".join(montants_fr) or "aucun montant servi à cette date")
            + ".",
            "المجموعة غير مذكورة في كشف الأجر؛ مبالغ الاتفاقية حسب المجموعة: "
            + ("، ".join(montants_ar) or "لا يوجد مبلغ في هذا التاريخ")
            + ".",
        )
        _document(ligne, docs.DOCUMENT_GROUPE)
        if condition:
            _document(ligne, docs.DOCUMENT_CONDITION)
        return ligne
    if "transport_assure" in attendus and "transport_assure" not in params:
        _motif(
            ligne,
            TRANSPORT_NON_LU,
            "La fiche n'indique pas si le transport est assuré par l'employeur ; le montant de la convention en dépend.",
            "لا يذكر كشف الأجر إن كان المؤجر يوفر النقل؛ ومبلغ الاتفاقية مرتبط بذلك.",
        )
        _document(ligne, docs.DOCUMENT_CONDITION)
        return ligne

    try:
        r = calc.prime_v1(secteur, code, date, **params)
    except Refus as e:
        _refus(ligne, e)
        return ligne
    if condition:
        _ajouter_citations(ligne, r)
        _hypotheses(ligne, r)
        texte = r.detail.get("condition", "")
        _motif(
            ligne,
            CONDITION_NON_VERIFIABLE,
            f"Prime soumise à une condition que la fiche ne permet pas de vérifier : « {texte} ».",
            f"منحة مشروطة لا يسمح كشف الأجر بالتحقق من شرطها: «{texte}».",
        )
        _document(ligne, docs.DOCUMENT_CONDITION)
        return ligne
    _avec_resultat(ligne, r)
    if r.unite != UNITE_PRIME_FICHE:
        _motif(
            ligne,
            UNITE_DIFFERENTE,
            f"La convention fixe ce montant en {r.unite}, la fiche imprime un montant du mois ; "
            "aucune conversion n'est faite (D6).",
            f"تحدد الاتفاقية هذا المبلغ بوحدة {r.unite}، وكشف الأجر يذكر مبلغا شهريا؛ لا يتم أي تحويل (D6).",
        )
        return ligne
    _comparer(ligne, imprimee["montant"], r)
    return ligne


# --- 3. Primes absentes de la fiche --------------------------------------------------------------------------------


def lignes_primes_absentes(p: dict, grille: dict, codes_imprimes: set[str]) -> list[dict]:
    """Primes de la grille en TND/mois, sans condition, sans groupe, sans transport, servies par le moteur à la date."""
    if p.get("date") is None:
        return []
    lignes = []
    for entree in grille.get("primes", []):
        code = entree["code"]
        if (
            code in codes_imprimes
            or entree["unite"] != UNITE_PRIME_FICHE
            or not _params_attendus(entree) <= {"variante"}
        ):
            continue
        try:
            r = calc.prime_v1(p["secteur"], code, p["date"])
        except Refus:
            continue
        ligne = _ligne("prime_absente", code, entree.get("label_fr", code), entree.get("label_ar", code))
        _avec_resultat(ligne, r)
        ligne["statut"] = ABSENTE
        lignes.append(ligne)
    return lignes


# --- 4. SMIG ------------------------------------------------------------------------------------------------------


def ligne_smig(p: dict) -> dict:
    regime, mode = p.get("regime_heures"), p.get("mode_paie")
    suffixe_fr = f" ({regime} h, {mode})" if regime is not None and mode is not None else ""
    suffixe_ar = f" ({regime} ساعة)" if regime is not None else ""
    ligne = _ligne("smig", None, "SMIG" + suffixe_fr, "الأجر الأدنى المضمون" + suffixe_ar)
    imprime = p.get("salaire_base_imprime")
    ligne["montant_imprime"] = imprime
    manquants = _absents(p, ("date", "regime_heures", "mode_paie", "salaire_base_imprime"))
    if manquants:
        _champ_absent(ligne, p, manquants)
        return ligne
    try:
        r = calc.smig(mode=p["mode_paie"], regime_heures=p["regime_heures"], date=p["date"])
    except Refus as e:
        _refus(ligne, e)
        return ligne
    _avec_resultat(ligne, r)
    ligne["hypotheses_fr"].append("Comparaison faite avec le salaire de base imprimé seul, sans les primes.")
    ligne["hypotheses_ar"].append("المقارنة مع الأجر الأساسي المطبوع وحده، دون المنح.")
    _comparer(ligne, p["salaire_base_imprime"], r)
    return ligne


# --- 5. Documents manquants ---------------------------------------------------------------------------------------


def champs_manquants(p: dict) -> list[dict]:
    ill = _illisibles(p)
    out: list[dict[str, Any]] = []
    for champ in docs.CHAMPS:
        if champ in ill:
            out.append({"champ": champ, "etat": "illisible", "raison": ill[champ]})
        elif champ in docs.CHAMPS_ATTENDUS and p.get(champ) is None:
            out.append({"champ": champ, "etat": "absent", "raison": None})
    return out


def documents_manquants(p: dict, champs: list[dict], lignes: list[dict]) -> list[dict]:
    fournis = set(p.get("documents_fournis") or [])
    besoins: dict[str, tuple[list[str], list[str]]] = {}

    def ajouter(document: str, raison_fr: str, raison_ar: str) -> None:
        if document in fournis:
            return
        rfr, rar = besoins.setdefault(document, ([], []))
        if raison_fr not in rfr:
            rfr.append(raison_fr)
            rar.append(raison_ar)

    for c in champs:
        lib_fr, lib_ar, document = docs.CHAMPS[c["champ"]]
        ajouter(document, raison_champ_fr(lib_fr, c["raison"]), raison_champ_ar(lib_ar, c["raison"]))
    for ligne in lignes:
        motif = ligne["motif"]
        court = MOTIF_COURT.get(motif["code"]) if motif else None
        for document in ligne["documents"]:
            if court is None:  # CHAMP_ABSENT : déjà donné par le champ
                continue
            ajouter(document, f"{ligne['libelle_fr']} : {court[0]}", f"{ligne['libelle_ar']}: {court[1]}")
    return [
        {
            "document": d,
            "libelle_fr": docs.DOCUMENTS[d][0],
            "libelle_ar": docs.DOCUMENTS[d][1],
            "raisons_fr": rfr,
            "raisons_ar": rar,
        }
        for d, (rfr, rar) in besoins.items()
    ]


# --- Rapport ------------------------------------------------------------------------------------------------------


def rapport_conformite(p: dict) -> dict:
    """p : params de la requête (déjà conformes au schéma). Refus seulement pour un secteur inconnu ou sans table."""
    secteur = p["secteur"]
    grille = charger_grille(secteur)
    exiger_tables_transcrites(grille, secteur)
    imprimees = p.get("primes_imprimees") or []
    lignes = [ligne_salaire(p)]
    lignes += [ligne_prime(p, grille, x) for x in imprimees]
    lignes += lignes_primes_absentes(p, grille, {x["code"] for x in imprimees})
    lignes.append(ligne_smig(p))
    champs = champs_manquants(p)
    return {
        "secteur": secteur,
        "convention_ar": grille["_meta"].get("convention_ar"),
        "fiche": {
            k: p.get(k)
            for k in (
                "population",
                "categorie",
                "sous_categorie",
                "anciennete_annees",
                "degre",
                "date",
                "regime_heures",
                "mode_paie",
            )
        },
        "origines": dict(p.get("origines") or {}),
        "lignes": lignes,
        "champs_manquants": champs,
        "documents_fournis": list(p.get("documents_fournis") or []),
        "documents_manquants": documents_manquants(p, champs, lignes),
        "bilan": {s: sum(ligne["statut"] == s for ligne in lignes) for s in STATUTS},
        "aucune_ligne_verifiee": not any(ligne["statut"] in (CONFORME, ECART) for ligne in lignes),
    }


def citations(rapport: dict) -> list[dict]:
    """Union, sans doublon et dans l'ordre des lignes, des citations du rapport."""
    out: list[dict] = []
    for ligne in rapport["lignes"]:
        for c in ligne["citations"]:
            if c not in out:
                out.append(c)
    return out
