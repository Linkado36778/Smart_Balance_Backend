"""Migracao de schema em bancos ja existentes (shared.database.ensure_meal_food_schema).

Meal_Food.food_weight_g foi adicionada ao modelo depois que os bancos foram
criados (o dump smart-balance.sql nao a tem) e create_all() nao altera tabelas
existentes. Sem a migracao, POST /meals (saved_meal=true) e GET /meals davam 500.
"""

from sqlalchemy import inspect, text

from shared.database import engine, ensure_meal_food_schema


def meal_food_columns():
    return {column["name"] for column in inspect(engine).get_columns("Meal_Food")}


def test_adds_missing_food_weight_column_and_meals_work(client, make_user):
    with engine.begin() as connection:
        connection.execute(text('ALTER TABLE "Meal_Food" DROP COLUMN IF EXISTS food_weight_g'))
    assert "food_weight_g" not in meal_food_columns()

    ensure_meal_food_schema()
    assert "food_weight_g" in meal_food_columns()

    ensure_meal_food_schema()  # idempotente
    assert "food_weight_g" in meal_food_columns()

    user = make_user()
    created = client.post("/meals", params={"user_id": user["id"]}, json={
        "name": "Almoco", "consumed_at": "2026-11-21 12:00:00",
        "list_foods_ids": [1], "list_foods_weights": [120], "saved_meal": True,
    })
    assert created.status_code == 200, created.text
    listed = client.get("/meals", params={"user_id": user["id"]})
    assert listed.status_code == 200, listed.text
    assert listed.json()[0]["foods"][0]["weight_g"] == 120


def test_adds_missing_pairing_columns_and_status_works(client):
    from shared.database import ensure_pairing_schema

    def pairing_columns():
        return {column["name"] for column in inspect(engine).get_columns("Pairing")}

    with engine.begin() as connection:
        for column in ("balance_id", "user_id", "poll_token_hash"):
            connection.execute(text(f'ALTER TABLE "Pairing" DROP COLUMN IF EXISTS {column}'))
    assert not {"balance_id", "user_id", "poll_token_hash"} & pairing_columns()

    ensure_pairing_schema()
    ensure_pairing_schema()  # idempotente
    assert {"balance_id", "user_id", "poll_token_hash"} <= pairing_columns()

    data = client.post("/generate_qr_code/").json()["data"]
    response = client.get(f"/pairing/{data['pairing_id']}/status", headers={"X-Pairing-Token": data["poll_token"]})
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "pending"
