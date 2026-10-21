from src.orchestrator.evaluation.run_golden import run_golden_set


def test_ds1_golden_set_has_complete_routing_accuracy() -> None:
    report = run_golden_set()
    assert report["cases"] == 24
    assert report["intent_accuracy"] == 1.0
    assert report["language_accuracy"] == 1.0
    assert report["flow_accuracy"] == 1.0
    assert report["failures"] == []
