"""Vocabulaire FICTIF des fiches de paie et conventions collectives tunisiennes (FR et AR).

Toutes les lignes générées à partir de ces listes sont inventées : aucun nom, montant ou document réel.
Le jeu « générique » (phrases de la vie courante) sert à mesurer l'oubli catastrophique.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Final

LABELS_FR: Final = (
    "Salaire de base", "Prime de transport", "Prime de présence", "Indemnité de logement",
    "Prime de rendement", "Prime de productivité", "Heures supplémentaires", "Salaire brut",
    "Salaire net", "Net à payer", "Retenue CNSS", "Cotisation CNSS", "Impôt sur le revenu",
    "Contribution sociale de solidarité", "Avance sur salaire", "Allocations familiales",
    "Congé payé", "Indemnité kilométrique", "Prime d'ancienneté", "Prime de panier",
    "Total des gains", "Total des retenues", "Salaire minimum garanti", "Augmentation de salaire",
)
LABELS_AR: Final = (
    "الأجر الأساسي", "منحة النقل", "منحة الحضور", "منحة السكن", "منحة المردودية", "منحة الإنتاج",
    "الساعات الإضافية", "الأجر الخام", "الأجر الصافي", "الصافي للدفع", "الخصم بعنوان الضمان الاجتماعي",
    "الضريبة على الدخل", "المساهمة الاجتماعية التضامنية", "تسبقة على الأجر", "المنح العائلية",
    "العطلة السنوية خالصة الأجر", "منحة الأقدمية", "منحة القفة", "مجموع المداخيل", "مجموع الخصومات",
    "الأجر الأدنى المضمون", "الزيادة في الأجور",
)
QUALIFS_FR: Final = (
    "Agent administratif", "Ouvrier qualifié", "Agent de gardiennage", "Chef d'équipe", "Technicien",
    "Agent de maîtrise", "Comptable", "Chauffeur", "Agent d'exécution", "Cadre",
)
QUALIFS_AR: Final = (
    "عون إداري", "عامل مختص", "عون حراسة", "رئيس فريق", "تقني", "عون تسيير", "محاسب", "سائق",
    "عون تنفيذ", "إطار",
)
SECTORS_FR: Final = (
    "du gardiennage", "du textile", "du bâtiment", "du commerce", "de l'hôtellerie", "des banques",
    "de l'industrie alimentaire", "du transport de fonds",
)
SECTORS_AR: Final = (
    "الحراسة", "النسيج", "البناء", "التجارة", "النزل", "البنوك", "الصناعات الغذائية", "نقل الأموال",
)
CLAUSES_FR: Final = (
    "Le salaire est payé chaque mois", "La période d'essai est de six mois",
    "Le travailleur a droit à un congé annuel", "Les heures supplémentaires sont majorées",
    "La prime est versée au prorata", "Le présent accord entre en vigueur",
)
CLAUSES_AR: Final = (
    "يصرف الأجر في آخر كل شهر", "مدة التجربة ستة أشهر", "للعامل الحق في عطلة سنوية",
    "تحتسب الساعات الإضافية بزيادة", "تصرف المنحة حسب أيام العمل", "يدخل هذا الاتفاق حيز التنفيذ",
)
MONTHS_FR: Final = (
    "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
    "novembre", "décembre",
)
MONTHS_AR: Final = (
    "جانفي", "فيفري", "مارس", "أفريل", "ماي", "جوان", "جويلية", "أوت", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
)
CATEGORIES: Final = ("1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "1B", "2A")
SUBCATS: Final = ("I", "II", "III", "IV")

GENERIC_FR: Final = (
    "Le train part de la gare à huit heures", "Il fait beau ce matin sur la côte",
    "Les enfants jouent dans le jardin public", "Nous avons acheté du pain et des olives",
    "La réunion de famille aura lieu dimanche", "Le marché central ouvre tôt le samedi",
    "Elle lit un roman au bord de la mer", "Le musée accueille une nouvelle exposition",
    "La pluie est attendue dans le nord du pays", "Mon frère prépare un examen difficile",
)
GENERIC_AR: Final = (
    "ذهب الطفل إلى المدرسة في الصباح", "الطقس جميل اليوم على الشاطئ", "اشترينا الخبز والزيتون من السوق",
    "يقرأ الرجل الجريدة في المقهى", "تفتح المكتبة أبوابها كل يوم", "سافرت العائلة إلى الجنوب في الصيف",
    "يلعب الأطفال في الحديقة العمومية", "ينتظر المسافرون القطار في المحطة", "زرنا المتحف الوطني يوم الأحد",
    "تهطل الأمطار في الشمال هذا الأسبوع",
)

MAX_LEN: Final = 44
"""Longueur maximale d'une ligne (au-delà, on tire une autre ligne)."""


