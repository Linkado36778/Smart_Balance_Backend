"""Database setup and initialization for the Smart Balance application."""

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, func, inspect, or_, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from application.models.application_models import Category, Nutrient, Food, Base

# Adiciona o diretório raiz do projeto ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

SQLALCHEMY_DATABASE_URL = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"

if not SQLALCHEMY_DATABASE_URL:
    raise RuntimeError("SQLALCHEMY_DATABASE_URL nao foi definida no arquivo .env")

os.environ.setdefault("PGCLIENTENCODING", "UTF8")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"client_encoding": "utf8"},
)

SESSEON_LOCAL = sessionmaker(autoflush=False, autocommit=False, bind=engine)

DEFAULT_CATEGORIES = [
    "Carnes e derivados",
    "Cereais",
    "Frango",
    "Frutas",
    "Hortaliças",
    "Leguminosas",
    "Ovos",
]

DEFAULT_NUTRIENTS = [
    {"name": "Proteinas", "unit": "g", "calories_per_unit": 4.0},
    {"name": "Carboidratos", "unit": "g", "calories_per_unit": 4.0},
    {"name": "Gorduras", "unit": "g", "calories_per_unit": 9.0},
    {"name": "Fibras", "unit": "g", "calories_per_unit": 0.0},
    {"name": "Sodio", "unit": "mg", "calories_per_unit": 0.0},
    {"name": "Potassio", "unit": "mg", "calories_per_unit": 0.0},
    {"name": "Calcio", "unit": "mg", "calories_per_unit": 0.0},
    {"name": "Ferro", "unit": "mg", "calories_per_unit": 0.0},
    {"name": "Vitamina C", "unit": "mg", "calories_per_unit": 0.0},
]

# Prompts curados do SigLIP para os alimentos da tabela Food (nome no banco ->
# prompt). Somente alimentos com model_label preenchido sao candidatos no
# reconhecimento; para incluir um novo alimento, adicione-o aqui ou preencha
# a coluna diretamente no banco.
#
# Alimento criado pelo usuario sem prompt recebe um gerado a partir do nome.
DEFAULT_MODEL_LABEL_TEMPLATE = "an image of {name}"


def build_model_label(name: str, model_label: str | None = None) -> str:
    """Returns the given SigLIP prompt or, when blank, one generated from the food name."""
    if model_label and model_label.strip():
        return model_label.strip()
    return DEFAULT_MODEL_LABEL_TEMPLATE.format(name=name.strip())


DEFAULT_FOOD_MODEL_LABELS = {
    "Arroz tipo 1, cozido": "an image of cooked white rice",
    "Feijão preto, cru": "an image of raw black beans",
    "Feijão preto, cozido": "an image of cooked black beans",
    "Alface crespa, crua": "an image of raw curly lettuce",
    "Fígado bovino, grelhado (bife de fígado)": "an image of grilled beef liver",
    "Ovo de galinha, frito": "an image of a fried egg",
    "Maçã Fuji, com casca, crua": "an image of a Fuji apple with peel",
    "Banana prata, crua": "an image of a raw banana",
    "Tomate salada, cru": "an image of a raw salad tomato",
    "Batata inglesa, frita": "an image of french fries",
    "Frango inteiro, cru, com pele": "an image of raw whole chicken with skin",
    "Frango inteiro, assado, com pele": "an image of roasted whole chicken with skin",
    "Peito de frango, sem pele, cru": "an image of raw skinless chicken breast",
    "Peito de frango, sem pele, cozido": "an image of cooked skinless chicken breast",
    "Peito de frango, com pele, cru": "an image of raw chicken breast with skin",
    "Peito de frango, com pele, assado": "an image of roasted chicken breast with skin",
    "Coxa de frango, com pele, crua": "an image of raw chicken thigh with skin",
    "Coxa de frango, com pele, assada": "an image of roasted chicken thigh with skin",
    "Asa de frango, com pele, crua": "an image of raw chicken wing with skin",
    "Asa de frango, com pele, assada": "an image of roasted chicken wing with skin",
    "Coração de frango, cru": "an image of raw chicken hearts",
    "Coração de frango, grelhado": "an image of grilled chicken hearts",
    "Fígado de frango, cru": "an image of raw chicken liver",
    "Fígado de frango, grelhado": "an image of grilled chicken liver",
    "Filé de frango à milanesa": "an image of breaded chicken fillet",
}

def get_db():
    """Dependency that provides a database session for each request."""
    db = SESSEON_LOCAL()
    try:
        yield db
    finally:
        db.close()

