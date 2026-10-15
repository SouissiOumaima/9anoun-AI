from src.orchestrator.legal_retrieval_prompt import extract_legal_prompt


def test_vocabulary_maps_explicit_sector_and_worker_category() -> None:
    extracted = extract_legal_prompt("Quel est le préavis pour un cadre dans une banque ?")
    assert extracted.sector == "banques"
    assert extracted.worker_category == "cadre"
    assert extracted.source_id == "CCS-BANQUES"


def test_ouvrier_is_not_sent_as_a_worker_category() -> None:
    extracted = extract_legal_prompt("Quel article BTP s'applique à un ouvrier ?")
    assert extracted.sector == "btp"
    assert extracted.worker_category is None
