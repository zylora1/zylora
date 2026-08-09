import pytest
from zylora_api.modules.auth.errors import AuthProblem
from zylora_api.modules.auth.security import AuthCrypto
from zylora_api.modules.templates.service import TemplateService


def test_catalogue_cursor_is_opaque_signed_and_filter_bound() -> None:
    service = TemplateService(None, AuthCrypto("cursor-secret-at-least-thirty-two-characters"))  # type: ignore[arg-type]
    cursor = service.encode_cursor(24, "filters-a")

    assert service.decode_cursor(cursor, "filters-a") == 24
    with pytest.raises(AuthProblem) as wrong_filters:
        service.decode_cursor(cursor, "filters-b")
    with pytest.raises(AuthProblem) as tampered:
        service.decode_cursor(cursor[:-2] + "zz", "filters-a")
    assert wrong_filters.value.code == "invalid_cursor"
    assert tampered.value.code == "invalid_cursor"
