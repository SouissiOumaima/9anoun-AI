"""Documents fictifs du jeu de référence DS3 : fiches de paie (et une facture) inventées.

Toutes les données sont inventées (noms, entreprises, montants) : aucune donnée personnelle réelle.
Chaque document porte la mention « DOCUMENT FICTIF ». Comme on écrit nous-mêmes le document, on
connaît exactement la bonne réponse : elle est écrite ici une seule fois, puis reprise dans le PDF
et dans ds3_golden.v0.json.

Régénérer (depuis la racine du dépôt, sous Linux ou Windows) :
    python -m src.document_intelligence.evaluation.fictive_documents

Pour chaque champ, `printed` = le texte tel qu'il est imprimé (ce que Gemini doit recopier),
`expected` = la valeur attendue dans la réponse ds3.v2 (après normalisation), ou None avec une raison.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import pymupdf

HERE: Final = Path(__file__).resolve().parent
GOLDEN_DIR: Final = HERE / "golden_sets"
DOCS_DIR: Final = GOLDEN_DIR / "documents"
GOLDEN_FILE: Final = GOLDEN_DIR / "ds3_golden.v0.json"
SOURCES_FILE: Final = GOLDEN_DIR / "sources_documents.csv"
TODAY: Final = "2026-10-15"
FICTIVE_MARK: Final = "DOCUMENT FICTIF - données inventées pour les tests 9anoun AI"


@dataclass(frozen=True)
class Value:
    printed: str | None
    expected: str | None
    reason: str | None = None  # zone_illisible | valeur_incoherente quand expected = None


@dataclass
class FictiveDoc:
    doc_id: str
    case_id: str
    file_name: str
    lang: str
    fmt: str  # pdf_natif | pdf_scanne
    categorie: str  # ok | partiel | refus | piege
    title: str
    header: list[tuple[str, str]]  # lignes à deux colonnes (gauche, droite) ; "" = vide
    rows: list[tuple[str, str]]  # tableau des rubriques (libellé, montant)
    fields: dict[str, Value]
    pay_lines: list[tuple[str, str]] = field(default_factory=list)  # (libellé, montant attendu)
    expected_type: str = "fiche_de_paie"
    document_type: str = "fiche_de_paie"
    refus_code: str | None = None
    stamp_on_row: str | None = None  # libellé de la ligne dont le montant est caché par un tampon
    note: str = ""


DOCS: Final[list[FictiveDoc]] = [
    FictiveDoc(
        doc_id="FICTIF-01", case_id="DS3-01", file_name="paie_fictive_01_fr.pdf", lang="fr", fmt="pdf_natif",
        categorie="ok", title="BULLETIN DE PAIE",
        header=[
            ("Société Atlas Services SARL (fictive)", "Période : Mars 2026"),
            ("Nom : Ahmed Ben Salah", "Date d'entrée : 01/09/2019"),
            ("Ancienneté : 6 ans 6 mois", "Catégorie : 3   Échelon : 2"),
            ("Emploi : Agent administratif", "Statut : Permanent"),
            ("Mode de paiement : Mensuel", "Horaire : 208 h"),
        ],
        rows=[("Salaire de base", "424,100"), ("Prime de transport", "56,000"), ("Prime de présence", "36,000"),
              ("Salaire brut", "516,100"), ("Retenue CNSS", "47,378"), ("Net à payer", "468,722")],
        fields={
            "employee_name": Value("Ahmed Ben Salah", "Ahmed Ben Salah"),
            "period_start": Value("Mars 2026", "2026-03-01"),
            "period_end": Value("Mars 2026", "2026-03-31"),
            "hire_date": Value("01/09/2019", "2019-09-01"),
            "seniority_years_printed": Value("6 ans 6 mois", "6 ans 6 mois"),
            "category": Value("3", "3"),
            "grade": Value("2", "2"),
            "job_qualification": Value("Agent administratif", "Agent administratif"),
            "employment_status": Value("Permanent", "permanent"),
            "pay_mode": Value("Mensuel", "mensuel"),
            "work_hours_regime": Value("208 h", "48"),
            "base_salary": Value("424,100", "424.100"),
            "gross_salary": Value("516,100", "516.100"),
            "cnss_employee": Value("47,378", "47.378"),
        },
        pay_lines=[("Prime de transport", "56.000"), ("Prime de présence", "36.000")],
        note="Cas de base : fiche complète en français, PDF natif, libellés et montants en deux colonnes.",
    ),
    FictiveDoc(
        doc_id="FICTIF-02", case_id="DS3-02", file_name="paie_fictive_02_tampon.pdf", lang="fr", fmt="pdf_natif",
        categorie="partiel", title="BULLETIN DE PAIE",
        header=[
            ("Société Carthage Tech (fictive)", "Période : du 01/04/2026 au 30/04/2026"),
            ("Nom : Mouna Ben Ali", "Date d'entrée : 15/02/2015"),
            ("Catégorie : 4   Échelon : 5", ""),
            ("Emploi : Technicien", "Statut : Permanent"),
            ("Mode de paiement : Mensuel", "Horaire : 173,33 h"),
        ],
        rows=[("Salaire de base", "612,450"), ("Prime de transport", "56,000"), ("Prime de rendement", "80,000"),
              ("Salaire brut", "748,450"), ("Retenue CNSS", "68,708"), ("Net à payer", "679,742")],
        stamp_on_row="Retenue CNSS",
        fields={
            "employee_name": Value("Mouna Ben Ali", "Mouna Ben Ali"),
            "period_start": Value("01/04/2026", "2026-04-01"),
            "period_end": Value("30/04/2026", "2026-04-30"),
            "hire_date": Value("15/02/2015", "2015-02-15"),
            "category": Value("4", "4"),
            "grade": Value("5", "5"),
            "job_qualification": Value("Technicien", "Technicien"),
            "employment_status": Value("Permanent", "permanent"),
            "pay_mode": Value("Mensuel", "mensuel"),
            "work_hours_regime": Value("173,33 h", "40"),
            "base_salary": Value("612,450", "612.450"),
            "gross_salary": Value("748,450", "748.450"),
            "cnss_employee": Value(None, None, "zone_illisible"),
        },
        pay_lines=[("Prime de transport", "56.000"), ("Prime de rendement", "80.000")],
        note="Montant CNSS caché par un tampon (image) : null attendu, jamais une valeur devinée.",
    ),
    FictiveDoc(
        doc_id="FICTIF-03", case_id="DS3-03", file_name="paie_fictive_03_ar_scan.pdf", lang="ar", fmt="pdf_scanne",
        categorie="ok", title="كشف الأجر",
        header=[
            ("شركة الياسمين للخدمات (وهمية)", "الفترة : ماي 2026"),
            ("الاسم واللقب : سامي بن عمر", "تاريخ الانتداب : 01/03/2021"),
            ("الصنف : 1 ب", "الدرجة : 3"),
            ("الخطة : عون تنفيذ", "الوضعية : قار"),
            ("طريقة الخلاص : شهري", "التوقيت : 173,33 س"),
        ],
        rows=[("الأجر الأساسي", "398,250"), ("منحة النقل", "56,000"), ("الأجر الخام", "454,250"),
              ("الضمان الاجتماعي", "41,700"), ("الصافي للدفع", "412,550")],
        fields={
            "employee_name": Value("سامي بن عمر", "سامي بن عمر"),
            "period_start": Value("ماي 2026", "2026-05-01"),
            "period_end": Value("ماي 2026", "2026-05-31"),
            "hire_date": Value("01/03/2021", "2021-03-01"),
            "category": Value("1 ب", "1B"),
            "grade": Value("3", "3"),
            "job_qualification": Value("عون تنفيذ", "عون تنفيذ"),
            "employment_status": Value("قار", "permanent"),
            "pay_mode": Value("شهري", "mensuel"),
            "work_hours_regime": Value("173,33 س", "40"),
            "base_salary": Value("398,250", "398.250"),
            "gross_salary": Value("454,250", "454.250"),
            "cnss_employee": Value("41,700", "41.700"),
        },
        pay_lines=[("منحة النقل", "56.000")],
        note="Fiche en arabe, page en image (scan) : passe par l'OCR de la partie A. Catégorie « 1 ب » -> 1B.",
    ),
    FictiveDoc(
        doc_id="FICTIF-04", case_id="DS3-04", file_name="paie_fictive_04_pieges.pdf", lang="fr", fmt="pdf_natif",
        categorie="piege", title="BULLETIN DE PAIE",
        header=[
            ("Entreprise Sfax Métal (fictive)", "Période : Février 2024"),
            ("Nom : Karim Haddad", "Date d'entrée : 01/09/19"),
            ("Catégorie : 2 b   Échelon : 7", ""),
            ("Emploi : Ouvrier qualifié", "Contrat : CDD"),
            ("Mode de paiement : Mensuel", "Horaire : 195 h"),
        ],
        rows=[("Salaire de base", "1.275,000"), ("Prime de transport", "56,000"), ("Salaire brut", "1.331,000"),
              ("Retenue CNSS", "122,186"), ("Net à payer", "1.208,814")],
        fields={
            "employee_name": Value("Karim Haddad", "Karim Haddad"),
            "period_start": Value("Février 2024", "2024-02-01"),
            "period_end": Value("Février 2024", "2024-02-29"),
            "hire_date": Value("01/09/19", None, "valeur_incoherente"),
            "category": Value("2 b", "2B"),
            "grade": Value("7", "7"),
            "job_qualification": Value("Ouvrier qualifié", "Ouvrier qualifié"),
            "employment_status": Value("CDD", None, "valeur_incoherente"),
            "pay_mode": Value("Mensuel", "mensuel"),
            "work_hours_regime": Value("195 h", None, "valeur_incoherente"),
            "base_salary": Value("1.275,000", "1275.000"),
            "gross_salary": Value("1.331,000", "1331.000"),
            "cnss_employee": Value("122,186", "122.186"),
        },
        pay_lines=[("Prime de transport", "56.000")],
        note="Pièges : année sur 2 chiffres, « CDD » (interprétation interdite), 195 h (aucune conversion "
        "fixe), séparateur des milliers, février d'une année bissextile, catégorie « 2 b ».",
    ),
    FictiveDoc(
        doc_id="FICTIF-05", case_id="DS3-05", file_name="facture_fictive_05.pdf", lang="fr", fmt="pdf_natif",
        categorie="refus", title="FACTURE N° F-2026-031",
        header=[
            ("Société Atlas Services SARL (fictive)", "Date : 12/03/2026"),
            ("Client : Cabinet Fictif & Associés", "Échéance : 12/04/2026"),
        ],
        rows=[("Maintenance informatique (mars 2026)", "1 000,000"), ("TVA 19 %", "190,000"),
              ("Total TTC", "1 190,000")],
        fields={},
        document_type="facture",
        refus_code="SOURCE_MANQUANTE",
        note="Une facture envoyée comme fiche de paie : aucun champ de paie à extraire. Piège : ne pas "
        "prendre la date de facture pour une période, ni le total pour un salaire.",
    ),
]


# ------------------------------------------------------------------ rendu PDF

_ARABIC_CSS: Final = "* {font-family: sans-serif; font-size: 10pt;}"
LEFT, RIGHT, AMOUNT_X, TOP, STEP = 60.0, 320.0, 460.0, 120.0, 22.0


def _stamp_png() -> bytes:
    """Petit tampon « PAYÉ » (image), pour cacher un montant."""
    tmp = pymupdf.open()
    page = tmp.new_page(width=110, height=40)
    page.draw_rect(pymupdf.Rect(3, 3, 107, 37), color=(0.8, 0.1, 0.1), fill=(1, 0.85, 0.85), width=2)
    page.insert_text((28, 26), "PAYÉ", fontsize=16, color=(0.8, 0.1, 0.1))
    png = bytes(page.get_pixmap(dpi=144).tobytes("png"))
    tmp.close()
    return png


def _text(page: pymupdf.Page, x: float, y: float, text: str, arabic: bool, size: float = 10) -> None:
    if not text:
        return
    if arabic:
        # Boîte assez haute pour ne pas réduire le texte ; la ligne de base tombe sur y, comme insert_text.
        box = pymupdf.Rect(x, y - size - 9.5, x + 220, y + 3)
        page.insert_htmlbox(box, f'<p dir="rtl">{text}</p>', css=_ARABIC_CSS, scale_low=1)
    else:
        page.insert_text((x, y), text, fontsize=size)


def _draw(doc_spec: FictiveDoc) -> pymupdf.Document:
    arabic = doc_spec.lang == "ar"
    pdf = pymupdf.open()
    page = pdf.new_page()  # A4
    page.insert_text((LEFT, 50), FICTIVE_MARK, fontsize=8, color=(0.6, 0.6, 0.6))
    _text(page, LEFT if not arabic else 230, 85, doc_spec.title, arabic, size=14)
    y = TOP
    for left, right in doc_spec.header:
        # En arabe, la première colonne est à droite.
        _text(page, RIGHT if arabic else LEFT, y, left, arabic)
        _text(page, LEFT if arabic else RIGHT, y, right, arabic)
        y += STEP
    y += STEP
    page.draw_line((LEFT, y - 14), (540, y - 14), color=(0.5, 0.5, 0.5))
    for label, amount in doc_spec.rows:
        _text(page, RIGHT if arabic else LEFT, y, label, arabic)
        if label == doc_spec.stamp_on_row:
            page.insert_image(pymupdf.Rect(AMOUNT_X - 10, y - 16, AMOUNT_X + 70, y + 8), stream=_stamp_png())
        else:
            page.insert_text((LEFT if arabic else AMOUNT_X, y), amount, fontsize=10)
        y += STEP
    return pdf


def _as_scan(pdf: pymupdf.Document) -> pymupdf.Document:
    """Transforme le PDF en « scan » : chaque page devient une image, sans couche texte."""
    scan = pymupdf.open()
    for page in (pdf[i] for i in range(pdf.page_count)):
        pix = page.get_pixmap(dpi=150, colorspace=pymupdf.csGRAY)
        new = scan.new_page(width=page.rect.width, height=page.rect.height)
        new.insert_image(new.rect, stream=pix.tobytes("png"))
    return scan


def write_pdf(doc_spec: FictiveDoc, out_dir: Path = DOCS_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = _draw(doc_spec)
    if doc_spec.fmt == "pdf_scanne":
        pdf = _as_scan(pdf)
    path = out_dir / doc_spec.file_name
    pdf.set_metadata({"title": doc_spec.file_name, "creator": "9anoun AI - DS3 (document fictif)"})
    pdf.save(path, garbage=4, deflate=True)
    pdf.close()
    return path


# ------------------------------------------------------------------ jeu de référence


def golden_case(d: FictiveDoc) -> dict[str, Any]:
    fields = {name: v.expected for name, v in d.fields.items()}
    unreadable = {name: v.reason for name, v in d.fields.items() if v.expected is None}
    if d.refus_code:
        attendu: dict[str, Any] = {"issue": "refus", "code_v2": d.refus_code}
    else:
        attendu = {
            "issue": "partiel" if unreadable else "ok",
            "document_type": d.document_type,
            "fields": fields,
            "pay_lines": [{"label": label, "amount": amount} for label, amount in d.pay_lines],
        }
        if unreadable:
            attendu["unreadable"] = unreadable
    return {
        "id": d.case_id,
        "categorie": d.categorie,
        "certitude": "L",
        "decision": None,
        "verification_humaine": False,
        "doc_id": d.doc_id,
        "requete": {"operation": "analyze_document", "expected_type": d.expected_type, "lang": d.lang,
                    "file_name": d.file_name},
        "attendu": attendu,
        "texte_imprime": {name: v.printed for name, v in d.fields.items()},
        "justification": {"document": d.file_name, "page": 1,
                          "emplacement": "en-tête (deux colonnes) et tableau des rubriques"},
        "note": d.note,
    }


def build_golden() -> dict[str, Any]:
    return {
        "version": "ds3_golden.v0",
        "description": "Jeu de référence DS3 (Document Intelligence), sur le modèle de track_b_golden.v0. "
        "Documents fictifs générés par fictive_documents.py : les valeurs attendues sont connues exactement. "
        "verification_humaine passe à true quand une deuxième personne a ouvert le PDF et vérifié le cas.",
        "conventions": {
            "doc_id": "identifiant du document dans sources_documents.csv",
            "issue": "ok | partiel (au moins une valeur présente mais illisible, attendue à null) | refus",
            "fields": "valeurs attendues dans la réponse ds3.v2 ; un champ non listé est attendu absent "
            "(null, absent_du_document)",
            "texte_imprime": "texte tel qu'il est imprimé : ce que Gemini doit recopier (null si caché)",
            "montant": "chaîne à 3 décimales, ex. \"512.027\"",
            "date": "AAAA-MM-JJ",
            "page": "numérotée à partir de 1",
        },
        "cases": [golden_case(d) for d in DOCS],
    }


SOURCE_COLUMNS: Final = ["doc_id", "fichier", "type_document", "langue", "format", "source", "url", "licence",
                         "date_telechargement", "donnees_personnelles", "anonymise", "stockage", "collecte_par",
                         "remarques"]


def write_sources(path: Path = SOURCES_FILE) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SOURCE_COLUMNS)
        writer.writeheader()
        for d in DOCS:
            writer.writerow({
                "doc_id": d.doc_id, "fichier": d.file_name, "type_document": d.document_type, "langue": d.lang,
                "format": d.fmt, "source": "fictif", "url": "", "licence": "création de l'équipe",
                "date_telechargement": TODAY, "donnees_personnelles": "non", "anonymise": "na",
                "stockage": "src/document_intelligence/evaluation/golden_sets/documents/",
                "collecte_par": "Hadil", "remarques": "généré par fictive_documents.py",
            })


def main() -> None:
    for d in DOCS:
        print(f"écrit : {write_pdf(d).relative_to(HERE)}")
    GOLDEN_FILE.write_text(json.dumps(build_golden(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_sources()
    print(f"{len(DOCS)} cas écrits dans {GOLDEN_FILE.relative_to(HERE)} et {SOURCES_FILE.relative_to(HERE)}")


if __name__ == "__main__":
    main()