def seed_categories():
    """Seeds the Category table with default categories if they don't already exist."""

    db = SESSEON_LOCAL()
    try:
        for category_id, category_name in enumerate(DEFAULT_CATEGORIES, start=1):
            category = db.query(Category).filter(Category.id == category_id).first()
            if category:
                category.name = category_name
            else:
                cat = Category(name=category_name)
                cat.id = category_id
                db.add(cat)

        if engine.dialect.name == "postgresql":
            db.execute(
                text(
                    """
                    SELECT setval(
                        pg_get_serial_sequence('"Category"', 'id'),
                        GREATEST((SELECT COALESCE(MAX(id), 1) FROM "Category"), :value),
                        true
                    )
                    """
                ),
                {"value": len(DEFAULT_CATEGORIES)},
            )

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def seed_nutrients():
    """Seeds the Nutrient table with default nutrients if they don't already exist."""

    db = SESSEON_LOCAL()
    try:
        for nutrient_id, nutrient_data in enumerate(DEFAULT_NUTRIENTS, start=1):
            nutrient = db.query(Nutrient).filter(Nutrient.id == nutrient_id).first()
            if nutrient:
                nutrient.name = nutrient_data["name"]
                nutrient.unit = nutrient_data["unit"]
                nutrient.calories_per_unit = nutrient_data["calories_per_unit"]
            else:
                nutrient = Nutrient(
                    name=nutrient_data["name"],
                    unit=nutrient_data["unit"],
                    calories_per_unit=nutrient_data["calories_per_unit"],
                )
                nutrient.id = nutrient_id
                db.add(nutrient)

        if engine.dialect.name == "postgresql":
            db.execute(
                text(
                    """
                    SELECT setval(
                        pg_get_serial_sequence('"Nutrient"', 'id'),
                        GREATEST((SELECT COALESCE(MAX(id), 1) FROM "Nutrient"), :value),
                        true
                    )
                    """
                ),
                {"value": len(DEFAULT_NUTRIENTS)},
            )

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def ensure_nutrient_schema():
    """Ensures that the Nutrient table has the calories_per_unit column, adding it if necessary."""
    inspector = inspect(engine)
    nutrient_columns = {
        column["name"]
        for column in inspector.get_columns("Nutrient")
    }

    if "calories_per_unit" in nutrient_columns:
        return

    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            connection.execute(
                text('ALTER TABLE "Nutrient" ADD COLUMN IF NOT EXISTS calories_per_unit FLOAT DEFAULT 0')
            )
        else:
            connection.execute(
                text('ALTER TABLE "Nutrient" ADD COLUMN calories_per_unit FLOAT DEFAULT 0')
            )

def ensure_meal_food_schema():
    """Ensures that the Meal_Food table has the food_weight_g column (per-food weight).

    The column was added to MealFoodAssociation after databases were already
    created (and is missing from smart-balance.sql). create_all() never alters
    existing tables, so without it every POST /meals with saved_meal=true and
    every GET /meals fails with UndefinedColumn (HTTP 500). Rows created before
    the column existed keep NULL: their per-food weight was never stored.
    """
    inspector = inspect(engine)
    meal_food_columns = {
        column["name"]
        for column in inspector.get_columns("Meal_Food")
    }

    if "food_weight_g" in meal_food_columns:
        return

    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            connection.execute(
                text('ALTER TABLE "Meal_Food" ADD COLUMN IF NOT EXISTS food_weight_g FLOAT')
            )
        else:
            connection.execute(
                text('ALTER TABLE "Meal_Food" ADD COLUMN food_weight_g FLOAT')
            )

def ensure_pairing_schema():
    """Ensures that the Pairing table has balance_id, user_id and poll_token_hash.

    Added for the scale to learn the result of its own pairing (GET
    /pairing/{id}/status). create_all() never alters existing tables, so
    databases created before (and smart-balance.sql) need these columns.
    Existing rows keep NULL: they were never bound to a balance or user.
    """
    columns = {column["name"] for column in inspect(engine).get_columns("Pairing")}
    statements = []
    if "balance_id" not in columns:
        statements.append('ALTER TABLE "Pairing" ADD COLUMN IF NOT EXISTS balance_id INTEGER '
                          'REFERENCES "Balance"(id) ON DELETE SET NULL')
    if "user_id" not in columns:
        statements.append('ALTER TABLE "Pairing" ADD COLUMN IF NOT EXISTS user_id INTEGER '
                          'REFERENCES "User"(id) ON DELETE SET NULL')
    if "poll_token_hash" not in columns:
        statements.append('ALTER TABLE "Pairing" ADD COLUMN IF NOT EXISTS poll_token_hash VARCHAR')
    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            if engine.dialect.name != "postgresql":
                statement = statement.replace(" IF NOT EXISTS", "")
            connection.execute(text(statement))

