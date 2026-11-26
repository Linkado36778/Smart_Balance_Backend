"""Reconhecimento de alimentos com SigLIP (food_recognition + SiglIp/test_01_Siglip.py).

Estes testes usam o modelo SigLIP REAL em cache local (HF_HUB_OFFLINE=1). Nenhum
limiar, label ou parametro do pipeline e alterado. Imagens, embeddings e tensores
nao sao registrados: apenas rotulos, confiancas e bounding boxes.
"""

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from application.models.application_models import Food, FoodNutrientAssociation

pytestmark = pytest.mark.siglip

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FOOD_IMAGES = PROJECT_ROOT / "images" / "alimentos"


def _model_available():
    try:
        from huggingface_hub import snapshot_download
        import os

        snapshot_download(os.environ.get("SIGLIP_MODEL_NAME", "google/siglip-base-patch16-224"), local_files_only=True)
        return True
    except Exception:  # pragma: no cover - depende do ambiente
        return False


requires_model = pytest.mark.skipif(not _model_available(), reason="modelo SigLIP nao encontrado no cache local")


def image_bytes(image: Image.Image, fmt="JPEG") -> bytes:
    buffer = BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


def food_image(db, food_id) -> bytes:
    food = db.get(Food, food_id)
    return (FOOD_IMAGES / food.image_url).read_bytes()


@pytest.fixture(autouse=True)
def reset_previous_images():
    from application.controller import food_recognition

    food_recognition.previous_images.clear()
    yield
    food_recognition.previous_images.clear()


def post_image(client, user_id, content, filename="img.jpg", content_type="image/jpeg", weight=None):
    route = "/food-recognition/image" if weight is None else "/food-recognition/image/weight"
    params = {"user_id": user_id}
    if weight is not None:
        params["weight"] = weight
    return client.post(route, params=params, files={"file": (filename, content, content_type)})


def assert_recognition_payload(recognition, db):
    assert recognition["model"] == "SigLIP"
    assert recognition["language"] == "EN/PT-BR"
    predictions = recognition["predictions"]
    assert len(predictions) == 3
    confidences = [p["confidence"] for p in predictions]
    assert confidences == sorted(confidences, reverse=True)
    assert all(0.0 <= c <= 1.0 for c in confidences) and sum(confidences) <= 1.0 + 1e-6
    for prediction in predictions:
        db_food = db.get(Food, prediction["food_id"])
        assert (db_food.user_id is None) == (prediction["source"] == "food")
        assert db_food is not None and db_food.name == prediction["label"]
        if prediction["source"] == "food":
            assert db_food.model_label == prediction["model_label"]
    assert recognition["confidence"] == predictions[0]["confidence"]
    food = recognition["recognized_food"]
    assert food["food_name"] == predictions[0]["label"]
    assert food["source"] == predictions[0]["source"] and food["food_id"] == predictions[0]["food_id"]
    db_food = db.get(Food, food["food_id"])
    assert db_food is not None and db_food.name == food["food_name"]
    assert food["category_id"] == db_food.category_id and food["brand_id"] == db_food.brand_id


def test_every_curated_label_is_seeded_in_the_database(db):
    from shared.database import DEFAULT_FOOD_MODEL_LABELS

    seeded = {f.name: f.model_label for f in db.query(Food).filter(Food.user_id.is_(None), Food.model_label.isnot(None))}
    assert seeded == DEFAULT_FOOD_MODEL_LABELS


def create_food(client, user_id, name, model_label=None, nutrients=None):
    body = {"name": name, "category_id": 1, "nutrients": nutrients or [{"id": 1, "amount": 10.0}]}
    if model_label is not None:
        body["model_label"] = model_label
    response = client.post("/foods", params={"user_id": user_id}, json=body)
    assert response.status_code == 200, response.text
    return response


