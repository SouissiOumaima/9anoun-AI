"""Rendu lisible du rapport de conformité, en français et en arabe, à partir de modèles fixes (D108).

Aucun texte n'est généré : chaque phrase est un modèle écrit ici, rempli avec les valeurs du rapport (montants
recopiés tels quels, messages du moteur recopiés tels quels).
"""

from __future__ import annotations

from pathlib import PurePosixPath

from .conformite import ABSENTE, CONFORME, ECART, MOTIFS_RAPPORT, NON_VERIFIABLE, STATUTS, fr

STATUT_FR = {CONFORME: "conforme", ECART: "écart", NON_VERIFIABLE: "non vérifiable", ABSENTE: "absente de la fiche"}
STATUT_AR = {
    CONFORME: "مطابق",
    ECART: "فارق",
    NON_VERIFIABLE: "غير قابل للتحقق",
    ABSENTE: "غير مذكورة في كشف الأجر",
}
BILAN_FR = {
    CONFORME: "conforme(s)",
    ECART: "écart(s)",
    NON_VERIFIABLE: "non vérifiable(s)",
    ABSENTE: "absente(s) de la fiche",
}
BILAN_AR = {CONFORME: "مطابق", ECART: "فارق", NON_VERIFIABLE: "غير قابل للتحقق", ABSENTE: "غير مذكورة في كشف الأجر"}

ORIGINE_FR = {
    "carte": "pris dans la carte du dossier",
    "utilisateur": "déclaré par l'utilisateur",
    "fiche": "lu sur la fiche",
}
ORIGINE_AR = {"carte": "مأخوذ من بطاقة الملف", "utilisateur": "مصرح به من المستعمل", "fiche": "مقروء من كشف الأجر"}
# Accord au féminin pour la population (« population déclarée par l'utilisateur »).
ORIGINE_FR_F = {
    "carte": "prise dans la carte du dossier",
    "utilisateur": "déclarée par l'utilisateur",
    "fiche": "lue sur la fiche",
}

CHAMPS_FICHE_FR = (
    ("population", "Population"),
    ("categorie", "Catégorie"),
    ("sous_categorie", "Sous-catégorie"),
    ("anciennete_annees", "Ancienneté (années)"),
    ("degre", "Degré"),
    ("date", "Période"),
    ("regime_heures", "Régime horaire (h/semaine)"),
    ("mode_paie", "Mode de paie"),
)
CHAMPS_FICHE_AR = {
    "population": "الفئة",
    "categorie": "الصنف",
    "sous_categorie": "الصنف الفرعي",
    "anciennete_annees": "الأقدمية (سنوات)",
    "degre": "الدرجة",
    "date": "الفترة",
    "regime_heures": "نظام العمل (ساعة في الأسبوع)",
    "mode_paie": "طريقة التأجير",
}
FEMININ = {"population", "categorie", "sous_categorie", "anciennete_annees", "date"}


def _article(article: str, mot: str) -> str:
    """« article 50 (جديد) » pour un numéro d'article ; un décret est cité tel quel."""
    return f"{mot} {article}" if article[:1].isdigit() else article


def _source_fr(c: dict) -> str:
    page = f", page {c['page']}" if c["page"] is not None else ""
    art = f", {_article(c['article'], 'article')}" if c["article"] else ""
    return f"{PurePosixPath(c['source_file']).name}{page}{art} ; décision {c['decision_ref']}"


def _source_ar(c: dict) -> str:
    page = f"، الصفحة {c['page']}" if c["page"] is not None else ""
    art = f"، {_article(c['article'], 'الفصل')}" if c["article"] else ""
    return f"{PurePosixPath(c['source_file']).name}{page}{art}؛ القرار {c['decision_ref']}"


MODE_AR = {"mensuel": "شهري", "horaire": "بالساعة"}


def _valeur(v: object) -> str:
    return str(v)