def ensure_food_model_label_schema():
    """Ensures that Food has the model_label column (SigLIP prompt).

    create_all() never alters existing tables, so databases created before
    (and smart-balance.sql) need this column. Existing rows keep NULL; the
    curated prompts are filled by seed_food_model_labels().
    """
    columns = {column["name"] for column in inspect(engine).get_columns("Food")}
    if "model_label" in columns:
        return

    statement = 'ALTER TABLE "Food" ADD COLUMN IF NOT EXISTS model_label VARCHAR'
    if engine.dialect.name != "postgresql":
        statement = statement.replace(" IF NOT EXISTS", "")
    with engine.begin() as connection:
        connection.execute(text(statement))

def ensure_food_user_schema():
    """Ensures that Food has the user_id column (owner of a user-created food).

    NULL = global food (TACO); filled = food created by that user. Existing
    rows keep NULL, i.e. they stay global.
    """
    columns = {column["name"] for column in inspect(engine).get_columns("Food")}
    if "user_id" in columns:
        return

    statements = [
        'ALTER TABLE "Food" ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES "User"(id)',
        'CREATE INDEX IF NOT EXISTS "ix_Food_user_id" ON "Food" (user_id)',
    ]
    with engine.begin() as connection:
        for statement in statements:
            if engine.dialect.name != "postgresql":
                statement = statement.replace(" IF NOT EXISTS", "")
            connection.execute(text(statement))

# Tabelas antigas de alimentos criados pelo usuario, unificadas em Food
LEGACY_CREATED_FOOD_TABLES = ("CreatedFood_Nutrient", "CreatedFood_Allergen", "CreatedFood")

def migrate_created_foods_into_food() -> dict[int, int]:
    """Moves the legacy CreatedFood tables into Food (user_id filled).

    Each created food becomes a Food row owned by its user, inserted AFTER
    every existing food (so user foods come last in the table), keeping the
    original creation order. Its nutrients and allergens are copied to
    Food_Nutrient / Allergen_Food and the legacy tables are dropped. Everything
    runs in a single transaction: on any error nothing is changed.

    Returns the id mapping {old CreatedFood.id: new Food.id}.
    """
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "CreatedFood" not in tables:
        return {}

    created_columns = {column["name"] for column in inspector.get_columns("CreatedFood")}
    label_column = "model_label" if "model_label" in created_columns else "NULL"
    id_mapping: dict[int, int] = {}

    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            # garante que os novos ids venham depois de todos os alimentos atuais
            connection.execute(text(
                """
                SELECT setval(
                    pg_get_serial_sequence('"Food"', 'id'),
                    (SELECT COALESCE(MAX(id), 1) FROM "Food"),
                    (SELECT COUNT(*) > 0 FROM "Food")
                )
                """
            ))

        created_foods = connection.execute(text(
            f'SELECT id, user_id, name, category_id, brand_id, image_url, description, '
            f'{label_column} AS model_label FROM "CreatedFood" ORDER BY id'
        )).mappings().all()

        for created_food in created_foods:
            new_id = connection.execute(
                text(
                    'INSERT INTO "Food" (name, category_id, brand_id, image_url, description, model_label, user_id) '
                    'VALUES (:name, :category_id, :brand_id, :image_url, :description, :model_label, :user_id) '
                    'RETURNING id'
                ),
                {
                    "name": created_food["name"],
                    "category_id": created_food["category_id"],
                    "brand_id": created_food["brand_id"],
                    "image_url": created_food["image_url"],
                    "description": created_food["description"],
                    "model_label": build_model_label(created_food["name"], created_food["model_label"]),
                    "user_id": created_food["user_id"],
                },
            ).scalar_one()
            id_mapping[created_food["id"]] = new_id

            params = {"new_id": new_id, "old_id": created_food["id"]}
            if "CreatedFood_Nutrient" in tables:
                connection.execute(text(
                    'INSERT INTO "Food_Nutrient" (food_id, nutrient_id, amount) '
                    'SELECT :new_id, nutrient_id, amount FROM "CreatedFood_Nutrient" WHERE created_food_id = :old_id'
                ), params)
            if "CreatedFood_Allergen" in tables:
                connection.execute(text(
                    'INSERT INTO "Allergen_Food" (food_id, allergen_id) '
                    'SELECT :new_id, allergen_id FROM "CreatedFood_Allergen" WHERE created_food_id = :old_id'
                ), params)

        for table in LEGACY_CREATED_FOOD_TABLES:
            connection.execute(text(f'DROP TABLE IF EXISTS "{table}"'))

    print(f"CreatedFood migrado para Food (id antigo -> id novo): {id_mapping}")
    return id_mapping