class TestRecognitionCandidates:
    """Candidatos do SigLIP: Food global com prompt + Food do proprio usuario (sem modelo real)."""

    def test_created_foods_only_for_their_owner(self, client, make_user, db):
        from SiglIp.test_01_Siglip import get_recognition_candidates

        owner, other = make_user(), make_user()
        create_food(client, owner["id"], "Pizza caseira de teste", model_label="  an image of a homemade pizza  ")
        create_food(client, owner["id"], "Bolo de cenoura de teste")

        owner_candidates = get_recognition_candidates(db, owner["id"])
        created = [c for c in owner_candidates if c["source"] == "created_food"]
        assert [(c["name"], c["model_label"]) for c in created] == [
            ("Pizza caseira de teste", "an image of a homemade pizza"),
            ("Bolo de cenoura de teste", "an image of Bolo de cenoura de teste"),  # gerado pelo nome
        ]

        other_candidates = get_recognition_candidates(db, other["id"])
        assert not [c for c in other_candidates if c["source"] == "created_food"]

        global_names = {c["name"] for c in other_candidates}
        assert global_names == {f.name for f in db.query(Food).filter(Food.user_id.is_(None), Food.model_label.isnot(None))}

    def test_blank_model_label_is_generated_and_saved(self, client, make_user, db):
        user = make_user()
        for name, model_label in (("Sopa de teste", None), ("Quiche de teste", ""), ("Torta de teste", "   ")):
            create_food(client, user["id"], name, model_label=model_label)
            food = db.query(Food).filter_by(user_id=user["id"], name=name).one()
            assert food.model_label == f"an image of {name}"

    def test_update_changes_model_label(self, client, make_user, db):
        user = make_user()
        create_food(client, user["id"], "Lasanha de teste")
        food = db.query(Food).filter_by(user_id=user["id"], name="Lasanha de teste").one()
        assert food.model_label == "an image of Lasanha de teste"

        response = client.patch(f"/foods/{food.id}", params={"user_id": user["id"]},
                                json={"name": "Lasanha de teste", "model_label": "an image of lasagna"})
        assert response.status_code == 200, response.text
        db.expire_all()
        assert db.get(Food, food.id).model_label == "an image of lasagna"

        # sem prompt, volta a ser gerado a partir do (novo) nome
        response = client.patch(f"/foods/{food.id}", params={"user_id": user["id"]},
                                json={"name": "Lasanha bolonhesa de teste", "model_label": ""})
        assert response.status_code == 200, response.text
        db.expire_all()
        assert db.get(Food, food.id).model_label == "an image of Lasanha bolonhesa de teste"

    def test_recognizes_created_food_with_its_nutrients(self, client, make_user, db, monkeypatch):
        """Quando o prompt de um alimento criado vence, o retorno usa esse alimento e seus nutrientes."""
        import torch
        import SiglIp.test_01_Siglip as siglip

        user = make_user()
        create_food(client, user["id"], "Tapioca de teste", model_label="an image of tapioca",
                    nutrients=[{"id": 1, "amount": 2.0}, {"id": 2, "amount": 50.0}])

        def fake_scores(image, texts):
            scores = torch.zeros(len(texts))
            scores[texts.index("an image of tapioca")] = 1.0
            return scores

        monkeypatch.setattr(siglip, "_score_candidates", fake_scores)
        response = post_image(client, user["id"], image_bytes(Image.new("RGB", (64, 64))), weight=200)
        assert response.status_code == 200, response.text
        food = response.json()["items"][0]["recognized_food"]["recognized_food"]
        created = db.query(Food).filter_by(user_id=user["id"], name="Tapioca de teste").one()
        assert food["source"] == "created_food" and food["food_id"] == created.id
        assert {n["nutrient_id"]: n["amount"] for n in food["nutrients"]} == pytest.approx({1: 4.0, 2: 100.0})


@requires_model
class TestRecognitionHappyPath:
    def test_first_image_recognized(self, client, make_user, db):
        user = make_user()
        response = post_image(client, user["id"], food_image(db, 10))  # batata frita
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["changed"] is False and body["first_image"] is True
        assert len(body["items"]) == 1 and body["items"][0]["bbox"] is None
        recognition = body["items"][0]["recognized_food"]
        assert_recognition_payload(recognition, db)
        assert "nutrients" not in recognition["recognized_food"]
        assert "Batata inglesa, frita" in [p["label"] for p in recognition["predictions"]]

    def test_weight_endpoint_scales_nutrients(self, client, make_user, db):
        user = make_user()
        response = post_image(client, user["id"], food_image(db, 8), weight=250)  # banana
        assert response.status_code == 200, response.text
        recognized = response.json()["items"][0]["recognized_food"]
        assert_recognition_payload(recognized, db)
        food = recognized["recognized_food"]
        per_100g = {a.nutrient_id: a.amount for a in db.query(FoodNutrientAssociation).filter_by(food_id=food["food_id"])}
        assert {n["nutrient_id"]: n["amount"] for n in food["nutrients"]} == pytest.approx({k: v * 2.5 for k, v in per_100g.items()})
        assert all(set(n) == {"nutrient_id", "name", "amount", "unit"} for n in food["nutrients"])

    def test_weight_endpoint_without_weight(self, client, make_user, db):
        user = make_user()
        response = client.post("/food-recognition/image/weight", params={"user_id": user["id"]}, files={"file": ("a.jpg", food_image(db, 8), "image/jpeg")})
        assert response.status_code == 200
        assert "nutrients" not in response.json()["items"][0]["recognized_food"]["recognized_food"]

    def test_png_and_webp_inputs(self, client, make_user, db):
        user = make_user()
        for food_id in (13, 7):  # PNG e WEBP do dataset
            from application.controller import food_recognition

            food_recognition.previous_images.clear()
            food = db.get(Food, food_id)
            response = post_image(client, user["id"], food_image(db, food_id), filename=food.image_url)
            assert response.status_code == 200, (food.image_url, response.text)

    def test_change_detection_on_second_image(self, client, make_user, db):
        """Fluxo do firmware: foto da balanca vazia e depois com o alimento."""
        user = make_user()
        background = Image.new("RGB", (640, 480), (235, 235, 235))
        food = Image.open(FOOD_IMAGES / db.get(Food, 10).image_url).convert("RGB").resize((240, 240))
        with_food = background.copy()
        with_food.paste(food, (200, 120))

        first = post_image(client, user["id"], image_bytes(background))
        assert first.status_code == 200 and first.json()["first_image"] is True

        second = post_image(client, user["id"], image_bytes(with_food), weight=150)
        assert second.status_code == 200, second.text
        body = second.json()
        assert body["changed"] is True and body["first_image"] is False
        x, y, w, h = body["items"][0]["bbox"]
        # bbox deve cobrir a regiao colada (200,120,240,240), com folga de padding
        assert x <= 205 and y <= 125 and x + w >= 435 and y + h >= 355
        assert x >= 180 and y >= 100 and x + w <= 460 and y + h <= 380
        recognition = body["items"][0]["recognized_food"]
        assert_recognition_payload(recognition, db)
        assert "nutrients" in recognition["recognized_food"]

    def test_tiny_and_large_images(self, client, make_user):
        user = make_user()
        from application.controller import food_recognition

        assert post_image(client, user["id"], image_bytes(Image.new("RGB", (1, 1), (10, 200, 10)))).status_code == 200
        food_recognition.previous_images.clear()
        big = Image.effect_noise((4000, 3000), 40).convert("RGB")
        assert post_image(client, user["id"], image_bytes(big)).status_code == 200

    def test_no_threshold_always_returns_a_food(self, client, make_user, db):
        """Documenta o comportamento atual: nao ha limiar de confianca; ruido tambem recebe um alimento."""
        user = make_user()
        noise = Image.effect_noise((224, 224), 120).convert("RGB")
        response = post_image(client, user["id"], image_bytes(noise))
        assert response.status_code == 200
        assert_recognition_payload(response.json()["items"][0]["recognized_food"], db)


