"""Candidatos e selecao manual do reconhecimento (confianca < 70%).

O modelo SigLIP e substituido por um falso que devolve probabilidades
controladas: assim os limites (95%, 70%, 69%, 50%) sao exatos e o teste
nao depende do conteudo da imagem. O ranking, os rotulos e a busca no
banco sao os do pipeline real (image_recognition_endpoint).
"""

from io import BytesIO
from types import SimpleNamespace

import pytest
import torch
from PIL import Image

from application.models.application_models import Food


@pytest.fixture(autouse=True)
def reset_previous_images():
    from application.controller import food_recognition

    food_recognition.previous_images.clear()
    yield
    food_recognition.previous_images.clear()


def jpeg() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (64, 64), (200, 180, 120)).save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture
def fake_siglip(monkeypatch):
    """Configura as probabilidades por db_name; o restante e dividido igualmente."""
    import SiglIp.test_01_Siglip as siglip

    def configure(scores: dict):
        names = [label["db_name"] for label in siglip.LABELS]
        assert set(scores) <= set(names)
        rest = (1.0 - sum(scores.values())) / (len(names) - len(scores))
        probs = torch.tensor([scores.get(name, rest) for name in names], dtype=torch.float32)

        processor = lambda **kwargs: {"pixel_values": torch.zeros(1)}  # noqa: E731
        model = lambda **kwargs: SimpleNamespace(logits_per_image=torch.zeros(1, len(names)))  # noqa: E731
        monkeypatch.setattr(siglip, "_get_model", lambda: (processor, model))
        # softmax devolve exatamente as probabilidades configuradas (float32)
        monkeypatch.setattr(siglip.torch, "softmax", lambda logits, dim=-1: probs)
        return probs

    return configure


def recognize(client, user_id, weight=150):
    response = client.post(
        "/food-recognition/image/weight",
        params={"user_id": user_id, "weight": weight},
        files={"file": ("a.jpg", jpeg(), "image/jpeg")},
    )
    assert response.status_code == 200, response.text
    return response.json()["items"][0]["recognized_food"]


ARROZ = "Arroz tipo 1, cozido"
FEIJAO = "Feijão preto, cozido"
FEIJAO_CRU = "Feijão preto, cru"
OVO = "Ovo de galinha, frito"
BATATA = "Batata inglesa, frita"


@pytest.mark.parametrize(
    "top, expected_manual",
    [(0.95, False), (0.85, False), (0.70, False), (0.69, True), (0.55, True), (0.50, True), (0.30, True)],
)
def test_threshold_is_strictly_below_70(client, make_user, fake_siglip, top, expected_manual):
    fake_siglip({ARROZ: top, FEIJAO: min(top / 2, (1.0 - top) / 2)})
    recognition = recognize(client, make_user()["id"])
    assert recognition["confidence_threshold"] == 0.70
    assert recognition["manual_selection_required"] is expected_manual
    assert recognition["recognized_food"]["food_name"] == ARROZ
    assert abs(recognition["confidence"] - top) < 1e-6


def test_requires_manual_selection_pure():
    from SiglIp.test_01_Siglip import requires_manual_selection

    assert requires_manual_selection(0.95) is False
    assert requires_manual_selection(0.70) is False
    # 0.70 em float32 (como sai do softmax) continua sendo 70%
    assert requires_manual_selection(torch.tensor(0.70, dtype=torch.float32).item()) is False
    assert requires_manual_selection(0.69) is True
    assert requires_manual_selection(0.6999) is True
    for invalid in (None, "abc", float("nan"), -0.1, 1.5):
        assert requires_manual_selection(invalid) is True


def test_candidates_sorted_unique_and_valid(client, make_user, fake_siglip, db):
    fake_siglip({ARROZ: 0.50, FEIJAO: 0.20, FEIJAO_CRU: 0.10, OVO: 0.06, BATATA: 0.05})
    recognition = recognize(client, make_user()["id"], weight=200)

    candidates = recognition["candidates"]
    assert [c["food_name"] for c in candidates] == [ARROZ, FEIJAO, FEIJAO_CRU, OVO, BATATA]
    confidences = [c["confidence"] for c in candidates]
    assert confidences == sorted(confidences, reverse=True)
    assert len({c["food_id"] for c in candidates}) == len(candidates)
    for candidate in candidates:
        food = db.get(Food, candidate["food_id"])
        assert food is not None and food.name == candidate["food_name"]
        assert set(candidate) == {"food_id", "food_name", "category_id", "brand_id", "confidence", "nutrients"}

    # 1o candidato == alimento reconhecido automaticamente (mesmos nutrientes do peso)
    assert candidates[0]["food_id"] == recognition["recognized_food"]["food_id"]
    assert candidates[0]["nutrients"] == recognition["recognized_food"]["nutrients"]
    # predictions (contrato antigo) continua com 3 itens
    assert len(recognition["predictions"]) == 3


def test_candidate_nutrients_scaled_to_weight(client, make_user, fake_siglip):
    fake_siglip({ARROZ: 0.40, FEIJAO: 0.35})
    at_100 = recognize(client, make_user()["id"], weight=100)["candidates"][1]["nutrients"]
    at_250 = recognize(client, make_user()["id"], weight=250)["candidates"][1]["nutrients"]
    assert at_100 and len(at_100) == len(at_250)
    for small, big in zip(at_100, at_250):
        assert abs(big["amount"] - small["amount"] * 2.5) < 1e-6


def test_candidates_without_weight_have_no_nutrients(client, make_user, fake_siglip):
    fake_siglip({ARROZ: 0.40})
    response = client.post(
        "/food-recognition/image",
        params={"user_id": make_user()["id"]},
        files={"file": ("a.jpg", jpeg(), "image/jpeg")},
    )
    candidates = response.json()["items"][0]["recognized_food"]["candidates"]
    assert candidates and all("nutrients" not in c for c in candidates)


def test_labels_missing_from_database_are_skipped(db):
    from SiglIp.test_01_Siglip import build_recognition_candidates

    ranked = [
        {"label": "Nao cadastrado 1", "confidence": 0.5},
        {"label": ARROZ, "confidence": 0.3},
        {"label": "Nao cadastrado 2", "confidence": 0.1},
    ]
    candidates = build_recognition_candidates(db, ranked)
    assert [c["food_name"] for c in candidates] == [ARROZ]


def test_no_candidates(db):
    from SiglIp.test_01_Siglip import build_recognition_candidates

    assert build_recognition_candidates(db, []) == []
    assert build_recognition_candidates(db, [{"label": "Inexistente", "confidence": 0.9}]) == []


def test_duplicate_foods_appear_once(db):
    from SiglIp.test_01_Siglip import build_recognition_candidates

    ranked = [
        {"label": ARROZ, "confidence": 0.4},
        {"label": ARROZ, "confidence": 0.3},  # dois rotulos para o mesmo alimento
        {"label": FEIJAO, "confidence": 0.2},
    ]
    candidates = build_recognition_candidates(db, ranked)
    assert [(c["food_name"], c["confidence"]) for c in candidates] == [(ARROZ, 0.4), (FEIJAO, 0.2)]


def test_candidates_limited(db):
    from SiglIp.test_01_Siglip import CANDIDATES_COUNT, LABELS, build_recognition_candidates

    ranked = [{"label": label["db_name"], "confidence": 0.04} for label in LABELS]
    assert len(build_recognition_candidates(db, ranked)) == CANDIDATES_COUNT