def seed_food_model_labels():
    """Fills Food.model_label: curated SigLIP prompts for global foods and a
    prompt generated from the name for user-created foods.

    Only rows whose model_label is still NULL/blank are filled, so prompts
    edited directly in the database are never overwritten. Foods missing from
    the database (e.g. before populate_db.py runs) are skipped.
    """
    db = SESSEON_LOCAL()
    try:
        foods = (
            db.query(Food)
            .filter(Food.user_id.is_(None))
            .filter(Food.name.in_(DEFAULT_FOOD_MODEL_LABELS.keys()))
            .filter(Food.model_label.is_(None))
            .all()
        )
        for food in foods:
            food.model_label = DEFAULT_FOOD_MODEL_LABELS[food.name]

        user_foods = (
            db.query(Food)
            .filter(Food.user_id.isnot(None))
            .filter(or_(Food.model_label.is_(None), func.trim(Food.model_label) == ""))
            .all()
        )
        for user_food in user_foods:
            user_food.model_label = build_model_label(user_food.name)

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

DIET_GOAL_COLUMNS = ("kcal_goal", "fat_goal", "carb_goal", "protein_goal")

def ensure_diet_schema():
    """Ensures that Diet has the nutritional goal columns of the current model.

    Databases created from smart-balance.sql have the legacy column
    goal VARCHAR NOT NULL and none of kcal_goal/fat_goal/carb_goal/protein_goal.
    create_all() never alters existing tables, so every POST /create_diet
    failed with UndefinedColumn (HTTP 500). The missing columns are added
    (existing rows keep NULL) and the legacy goal column is kept with its data,
    only becoming nullable, because the model no longer fills it.
    """
    columns = {column["name"]: column for column in inspect(engine).get_columns("Diet")}
    statements = [
        f'ALTER TABLE "Diet" ADD COLUMN IF NOT EXISTS {name} FLOAT'
        for name in DIET_GOAL_COLUMNS
        if name not in columns
    ]
    if "goal" in columns and not columns["goal"]["nullable"] and engine.dialect.name == "postgresql":
        statements.append('ALTER TABLE "Diet" ALTER COLUMN goal DROP NOT NULL')
    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            if engine.dialect.name != "postgresql":
                statement = statement.replace(" IF NOT EXISTS", "")
            connection.execute(text(statement))

def ensure_full_name_schema():
    """Ensures that User and Nutricionist have the full_name column.

    Neither table had any name column (no first_name/last_name/name), so there
    is nothing to derive it from: existing rows keep NULL until the name is
    informed through the create/update endpoints.
    """
    for table in ("User", "Nutricionist"):
        columns = {column["name"] for column in inspect(engine).get_columns(table)}
        if "full_name" in columns:
            continue
        statement = f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS full_name VARCHAR'
        if engine.dialect.name != "postgresql":
            statement = statement.replace(" IF NOT EXISTS", "")
        with engine.begin() as connection:
            connection.execute(text(statement))

def ensure_food_nutrient_association_schema():
    """"Ensures that the Food_Nutrient association table has a composite primary key on (nutrient_id, food_id), adding it if necessary."""
    inspector = inspect(engine)
    primary_key = inspector.get_pk_constraint("Food_Nutrient")
    primary_key_columns = set(primary_key.get("constrained_columns") or [])

    if primary_key_columns == {"nutrient_id", "food_id"}:
        return

    if engine.dialect.name != "postgresql":
        return

    with engine.begin() as connection:
        connection.execute(text('ALTER TABLE "Food_Nutrient" DROP CONSTRAINT IF EXISTS "Food_Nutrient_pkey"'))
        connection.execute(text('ALTER TABLE "Food_Nutrient" ALTER COLUMN "food_id" SET NOT NULL'))
        connection.execute(text('ALTER TABLE "Food_Nutrient" ADD PRIMARY KEY ("nutrient_id", "food_id")'))

def initialize_database():
    """Initializes the database by creating tables, ensuring schema consistency, and seeding default data."""
    Base.metadata.create_all(bind=engine)
    ensure_nutrient_schema()
    ensure_food_nutrient_association_schema()
    ensure_meal_food_schema()
    ensure_pairing_schema()
    ensure_food_model_label_schema()
    ensure_food_user_schema()
    ensure_diet_schema()
    ensure_full_name_schema()
    migrate_created_foods_into_food()
    seed_categories()
    seed_nutrients()
    seed_food_model_labels()

def create_table():
    """Creates the database tables based on the defined models."""
    print(f"Modelos registrados no Base.metadata: {len(Base.metadata.tables)}")
    for table_name in Base.metadata.tables.keys():
        print(f"- {table_name}")

    print(f"\nCriando {len(Base.metadata.tables)} tabelas...")
    initialize_database()
    print("Tabelas criadas!")

# Chama create_table() apenas quando o script é executado diretamente
if __name__ == "__main__":
    create_table()
    print("Banco de dados criado com sucesso!")
