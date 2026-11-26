"""Rotas auxiliares: raiz, health check, documentacao, OpenAPI e arquivos estaticos."""

from urllib.parse import quote

from sqlalchemy import create_engine

from application.models.application_models import Food


def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "API running"
    assert isinstance(body["routes"], list)


def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "database": "available"}


def test_health_database_unavailable(client, monkeypatch):
    import main

    broken_engine = create_engine("postgresql://nobody:nothing@127.0.0.1:1/none", connect_args={"connect_timeout": 2})
    monkeypatch.setattr(main, "engine", broken_engine)
    response = client.get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unhealthy"
    assert body["database"] == "unavailable"
    assert "nothing" not in body["detail"], "a senha da conexao nao pode vazar na resposta"


def test_endpoint_with_database_unavailable_returns_500(client, app):
    """Falha de conexao em um endpoint comum: erro 500 controlado, sem travar a API."""
    from sqlalchemy.orm import sessionmaker
    from shared.database import get_db

    broken = sessionmaker(bind=create_engine("postgresql://x:y@127.0.0.1:1/none", connect_args={"connect_timeout": 2}))

    def broken_db():
        session = broken()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = broken_db
    try:
        response = client.get("/categories")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 500
    # a API continua respondendo apos a falha
    assert client.get("/categories").status_code == 200


def test_docs_page(client):
    response = client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_openapi_lists_all_routes(client, app):
    from fastapi.routing import APIRoute

    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema_paths = response.json()["paths"]
    for route in app.routes:
        if isinstance(route, APIRoute) and route.include_in_schema:
            assert route.path in schema_paths, route.path


def test_static_food_images_exist_for_every_food(client, db):
    foods = db.query(Food).filter(Food.user_id.is_(None)).all()  # alimentos globais
    assert len(foods) == 25
    for food in foods:
        assert food.image_url, food.name
        response = client.get(f"/images/alimentos/{quote(food.image_url)}")
        assert response.status_code == 200, food.image_url
        assert response.headers["content-type"].startswith("image/"), food.image_url


def test_static_missing_file_returns_404(client):
    assert client.get("/images/alimentos/nao-existe.jpg").status_code == 404
    assert client.get("/qr_codes/nao-existe.png").status_code == 404
