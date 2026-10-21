"""Tests de l'appel à Gemini, de la chaîne complète et du score, avec un faux client Gemini.

Aucun appel réseau, aucune clé : le faux client renvoie un JSON préparé à l'avance.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from src.document_intelligence.contract.v2.models import DS3Response
from src.document_intelligence.evaluation.fictive_documents import DOCS_DIR
from src.document_intelligence.evaluation.run_gemini_eval import request_for, score_case
from src.document_intelligence.extraction.assemble import PAYSLIP_FIELDS, GeminiPayslipAnswer
from src.document_intelligence.extraction.gemini import (
    GeminiError,
    GeminiPayslipOutput,
    ask_gemini,
    build_prompt,
)
from src.document_intelligence.extraction.pipeline import analyze_payslip_pdf
from src.document_intelligence.reading.pdf_natif import read_pdf
from src.document_intelligence.tests.test_document_intelligence_golden import (
    CASES,
    NEEDS_OCR,
    _perfect_gemini,
)


class FakeClient:
    """Imite google.genai.Client : client.models.generate_content(...) renvoie un objet avec .text."""

    def __init__(self, text: str | None = None, error: Exception | None = None) -> None:
        self.text, self.error = text, error
        self.calls: list[dict[str, Any]] = []
        self.models = self

    def generate_content(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.text)


def _output_json(answer: GeminiPayslipAnswer) -> str:
    """Ce que Gemini renverrait pour cette réponse (format GeminiPayslipOutput)."""
    data: dict[str, Any] = {"document_type": answer.document_type}
    for name in PAYSLIP_FIELDS:
        found = answer.fields.get(name)
        data[name] = found.model_dump() if found else {"raw": None, "line_id": None}
    data["pay_lines"] = [line.model_dump() for line in answer.pay_lines]
    GeminiPayslipOutput.model_validate(data)
    return json.dumps(data, ensure_ascii=False)


def _perfect_client(case_id: str) -> FakeClient:
    case = CASES[case_id]
    doc = read_pdf(DOCS_DIR / case["requete"]["file_name"], document_id=case["doc_id"])
    return FakeClient(_output_json(_perfect_gemini(case, doc)))


def _run(case_id: str, client: FakeClient) -> dict[str, Any]:
    case = CASES[case_id]
    return analyze_payslip_pdf(DOCS_DIR / case["requete"]["file_name"], request_for(case), client=client)


# ------------------------------------------------------------ prompt et appel


def test_prompt_contains_rules_fields_and_numbered_lines() -> None:
    doc = read_pdf(DOCS_DIR / "paie_fictive_01_fr.pdf")
    prompt = build_prompt(doc)
    assert "Ne devine jamais" in prompt
    assert all(f"- {name} :" in prompt for name in PAYSLIP_FIELDS)
    assert "[p1_l8] Salaire de base  424,100" in prompt


def test_call_uses_json_output_and_zero_temperature() -> None:
    client = _perfect_client("DS3-01")
    ask_gemini(read_pdf(DOCS_DIR / "paie_fictive_01_fr.pdf"), client=client, model="modele-test")
    call = client.calls[0]
    assert call["model"] == "modele-test"
    assert call["config"]["temperature"] == 0.0
    assert call["config"]["response_mime_type"] == "application/json"
    assert call["config"]["response_schema"] is GeminiPayslipOutput


@pytest.mark.parametrize("text", [None, "", "pas du json", '{"document_type": "fiche_de_paie"}'])
def test_unusable_answer_raises_gemini_error(text: str | None) -> None:
    with pytest.raises(GeminiError):
        ask_gemini(read_pdf(DOCS_DIR / "paie_fictive_01_fr.pdf"), client=FakeClient(text))


# ------------------------------------------------------------ chaîne complète


@pytest.mark.parametrize("case_id", sorted(set(CASES) - NEEDS_OCR))
def test_perfect_gemini_scores_100_percent(case_id: str) -> None:
    response = _run(case_id, _perfect_client(case_id))
    DS3Response.model_validate(response)
    score = score_case(CASES[case_id], response)
    assert score.status_ok
    assert score.count() == {"correct": len(PAYSLIP_FIELDS)}


def test_scanned_page_is_not_sent_to_gemini() -> None:
    client = FakeClient("{}")
    response = _run("DS3-03", client)
    assert client.calls == []  # rien à lire : pas d'appel (ni de coût) inutile
    assert response["status"] == "refus" and response["refus"]["code"] == "SOURCE_MANQUANTE"
    assert any("OCR" in w for w in response["warnings"])


def test_gemini_failure_gives_a_retryable_error_without_details() -> None:
    response = _run("DS3-01", FakeClient(error=RuntimeError("quota dépassé pour la clé xyz")))
    DS3Response.model_validate(response)
    assert response["status"] == "erreur" and response["retryable"] is True
    assert "xyz" not in json.dumps(response)  # aucun détail technique renvoyé à DS1


def test_corrupted_file_is_refused(tmp_path: Any) -> None:
    broken = tmp_path / "casse.pdf"
    broken.write_bytes(b"ceci n'est pas un pdf")
    case = CASES["DS3-01"]
    response = analyze_payslip_pdf(broken, request_for(case), client=FakeClient("{}"))
    assert response["status"] == "refus" and response["ds3_code"] == "FILE_EMPTY_OR_CORRUPTED"


# ------------------------------------------------------------ score


def test_score_detects_an_invention_and_a_wrong_value() -> None:
    case = CASES["DS3-04"]
    answer = _perfect_gemini(case, read_pdf(DOCS_DIR / case["requete"]["file_name"]))
    response = _run("DS3-04", FakeClient(_output_json(answer)))
    # On abîme la réponse comme le ferait un mauvais modèle :
    fields = response["result"]["fields"]
    fields["employment_status"]["value"] = "temporaire"  # « CDD » interprété : invention
    fields["grade"]["value"] = "1"  # mauvaise valeur
    fields["base_salary"]["value"] = None  # valeur ratée : silence
    outcomes = {name: o for name, (o, _, _) in score_case(case, response).fields.items()}
    assert outcomes["employment_status"] == "invention"
    assert outcomes["grade"] == "faux"
    assert outcomes["base_salary"] == "silence"
