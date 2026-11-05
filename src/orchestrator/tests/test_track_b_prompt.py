from src.orchestrator import sector_mapping
from src.orchestrator.sector_mapping import needs_sector_clarification, resolve_active_ds5_sector
from src.orchestrator.track_b_prompt import extract_track_b_prompt


def test_prompt_extractor_recognizes_prime_parameters() -> None:
    extracted = extract_track_b_prompt(
        "Calcule la prime de transport secteur construction métallique pour les cadres au 2024-06-01."
    )
    assert extracted.operation == "prime"
    assert extracted.missing == ()
    assert extracted.params == {
        "secteur": "METALLURGIE_BATIMENT", "code": "prime_transport",
        "groupe": "cadres", "date": "2024-06-01",
    }


def test_prompt_extractor_recognizes_btp_sector() -> None:
    extracted = extract_track_b_prompt(
        "Calcule le salaire de base BTP, catégorie 4, "
        "15 ans d'ancienneté au 2024-01-01 pour population admin_tech."
    )
    assert extracted.params["secteur"] == "BATIMENT_TRAVAUX_PUBLICS"


def test_prompt_extractor_builds_btp_occasionnel_with_required_subcategory() -> None:
    extracted = extract_track_b_prompt(
        "Calcule le salaire de base BTP pour population ouvriers_occasionnels, catégorie 7, "
        "sous-catégorie 2, au 2023-06-01."
    )
    assert extracted.missing == ()
    assert extracted.params == {
        "secteur": "BATIMENT_TRAVAUX_PUBLICS", "population": "ouvriers_occasionnels",
        "categorie": "7", "sous_categorie": "2", "date": "2023-06-01",
    }


def test_prompt_extractor_requests_subcategory_only_for_btp_categories_six_and_seven() -> None:
    extracted = extract_track_b_prompt(
        "Calcule le salaire de base BTP pour population ouvriers_occasionnels, catégorie 6, au 2023-06-01."
    )
    assert extracted.missing == ("sous_categorie",)


def test_prompt_extractor_reads_the_shared_table_for_associations() -> None:
    extracted = extract_track_b_prompt(
        "Calcule le salaire de base des associations, population techniciens, catégorie I, "
        "3 ans d'ancienneté au 2024-01-01."
    )
    assert extracted.params["secteur"] == "ASSOCIATIONS_PERSONNES_HANDICAPEES"


def test_prompt_extractor_never_maps_ambiguous_building_or_metallurgy() -> None:
    building = extract_track_b_prompt("Calcule le salaire de base bâtiment, catégorie 4 au 2024-01-01.")
    metallurgy = extract_track_b_prompt("Calcule le salaire de base métallurgie, catégorie 4 au 2024-01-01.")
    assert "secteur" in building.missing
    assert "secteur" in metallurgy.missing


def test_prompt_extractor_supports_newly_active_assurance_sector() -> None:
    extracted = extract_track_b_prompt("Calcule le salaire de base assurance, catégorie 4 au 2024-01-01.")
    assert extracted.params["secteur"] == "ASSURANCE"
    assert extracted.missing == ("anciennete_annees",)


def test_prompt_extractor_accepts_textual_category_codes_for_private_education() -> None:
    extracted = extract_track_b_prompt(
        "Calcule le salaire de base dans l'enseignement privé, population: instituteurs, "
        "catégorie instituteur_principal, 3 ans d'ancienneté au 2024-01-01."
    )
    assert extracted.missing == ()
    assert extracted.params == {
        "secteur": "ENSEIGNEMENT_PRIVE", "population": "instituteurs",
        "categorie": "instituteur_principal", "anciennete_annees": 3, "date": "2024-01-01",
    }


def test_prompt_extractor_marks_multiple_active_sectors_for_clarification() -> None:
    extracted = extract_track_b_prompt(
        "Calcule le salaire de base BTP et construction métallique, catégorie 4 au 2024-01-01."
    )
    assert extracted.sector_clarification is True
    assert "secteur" in extracted.missing


def test_sector_detection_does_not_match_unrelated_substrings() -> None:
    for message in (
        "Je veux comprendre mes cotisations de sécurité sociale.",
        "Calcule le salaire de base agent de sécurité sociale, catégorie 4, 5 ans d'ancienneté au 2024-01-01.",
        "Calcule le salaire de base assurance sociale, catégorie 4, 5 ans d'ancienneté au 2024-01-01.",
        "Calcule le salaire de base assurance maladie, catégorie 4, 5 ans d'ancienneté au 2024-01-01.",
    ):
        assert resolve_active_ds5_sector(message) is None
        assert sector_mapping._matched_sectors(message.casefold()) == []


def test_social_protection_wording_cannot_hide_a_building_clarification() -> None:
    message = "Calcule le salaire de base dans le bâtiment et ma sécurité sociale, catégorie 4 au 2024-01-01."
    assert needs_sector_clarification(message) is True


def test_explicit_assurance_still_routes_to_its_active_sector() -> None:
    assert resolve_active_ds5_sector("Calcule le salaire de base assurance, catégorie 4 au 2024-01-01.") == "ASSURANCE"
    assert resolve_active_ds5_sector("Calcule le salaire de base pour une compagnie d'assurance, catégorie 4 au 2024-01-01.") == "ASSURANCE"


def test_sector_detection_keeps_specific_gardiennage_expressions() -> None:
    assert [sector["ds2_code"] for sector in sector_mapping._matched_sectors("contrat de gardiennage")] == [
        "gardiennage_securite_transport_fonds",
    ]
    assert [sector["ds2_code"] for sector in sector_mapping._matched_sectors("transport de fonds")] == [
        "gardiennage_securite_transport_fonds",
    ]
    assert [sector["ds2_code"] for sector in sector_mapping._matched_sectors("agent de sécurité")] == [
        "gardiennage_securite_transport_fonds",
    ]
    assert resolve_active_ds5_sector("Calcule le salaire de base pour un agent de sécurité, catégorie 4 au 2024-01-01.") == "GARDIENNAGE_SECURITE_TRANSPORT_FONDS"
