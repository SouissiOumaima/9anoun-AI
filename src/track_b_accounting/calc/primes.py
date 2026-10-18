"""Primes conventionnelles de la section "primes" d'une grille sectorielle (D4, D6).

Les paramètres exigés dépendent de ce que contient l'entrée JSON de la prime :
- montants datés à plusieurs colonnes (ex. prime_transport) → groupe=<colonne> ;
- complement_si_prime_superieure → variante="base" (défaut) | "complement_si_prime_superieure" ;
- montant_reduit_si_transport_assure → transport_assure=True|False (obligatoire) ;
- condition (texte) → condition_remplie=True|False (obligatoire ; False → Refus HORS_SCOPE).
"""
from __future__ import annotations

from .loaders import GRILLES, charger_grille, decision_ref, exiger_tables_transcrites
from .models import Citation, Refus, Result, arrondi_millime, parse_date, plus_recent_avant

_CLES_NON_MONTANT = {"effective_date", "au_titre_de"}
_COMPLEMENT = "complement_si_prime_superieure"


def _bool_obligatoire(params: dict, nom: str, code: str) -> bool:
    v = params.get(nom)
    if not isinstance(v, bool):
        raise Refus(Refus.PARAM_INVALIDE, f"{code} : paramètre {nom}=True|False obligatoire (reçu {v!r}).",
                    f"{code}: المعامل {nom} إلزامي (True أو False)، القيمة المستلمة {v!r}.")
    return v


def _params_attendus(p: dict) -> set[str]:
    attendus = set()
    montants = p.get("montants") or []
    if montants and "montant" not in montants[0]:
        attendus.add("groupe")
    if _COMPLEMENT in p:
        attendus.add("variante")
    if "montant_reduit_si_transport_assure" in p:
        attendus.add("transport_assure")
    if "condition" in p:
        attendus.add("condition_remplie")
    return attendus


def _notes(p: dict, detail: dict) -> None:
    """Mention de la source reproduite sans calcul (ex. décrets exclus de la prime de transport), FR puis AR."""
    if "note" in p:
        detail["note"] = p["note"]
    if "note_ar" in p:
        detail["note_ar"] = p["note_ar"]


def _ligne_datee(lignes: list[dict], jour, code: str) -> dict:
    ligne = plus_recent_avant(lignes, jour)
    if ligne is None:
        premiere = min(l["effective_date"] for l in lignes)
        raise Refus(Refus.SOURCE_MANQUANTE,
                    f"{code} : aucun montant en vigueur au {jour.isoformat()} (première date d'effet : {premiere}).",
                    f"{code}: لا يوجد مبلغ ساري المفعول بتاريخ {jour.isoformat()} (أول تاريخ نفاذ: {premiere}).")
    return ligne


def prime(secteur: str, code: str, date, **params) -> Result:
    grille = charger_grille(secteur)
    jour = parse_date(date)
    if code in grille.get("primes_non_couvertes", {}):
        # Prime présente dans la source mais non exposée (ex. condition ambiguë) : refus lu dans le JSON (D9).
        bloc = grille["primes_non_couvertes"][code]
        raise Refus(Refus.SOURCE_MANQUANTE, bloc["message_fr"], bloc["message_ar"])
    exiger_tables_transcrites(grille, secteur)
    p = next((x for x in grille.get("primes", []) if x["code"] == code), None)
    if p is None:
        codes = ", ".join(x["code"] for x in grille.get("primes", [])) or "aucune prime transcrite"
        raise Refus(Refus.SOURCE_MANQUANTE, f"Prime {code!r} absente des données vérifiées ({secteur} : {codes}).",
                    f"المنحة {code!r} غير موجودة في البيانات المُتحقَّق منها ({secteur}).")

    inconnus = set(params) - _params_attendus(p)
    if inconnus:
        raise Refus(Refus.PARAM_INVALIDE,
                    f"{code} : paramètre(s) non prévu(s) : {', '.join(sorted(inconnus))} "
                    f"(acceptés : {', '.join(sorted(_params_attendus(p))) or 'aucun'}).",
                    f"{code}: معامل غير متوقع: {', '.join(sorted(inconnus))}.")

    detail = {"secteur": secteur, "code": code}
    # Libellé de la prime : label_ar tel qu'imprimé, label_fr traduction (pas une citation).
    for cle in ("label_fr", "label_ar"):
        if p.get(cle):
            detail[cle] = p[cle]
    detail.update(date_calcul=jour.isoformat(), regles="D6")

    if "condition" in p:
        if not _bool_obligatoire(params, "condition_remplie", code):
            raise Refus(Refus.HORS_SCOPE,
                        f"{code} : condition d'octroi non remplie ({p['condition']}) ; la source ne prévoit "
                        "aucun montant dans ce cas.",
                        f"{code}: شرط الإسناد غير متوفر؛ لا ينص المصدر على أي مبلغ في هذه الحالة.")
        detail["condition"] = p["condition"]

    if "montants" in p:
        variante = params.get("variante", "base")
        if variante not in ("base", _COMPLEMENT) or (variante == _COMPLEMENT and _COMPLEMENT not in p):
            raise Refus(Refus.PARAM_INVALIDE, f"{code} : variante inconnue {variante!r}.",
                        f"{code}: صيغة غير معروفة {variante!r}.")
        ligne = _ligne_datee(p[_COMPLEMENT] if variante == _COMPLEMENT else p["montants"], jour, code)
        if "montant" in ligne:
            valeur = ligne["montant"]
        else:
            groupes = sorted(set(ligne) - _CLES_NON_MONTANT)
            groupe = params.get("groupe")
            if groupe not in groupes:
                raise Refus(Refus.PARAM_INVALIDE, f"{code} : groupe={groupe!r} invalide (attendu : {', '.join(groupes)}).",
                            f"{code}: الصنف {groupe!r} غير صالح (المتوفر: {', '.join(groupes)}).")
            valeur = ligne[groupe]
            detail["groupe"] = groupe
            libelle = p.get("libelles_groupes", {}).get(groupe)
            if libelle:
                detail["groupe_libelle"], detail["groupe_libelle_ar"] = libelle["fr"], libelle["ar"]
        if "variante" in _params_attendus(p):
            detail["variante"] = variante
        detail["effective_date"] = ligne["effective_date"]
        if "au_titre_de" in ligne:
            detail["au_titre_de"] = ligne["au_titre_de"]
        _notes(p, detail)
    else:
        # Montant unique : la source ne fixe pas de date d'effet distincte (cf. D4, prime_panier_qefa).
        valeur = p["montant"]
        detail["effective_date"] = p.get("effective_date")
        _notes(p, detail)
        if "montant_reduit_si_transport_assure" in p:
            transport = _bool_obligatoire(params, "transport_assure", code)
            detail["transport_assure"] = transport
            if transport:
                valeur = p["montant_reduit_si_transport_assure"]

    hyp = p.get("hypotheses")
    if hyp:
        # Interprétations affichées (ex. « لكل الأصناف » : même montant pour toutes les catégories).
        detail["hypotheses"], detail["hypotheses_ar"] = list(hyp["fr"]), list(hyp["ar"])

    ref = decision_ref(grille, secteur)
    return Result(
        montant=arrondi_millime(valeur),
        unite=p["unite"],
        detail=detail,
        citations=[Citation(
            source_file=grille["_meta"]["source_file"],
            page=p["source_pdf_page"],
            article=p["source_article"],
            data_file=GRILLES[secteur],
            decision_ref=ref,
        )],
    )
