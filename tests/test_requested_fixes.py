"""Correcoes de 2026-11-25: dieta (500), pareamento no usuario, full_name e
alimentos do usuario em refeicoes.
"""

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import inspect, text

from application.models.application_models import (
    Diet,
    DietFoodAssociation,
    Food,
    FoodNutrientAssociation,
    MealFoodAssociation,
    Nutrient,
    Pairing,
    User,
    UserBalanceAssociation,
)
from conftest import TEST_PASSWORD, unique_email
from shared.database import engine, ensure_diet_schema, ensure_full_name_schema
from test_balance_pairing import generate_token, register_balance


def create_user_food(client, user_id, nutrients=None, **overrides):
    payload = {
        "name": f"Comida-{uuid.uuid4().hex[:8]}",
        "nutrients": nutrients if nutrients is not None else [{"id": 1, "amount": 20.0}, {"id": 3, "amount": 5.0}],
    }
    payload.update(overrides)
    response = client.post("/foods", params={"user_id": user_id}, json=payload)
    assert response.status_code == 200, response.text
    foods = client.get("/foods/created", params={"user_id": user_id}).json()
    return next(f for f in foods if f["name"] == payload["name"])["id"]


def pair(client, user_id, balance_id):
    _, token = generate_token(client, balance_id)
    response = client.post("/pair-scale", params={"user_id": user_id, "token": token})
    assert response.status_code == 200, response.text


def diet_columns():
    return {c["name"]: c for c in inspect(engine).get_columns("Diet")}


# ------------------------------------------------------------------ Dietas

class TestDiet:
    def test_create_list_with_goals_and_user_food(self, client, make_user, make_nutricionist, db):
        user, nutri = make_user(), make_nutricionist()
        own_food = create_user_food(client, user["id"])
        response = client.post(f"/create_diet/{nutri['id']}/{user['id']}", json={
            "name": "  Hipertrofia  ", "user_id": user["id"], "nutricionist_id": nutri["id"],
            "list_foods_ids": [1, own_food, 1], "kcal_goal": 2500, "protein_goal": 160,
        })
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        # campos antigos preservados
        assert {"diet_id", "diet_name", "user_id", "nutricionist_id"} <= set(data)
        assert data["diet_name"] == "Hipertrofia"
        assert data["list_foods_ids"] == [1, own_food]  # id repetido nao gera 409
        assert data["kcal_goal"] == 2500 and data["protein_goal"] == 160

        listing = client.get(f"/list_diets_by_user/{user['id']}")
        assert listing.status_code == 200
        diet = listing.json()[0]
        assert diet["id"] == data["diet_id"] and diet["name"] == "Hipertrofia"
        assert diet["kcal_goal"] == 2500 and diet["fat_goal"] is None
        assert diet["list_foods_ids"] == sorted([1, own_food])

    def test_invalid_data(self, client, make_user, make_nutricionist, db):
        user, nutri = make_user(), make_nutricionist()
        base = {"name": "D", "user_id": user["id"], "nutricionist_id": nutri["id"]}
        assert client.post(f"/create_diet/{nutri['id']}/999999", json={**base, "user_id": 999999}).status_code == 404
        assert client.post(f"/create_diet/999999/{user['id']}", json={**base, "nutricionist_id": 999999}).status_code == 404
        assert client.post(f"/create_diet/{nutri['id']}/{user['id']}", json={**base, "name": "  "}).status_code == 400
        # alimento criado por outro usuario nao pode entrar na dieta
        other_food = create_user_food(client, make_user()["id"])
        bad = client.post(f"/create_diet/{nutri['id']}/{user['id']}", json={**base, "list_foods_ids": [other_food]})
        assert bad.status_code == 400
        assert db.query(Diet).filter_by(user_id=user["id"]).count() == 0

    def test_legacy_dump_schema_is_migrated(self, client, make_user, make_nutricionist, db):
        """Schema do smart-balance.sql: goal NOT NULL e sem as metas -> antes 500 (UndefinedColumn)."""
        user, nutri = make_user(), make_nutricionist()
        with engine.begin() as connection:
            for column in ("kcal_goal", "fat_goal", "carb_goal", "protein_goal"):
                connection.execute(text(f'ALTER TABLE "Diet" DROP COLUMN {column}'))
            connection.execute(text('ALTER TABLE "Diet" ADD COLUMN goal VARCHAR'))
            connection.execute(text(
                'INSERT INTO "Diet" (name, user_id, nutricionist_id, goal) VALUES (\'Legada\', :u, :n, \'Ganho de massa\')'
            ), {"u": user["id"], "n": nutri["id"]})
            connection.execute(text('UPDATE "Diet" SET goal = \'-\' WHERE goal IS NULL'))
            connection.execute(text('ALTER TABLE "Diet" ALTER COLUMN goal SET NOT NULL'))

        try:
            ensure_diet_schema()
            ensure_diet_schema()  # idempotente
            columns = diet_columns()
            assert {"kcal_goal", "fat_goal", "carb_goal", "protein_goal"} <= set(columns)
            assert columns["goal"]["nullable"] is True

            response = client.post(f"/create_diet/{nutri['id']}/{user['id']}", json={
                "name": "Nova", "user_id": user["id"], "nutricionist_id": nutri["id"], "list_foods_ids": [2], "kcal_goal": 1800,
            })
            assert response.status_code == 200, response.text
            with engine.connect() as connection:
                legacy = connection.execute(text('SELECT goal FROM "Diet" WHERE name = \'Legada\'')).scalar_one()
            assert legacy == "Ganho de massa"  # dado antigo preservado
            assert [d["name"] for d in client.get(f"/list_diets_by_user/{user['id']}").json()] == ["Legada", "Nova"]
        finally:
            with engine.begin() as connection:
                connection.execute(text('ALTER TABLE "Diet" DROP COLUMN IF EXISTS goal'))


