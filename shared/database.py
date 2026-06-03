from sqlalchemy import create_engine
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

# Importa os modelos para registrar as tabelas no Base metadata
import application.models.application_models

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_table():
    print(f"Modelos registrados no Base.metadata: {len(Base.metadata.tables)}")
    for table_name in Base.metadata.tables.keys():
        print(f"- {table_name}")

    print(f"\nCriando {len(Base.metadata.tables)} tabelas...")
    Base.metadata.create_all(bind=engine)
    print("Tabelas criadas!")

# Chama create_table() apenas quando o script é executado diretamente
if __name__ == "__main__":
    create_table()
    print("Banco de dados criado com sucesso!")
