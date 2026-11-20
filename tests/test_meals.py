"""Refeicoes (food_controller /meals)."""

from datetime import datetime

from application.models.application_models import FoodNutrientAssociation, Meal, MealFoodAssociation, Nutrient


def meal_payload(user_id, **overrides):
    payload = {
        "name": "Almoco",
        "user_id": user_id,
        "consumed_at": "2026-11-20T12:30:00",
        "weight_g": 250.0,
        "list_foods_ids": [1, 3],
        "saved_meal": True,
    }
    payload.update(overrides)
    return payload


def expected_calories(db, food_ids):
    total = 0.0
    for food_id in food_ids:
        for assoc, nutrient in (
            db.query(FoodNutrientAssociation, Nutrient)
            .join(Nutrient, Nutrient.id == FoodNutrientAssociation.nutrient_id)
            .filter(FoodNutrientAssociation.food_id == food_id)
        ):
            total += assoc.amount * (nutrient.calories_per_unit or 0.0)
    return total


class TestCreateMeal:
    def test_success_persists_and_computes_calories(self, client, make_user, db):
        user = make_user()
        response = client.post("/meals", json=meal_payload(user["id"]))
        assert response.status_code == 200, response.text
        body = response.json()
        assert set(body) >= {"id", "name", "calories", "weight_g", "consumed_at", "user_id", "saved_meal"}
        assert body["calories"] > 0
        assert abs(body["calories"] - expected_calories(db, [1, 3])) < 1e-6
        row = db.get(Meal, body["id"])
        assert row.user_id == user["id"] and row.weight_g == 250.0 and row.saved_meal is True
        assert row.consumed_at == datetime(2026, 11, 20, 12, 30)
        assert sorted(a.food_id for a in db.query(MealFoodAssociation).filter_by(meal_id=row.id)) == [1, 3]

    def test_consumed_at_accepts_hour_minute_format(self, client, make_user):
        """O validador do schema declara aceitar consumed_at no formato H:M."""
        user = make_user()
        response = client.post("/meals", json=meal_payload(user["id"], consumed_at="12:30"))
        assert response.status_code == 200, response.text

    def test_not_saved_meal_is_not_persisted(self, client, make_user, db):
        user = make_user()
        response = client.post("/meals", json=meal_payload(user["id"], saved_meal=False))
        assert response.status_code == 200
        assert db.query(Meal).filter_by(user_id=user["id"]).count() == 0

    def test_validation_errors_do_not_persist(self, client, make_user, db):
        user = make_user()
        assert client.post("/meals", json=meal_payload(user["id"], list_foods_ids=[])).status_code == 400
        assert client.post("/meals", json=meal_payload(999999)).status_code == 400
        assert client.post("/meals", json=meal_payload(user["id"], list_foods_ids=[1, 999999])).status_code == 400
        assert client.post("/meals", json=meal_payload(user["id"], weight_g=0)).status_code == 400
        assert client.post("/meals", json=meal_payload(user["id"], weight_g=-5)).status_code == 400
        assert client.post("/meals", json={**meal_payload(user["id"]), "extra": True}).status_code == 422
        assert client.post("/meals", json=meal_payload(user["id"], consumed_at="ontem")).status_code == 422
        assert client.post("/meals", json={}).status_code == 422
        assert db.query(Meal).filter_by(user_id=user["id"]).count() == 0

    def test_repeated_food_ids_are_associated_once(self, client, make_user, db):
        """Mesmo alimento pesado duas vezes na balanca: antes gerava 409 (IntegrityError em Meal_Food)."""
        user = make_user()
        response = client.post("/meals", json=meal_payload(user["id"], list_foods_ids=[1, 3, 1]))
        assert response.status_code == 200, response.text
        meal_id = response.json()["id"]
        assert sorted(a.food_id for a in db.query(MealFoodAssociation).filter_by(meal_id=meal_id)) == [1, 3]
        assert abs(response.json()["calories"] - expected_calories(db, [1, 3])) < 1e-6

    def test_firmware_payload_contract(self, client, make_user, db):
        """Corpo exatamente como o firmware LVGL monta (meal_registration_build_json)."""
        user = make_user()
        body = {
            "name": "Refeição",
            "user_id": user["id"],
            "consumed_at": "2026-11-20 12:30:05",
            "calories": 312,
            "weight_g": 250,
            "list_foods_ids": [1, 3],
            "saved_meal": True,
        }
        response = client.post("/meals", json=body)
        assert response.status_code == 200, response.text
        row = db.get(Meal, response.json()["id"])
        assert row.name == "Refeição" and row.weight_g == 250
        assert row.consumed_at == datetime(2026, 11, 20, 12, 30, 5)


