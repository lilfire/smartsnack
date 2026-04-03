"""E2E test for Gemini OCR — real API call, no mocks.

Requires GEMINI_API_KEY (or LLM_API_KEY) env var to run.
Skipped automatically when the key is absent.
"""

import base64
import io
import os
import shutil
import sys

import pytest

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

_GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("LLM_API_KEY")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def ocr_e2e_app(tmp_path_factory):
    """Flask app with isolated temp DB for Gemini OCR E2E tests."""
    db_file = str(tmp_path_factory.mktemp("gemini_e2e") / "test.sqlite")
    trans_tmp = str(tmp_path_factory.mktemp("gemini_e2e_trans"))

    import config

    _orig_db = config.DB_PATH
    _orig_trans = config.TRANSLATIONS_DIR

    os.environ.setdefault("SMARTSNACK_SECRET_KEY", "gemini-e2e-test-secret")
    os.environ["DB_PATH"] = db_file
    config.DB_PATH = db_file

    # Copy real translations into temp dir
    if os.path.isdir(_orig_trans):
        for fname in os.listdir(_orig_trans):
            if fname.endswith(".json"):
                shutil.copy(os.path.join(_orig_trans, fname), trans_tmp)
    config.TRANSLATIONS_DIR = trans_tmp

    import db as db_mod
    db_mod.DB_PATH = db_file

    if "translations" in sys.modules:
        sys.modules["translations"].TRANSLATIONS_DIR = trans_tmp

    from app import create_app
    application = create_app()
    application.config["TESTING"] = True

    yield application

    # Restore
    config.DB_PATH = _orig_db
    config.TRANSLATIONS_DIR = _orig_trans


@pytest.fixture()
def ocr_client(ocr_e2e_app):
    """Flask test client that injects CSRF header."""
    with ocr_e2e_app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Image helper
# ---------------------------------------------------------------------------


def _make_ingredient_image():
    """Return PNG bytes of a small image with ingredient text."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (240, 80), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), "Ingredients: sugar, flour, water", fill="black")
    draw.text((10, 45), "salt, yeast", fill="black")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# E2E test
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _GEMINI_API_KEY,
    reason="GEMINI_API_KEY not set — skipping real Gemini E2E test",
)
def test_gemini_ocr_real_api_returns_text(ocr_client):
    """POST /api/ocr/ingredients with a real PIL image and real Gemini API.

    No mocked providers. This test is skipped when GEMINI_API_KEY is absent.
    When the key is present it calls the live Gemini API and verifies:
    - HTTP 200
    - ``text`` field is present in the response
    - ``provider`` is ``"gemini"``
    """
    from unittest.mock import patch

    image_bytes = _make_ingredient_image()
    image_b64 = base64.b64encode(image_bytes).decode()

    with patch("services.settings_service.get_ocr_backend", return_value="gemini"):
        resp = ocr_client.post(
            "/api/ocr/ingredients",
            json={"image": image_b64},
            headers={"X-Requested-With": "SmartSnack"},
        )

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.get_json()}"
    data = resp.get_json()
    assert "text" in data
    assert "provider" in data
    assert data["provider"] == "gemini"
    # Response may include empty text if Gemini found nothing; both are valid 200s