# ------------------------------------------------------ Usuario e pareamento

class TestUserPairing:
    def test_user_without_pairing(self, client, make_user):
        user = make_user()
        data = client.get(f"/user/{user['id']}").json()["data"]
        assert data["has_paired_scale"] is False and data["balance_id"] is None

        link = client.get(f"/user/{user['id']}/balance")
        assert link.status_code == 200
        assert link.json()["data"] == {
            "user_id": user["id"], "has_paired_scale": False, "balance_id": None,
            "balance_name": None, "balance_ids": [],
        }
        assert client.get("/user/999999/balance").status_code == 404

    def test_user_with_pairing_and_unpairing(self, client, make_user, db):
        user = make_user()
        first, second = register_balance(client, "Cozinha"), register_balance(client, "Escritorio")
        pair(client, user["id"], first["id"])
        pair(client, user["id"], second["id"])

        data = client.get(f"/user/{user['id']}").json()["data"]
        assert data["has_paired_scale"] is True and data["balance_id"] == second["id"]  # pareamento mais recente

        link = client.get(f"/user/{user['id']}/balance").json()["data"]
        assert link["balance_id"] == second["id"] and link["balance_name"] == "Escritorio"
        assert link["balance_ids"] == [second["id"], first["id"]]

        login = client.get(f"/login_User/{user['email']}/{TEST_PASSWORD}").json()
        assert login["has_paired_scale"] is True and login["balance_id"] == second["id"]

        # vinculo removido: volta para o anterior ainda ativo e depois para nenhum
        db.query(UserBalanceAssociation).filter_by(user_id=user["id"], balance_id=second["id"]).delete()
        db.commit()
        assert client.get(f"/user/{user['id']}").json()["data"]["balance_id"] == first["id"]
        db.query(UserBalanceAssociation).filter_by(user_id=user["id"]).delete()
        db.commit()
        data = client.get(f"/user/{user['id']}").json()["data"]
        assert data["has_paired_scale"] is False and data["balance_id"] is None

    def test_legacy_link_without_pairing_record(self, client, make_user, db):
        """User_Balance antigo, sem Pairing (e duplicado, bancos sem PK) nao quebra."""
        user = make_user()
        balance = register_balance(client)
        db.add(UserBalanceAssociation(user_id=user["id"], balance_id=balance["id"]))
        db.commit()
        data = client.get(f"/user/{user['id']}/balance").json()["data"]
        assert data["has_paired_scale"] is True and data["balance_ids"] == [balance["id"]]


# ------------------------------------------------------------ full_name

