"""Fixtures compartilhadas da suite de testes HTTP/integracao do Smart Balance.

Isolamento:
- Usa um banco PostgreSQL DEDICADO (padrao ``Smart-Balance-test``) no mesmo
  servidor configurado no ``.env``. O banco de desenvolvimento/producao nunca
  e tocado: o nome do banco de testes e obrigado a terminar em ``test``.
- O schema e recriado do zero a cada sessao (drop_all/create_all) e semeado
  apenas com dados de REFERENCIA (alimentos, nutrientes, alergenos, categorias,
  marcas) extraidos do dump ``smart-balance.sql``. Nenhum usuario real e
  importado; usuarios/nutricionistas sao criados com dados ficticios.
- O diretorio de trabalho e trocado para uma pasta temporaria, porque o codigo
  grava arquivos com caminhos relativos (``static/images``, ``tmp/``,
  ``output/``) e o shutdown da API apaga ``tmp/`` e ``output/``.
"""

import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest
from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DUMP_PATH = PROJECT_ROOT / "smart-balance.sql"

# ---------------------------------------------------------------------------
# Configuracao do ambiente ANTES de importar a aplicacao
# ---------------------------------------------------------------------------

_env = dotenv_values(PROJECT_ROOT / ".env")
for _key, _value in _env.items():
    if _value is not None:
        os.environ.setdefault(_key, _value)

TEST_DB_NAME = os.environ.get("TEST_POSTGRES_DB", "Smart-Balance-test")
if not TEST_DB_NAME.lower().endswith("test"):
    raise RuntimeError(
        f"TEST_POSTGRES_DB='{TEST_DB_NAME}' recusado: o nome do banco de testes deve terminar em 'test'."
    )
os.environ["POSTGRES_DB"] = TEST_DB_NAME
os.environ["APP_ENV"] = "test"
os.environ.setdefault("HF_HUB_OFFLINE", "1")  # usa apenas o modelo ja em cache

WORK_DIR = Path(tempfile.mkdtemp(prefix="smart_balance_tests_"))
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, text  # noqa: E402


def _ensure_test_database():
    admin_url = (
        f"postgresql://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
        f"@{os.environ['POSTGRES_HOST']}:{os.environ['POSTGRES_PORT']}/postgres"
    )
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": TEST_DB_NAME}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    admin_engine.dispose()


_ensure_test_database()

from shared.database import engine, SESSEON_LOCAL, initialize_database  # noqa: E402
from application.models.application_models import Base  # noqa: E402

assert engine.url.database == TEST_DB_NAME, "A suite precisa estar conectada ao banco de testes."

# ---------------------------------------------------------------------------
# Seed de dados de referencia a partir do dump
# ---------------------------------------------------------------------------

REFERENCE_TABLES = ["Category", "Nutrient", "Allergen", "Brand", "Food", "Food_Nutrient", "Allergen_Food"]


def _unescape_copy_value(value: str):
    if value == r"\N":
        return None
    return (
        value.replace(r"\t", "\t").replace(r"\n", "\n").replace(r"\r", "\r").replace("\\\\", "\\")
    )


def _read_copy_blocks(path: Path) -> dict:
    blocks = {}
    current = None
    with open(path, encoding="utf-8") as dump:
        for line in dump:
            line = line.rstrip("\n")
            if current is None:
                if line.startswith("COPY public."):
                    table = line.split('"')[1]
                    columns = line[line.index("(") + 1 : line.index(")")].split(", ")
                    current = (table, columns)
                    blocks[table] = (columns, [])
                continue
            if line == r"\.":
                current = None
                continue
            blocks[current[0]][1].append([_unescape_copy_value(v) for v in line.split("\t")])
    return blocks


def _seed_reference_data():
    blocks = _read_copy_blocks(DUMP_PATH)
    with engine.begin() as conn:
        for table in REFERENCE_TABLES:
            columns, rows = blocks.get(table, ([], []))
            if not rows:
                continue
            cols_sql = ", ".join(f'"{c}"' for c in columns)
            params_sql = ", ".join(f":{c}" for c in columns)
            conn.execute(
                text(f'INSERT INTO "{table}" ({cols_sql}) VALUES ({params_sql})'),
                [dict(zip(columns, row)) for row in rows],
            )
            if "id" in columns:
                conn.execute(
                    text(
                        f"SELECT setval(pg_get_serial_sequence('\"{table}\"', 'id'), "
                        f'(SELECT COALESCE(MAX(id), 1) FROM "{table}"), true)'
                    )
                )


@pytest.fixture(scope="session", autouse=True)
def test_database():
    """Recria o schema do banco de testes, carrega os dados de referencia e isola o cwd."""
    original_cwd = os.getcwd()
    os.chdir(WORK_DIR)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    _seed_reference_data()
    initialize_database()
    yield engine
    engine.dispose()
    os.chdir(original_cwd)


@pytest.fixture(scope="session")
def app():
    from main import app as fastapi_app

    return fastapi_app


@pytest.fixture(scope="session")
def client(app, test_database):
    from fastapi.testclient import TestClient

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def db():
    session = SESSEON_LOCAL()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# ---------------------------------------------------------------------------
# Fabricas de dados ficticios
# ---------------------------------------------------------------------------

def unique_email(prefix: str = "user") -> str:
    return f"{prefix}.{uuid.uuid4().hex[:10]}@example.test"


TEST_PASSWORD = "Senha-Teste-123"


@pytest.fixture
def make_user(client):
    def _make(**overrides):
        payload = {
            "email": unique_email(),
            "birthdate": "1990-05-17",
            "weight_kg": 72.5,
            "height_m": 1.78,
            "sex": "M",
            "password": TEST_PASSWORD,
            "is_active": True,
        }
        payload.update(overrides)
        response = client.post("/user", json=payload)
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        data["_password"] = payload["password"]
        return data

    return _make


@pytest.fixture
def make_nutricionist(client, db):
    from application.models.application_models import Nutricionist

    def _make(**overrides):
        payload = {
            "email": unique_email("nutri"),
            "password": TEST_PASSWORD,
            "phone": "13999990000",
            "crn": "CRN-3 12345",
        }
        payload.update(overrides)
        response = client.post("/nutricionist", json=payload)
        assert response.status_code == 200, response.text
        nutri = db.query(Nutricionist).filter(Nutricionist.email == payload["email"]).one()
        return {"id": nutri.id, "email": payload["email"], "_password": payload["password"]}

    return _make


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def work_dir() -> Path:
    return WORK_DIR
