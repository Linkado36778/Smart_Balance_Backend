"""Fluxos de integracao entre endpoints, na ordem de uso real do sistema."""

from urllib.parse import parse_qs, urlparse

import pytest
from PIL import Image

from application.models.application_models import Food, Meal, MealFoodAssociation, UserBalanceAssociation
from conftest import TEST_PASSWORD, unique_email
from test_food_recognition import FOOD_IMAGES, image_bytes, requires_model


def test_user_nutricionist_diet_flow(client, db):
    user_email, nutri_email = unique_email(), unique_email("nutri")
    assert client.post("/nutricionist", json={"email": nutri_email, "password": TEST_PASSWORD, "phone": "1", "crn": "CRN-1 11111"}).status_code == 200
    nutri = client.get(f"/login_Nutricionist/{nutri_email}/{TEST_PASSWORD}").json()
    user = client.post("/user", json={
        "email": user_email, "birthdate": "2000-01-01", "weight_kg": 60, "height_m": 1.6,
        "sex": "F", "password": TEST_PASSWORD, "is_active": True,
    }).json()["data"]
    assert client.post("/auth/commun_user", json={"email": user_email, "password": TEST_PASSWORD}).status_code == 200
    assert client.post("/link_user_nutricionist", params={"user_id": user["id"], "nutricionist_id": nutri["id"]}).status_code == 200
    assert [u["id"] for u in client.get(f"/list_user_data_by_nutricionist/{nutri['id']}").json()] == [user["id"]]
    diet = client.post(f"/create_diet/{nutri['id']}/{user['id']}", json={
        "name": "Plano", "user_id": user["id"], "nutricionist_id": nutri["id"], "list_foods_ids": [1, 2, 3], "kcal_goal": 2000,
    })
    assert diet.status_code == 200
    assert [d["id"] for d in client.get(f"/list_diets_by_user/{user['id']}").json()] == [diet.json()["data"]["diet_id"]]


def test_allergen_flow_marks_foods(client, make_user, db):
    user = make_user()
    allergen = client.post("/add_allergen", json={"name": "Alergeno de fluxo"}).json()["data"]
    assert client.post("/add_allergen_to_user", json={"user_id": user["id"], "allergen_id": allergen["id"]}).status_code == 200
    created = client.post("/foods", params={"user_id": user["id"]}, json={"name": f"Bolo {user['id']}", "allergen_ids": [allergen["id"]]})
    assert created.status_code == 200
    from application.models.application_models import CreatedFood

    created_id = db.query(CreatedFood).filter_by(user_id=user["id"]).one().id
    assert client.get(f"/foods/{created_id}", params={"user_id": user["id"]}).json()["user_allergic"] is True
    assert [a["id"] for a in client.get(f"/list_allergens_by_user/{user['id']}").json()] == [allergen["id"]]


def test_scale_pairing_flow(client, make_user, db):
    user = make_user()
    balance = client.post("/register_balance", json={"id": 0, "name": "Balanca fluxo"}).json()["data"]
    qr = client.post("/generate_qr_code/").json()["data"]
    token = parse_qs(urlparse(qr["pairing_url"]).query)["token"][0]
    assert client.get(urlparse(qr["qr_code_url"]).path).status_code == 200
    paired = client.post("/pair-scale", params={"user_id": user["id"], "balance_id": balance["id"], "token": token})
    assert paired.status_code == 200
    assert db.get(UserBalanceAssociation, (user["id"], balance["id"])) is not None


@pytest.mark.siglip
@requires_model
def test_recognition_to_meal_flow(client, make_user, db):
    """Balanca vazia -> alimento na balanca (com peso) -> refeicao com o alimento reconhecido -> CRUD da refeicao."""
    from application.controller import food_recognition

    food_recognition.previous_images.clear()
    user = make_user()
    background = Image.new("RGB", (640, 480), (240, 240, 240))
    with_food = background.copy()
    with_food.paste(Image.open(FOOD_IMAGES / db.get(Food, 8).image_url).convert("RGB").resize((220, 220)), (180, 120))

    def post(content, weight):
        return client.post("/food-recognition/image/weight", params={"user_id": user["id"], "weight": weight},
                           files={"file": ("frame.jpg", content, "image/jpeg")})

    assert post(image_bytes(background), 0).status_code == 200
    recognition = post(image_bytes(with_food), 180)
    assert recognition.status_code == 200, recognition.text
    food = recognition.json()["items"][0]["recognized_food"]["recognized_food"]
    assert db.get(Food, food["food_id"]) is not None

    meal = client.post("/meals", params={"user_id": user["id"]}, json={
        "name": "Lanche", "consumed_at": "2026-11-20T16:00:00",
        "list_foods_ids": [food["food_id"]], "list_foods_weights": [180], "saved_meal": True,
    })
    assert meal.status_code == 200, meal.text
    meal_id = meal.json()["id"]
    meals = client.get("/meals", params={"user_id": user["id"]}).json()
    assert meals[0]["foods"][0]["id"] == food["food_id"]
    assert meals[0]["foods"][0]["weight_g"] == 180

    other_food = 1 if food["food_id"] != 1 else 3
    assert client.patch(f"/meals/{meal_id}/{user['id']}", json={
        "name": "Lanche da tarde", "consumed_at": "2026-11-20T16:30:00",
        "list_foods_ids": [food["food_id"], other_food], "list_foods_weights": [120, 80], "saved_meal": True,
    }).status_code == 200
    assert db.query(MealFoodAssociation).filter_by(meal_id=meal_id).count() == 2
    assert client.delete(f"/meals/{meal_id}/{user['id']}").status_code == 200
    db.expunge_all()
    assert db.get(Meal, meal_id) is None
    food_recognition.previous_images.clear()
