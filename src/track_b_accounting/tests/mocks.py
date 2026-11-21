"""Doublures pour la démo du contrat v0 — PAS du code de production.

MockOrchestrator : envoie des requêtes à un handler (callable dict → dict).
MockTrackA       : met en forme une réponse en phrase citée FR/AR. Aucun calcul : le montant,
                   l'unité et les sources sont recopiés tels quels depuis la réponse.
"""

from __future__ import annotations

import json
from pathlib import Path

DEMO_FILE = Path(__file__).resolve().parents[3] / "data" / "mock_cards" / "track_b_requests_demo.json"
# Démos du contrat v1 (D75), à part : le fichier v0 et ses réponses de référence restent à l'octet près.
DEMO_FILE_V1 = DEMO_FILE.with_name("track_b_requests_demo.v1.json")


class MockOrchestrator:
    def __init__(self, handler, requetes: list[dict] | None = None):
        self.handler = handler
        self.requetes = requetes if requetes is not None else json.loads(DEMO_FILE.read_text(encoding="utf-8"))

    def run(self):
        """Liste de couples (requête, réponse). La réponse transite en JSON texte, comme sur le réseau."""
        echanges = []
        for req in self.requetes:
            fil = json.dumps(self.handler(json.loads(json.dumps(req))), ensure_ascii=False)
            echanges.append((req, json.loads(fil)))
        return echanges


_OBJET = {
    "salaire_base": ("Le salaire de base", "الأجر الأساسي"),
    "prime": ("La prime", "المنحة"),
    "smig": ("Le SMIG", "الأجر الأدنى المضمون"),
}


class MockTrackA:
    @staticmethod
    def _source(c: dict, lang: str) -> str:
        nom = Path(c["source_file"]).name
        page = f"p. {c['page']}" if lang == "fr" else f"ص {c['page']}"
        art = f", {c['article']}" if c.get("article") else ""
        return (
            f"{nom}, {page}{art} ; {c['decision_ref']}" if lang == "fr" else f"{nom}، {page}{art}؛ {c['decision_ref']}"
        )

    def formuler(self, requete: dict, reponse: dict) -> str:
        lang = requete.get("lang", "fr")
        if reponse["status"] == "ok":
            res = reponse["result"]
            fr, ar = _OBJET.get(requete["operation"], ("Le montant", "المبلغ"))
            sources = " | ".join(self._source(c, lang) for c in reponse["citations"])
            if lang == "ar":
                return f"{ar}: {res['montant']} {res['unite']} [المصدر: {sources}]"
            return f"{fr} est de {res['montant']} {res['unite']} [source : {sources}]."
        if reponse["status"] == "refus":
            r = reponse["refus"]
            msg = r["message_ar"] if lang == "ar" else r["message_fr"]
            return f"[{r['code']}] {msg}"
        e = reponse["erreur"]
        return e["message_ar"] if lang == "ar" else e["message_fr"]
