"""SMIG non agricole (décret gouvernemental n°769/2022) — D2, D3, D6."""
from __future__ import annotations

import datetime as dt

from .loaders import SMIG_FILE, charger_smig, decision_ref_smig
from .models import Citation, Refus, Result, arrondi_millime, parse_date

UNITES = {"mensuel": "TND/mois", "horaire": "TND/heure"}


def smig(mode: str, regime_heures: int, date) -> Result:
    data = charger_smig()
    bloc = data["smig_non_agricole"]
    decret = bloc["decree"]
    jour = parse_date(date)

    page = bloc.get("source_pdf_page")
    if isinstance(page, bool) or not isinstance(page, int):
        raise Refus(Refus.SOURCE_MANQUANTE,
                    f"Page source du barème SMIG absente de {SMIG_FILE} (smig_non_agricole.source_pdf_page) : "
                    "montant non citable.",
                    f"صفحة مصدر جدول الأجر الأدنى غير موجودة في {SMIG_FILE}: لا يمكن الاستشهاد بالمبلغ.")
    ref = decision_ref_smig(bloc)

    modes = sorted({l["mode_remuneration"] for l in bloc["bareme"]})
    if mode not in modes:
        raise Refus(Refus.PARAM_INVALIDE, f"Mode de rémunération inconnu : {mode!r} (attendu : {', '.join(modes)}).",
                    f"طريقة تأجير غير معروفة: {mode!r} (المتوفر: {', '.join(modes)}).")
    if isinstance(regime_heures, bool) or not isinstance(regime_heures, int):
        raise Refus(Refus.PARAM_INVALIDE, f"Régime hebdomadaire invalide : {regime_heures!r} (entier attendu).",
                    f"نظام العمل الأسبوعي غير صالح: {regime_heures!r} (المطلوب عدد صحيح).")

    effet = dt.date.fromisoformat(decret["effective_date"])
    if jour < effet:
        raise Refus(Refus.SOURCE_MANQUANTE,
                    f"Seul le barème du décret n°{decret['number']}/{decret['year']} (effet {effet.isoformat()}) "
                    f"est vérifié ; aucun SMIG disponible au {jour.isoformat()}.",
                    f"جدول الأمر عدد {decret['number']} لسنة {decret['year']} (نافذ منذ {effet.isoformat()}) هو "
                    f"الوحيد المُتحقَّق منه؛ لا يتوفر أجر أدنى بتاريخ {jour.isoformat()}.")

    ligne = next((l for l in bloc["bareme"]
                  if l["mode_remuneration"] == mode and l["regime_hebdomadaire_heures"] == regime_heures), None)
    if ligne is None:
        regimes = sorted({l["regime_hebdomadaire_heures"] for l in bloc["bareme"] if l["mode_remuneration"] == mode})
        raise Refus(Refus.SOURCE_MANQUANTE,
                    f"Régime de {regime_heures} h absent du barème SMIG ({mode} : {regimes} h). "
                    "Aucune interpolation entre régimes n'est écrite dans la source.",
                    f"نظام {regime_heures} ساعة غير موجود في جدول الأجر الأدنى ({mode}: {regimes}). "
                    "لا ينص المصدر على أي احتساب بين الأنظمة.")

    return Result(
        montant=arrondi_millime(ligne["montant"]),
        unite=UNITES.get(mode, f"TND/{mode}"),
        detail={
            "mode_remuneration": mode,
            "regime_hebdomadaire_heures": regime_heures,
            "decret": f"{decret['number']}/{decret['year']}",
            "effective_date": decret["effective_date"],
            "date_calcul": jour.isoformat(),
            "regles": "D6",
        },
        citations=[Citation(
            source_file=data["_meta"]["source_file"],
            page=page,
            article=f"décret gouvernemental n°{decret['number']} du {decret['date']}",
            data_file=SMIG_FILE,
            decision_ref=ref,
        )],
    )