class TestListMeals:
    def test_list_with_foods(self, client, make_user):
        user = make_user()
        meal_id = client.post("/meals", json=meal_payload(user["id"])).json()["id"]
        response = client.get("/meals", params={"user_id": user["id"]})
        assert response.status_code == 200
        meals = response.json()
        assert [m["id"] for m in meals] == [meal_id]
        assert sorted(f["id"] for f in meals[0]["foods"]) == [1, 3]
        assert all(set(f) == {"id", "name", "category_id", "brand_id", "image"} for f in meals[0]["foods"])

    def test_user_without_meals(self, client, make_user):
        user = make_user()
        assert client.get("/meals", params={"user_id": user["id"]}).status_code == 404
        assert client.get("/meals").status_code == 422


class TestUpdateMeal:
    def test_success(self, client, make_user, db):
        user = make_user()
        meal_id = client.post("/meals", json=meal_payload(user["id"])).json()["id"]
        response = client.patch(f"/meals/{meal_id}/{user['id']}", json=meal_payload(user["id"], name="Jantar", weight_g=300, list_foods_ids=[6]))
        assert response.status_code == 200
        assert response.json()["name"] == "Jantar"
        db.expunge_all()
        row = db.get(Meal, meal_id)
        assert row.name == "Jantar" and row.weight_g == 300
        # calorias recalculadas para os novos alimentos (antes eram zeradas pelo valor default do body)
        assert row.calories > 0 and abs(row.calories - expected_calories(db, [6])) < 1e-6
        assert [a.food_id for a in db.query(MealFoodAssociation).filter_by(meal_id=meal_id)] == [6]

    def test_repeated_food_ids_are_associated_once(self, client, make_user, db):
        user = make_user()
        meal_id = client.post("/meals", json=meal_payload(user["id"])).json()["id"]
        response = client.patch(f"/meals/{meal_id}/{user['id']}", json=meal_payload(user["id"], list_foods_ids=[6, 6]))
        assert response.status_code == 200, response.text
        db.expunge_all()
        assert [a.food_id for a in db.query(MealFoodAssociation).filter_by(meal_id=meal_id)] == [6]

    def test_other_user_cannot_update(self, client, make_user):
        owner, other = make_user(), make_user()
        meal_id = client.post("/meals", json=meal_payload(owner["id"])).json()["id"]
        assert client.patch(f"/meals/{meal_id}/{other['id']}", json=meal_payload(other["id"])).status_code == 404

    def test_body_cannot_move_meal_to_another_user(self, client, make_user, db):
        owner, other = make_user(), make_user()
        meal_id = client.post("/meals", json=meal_payload(owner["id"])).json()["id"]
        client.patch(f"/meals/{meal_id}/{owner['id']}", json=meal_payload(other["id"]))
        db.expunge_all()
        assert db.get(Meal, meal_id).user_id == owner["id"]

    def test_invalid_food_keeps_previous_state(self, client, make_user, db):
        user = make_user()
        meal_id = client.post("/meals", json=meal_payload(user["id"])).json()["id"]
        bad = client.patch(f"/meals/{meal_id}/{user['id']}", json=meal_payload(user["id"], name="X", list_foods_ids=[999999]))
        assert bad.status_code == 400
        db.expunge_all()
        assert db.get(Meal, meal_id).name == "Almoco"
        assert db.query(MealFoodAssociation).filter_by(meal_id=meal_id).count() == 2


class TestDeleteMeal:
    def test_success_and_errors(self, client, make_user, db):
        owner, other = make_user(), make_user()
        meal_id = client.post("/meals", json=meal_payload(owner["id"])).json()["id"]
        assert client.delete(f"/meals/{meal_id}/{other['id']}").status_code == 404
        response = client.delete(f"/meals/{meal_id}/{owner['id']}")
        assert response.status_code == 200
        assert response.json() == {"message": "Meal deleted successfully"}
        db.expunge_all()
        assert db.get(Meal, meal_id) is None
        assert db.query(MealFoodAssociation).filter_by(meal_id=meal_id).count() == 0
        assert client.delete(f"/meals/{meal_id}/{owner['id']}").status_code == 404
        assert client.delete("/meals/abc/1").status_code == 422