class TestFullName:
    def test_user_full_name(self, client, make_user, db):
        user = make_user(full_name="  João   da Silva ")
        assert user["full_name"] == "João da Silva"
        assert client.get(f"/user/{user['id']}").json()["data"]["full_name"] == "João da Silva"

        body = {"email": user["email"], "birthdate": "1990-05-17", "weight_kg": 70, "height_m": 1.7,
                "sex": "M", "password": TEST_PASSWORD, "is_active": True}
        # cliente antigo, sem full_name: o nome e mantido
        assert client.patch(f"/update_User/{user['id']}", json=body).json()["data"]["full_name"] == "João da Silva"
        updated = client.patch(f"/update_User/{user['id']}", json={**body, "full_name": "João Souza"})
        assert updated.json()["data"]["full_name"] == "João Souza"
        assert client.patch(f"/update_User/{user['id']}", json={**body, "full_name": "x" * 151}).status_code == 422

    def test_user_without_full_name_still_works(self, client, make_user):
        """O app atual nao envia full_name."""
        user = make_user()
        assert user["full_name"] is None
        assert client.get(f"/user/{user['id']}").json()["data"]["full_name"] is None

    def test_nutricionist_full_name(self, client, make_nutricionist, db):
        nutri = make_nutricionist(full_name="Maria Nutri")
        assert client.get(f"/get_Nutricionist/{nutri['id']}").json()["full_name"] == "Maria Nutri"
        assert client.get(f"/login_Nutricionist/{nutri['email']}/{TEST_PASSWORD}").json()["full_name"] == "Maria Nutri"
        body = {"email": nutri["email"], "password": TEST_PASSWORD, "phone": "1", "crn": nutri["crn"]}
        assert client.patch(f"/update_Nutricionist/{nutri['id']}", json=body).json()["data"]["full_name"] == "Maria Nutri"
        assert client.patch(f"/update_Nutricionist/{nutri['id']}", json={**body, "full_name": "Maria S."}).json()["data"]["full_name"] == "Maria S."

    def test_patients_list_and_detail(self, client, make_user, make_nutricionist):
        nutri = make_nutricionist()
        patient = make_user(full_name="Paciente Um")
        outsider = make_user(full_name="Outro")
        assert client.post("/link_user_nutricionist", params={"user_id": patient["id"], "nutricionist_CRN": nutri["crn"]}).status_code == 200

        listing = client.get(f"/list_user_data_by_nutricionist/{nutri['id']}").json()
        assert [(p["id"], p["user_id"], p["full_name"]) for p in listing] == [(patient["id"], patient["id"], "Paciente Um")]
        assert all("password" not in p and "has_paired_scale" in p for p in listing)

        detail = client.get(f"/nutricionist/{nutri['id']}/patients/{patient['id']}")
        assert detail.status_code == 200
        assert detail.json()["data"]["full_name"] == "Paciente Um" and detail.json()["data"]["user_id"] == patient["id"]
        assert client.get(f"/nutricionist/{nutri['id']}/patients/{outsider['id']}").status_code == 404
        assert client.get(f"/nutricionist/999999/patients/{patient['id']}").status_code == 404

    def test_full_name_migration(self, client):
        for table in ("User", "Nutricionist"):
            with engine.begin() as connection:
                connection.execute(text(f'ALTER TABLE "{table}" DROP COLUMN full_name'))
        ensure_full_name_schema()
        ensure_full_name_schema()  # idempotente
        for table in ("User", "Nutricionist"):
            assert "full_name" in {c["name"] for c in inspect(engine).get_columns(table)}


# ---------------------------------------------- Refeicoes com as duas origens

def expected(db, foods_and_weights):
    calories, nutrients = 0.0, {}
    for food_id, weight in foods_and_weights:
        for assoc, nutrient in (
            db.query(FoodNutrientAssociation, Nutrient)
            .join(Nutrient, Nutrient.id == FoodNutrientAssociation.nutrient_id)
            .filter(FoodNutrientAssociation.food_id == food_id)
        ):
            amount = assoc.amount * weight / 100.0
            nutrients[nutrient.name] = nutrients.get(nutrient.name, 0.0) + amount
            calories += amount * (nutrient.calories_per_unit or 0.0)
    return calories, nutrients


class TestMealsWithUserFoods:
    def post(self, client, user_id, ids, weights):
        return client.post("/meals", params={"user_id": user_id}, json={
            "name": "Almoco", "consumed_at": "2026-11-25 12:00:00",
            "list_foods_ids": ids, "list_foods_weights": weights, "saved_meal": True,
        })

    @pytest.mark.parametrize("kind", ["standard", "custom", "mixed"])
    def test_meal_totals_and_items(self, client, make_user, db, kind):
        from application.controller.food_controller import PostCreateMealBodyRequest, calculate_meal_totals

        user = make_user()
        own = create_user_food(client, user["id"], nutrients=[{"id": 1, "amount": 25.0}, {"id": 2, "amount": 40.0}, {"id": 3, "amount": 8.0}])
        ids, weights = {"standard": ([1], [150.0]), "custom": ([own], [80.0]), "mixed": ([1, own], [150.0, 80.0])}[kind]

        calories, nutrients = expected(db, zip(ids, weights))
        assert calories > 0

        # totais por nutriente calculados para as duas origens
        meal_body = PostCreateMealBodyRequest(name="x", consumed_at=datetime(2026, 11, 25, 12), list_foods_ids=ids, list_foods_weights=weights)
        _, total_calories, total_nutrients = calculate_meal_totals(db, meal_body, user["id"])
        assert abs(total_calories - calories) < 1e-6
        assert total_nutrients.keys() == nutrients.keys()
        assert all(abs(total_nutrients[k] - v) < 1e-6 for k, v in nutrients.items())

        response = self.post(client, user["id"], ids, weights)
        assert response.status_code == 200, response.text
        body = response.json()
        assert abs(body["calories"] - calories) < 1e-6 and body["weight_g"] == sum(weights)
        assert {a.food_id: a.food_weight_g for a in db.query(MealFoodAssociation).filter_by(meal_id=body["id"])} == dict(zip(ids, weights))

        listed = next(m for m in client.get("/meals", params={"user_id": user["id"]}).json() if m["id"] == body["id"])
        assert sorted((f["id"], f["weight_g"], f["created_by_user"]) for f in listed["foods"]) == sorted(
            (food_id, weight, food_id == own) for food_id, weight in zip(ids, weights)
        )

    def test_other_users_food_is_rejected(self, client, make_user, db):
        owner, intruder = make_user(), make_user()
        own = create_user_food(client, owner["id"])
        response = self.post(client, intruder["id"], [1, own], [100.0, 50.0])
        assert response.status_code == 400
        assert f"Food_id: {own}" in response.text
