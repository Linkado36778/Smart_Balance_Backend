"""Refeicoes (food_controller /meals).

Contrato atual (commit 9370e65): POST /meals?user_id=<id> com corpo
{name, consumed_at, list_foods_ids, list_foods_weights, saved_meal}. O corpo
nao aceita mais user_id, calories nem weight_g (extra="forbid"); o backend
calcula as calorias escalando os nutrientes (por 100 g) pelo peso de cada
alimento, e o peso total e a soma de list_foods_weights.
"""

from datetime import datetime

from application.models.application_models import FoodNutrientAssociation, Meal, MealFoodAssociation, Nutrient


def meal_payload(**overrides):
    payload = {
        "name": "Almoco",
        "consumed_at": "2026-11-20T12:30:00",
        "list_foods_ids": [1, 3],
        "list_foods_weights": [150.0, 100.0],
        "saved_meal": True,
    }
    payload.update(overrides)
    return payload


def post_meal(client, user_id, **overrides):
    return client.post("/meals", params={"user_id": user_id}, json=meal_payload(**overrides))


def expected_calories(db, foods_and_weights):
    """Calorias pela regra do backend: amount (por 100 g) x peso / 100 x kcal/unidade."""
    total = 0.0
    for food_id, weight in foods_and_weights:
        for assoc, nutrient in (
            db.query(FoodNutrientAssociation, Nutrient)
            .join(Nutrient, Nutrient.id == FoodNutrientAssociation.nutrient_id)
            .filter(FoodNutrientAssociation.food_id == food_id)
        ):
            total += assoc.amount * weight / 100.0 * (nutrient.calories_per_unit or 0.0)
    return total


def food_weights(db, meal_id):
    return {a.food_id: a.food_weight_g for a in db.query(MealFoodAssociation).filter_by(meal_id=meal_id)}


