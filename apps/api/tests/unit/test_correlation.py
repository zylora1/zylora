from zylora_api.core.correlation import normalize_correlation_id


def test_valid_correlation_id_is_preserved() -> None:
    assert normalize_correlation_id("request-12345678") == "request-12345678"


def test_invalid_correlation_id_is_replaced() -> None:
    generated = normalize_correlation_id("bad value")
    assert len(generated) == 32
    assert generated != "bad value"