def amount(rng: random.Random) -> str:
    """Montant en dinars au format des fiches de paie : 3 décimales, point (ex. 424.100)."""
    return f"{rng.randint(1, 2999)}.{rng.randint(0, 999):03d}"


def date(rng: random.Random) -> str:
    return f"{rng.randint(1, 28):02d}/{rng.randint(1, 12):02d}/{rng.randint(2015, 2026)}"


def _fr(rng: random.Random) -> str:
    c = rng.choice
    templates: list[Callable[[], str]] = [
        lambda: f"{c(LABELS_FR)} {amount(rng)}",
        lambda: f"{c(LABELS_FR)} : {amount(rng)} DT",
        lambda: f"{c(LABELS_FR)} {rng.choice(['208', '173.33', '26'])} {amount(rng)}",
        lambda: f"Catégorie {c(CATEGORIES)} Échelon {rng.randint(1, 12)}",
        lambda: f"Catégorie {c(CATEGORIES)} sous-catégorie {c(SUBCATS)}",
        lambda: f"Article {rng.randint(1, 60)} : {c(CLAUSES_FR)}",
        lambda: f"Période du {date(rng)} au {date(rng)}",
        lambda: f"Date d'embauche : {date(rng)}",
        lambda: f"Mois de {c(MONTHS_FR)} {rng.randint(2018, 2026)}",
        lambda: f"Régime horaire : {rng.choice(['40', '48'])} heures",
        lambda: f"Convention collective {c(SECTORS_FR)}",
        lambda: f"Qualification : {c(QUALIFS_FR)}",
        lambda: f"Matricule CNSS : {rng.randint(10**7, 10**8 - 1)}-{rng.randint(10, 99)}",
    ]
    return c(templates)()


def _ar(rng: random.Random) -> str:
    c = rng.choice
    templates: list[Callable[[], str]] = [
        lambda: f"{c(LABELS_AR)} {amount(rng)}",
        lambda: f"{c(LABELS_AR)} : {amount(rng)} د",
        lambda: f"الصنف {c(CATEGORIES)} الدرجة {rng.randint(1, 12)}",
        lambda: f"الفصل {rng.randint(1, 60)} : {c(CLAUSES_AR)}",
        lambda: f"الفترة من {date(rng)} إلى {date(rng)}",
        lambda: f"تاريخ الانتداب : {date(rng)}",
        lambda: f"شهر {c(MONTHS_AR)} {rng.randint(2018, 2026)}",
        lambda: f"نظام {rng.choice(['40', '48'])} ساعة في الأسبوع",
        lambda: f"الاتفاقية المشتركة لقطاع {c(SECTORS_AR)}",
        lambda: f"المؤهل المهني : {c(QUALIFS_AR)}",
        lambda: f"{c(LABELS_AR)} {c(LABELS_FR)}",  # ligne bilingue (mixte)
    ]
    return c(templates)()


def domain_line(rng: random.Random, p_arabic: float = 0.5) -> str:
    """Une ligne fictive de fiche de paie ou de convention collective (≈ moitié FR, moitié AR)."""
    while True:
        text = _ar(rng) if rng.random() < p_arabic else _fr(rng)
        if len(text) <= MAX_LEN:
            return text


def generic_line(rng: random.Random) -> str:
    """Une phrase de la vie courante, hors domaine (pour mesurer l'oubli)."""
    return rng.choice(GENERIC_AR) if rng.random() < 0.5 else rng.choice(GENERIC_FR)