class TestCreateMeal:
    def test_success_persists_and_computes_calories(self, client, make_user, db):
        user = make_user()
        response = post_meal(client, user["id"])
        assert response.status_code == 200, response.text
        body = response.json()
        assert set(body) >= {"id", "name", "calories", "weight_g", "consumed_at", "user_id", "saved_meal"}
        assert body["calories"] > 0
        assert abs(body["calories"] - expected_calories(db, [(1, 150.0), (3, 100.0)])) < 1e-6
        row = db.get(Meal, body["id"])
        assert row.user_id == user["id"] and row.weight_g == 250.0 and row.saved_meal is True
        assert row.consumed_at == datetime(2026, 11, 20, 12, 30)
        assert food_weights(db, row.id) == {1: 150.0, 3: 100.0}

    def test_calories_scale_with_weight(self, client, make_user):
        user = make_user()
        small = post_meal(client, user["id"], list_foods_ids=[1], list_foods_weights=[100.0]).json()
        large = post_meal(client, user["id"], list_foods_ids=[1], list_foods_weights=[250.0]).json()
        assert small["calories"] > 0
        assert abs(large["calories"] - small["calories"] * 2.5) < 1e-6

    def test_consumed_at_accepts_hour_minute_format(self, client, make_user):
        """O validador do schema declara aceitar consumed_at no formato H:M."""
        user = make_user()
        response = post_meal(client, user["id"], consumed_at="12:30")
        assert response.status_code == 200, response.text

    def test_firmware_payload(self, client, make_user, db):
        """Corpo exato enviado pela balanca (meal_registration.c): data com espaco, pesos inteiros."""
        user = make_user()
        response = client.post(
            f"/meals?user_id={user['id']}",
            content='{"name":"Refeição","consumed_at":"2026-11-21 12:00:00",'
                    '"list_foods_ids":[1,3],"list_foods_weights":[200,100],"saved_meal":true}',
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert isinstance(body["id"], int) and body["id"] > 0
        assert body["name"] == "Refeição" and body["weight_g"] == 300.0
        assert food_weights(db, body["id"]) == {1: 200.0, 3: 100.0}

    def test_not_saved_meal_is_not_persisted(self, client, make_user, db):
        user = make_user()
        response = post_meal(client, user["id"], saved_meal=False)
        assert response.status_code == 200
        assert db.query(Meal).filter_by(user_id=user["id"]).count() == 0

    def test_validation_errors_do_not_persist(self, client, make_user, db):
        user = make_user()
        uid = user["id"]
        assert post_meal(client, uid, list_foods_ids=[], list_foods_weights=[]).status_code == 400
        assert post_meal(client, 999999).status_code == 400
        assert post_meal(client, uid, list_foods_ids=[1, 999999]).status_code == 400
        # um peso por alimento, todos > 0
        assert post_meal(client, uid, list_foods_weights=[150.0]).status_code == 400
        assert post_meal(client, uid, list_foods_weights=[]).status_code == 400
        assert post_meal(client, uid, list_foods_weights=[150.0, 0]).status_code == 400
        assert post_meal(client, uid, list_foods_weights=[150.0, -5]).status_code == 400
        assert client.post("/meals", params={"user_id": uid}, json={**meal_payload(), "extra": True}).status_code == 422
        assert post_meal(client, uid, consumed_at="ontem").status_code == 422
        assert client.post("/meals", params={"user_id": uid}, json={}).status_code == 422
        assert db.query(Meal).filter_by(user_id=uid).count() == 0

    def test_old_contract_is_rejected(self, client, make_user, db):
        """Campos removidos do corpo (user_id, calories, weight_g) e user_id fora da query dao 422."""
        user = make_user()
        uid = user["id"]
        for field, value in (("user_id", uid), ("calories", 100.0), ("weight_g", 250.0)):
            response = client.post("/meals", params={"user_id": uid}, json=meal_payload(**{field: value}))
            assert response.status_code == 422, field
        assert client.post("/meals", json=meal_payload()).status_code == 422  # sem ?user_id=
        assert db.query(Meal).filter_by(user_id=uid).count() == 0


class TestListMeals:
    def test_list_with_foods(self, client, make_user):
        user = make_user()
        meal_id = post_meal(client, user["id"]).json()["id"]
        response = client.get("/meals", params={"user_id": user["id"]})
        assert response.status_code == 200
        meals = response.json()
        assert [m["id"] for m in meals] == [meal_id]
        assert sorted(f["id"] for f in meals[0]["foods"]) == [1, 3]
        assert all(set(f) == {"id", "name", "category_id", "brand_id", "weight_g", "image"} for f in meals[0]["foods"])

    def test_each_food_has_its_own_weight(self, client, make_user):
        """Cada alimento traz o proprio peso (antes todos recebiam o ultimo peso da refeicao)."""
        user = make_user()
        post_meal(client, user["id"], list_foods_ids=[1, 3, 6], list_foods_weights=[150.0, 100.0, 60.0])
        foods = client.get("/meals", params={"user_id": user["id"]}).json()[0]["foods"]
        assert {f["id"]: f["weight_g"] for f in foods} == {1: 150.0, 3: 100.0, 6: 60.0}

    def test_user_without_meals(self, client, make_user):
        user = make_user()
        assert client.get("/meals", params={"user_id": user["id"]}).status_code == 404
        assert client.get("/meals").status_code == 422


class TestUpdateMeal:
    def test_success(self, client, make_user, db):
        user = make_user()
        meal_id = post_meal(client, user["id"]).json()["id"]
        response = client.patch(f"/meals/{meal_id}/{user['id']}",
                                json=meal_payload(name="Jantar", list_foods_ids=[6], list_foods_weights=[300.0]))
        assert response.status_code == 200
        assert response.json()["name"] == "Jantar"
        db.expunge_all()
        row = db.get(Meal, meal_id)
        assert row.name == "Jantar" and row.weight_g == 300
        # calorias recalculadas para os novos alimentos e pesos
        assert row.calories > 0 and abs(row.calories - expected_calories(db, [(6, 300.0)])) < 1e-6
        assert food_weights(db, meal_id) == {6: 300.0}

    def test_other_user_cannot_update(self, client, make_user):
        owner, other = make_user(), make_user()
        meal_id = post_meal(client, owner["id"]).json()["id"]
        assert client.patch(f"/meals/{meal_id}/{other['id']}", json=meal_payload()).status_code == 404

    def test_body_cannot_move_meal_to_another_user(self, client, make_user, db):
        owner, other = make_user(), make_user()
        meal_id = post_meal(client, owner["id"]).json()["id"]
        # user_id nao faz mais parte do corpo: tentar move-lo e recusado (422)
        assert client.patch(f"/meals/{meal_id}/{owner['id']}",
                            json={**meal_payload(), "user_id": other["id"]}).status_code == 422
        db.expunge_all()
        assert db.get(Meal, meal_id).user_id == owner["id"]

    def test_invalid_food_keeps_previous_state(self, client, make_user, db):
        user = make_user()
        meal_id = post_meal(client, user["id"]).json()["id"]
        bad = client.patch(f"/meals/{meal_id}/{user['id']}",
                           json=meal_payload(name="X", list_foods_ids=[999999], list_foods_weights=[10.0]))
        assert bad.status_code == 400
        db.expunge_all()
        assert db.get(Meal, meal_id).name == "Almoco"
        assert db.query(MealFoodAssociation).filter_by(meal_id=meal_id).count() == 2


class TestDeleteMeal:
    def test_success_and_errors(self, client, make_user, db):
        owner, other = make_user(), make_user()
        meal_id = post_meal(client, owner["id"]).json()["id"]
        assert client.delete(f"/meals/{meal_id}/{other['id']}").status_code == 404
        response = client.delete(f"/meals/{meal_id}/{owner['id']}")
        assert response.status_code == 200
        assert response.json() == {"message": "Meal deleted successfully"}
        db.expunge_all()
        assert db.get(Meal, meal_id) is None
        assert db.query(MealFoodAssociation).filter_by(meal_id=meal_id).count() == 0
        assert client.delete(f"/meals/{meal_id}/{owner['id']}").status_code == 404
        assert client.delete("/meals/abc/1").status_code == 422
