"""POST /upload-image (vision_recognition_controller)."""

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image


def jpeg_bytes(size=(64, 64), color=(200, 30, 30)):
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture
def upload_dir(work_dir):
    import application.controller.vision_recognition_controller as vision

    return work_dir / vision.UPLOAD_DIR


def test_upload_with_category(client, upload_dir):
    content = jpeg_bytes()
    response = client.post("/upload-image", params={"category": "frutas"}, files={"file": ("maca.jpg", content, "image/jpeg")})
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["filename"] == "maca.jpg"
    saved = upload_dir / "frutas" / "maca.jpg"
    assert saved.read_bytes() == content
    assert Path(data["saved_path"]).name == "maca.jpg"


def test_upload_without_category(client, upload_dir):
    content = jpeg_bytes(color=(1, 2, 3))
    response = client.post("/upload-image", files={"file": ("sem_categoria.jpg", content, "image/jpeg")})
    assert response.status_code == 200
    assert (upload_dir / "sem_categoria.jpg").read_bytes() == content


def test_rejects_non_image_content_type(client, upload_dir):
    response = client.post("/upload-image", files={"file": ("notas.txt", b"texto", "text/plain")})
    assert response.status_code == 400
    assert response.json()["message"] == "File provided is not an image."
    assert not (upload_dir / "notas.txt").exists()


def test_missing_file(client):
    assert client.post("/upload-image").status_code == 422


@pytest.mark.parametrize(
    "filename,category",
    [
        ("../../fora_do_upload.jpg", None),
        ("fora_do_upload.jpg", "../../"),
        ("fora_do_upload.jpg", "frutas/../../.."),
    ],
)
def test_path_traversal_is_blocked(client, work_dir, upload_dir, filename, category):
    params = {"category": category} if category else {}
    response = client.post("/upload-image", params=params, files={"file": (filename, jpeg_bytes(), "image/jpeg")})
    written = [p for p in work_dir.rglob("fora_do_upload.jpg") if upload_dir.resolve() not in p.resolve().parents]
    assert written == [], f"arquivo gravado fora do diretorio de upload: {written}"
    assert response.status_code in (200, 400)
    if response.status_code == 200:
        saved = Path(response.json()["data"]["saved_path"]).resolve()
        assert upload_dir.resolve() in saved.parents
