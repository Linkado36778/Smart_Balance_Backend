from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
import os
import sys
from dotenv import load_dotenv
from pathlib import Path

# Adiciona o diretório raiz do projeto ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

SQLALCHEMY_DATABASE_URL = os.getenv("SQLALCHEMY_DATABASE_URL")

if not SQLALCHEMY_DATABASE_URL:
    raise RuntimeError("SQLALCHEMY_DATABASE_URL nao foi definida no arquivo .env")

os.environ.setdefault("PGCLIENTENCODING", "UTF8")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"client_encoding": "utf8"},
)

SessionLocal = sessionmaker(autoflush=False, autocommit=False, bind=engine)
Base = declarative_base()

DEFAULT_CATEGORIES = [
    "Cereais",
    "Legumes",
    "Proteinas",
    "Laticinios",
    "Frutas",
    "Verduras",
    "Gorduras",
    "Bebidas",
    "Outros",
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
    {"name": "Vitamina D", "unit": "ug", "calories_per_unit": 0.0},
]

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def seed_categories():
    from application.models.application_models import Category

    db = SessionLocal()
    try:
        for category_id, category_name in enumerate(DEFAULT_CATEGORIES, start=1):
            category = db.query(Category).filter(Category.category_id == category_id).first()
            if category:
                category.category_name = category_name
            else:
                db.add(Category(category_id=category_id, category_name=category_name))

        if engine.dialect.name == "postgresql":
            db.execute(
                text("SELECT setval(pg_get_serial_sequence('\"Category\"', 'category_id'), :value, true)"),
                {"value": len(DEFAULT_CATEGORIES)},
            )

        db.commit()
    finally:
        db.close()

def seed_nutrients():
    from application.models.application_models import Nutrient

    db = SessionLocal()
    try:
        for nutrient_id, nutrient_data in enumerate(DEFAULT_NUTRIENTS, start=1):
            nutrient = db.query(Nutrient).filter(Nutrient.nutrient_id == nutrient_id).first()
            if nutrient:
                nutrient.nutrient_name = nutrient_data["name"]
                nutrient.nutrient_unit = nutrient_data["unit"]
                nutrient.nutrient_calories_per_unit = nutrient_data["calories_per_unit"]
            else:
                db.add(
                    Nutrient(
                        nutrient_id=nutrient_id,
                        nutrient_name=nutrient_data["name"],
                        nutrient_unit=nutrient_data["unit"],
                        nutrient_calories_per_unit=nutrient_data["calories_per_unit"],
                    )
                )

        if engine.dialect.name == "postgresql":
            db.execute(
                text("SELECT setval(pg_get_serial_sequence('\"Nutrient\"', 'nutrient_id'), :value, true)"),
                {"value": len(DEFAULT_NUTRIENTS)},
            )

        db.commit()
    finally:
        db.close()

def ensure_nutrient_schema():
    inspector = inspect(engine)
    nutrient_columns = {
        column["name"]
        for column in inspector.get_columns("Nutrient")
    }

    if "nutrient_calories_per_unit" in nutrient_columns:
        return

    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            connection.execute(
                text('ALTER TABLE "Nutrient" ADD COLUMN IF NOT EXISTS nutrient_calories_per_unit FLOAT DEFAULT 0')
            )
        else:
            connection.execute(
                text('ALTER TABLE "Nutrient" ADD COLUMN nutrient_calories_per_unit FLOAT DEFAULT 0')
            )

def ensure_food_nutrient_association_schema():
    inspector = inspect(engine)
    primary_key = inspector.get_pk_constraint("Food_Nutrient")
    primary_key_columns = set(primary_key.get("constrained_columns") or [])

    if primary_key_columns == {"nutrient_id_FK", "food_id_FK1"}:
        return

    if engine.dialect.name != "postgresql":
        return

    with engine.begin() as connection:
        connection.execute(text('ALTER TABLE "Food_Nutrient" DROP CONSTRAINT IF EXISTS "Food_Nutrient_pkey"'))
        connection.execute(text('ALTER TABLE "Food_Nutrient" ALTER COLUMN "food_id_FK1" SET NOT NULL'))
        connection.execute(text('ALTER TABLE "Food_Nutrient" ADD PRIMARY KEY ("nutrient_id_FK", "food_id_FK1")'))

def initialize_database():
    Base.metadata.create_all(bind=engine)
    ensure_nutrient_schema()
    ensure_food_nutrient_association_schema()
    seed_categories()
    seed_nutrients()

def create_table():
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
