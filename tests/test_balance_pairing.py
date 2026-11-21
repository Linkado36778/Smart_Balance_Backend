"""Balanca e pareamento por QR Code (user_controller)."""

import hashlib
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

from application.models.application_models import Balance, Pairing, UserBalanceAssociation


def register_balance(client, name="Balanca de teste"):
    response = client.post("/register_balance", json={"id": 0, "name": name})
    assert response.status_code == 200
    return response.json()["data"]


def generate_token(client, balance_id=None):
    params = {"balance_id": balance_id} if balance_id is not None else None
    response = client.post("/generate_qr_code/", params=params)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    token = parse_qs(urlparse(data["pairing_url"]).query)["token"][0]
    return data, token


def status(client, data, poll_token=None):
    headers = {"X-Pairing-Token": poll_token if poll_token is not None else data["poll_token"]}
    return client.get(f"/pairing/{data['pairing_id']}/status", headers=headers)


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
        assert set(data) == {"pairing_url", "pairing_id", "expires_at", "expires_in", "qr_code_url",
                             "balance_id", "poll_token"}
        assert data["expires_in"] == 300
        assert data["balance_id"] is None
        row = db.get(Pairing, data["pairing_id"])
        assert row.token_hash == hashlib.sha256(token.encode()).hexdigest()
        assert row.used_at is None
        assert timedelta(minutes=4) < row.expires_at - datetime.now() <= timedelta(minutes=5)
        png = client.get(urlparse(data["qr_code_url"]).path)
        assert png.status_code == 200 and png.content[:8] == b"\x89PNG\r\n\x1a\n"
        assert token not in row.token_hash
        # credencial de consulta: so o hash e guardado e ela nunca vai no QR Code
        assert row.poll_token_hash == hashlib.sha256(data["poll_token"].encode()).hexdigest()
        assert data["poll_token"] not in data["pairing_url"]

    def test_bound_to_balance(self, client, db):
        balance = register_balance(client)
        data, token = generate_token(client, balance["id"])
        assert data["balance_id"] == balance["id"]
        assert db.get(Pairing, data["pairing_id"]).balance_id == balance["id"]
        assert parse_qs(urlparse(data["pairing_url"]).query)["balance_id"] == [str(balance["id"])]

    def test_unknown_balance(self, client):
        response = client.post("/generate_qr_code/", params={"balance_id": 999999})
        assert response.status_code == 404 and response.json()["detail"] == "Balance not found"


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

    def test_repairing_same_user_is_idempotent(self, client, make_user, db):
        """Novo QR Code para o mesmo usuario/balanca: sucesso sem duplicar o vinculo.

        Antes respondia 400 sem consumir o token, e a balanca (que consulta o
        status do proprio pareamento) nunca veria a confirmacao.
        """
        user, balance = make_user(), register_balance(client)
        _, token1 = generate_token(client, balance["id"])
        data2, token2 = generate_token(client, balance["id"])
        assert client.post("/pair-scale", params={"user_id": user["id"], "token": token1}).status_code == 200
        again = client.post("/pair-scale", params={"user_id": user["id"], "token": token2})
        assert again.status_code == 200, again.text
        assert again.json()["message"] == "Scale already paired with this user"
        db.expunge_all()
        assert db.get(Pairing, data2["pairing_id"]).used_at is not None
        assert db.query(UserBalanceAssociation).filter_by(user_id=user["id"], balance_id=balance["id"]).count() == 1
        assert status(client, data2).json()["data"]["status"] == "paired"


class TestPairBoundToken:
    def test_balance_comes_from_token(self, client, make_user, db):
        user, balance = make_user(), register_balance(client)
        data, token = generate_token(client, balance["id"])
        response = client.post("/pair-scale", params={"user_id": user["id"], "token": token})
        assert response.status_code == 200, response.text
        assert response.json()["data"]["balance_id"] == balance["id"]
        db.expunge_all()
        row = db.get(Pairing, data["pairing_id"])
        assert row.user_id == user["id"] and row.balance_id == balance["id"] and row.used_at is not None
        assert db.get(UserBalanceAssociation, (user["id"], balance["id"])) is not None

    def test_cannot_pair_another_balance_with_token(self, client, make_user, db):
        user, balance, other = make_user(), register_balance(client), register_balance(client, "Outra")
        data, token = generate_token(client, balance["id"])
        response = client.post("/pair-scale", params={"user_id": user["id"], "balance_id": other["id"], "token": token})
        assert response.status_code == 400 and response.json()["detail"] == "Token does not belong to this balance"
        db.expunge_all()
        assert db.get(Pairing, data["pairing_id"]).used_at is None
        assert db.get(UserBalanceAssociation, (user["id"], other["id"])) is None

    def test_matching_balance_id_is_accepted(self, client, make_user):
        user, balance = make_user(), register_balance(client)
        _, token = generate_token(client, balance["id"])
        assert client.post("/pair-scale", params={"user_id": user["id"], "balance_id": balance["id"], "token": token}).status_code == 200

    def test_legacy_token_requires_balance_id(self, client, make_user):
        user = make_user()
        _, token = generate_token(client)
        response = client.post("/pair-scale", params={"user_id": user["id"], "token": token})
        assert response.status_code == 400 and response.json()["detail"] == "balance_id is required for this token"


class TestPairingStatus:
    def test_pending_then_paired(self, client, make_user):
        user, balance = make_user(), register_balance(client)
        data, token = generate_token(client, balance["id"])
        before = status(client, data)
        assert before.status_code == 200
        assert before.json()["data"]["status"] == "pending" and before.json()["data"]["user_id"] is None
        client.post("/pair-scale", params={"user_id": user["id"], "token": token})
        after = status(client, data).json()["data"]
        assert after == {**after, "status": "paired", "user_id": user["id"], "balance_id": balance["id"]}
        assert set(after) == {"pairing_id", "status", "user_id", "balance_id", "expires_at"}

    def test_expired(self, client, db):
        data, _ = generate_token(client, register_balance(client)["id"])
        row = db.get(Pairing, data["pairing_id"])
        row.expires_at = datetime.now() - timedelta(minutes=1)
        db.commit()
        assert status(client, data).json()["data"]["status"] == "expired"

    def test_unpaired_when_association_removed(self, client, make_user, db):
        user, balance = make_user(), register_balance(client)
        data, token = generate_token(client, balance["id"])
        client.post("/pair-scale", params={"user_id": user["id"], "token": token})
        db.delete(db.get(UserBalanceAssociation, (user["id"], balance["id"])))
        db.commit()
        body = status(client, data).json()["data"]
        assert body["status"] == "unpaired" and body["user_id"] is None

    def test_requires_the_right_poll_token(self, client):
        data, _ = generate_token(client, register_balance(client)["id"])
        assert client.get(f"/pairing/{data['pairing_id']}/status").status_code == 401
        wrong = status(client, data, poll_token="outro-token")
        unknown = client.get("/pairing/999999/status", headers={"X-Pairing-Token": data["poll_token"]})
        # token errado e id inexistente sao indistinguiveis
        assert wrong.status_code == unknown.status_code == 404
        assert wrong.json() == unknown.json() == {"detail": "Pairing not found"}

    def test_qr_token_is_not_a_poll_token(self, client):
        data, token = generate_token(client, register_balance(client)["id"])
        assert status(client, data, poll_token=token).status_code == 404
