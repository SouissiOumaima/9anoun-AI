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


def test_prompt_extractor_does_not_call_ds5_for_preparation_sector() -> None:
    extracted = extract_track_b_prompt("Calcule le salaire de base assurance, catégorie 4 au 2024-01-01.")
    assert "secteur" in extracted.missing
