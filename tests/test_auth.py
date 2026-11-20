"""POST /auth/commun_user e POST /auth/nutricionist."""

import pytest

from conftest import TEST_PASSWORD


@pytest.mark.parametrize("route,factory", [("/auth/commun_user", "make_user"), ("/auth/nutricionist", "make_nutricionist")])
class TestAuth:
    def test_valid_credentials(self, client, request, route, factory):
        account = request.getfixturevalue(factory)()
        response = client.post(route, json={"email": account["email"], "password": TEST_PASSWORD})
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"] is None

    def test_wrong_password_returns_401(self, client, request, route, factory):
        account = request.getfixturevalue(factory)()
        response = client.post(route, json={"email": account["email"], "password": "errada"})
        assert response.status_code == 401
        assert response.json()["success"] is False
        assert response.json()["message"] == "Credencial inválida"

    def test_unknown_email_returns_401(self, client, route, factory):
        response = client.post(route, json={"email": "ninguem@example.test", "password": "x"})
        assert response.status_code == 401
        assert response.json()["message"] == "Credencial inválida"

    def test_missing_fields_422(self, client, route, factory):
        assert client.post(route, json={"email": "a@b.com"}).status_code == 422
        assert client.post(route, json={}).status_code == 422

    def test_malformed_json_422(self, client, route, factory):
        response = client.post(route, content=b"{email:", headers={"content-type": "application/json"})
        assert response.status_code == 422
