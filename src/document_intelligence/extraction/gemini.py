"""Appel à Gemini (étape 2 de l'extracteur DS3) : trouver où se trouve chaque valeur.

Gemini reçoit le texte du document, ligne par ligne, avec les identifiants ([p1_l7]).
Pour chaque champ, il renvoie seulement le texte recopié tel qu'il est imprimé et l'identifiant
de sa ligne. Il ne convertit rien, ne calcule rien et ne déduit rien : le reste est fait par
du code (verify.py, normalize.py, assemble.py).

Configuration (fichier .env à la racine, jamais commité) :
    GEMINI_API_KEY=...            la clé
    GEMINI_MODEL=gemini-flash-latest   (facultatif)
"""

from __future__ import annotations

import importlib
import os
from typing import Any, Final, Literal

from pydantic import BaseModel, ValidationError

from src.document_intelligence.extraction.assemble import PAYSLIP_FIELDS, GeminiPayslipAnswer, RawPayLine
from src.document_intelligence.extraction.verify import RawField
from src.document_intelligence.intermediate import IntermediateDocument

DEFAULT_MODEL: Final = "gemini-flash-latest"


class GeminiError(Exception):
    """Gemini n'a pas pu répondre, ou sa réponse ne respecte pas le format demandé."""


# ------------------------------------------------------------------ format de sortie imposé à Gemini
# Modèles simples (sans extra="forbid") : c'est la forme que l'API Gemini sait imposer.


class _Raw(BaseModel):
    raw: str | None = None
    line_id: str | None = None


class _PayLine(BaseModel):
    label: str
    amount: str | None = None
    line_id: str | None = None


class GeminiPayslipOutput(BaseModel):
    document_type: Literal["fiche_de_paie", "facture", "contrat_travail", "convention_collective",
                           "piece_dossier", "inconnu"]
    employee_name: _Raw
    period_start: _Raw
    period_end: _Raw
    hire_date: _Raw
    seniority_years_printed: _Raw
    category: _Raw
    sub_category: _Raw
    grade: _Raw
    job_qualification: _Raw
    employment_status: _Raw
    pay_mode: _Raw
    work_hours_regime: _Raw
    base_salary: _Raw
    gross_salary: _Raw
    cnss_employee: _Raw
    pay_lines: list[_PayLine]

    def to_answer(self) -> GeminiPayslipAnswer:
        return GeminiPayslipAnswer(
            document_type=self.document_type,
            fields={name: RawField(**getattr(self, name).model_dump()) for name in PAYSLIP_FIELDS},
            pay_lines=[RawPayLine(**line.model_dump()) for line in self.pay_lines],
        )


assert set(PAYSLIP_FIELDS) <= set(GeminiPayslipOutput.model_fields), "format Gemini incomplet"


# ------------------------------------------------------------------ prompt

FIELD_GUIDE: Final[dict[str, str]] = {
    "employee_name": "nom et prénom du salarié",
    "period_start": "date de début de la période de paie ; si seul le mois est imprimé (ex. « Mars 2026 »), "
    "recopie le mois",
    "period_end": "date de fin de la période de paie ; si seul le mois est imprimé, recopie le mois",
    "hire_date": "date d'entrée / d'embauche (تاريخ الانتداب)",
    "seniority_years_printed": "ancienneté, seulement si elle est imprimée (ex. « 6 ans 6 mois »)",
    "category": "catégorie seule, sans le mot « Catégorie » (ex. « 3 », « 1 ب ») (الصنف)",
    "sub_category": "sous-catégorie, seulement si elle est imprimée",
    "grade": "échelon seul (ex. « 2 ») (الدرجة)",
    "job_qualification": "emploi ou qualification, tel qu'imprimé (الخطة)",
    "employment_status": "mot imprimé pour le statut ou le contrat (ex. « Permanent », « CDD », « قار »)",
    "pay_mode": "mode de paiement imprimé (ex. « Mensuel », « Horaire », « شهري »)",
    "work_hours_regime": "horaire imprimé avec son unité (ex. « 208 h », « 173,33 س »)",
    "base_salary": "montant du salaire de base (الأجر الأساسي)",
    "gross_salary": "montant du salaire brut (الأجر الخام)",
    "cnss_employee": "montant de la retenue CNSS du salarié (الضمان الاجتماعي)",
}

