from app.agents.signals import macro


def test_macro_signals_load_reviewed_starter_dataset() -> None:
    result = macro.recession_signals()

    assert set(result["metrics"]) == {
        "US 10y−2y",
        "CA 10y−2y",
        "US unemployment",
        "Unemp. vs 12m low",
    }
    assert len(result["notes"]) == 3
    assert any("historical reference data only" in item for item in result["warnings"])
    assert all("not found" not in item for item in result["warnings"])