def texte_fr(r: dict) -> str:
    origines = r["origines"]
    o = origines.get("secteur")
    lignes = ["RAPPORT DE CONFORMITÉ D'UNE FICHE DE PAIE", ""]
    lignes.append(f"Secteur : {r['secteur']}" + (f" ({ORIGINE_FR[o]})" if o else ""))
    for champ, libelle in CHAMPS_FICHE_FR:
        v = r["fiche"].get(champ)
        if v is None:
            continue
        o = origines.get(champ)
        precision = (ORIGINE_FR_F if champ in FEMININ else ORIGINE_FR).get(o, "") if o else ""
        lignes.append(f"{libelle} : {_valeur(v)}" + (f" ({precision})" if precision else ""))
    lignes.append("")
    if r["aucune_ligne_verifiee"]:
        lignes += [
            "Aucune ligne n'a pu être vérifiée : ce rapport indique seulement ce qui manque pour conclure.",
            "",
        ]
    for i, ligne in enumerate(r["lignes"], 1):
        lignes.append(f"{i}. {ligne['libelle_fr']} : {STATUT_FR[ligne['statut']]}")
        if ligne["montant_convention"] is not None:
            lignes.append(f"   Montant de la convention : {fr(ligne['montant_convention'])} {ligne['unite']}")
        if ligne["montant_imprime"] is not None:
            lignes.append(f"   Montant imprimé : {fr(ligne['montant_imprime'])}")
        if ligne["difference"] is not None:
            lignes.append(f"   Différence (imprimé − convention) : {fr(ligne['difference'])}")
        if ligne["statut"] == ABSENTE:
            lignes.append("   Signalée seulement : la fiche ne permet pas de dire si cette prime est due.")
        m = ligne["motif"]
        if m is not None:
            prefixe = "Raison" if m["code"] in MOTIFS_RAPPORT else f"Refus du moteur ({m['code']})"
            lignes.append(f"   {prefixe} : {m['message_fr']}")
        if ligne["observation"] is not None:
            lignes.append(f"   Observation : {ligne['observation']['message_fr']}")
        for h in ligne["hypotheses_fr"]:
            lignes.append(f"   Hypothèse : {h}")
        for c in ligne["citations"]:
            lignes.append(f"   Source : {_source_fr(c)}")
    lignes.append("")
    if r["documents_manquants"]:
        lignes.append("Documents qui permettraient de conclure :")
        for d in r["documents_manquants"]:
            lignes.append(f"- {d['libelle_fr']} — {' ; '.join(d['raisons_fr'])}.")
    else:
        lignes.append("Aucun document manquant.")
    lignes.append("")
    b = r["bilan"]
    lignes.append("Bilan : " + ", ".join(f"{b[s]} {BILAN_FR[s]}" for s in STATUTS) + ".")
    lignes.append(
        "Ce rapport compare la fiche aux montants de la convention, avec leurs sources ; "
        "il ne dit pas qu'une somme est due."
    )
    return "\n".join(lignes) + "\n"


def texte_ar(r: dict) -> str:
    origines = r["origines"]
    o = origines.get("secteur")
    lignes = ["تقرير مطابقة كشف الأجر", ""]
    lignes.append(f"القطاع: {r['secteur']}" + (f" ({ORIGINE_AR[o]})" if o else ""))
    for champ, _ in CHAMPS_FICHE_FR:
        v = r["fiche"].get(champ)
        if v is None:
            continue
        o = origines.get(champ)
        valeur = MODE_AR.get(str(v), str(v)) if champ == "mode_paie" else _valeur(v)
        lignes.append(f"{CHAMPS_FICHE_AR[champ]}: {valeur}" + (f" ({ORIGINE_AR[o]})" if o else ""))
    lignes.append("")
    if r["aucune_ligne_verifiee"]:
        lignes += ["لم يتسنّ التحقق من أي سطر: يبيّن هذا التقرير فقط ما ينقص للحسم.", ""]
    for i, ligne in enumerate(r["lignes"], 1):
        lignes.append(f"{i}. {ligne['libelle_ar']}: {STATUT_AR[ligne['statut']]}")
        if ligne["montant_convention"] is not None:
            lignes.append(f"   مبلغ الاتفاقية: {ligne['montant_convention']} {ligne['unite']}")
        if ligne["montant_imprime"] is not None:
            lignes.append(f"   المبلغ المطبوع: {ligne['montant_imprime']}")
        if ligne["difference"] is not None:
            lignes.append(f"   الفارق (المطبوع − الاتفاقية): {ligne['difference']}")
        if ligne["statut"] == ABSENTE:
            lignes.append("   للإشارة فقط: لا يسمح كشف الأجر بالقول إن هذه المنحة مستحقة.")
        m = ligne["motif"]
        if m is not None:
            prefixe = "السبب" if m["code"] in MOTIFS_RAPPORT else f"رفض المحرك ({m['code']})"
            lignes.append(f"   {prefixe}: {m['message_ar']}")
        if ligne["observation"] is not None:
            lignes.append(f"   ملاحظة: {ligne['observation']['message_ar']}")
        for h in ligne["hypotheses_ar"]:
            lignes.append(f"   فرضية: {h}")
        for c in ligne["citations"]:
            lignes.append(f"   المصدر: {_source_ar(c)}")
    lignes.append("")
    if r["documents_manquants"]:
        lignes.append("الوثائق التي تسمح بالحسم:")
        for d in r["documents_manquants"]:
            lignes.append(f"- {d['libelle_ar']} — {'؛ '.join(d['raisons_ar'])}.")
    else:
        lignes.append("لا توجد وثيقة ناقصة.")
    lignes.append("")
    b = r["bilan"]
    lignes.append("الحصيلة: " + "، ".join(f"{BILAN_AR[s]}: {b[s]}" for s in STATUTS) + ".")
    lignes.append("يقارن هذا التقرير كشف الأجر بمبالغ الاتفاقية مع مصادرها؛ ولا يعني أن مبلغا ما مستحق.")
    return "\n".join(lignes) + "\n"