@requires_model
def test_identical_second_image_returns_400(client, make_user, db):
    user = make_user()
    content = food_image(db, 1)
    assert post_image(client, user["id"], content).status_code == 200
    response = post_image(client, user["id"], content)
    assert response.status_code == 400
    assert "Nenhuma região de diferença" in response.json()["detail"]


class TestRecognitionErrors:
    def test_unknown_user(self, client, db):
        assert post_image(client, 999999, b"x").status_code == 404

    def test_missing_file_or_user(self, client, make_user):
        user = make_user()
        assert client.post("/food-recognition/image", params={"user_id": user["id"]}).status_code == 422
        assert client.post("/food-recognition/image", files={"file": ("a.jpg", b"x", "image/jpeg")}).status_code == 422
        assert client.post("/food-recognition/image/weight", params={"user_id": user["id"], "weight": "abc"},
                           files={"file": ("a.jpg", b"x", "image/jpeg")}).status_code == 422

    def test_empty_file(self, client, make_user):
        user = make_user()
        for route in ("/food-recognition/image", "/food-recognition/image/weight"):
            response = client.post(route, params={"user_id": user["id"]}, files={"file": ("vazio.jpg", b"", "image/jpeg")})
            assert response.status_code == 400 and response.json()["detail"] == "Empty image file."

    def test_invalid_content(self, client, make_user):
        user = make_user()
        for name, content, ctype in (
            ("texto.txt", b"isto nao e uma imagem", "text/plain"),
            ("falsa.jpg", b"isto nao e uma imagem", "image/jpeg"),
            ("corrompida.jpg", image_bytes(Image.new("RGB", (64, 64)))[:40], "image/jpeg"),
        ):
            response = post_image(client, user["id"], content, filename=name, content_type=ctype)
            assert response.status_code == 400, (name, response.text)
            assert "Invalid image data" in response.json()["detail"]

    def test_invalid_first_image_does_not_become_reference(self, client, make_user):
        """Uma imagem invalida nao deve ser usada como 'imagem anterior' da proxima requisicao."""
        from application.controller import food_recognition

        user = make_user()
        post_image(client, user["id"], b"lixo", filename="lixo.jpg")
        assert food_recognition.get_previous_image_path(user["id"]) is None

    def test_model_unavailable(self, client, make_user, monkeypatch):
        import SiglIp.test_01_Siglip as siglip

        def broken_model():
            raise OSError("modelo indisponivel")

        monkeypatch.setattr(siglip, "_get_model", broken_model)
        user = make_user()
        response = post_image(client, user["id"], image_bytes(Image.new("RGB", (64, 64), (1, 1, 1))))
        assert response.status_code in (500, 503), response.text
        assert "modelo indisponivel" in response.json()["detail"]
        assert client.get("/health").status_code == 200
