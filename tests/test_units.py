from scalesync.units import factor_between, normalize_unit_token


def test_normalize_unit_token() -> None:
    assert normalize_unit_token("centimeters") == "cm"
    assert normalize_unit_token("METER") == "m"
    assert normalize_unit_token(None) is None


def test_factor_between() -> None:
    assert factor_between("cm", "m") == 0.01
    assert factor_between("m", "cm") == 100.0

