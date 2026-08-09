import base64
from io import BytesIO

import pytest
from PIL import Image  # type: ignore[import-not-found]
from zylora_api.modules.auth.errors import AuthProblem
from zylora_api.modules.templates.assets import AssetUploadRequest, asset_key, process_raster


def encoded_png() -> str:
    output = BytesIO()
    Image.new("RGB", (24, 18), "#164e46").save(output, format="PNG", pnginfo=None)
    return base64.b64encode(output.getvalue()).decode()


def test_asset_pipeline_decodes_strips_and_reencodes_to_immutable_webp() -> None:
    data, width, height, mime = process_raster(
        AssetUploadRequest(
            content_base64=encoded_png(),
            mime_type="image/png",
            license="Owned",
            provenance="Studio upload",
        )
    )
    key, checksum = asset_key(data)

    assert (width, height, mime) == (24, 18, "image/webp")
    assert key == f"templates/assets/sha256/{checksum[:2]}/{checksum}.webp"
    with Image.open(BytesIO(data)) as processed:
        assert processed.format == "WEBP"
        assert processed.info.get("exif") is None


@pytest.mark.parametrize("mime", ["image/svg+xml", "text/html", "application/zip"])
def test_asset_pipeline_rejects_executable_or_archive_types(mime: str) -> None:
    with pytest.raises(AuthProblem) as caught:
        process_raster(
            AssetUploadRequest(
                content_base64=encoded_png(), mime_type=mime, license="Owned", provenance="Upload"
            )
        )
    assert caught.value.code == "asset_type_rejected"


def test_asset_pipeline_rejects_invalid_and_polyglot_content() -> None:
    payload = base64.b64encode(b"<script>alert(1)</script>\x89PNG").decode()
    with pytest.raises(AuthProblem) as caught:
        process_raster(
            AssetUploadRequest(
                content_base64=payload, mime_type="image/png", license="Owned", provenance="Upload"
            )
        )
    assert caught.value.code == "asset_decode_failed"
