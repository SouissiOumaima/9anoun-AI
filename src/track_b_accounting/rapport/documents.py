"""Documents qui permettraient de conclure, quand une ligne du rapport reste non vérifiable (D109).

Table fixe : un champ absent ou illisible, une condition d'octroi, un groupe ou un refus PARAM_INVALIDE du salaire
donnent toujours le même document. Aucun texte n'est généré : libellés FR et AR écrits ici une fois pour toutes.
"""

from __future__ import annotations

# code → (libellé FR, libellé AR)
DOCUMENTS: dict[str, tuple[str, str]] = {
    "fiche_de_paie": ("fiche de paie", "كشف الأجر"),
    "fiche_de_paie_lisible": ("copie lisible de la fiche de paie", "نسخة مقروءة من كشف الأجر"),
    "contrat_de_travail": (
        "contrat de travail (date d'entrée, régime horaire, mode de paie)",
        "عقد الشغل (تاريخ الانتداب، نظام العمل الأسبوعي، طريقة التأجير)",
    ),
    "attestation_classification": (
        "attestation de classification professionnelle (population, catégorie, groupe)",
        "شهادة في التصنيف المهني (الفئة، الصنف، المجموعة)",
    ),
    "attestation_employeur_prime": (
        "attestation de l'employeur sur la condition d'octroi de la prime",
        "شهادة من المؤجر في شرط إسناد المنحة",
    ),
}

# Champs de la fiche : libellé FR, libellé AR, document qui permettrait de conclure.
CHAMPS: dict[str, tuple[str, str, str]] = {
    "population": ("population", "الفئة", "attestation_classification"),
    "categorie": ("catégorie", "الصنف", "attestation_classification"),
    "sous_categorie": ("sous-catégorie", "الصنف الفرعي", "attestation_classification"),
    "anciennete_annees": ("ancienneté", "الأقدمية", "contrat_de_travail"),
    "degre": ("degré", "الدرجة", "attestation_classification"),
    "date": ("période", "الفترة", "fiche_de_paie_lisible"),
    "regime_heures": ("régime horaire", "نظام العمل الأسبوعي", "contrat_de_travail"),
    "mode_paie": ("mode de paie", "طريقة التأجير", "contrat_de_travail"),
    "salaire_base_imprime": ("salaire de base imprimé", "الأجر الأساسي المطبوع", "fiche_de_paie_lisible"),
}

# Champs dont la simple absence est signalée ; les autres (population, sous-catégorie, degré) peuvent manquer
# normalement et ne le sont que s'ils sont déclarés illisibles.
CHAMPS_ATTENDUS = ("date", "categorie", "anciennete_annees", "regime_heures", "mode_paie", "salaire_base_imprime")

# Refus PARAM_INVALIDE du salaire : une valeur envoyée n'existe pas dans la grille ; ces documents la confirment.
DOCUMENTS_REFUS_SALAIRE = ("attestation_classification", "contrat_de_travail")
DOCUMENT_GROUPE = "attestation_classification"
DOCUMENT_CONDITION = "attestation_employeur_prime"