INSTRUCTIONS: Final = """\
Tu aides à lire des fiches de paie tunisiennes (en français ou en arabe).
Le document est donné ligne par ligne. Chaque ligne commence par son identifiant entre crochets, ex. [p1_l7].

Pour chaque champ demandé, renvoie :
- raw : le texte EXACTEMENT comme il est imprimé (mêmes chiffres, même virgule, mêmes mots, même langue) ;
- line_id : l'identifiant de la ligne où tu l'as lu (sans les crochets).

Règles strictes :
1. Recopie, ne transforme jamais : pas de conversion de date, de montant ou d'unité, pas de traduction,
   pas de calcul. Exemple : imprimé « 424,100 » -> raw = "424,100".
2. Ne devine jamais. Si la valeur n'est pas dans le document : raw = null et line_id = null.
3. Si la valeur se trouve dans une zone marquée « <zone image non lue> » ou « <texte natif illisible> » :
   raw = null et line_id = l'identifiant de cette zone.
4. Ne déduis rien : recopie le mot imprimé même s'il ne correspond pas à une liste (ex. « CDD » reste « CDD »).
5. Une valeur doit venir d'UNE seule ligne : celle que tu indiques dans line_id.
6. Si le document n'est pas une fiche de paie (ex. une facture), indique son type dans document_type et
   laisse tous les champs à null : ne prends pas une date de facture pour une période, ni un total pour
   un salaire.
7. pay_lines : chaque prime ou indemnité imprimée (pas le salaire de base, ni le brut, ni les retenues,
   ni le net), avec son libellé exact (label), son montant exact (amount) et sa ligne (line_id).
"""


def build_prompt(doc: IntermediateDocument) -> str:
    """Prompt complet : consignes, description des champs, puis le texte du document."""
    guide = "\n".join(f"- {name} : {description}" for name, description in FIELD_GUIDE.items())
    return f"{INSTRUCTIONS}\nChamps demandés :\n{guide}\n\n=== DOCUMENT ===\n{doc.full_text()}\n=== FIN ===\n"


# ------------------------------------------------------------------ appel


def _default_client() -> Any:
    genai = importlib.import_module("google.genai")  # chargé ici : les tests n'en ont pas besoin

    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise GeminiError("GEMINI_API_KEY absente : la mettre dans le fichier .env (jamais dans le code).")
    return genai.Client(api_key=key)


def ask_gemini(doc: IntermediateDocument, client: Any | None = None, model: str | None = None) -> GeminiPayslipAnswer:
    """Envoie le document à Gemini et renvoie sa réponse, au format GeminiPayslipAnswer.

    `client` permet aux tests de remplacer Gemini par un faux client (aucun appel réseau).
    Lève GeminiError si l'appel échoue ou si la réponse n'a pas le bon format.
    """
    client = client or _default_client()
    try:
        response = client.models.generate_content(
            model=model or os.getenv("GEMINI_MODEL", DEFAULT_MODEL),
            contents=build_prompt(doc),
            config={
                "temperature": 0.0,  # la même entrée donne (presque) toujours la même sortie
                "response_mime_type": "application/json",
                "response_schema": GeminiPayslipOutput,
            },
        )
    except Exception as exc:  # erreur réseau, quota, clé refusée…
        raise GeminiError(f"Appel à Gemini impossible : {type(exc).__name__} : {str(exc)[:300]}") from exc
    text = getattr(response, "text", None)
    if not text:
        raise GeminiError("Réponse vide de Gemini.")
    try:
        return GeminiPayslipOutput.model_validate_json(text).to_answer()
    except ValidationError as exc:
        raise GeminiError(f"Réponse de Gemini hors format : {exc.error_count()} erreur(s).") from exc
