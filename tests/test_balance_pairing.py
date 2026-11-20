"""Balanca e pareamento por QR Code (user_controller)."""

import hashlib
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

from application.models.application_models import Balance, Pairing, UserBalanceAssociation


def register_balance(client, name="Balanca de teste"):
    response = client.post("/register_balance", json={"id": 0, "name": name})
    assert response.status_code == 200
    return response.json()["data"]


def generate_token(client):
    response = client.post("/generate_qr_code/")
    assert response.status_code == 200
    data = response.json()["data"]
    token = parse_qs(urlparse(data["pairing_url"]).query)["token"][0]
    return data, token


class TestRegisterBalance:
    def test_success(self, client, db):
        data = register_balance(client, "Balanca cozinha")
        assert data["name"] == "Balanca cozinha" and isinstance(data["id"], int)
        assert db.get(Balance, data["id"]).name == "Balanca cozinha"

    def test_validation(self, client):
        assert client.post("/register_balance", json={}).status_code == 422
        assert client.post("/register_balance", json={"id": 1}).status_code == 422


class TestGenerateQrCode:
    def test_success(self, client, db):
        data, token = generate_token(client)
        assert set(data) == {"pairing_url", "pairing_id", "expires_at", "qr_code_url"}
        row = db.get(Pairing, data["pairing_id"])
        assert row.token_hash == hashlib.sha256(token.encode()).hexdigest()
        assert row.used_at is None
        assert timedelta(minutes=4) < row.expires_at - datetime.now() <= timedelta(minutes=5)
        png = client.get(urlparse(data["qr_code_url"]).path)
        assert png.status_code == 200 and png.content[:8] == b"\x89PNG\r\n\x1a\n"
        assert token not in row.token_hash


class TestPairScale:
    def test_success_and_token_reuse(self, client, make_user, db):
        user, balance = make_user(), register_balance(client)
        data, token = generate_token(client)
        response = client.post("/pair-scale", params={"user_id": user["id"], "balance_id": balance["id"], "token": token})
        assert response.status_code == 200, response.text
        body = response.json()["data"]
        assert body["user_id"] == user["id"] and body["balance_id"] == balance["id"]
        assert db.get(UserBalanceAssociation, (user["id"], balance["id"])) is not None
        assert db.get(Pairing, data["pairing_id"]).used_at is not None

        reuse = client.post("/pair-scale", params={"user_id": user["id"], "balance_id": balance["id"], "token": token})
        assert reuse.status_code == 400 and reuse.json()["detail"] == "Token already used"

    def test_invalid_and_expired_token(self, client, make_user, db):
        user, balance = make_user(), register_balance(client)
        assert client.post("/pair-scale", params={"user_id": user["id"], "balance_id": balance["id"], "token": "invalido"}).status_code == 404
        data, token = generate_token(client)
        row = db.get(Pairing, data["pairing_id"])
        row.expires_at = datetime.now() - timedelta(minutes=1)
        db.commit()
        expired = client.post("/pair-scale", params={"user_id": user["id"], "balance_id": balance["id"], "token": token})
        assert expired.status_code == 400 and expired.json()["detail"] == "Token expired"
        assert client.post("/pair-scale", params={"user_id": user["id"]}).status_code == 422

    def test_nonexistent_user_or_balance_does_not_consume_token(self, client, make_user, db):
        user, balance = make_user(), register_balance(client)
        data, token = generate_token(client)
        r1 = client.post("/pair-scale", params={"user_id": 999999, "balance_id": balance["id"], "token": token})
        r2 = client.post("/pair-scale", params={"user_id": user["id"], "balance_id": 999999, "token": token})
        assert r1.status_code == 404, r1.text
        assert r2.status_code == 404, r2.text
        db.expunge_all()
        assert db.get(Pairing, data["pairing_id"]).used_at is None

    def test_duplicate_pairing_is_client_error(self, client, make_user, db):
        user, balance = make_user(), register_balance(client)
        _, token1 = generate_token(client)
        data2, token2 = generate_token(client)
        assert client.post("/pair-scale", params={"user_id": user["id"], "balance_id": balance["id"], "token": token1}).status_code == 200
        dup = client.post("/pair-scale", params={"user_id": user["id"], "balance_id": balance["id"], "token": token2})
        assert dup.status_code in (400, 409), dup.text
        db.expunge_all()
        assert db.get(Pairing, data2["pairing_id"]).used_at is None
