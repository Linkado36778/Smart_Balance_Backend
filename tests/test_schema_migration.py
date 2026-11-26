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


def test_adds_missing_model_label_column_and_seeds_prompts(client):
    from shared.database import DEFAULT_FOOD_MODEL_LABELS, ensure_food_model_label_schema, seed_food_model_labels

    def food_columns():
        return {column["name"] for column in inspect(engine).get_columns("Food")}

    with engine.begin() as connection:
        connection.execute(text('ALTER TABLE "Food" DROP COLUMN IF EXISTS model_label'))
    assert "model_label" not in food_columns()

    ensure_food_model_label_schema()
    ensure_food_model_label_schema()  # idempotente
    assert "model_label" in food_columns()

    with engine.begin() as connection:
        connection.execute(text('UPDATE "Food" SET model_label = :label WHERE name = :name'),
                           {"label": "an image of custom rice", "name": "Arroz tipo 1, cozido"})
    seed_food_model_labels()

    with engine.connect() as connection:
        rows = dict(connection.execute(text(
            'SELECT name, model_label FROM "Food" WHERE model_label IS NOT NULL AND user_id IS NULL'
        )).all())
    # prompt editado no banco e preservado; os demais sao semeados
    assert rows == {**DEFAULT_FOOD_MODEL_LABELS, "Arroz tipo 1, cozido": "an image of custom rice"}

    with engine.begin() as connection:
        connection.execute(text('UPDATE "Food" SET model_label = :label WHERE name = :name'),
                           {"label": DEFAULT_FOOD_MODEL_LABELS["Arroz tipo 1, cozido"], "name": "Arroz tipo 1, cozido"})


def test_seed_fills_blank_user_food_model_labels(client, make_user):
    from shared.database import seed_food_model_labels

    user = make_user()
    with engine.begin() as connection:
        for name, label in (("Antigo sem prompt", None), ("Antigo vazio", " "), ("Antigo com prompt", "an image of x")):
            connection.execute(
                text('INSERT INTO "Food" (user_id, name, model_label) VALUES (:user_id, :name, :label)'),
                {"user_id": user["id"], "name": name, "label": label},
            )

    seed_food_model_labels()

    with engine.connect() as connection:
        rows = dict(connection.execute(
            text('SELECT name, model_label FROM "Food" WHERE user_id = :user_id'), {"user_id": user["id"]}
        ).all())
    assert rows == {
        "Antigo sem prompt": "an image of Antigo sem prompt",
        "Antigo vazio": "an image of Antigo vazio",
        "Antigo com prompt": "an image of x",
    }


LEGACY_CREATED_FOOD_DDL = (
    'CREATE TABLE "CreatedFood" (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES "User"(id), '
    'name VARCHAR NOT NULL, category_id INTEGER REFERENCES "Category"(id), brand_id INTEGER REFERENCES "Brand"(id), '
    'image_url VARCHAR, description VARCHAR, model_label VARCHAR)',
    'CREATE TABLE "CreatedFood_Nutrient" (created_food_id INTEGER REFERENCES "CreatedFood"(id) ON DELETE CASCADE, '
    'nutrient_id INTEGER REFERENCES "Nutrient"(id) ON DELETE CASCADE, amount FLOAT NOT NULL, '
    'PRIMARY KEY (created_food_id, nutrient_id))',
    'CREATE TABLE "CreatedFood_Allergen" (created_food_id INTEGER REFERENCES "CreatedFood"(id) ON DELETE CASCADE, '
    'allergen_id INTEGER REFERENCES "Allergen"(id) ON DELETE CASCADE, PRIMARY KEY (created_food_id, allergen_id))',
)


def test_migrates_legacy_created_foods_into_food(client, make_user, db):
    """Bancos antigos: CreatedFood* vira Food (user_id preenchido), depois de todos os alimentos."""
    from application.models.application_models import AllergenFoodAssociation, Food, FoodNutrientAssociation
    from shared.database import ensure_food_user_schema, migrate_created_foods_into_food

    user = make_user()
    with engine.begin() as connection:
        for ddl in LEGACY_CREATED_FOOD_DDL:
            connection.execute(text(ddl))
        for name, label in (("Pizza legado", "an image of pizza"), ("Bolo legado", None)):
            connection.execute(
                text('INSERT INTO "CreatedFood" (user_id, name, category_id, model_label) VALUES (:u, :n, 1, :l)'),
                {"u": user["id"], "n": name, "l": label},
            )
        connection.execute(text(
            'INSERT INTO "CreatedFood_Nutrient" SELECT id, 1, 12.5 FROM "CreatedFood" WHERE name = \'Pizza legado\''
        ))
        connection.execute(text(
            'INSERT INTO "CreatedFood_Allergen" SELECT id, 1 FROM "CreatedFood" WHERE name = \'Pizza legado\''
        ))
        max_food_id = connection.execute(text('SELECT MAX(id) FROM "Food"')).scalar()

    ensure_food_user_schema()
    mapping = migrate_created_foods_into_food()
    assert migrate_created_foods_into_food() == {}  # idempotente: tabelas antigas ja removidas

    tables = set(inspect(engine).get_table_names())
    assert not {"CreatedFood", "CreatedFood_Nutrient", "CreatedFood_Allergen"} & tables

    db.expire_all()
    migrated = db.query(Food).filter(Food.user_id == user["id"]).order_by(Food.id).all()
    assert [(f.name, f.model_label, f.category_id) for f in migrated] == [
        ("Pizza legado", "an image of pizza", 1),
        ("Bolo legado", "an image of Bolo legado", 1),
    ]
    assert sorted(mapping.values()) == [f.id for f in migrated]
    assert all(f.id > max_food_id for f in migrated)  # por ultimo na tabela Food

    pizza = migrated[0]
    assert {a.nutrient_id: a.amount for a in db.query(FoodNutrientAssociation).filter_by(food_id=pizza.id)} == {1: 12.5}
    assert [a.allergen_id for a in db.query(AllergenFoodAssociation).filter_by(food_id=pizza.id)] == [1]

    # o alimento migrado ja pode ser usado numa refeicao
    meal = client.post("/meals", params={"user_id": user["id"]}, json={
        "name": "Jantar", "consumed_at": "2026-11-21 20:00:00",
        "list_foods_ids": [pizza.id], "list_foods_weights": [200], "saved_meal": True,
    })
    assert meal.status_code == 200, meal.text


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
