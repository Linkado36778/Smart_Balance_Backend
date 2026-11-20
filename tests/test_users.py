"""Usuarios e nutricionistas (user_controller)."""

from datetime import datetime

from application.models.application_models import Meal, Nutricionist, User
from conftest import TEST_PASSWORD, unique_email


def user_payload(**overrides):
    payload = {
        "email": unique_email(),
        "birthdate": "1990-05-17",
        "weight_kg": 72.5,
        "height_m": 1.78,
        "sex": "F",
        "password": TEST_PASSWORD,
        "is_active": True,
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------- POST /user

class TestCreateUser:
    def test_success_persists_hashed_password(self, client, db):
        payload = user_payload()
        response = client.post("/user", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert set(data) == {"id", "email", "birthdate", "weight_kg", "height_m", "sex", "created_at", "is_active"}
        assert isinstance(data["id"], int)
        assert data["email"] == payload["email"]
        assert data["weight_kg"] == 72.5 and data["height_m"] == 1.78
        row = db.get(User, data["id"])
        assert row is not None and row.email == payload["email"]
        assert row.password != TEST_PASSWORD and row.password.startswith("$argon2")
        assert row.birthdate == datetime(1990, 5, 17)

    def test_invalid_email(self, client, db):
        response = client.post("/user", json=user_payload(email="sem-arroba"))
        assert response.status_code == 400
        assert db.query(User).filter(User.email == "sem-arroba").count() == 0

    def test_duplicate_email(self, client, make_user, db):
        user = make_user()
        response = client.post("/user", json=user_payload(email=user["email"]))
        assert response.status_code == 400
        assert response.json()["detail"] == "Email already registered"
        assert db.query(User).filter(User.email == user["email"]).count() == 1

    def test_missing_field_and_wrong_types(self, client):
        payload = user_payload()
        del payload["password"]
        assert client.post("/user", json=payload).status_code == 422
        assert client.post("/user", json=user_payload(weight_kg="abc")).status_code == 422
        assert client.post("/user", json=user_payload(birthdate="17/05/1990")).status_code == 422
        assert client.post("/user", json={}).status_code == 422
        assert client.post("/user", content=b"not json", headers={"content-type": "application/json"}).status_code == 422

    def test_nonexistent_nutricionist_is_client_error(self, client, db):
        payload = user_payload(nutricionist_id=999999)
        response = client.post("/user", json=payload)
        assert 400 <= response.status_code < 500, response.text
        assert db.query(User).filter(User.email == payload["email"]).count() == 0


# ---------------------------------------------------------- GET /user/{id}

class TestGetUser:
    def test_success_by_path_param(self, client, make_user):
        user = make_user()
        response = client.get(f"/user/{user['id']}")
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["id"] == user["id"]
        assert data["email"] == user["email"]
        assert "password" not in data

    def test_not_found(self, client):
        assert client.get("/user/999999").status_code == 404

    def test_invalid_path_param(self, client):
        assert client.get("/user/abc").status_code == 422


# ------------------------------------------------ PATCH /update_User/{id}

class TestUpdateUser:
    def test_success(self, client, make_user, db):
        user = make_user()
        payload = user_payload(email=unique_email("upd"), weight_kg=80.0, password="Nova-Senha-1", is_active=False)
        response = client.patch(f"/update_User/{user['id']}", json=payload)
        assert response.status_code == 200
        assert response.json()["data"]["weight_kg"] == 80.0
        row = db.get(User, user["id"])
        assert row.email == payload["email"] and row.weight_kg == 80.0 and row.is_active is False
        assert client.post("/auth/commun_user", json={"email": payload["email"], "password": "Nova-Senha-1"}).status_code == 200

    def test_not_found(self, client):
        assert client.patch("/update_User/999999", json=user_payload()).status_code == 404

    def test_invalid_email_rejected(self, client, make_user, db):
        user = make_user()
        response = client.patch(f"/update_User/{user['id']}", json=user_payload(email="invalido"))
        assert response.status_code == 400
        assert db.get(User, user["id"]).email == user["email"]

    def test_duplicate_email_rejected(self, client, make_user, db):
        first, second = make_user(), make_user()
        response = client.patch(f"/update_User/{second['id']}", json=user_payload(email=first["email"]))
        assert response.status_code == 400
        assert db.query(User).filter(User.email == first["email"]).count() == 1

    def test_same_email_keeps_working(self, client, make_user):
        user = make_user()
        assert client.patch(f"/update_User/{user['id']}", json=user_payload(email=user["email"])).status_code == 200


# ---------------------------------------------- DELETE /delete_User/{id}

class TestDeleteUser:
    def test_success(self, client, make_user, db):
        user = make_user()
        response = client.delete(f"/delete_User/{user['id']}")
        assert response.status_code == 200
        assert response.json()["data"] == {"id": user["id"]}
        assert db.get(User, user["id"]) is None

    def test_not_found(self, client):
        assert client.delete("/delete_User/999999").status_code == 404

    def test_user_with_meals_is_conflict_not_500(self, client, make_user, db):
        user = make_user()
        meal = client.post("/meals", json={
            "name": "Almoco", "user_id": user["id"], "consumed_at": "2026-11-20T12:00:00",
            "weight_g": 100, "list_foods_ids": [1], "saved_meal": True,
        })
        assert meal.status_code == 200
        response = client.delete(f"/delete_User/{user['id']}")
        assert response.status_code == 409, response.text
        assert db.get(User, user["id"]) is not None
        assert db.query(Meal).filter(Meal.user_id == user["id"]).count() == 1


# --------------------------------------- GET /login_User/{email}/{password}

class TestLoginUser:
    def test_success_does_not_expose_password_hash(self, client, make_user):
        user = make_user()
        response = client.get(f"/login_User/{user['email']}/{TEST_PASSWORD}")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == user["id"] and body["email"] == user["email"]
        assert "password" not in body

    def test_wrong_password(self, client, make_user):
        user = make_user()
        assert client.get(f"/login_User/{user['email']}/errada").status_code == 401

    def test_unknown_user(self, client):
        assert client.get("/login_User/ninguem@example.test/x").status_code == 404


# ----------------------------------------------------------- Nutricionist

def nutri_payload(**overrides):
    payload = {"email": unique_email("nutri"), "password": TEST_PASSWORD, "phone": "13999990000", "crn": "CRN-3 12345"}
    payload.update(overrides)
    return payload


class TestNutricionist:
    def test_create_success(self, client, db):
        payload = nutri_payload()
        response = client.post("/nutricionist", json=payload)
        assert response.status_code == 200
        assert response.json() == {"message": "Nutricionist created successfully", "success": True, "data": None}
        row = db.query(Nutricionist).filter(Nutricionist.email == payload["email"]).one()
        assert row.crn == "CRN-3 12345" and row.password.startswith("$argon2")

    def test_create_validation(self, client, make_nutricionist):
        assert client.post("/nutricionist", json=nutri_payload(email="x")).status_code == 400
        assert client.post("/nutricionist", json=nutri_payload(crn="12345")).status_code == 400
        existing = make_nutricionist()
        dup = client.post("/nutricionist", json=nutri_payload(email=existing["email"]))
        assert dup.status_code == 400
        assert client.post("/nutricionist", json={"email": unique_email()}).status_code == 422

    def test_get(self, client, make_nutricionist):
        nutri = make_nutricionist()
        response = client.get(f"/get_Nutricionist/{nutri['id']}")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == nutri["id"] and body["email"] == nutri["email"]
        assert "password" not in body
        assert client.get("/get_Nutricionist/999999").status_code == 404
        assert client.get("/get_Nutricionist/abc").status_code == 422

    def test_update(self, client, make_nutricionist, db):
        nutri = make_nutricionist()
        payload = nutri_payload(phone="13888887777", crn="CRN-4 54321")
        response = client.patch(f"/update_Nutricionist/{nutri['id']}", json=payload)
        assert response.status_code == 200
        assert response.json()["data"] == {"id": nutri["id"], "email": payload["email"], "phone": "13888887777", "crn": "CRN-4 54321"}
        row = db.get(Nutricionist, nutri["id"])
        assert row.phone == "13888887777"
        assert client.patch("/update_Nutricionist/999999", json=nutri_payload()).status_code == 404

    def test_update_rejects_invalid_crn_and_email(self, client, make_nutricionist, db):
        nutri = make_nutricionist()
        assert client.patch(f"/update_Nutricionist/{nutri['id']}", json=nutri_payload(crn="invalido")).status_code == 400
        assert client.patch(f"/update_Nutricionist/{nutri['id']}", json=nutri_payload(email="invalido")).status_code == 400
        assert db.get(Nutricionist, nutri["id"]).crn == "CRN-3 12345"

    def test_delete(self, client, make_nutricionist, db):
        nutri = make_nutricionist()
        response = client.delete(f"/delete_Nutricionist/{nutri['id']}")
        assert response.status_code == 200
        assert db.get(Nutricionist, nutri["id"]) is None
        assert client.delete("/delete_Nutricionist/999999").status_code == 404

    def test_delete_with_linked_user_is_conflict_not_500(self, client, make_nutricionist, make_user, db):
        nutri = make_nutricionist()
        make_user(nutricionist_id=nutri["id"])
        response = client.delete(f"/delete_Nutricionist/{nutri['id']}")
        assert response.status_code == 409, response.text
        assert db.get(Nutricionist, nutri["id"]) is not None

    def test_login(self, client, make_nutricionist):
        nutri = make_nutricionist()
        response = client.get(f"/login_Nutricionist/{nutri['email']}/{TEST_PASSWORD}")
        assert response.status_code == 200
        assert response.json()["id"] == nutri["id"]
        assert "password" not in response.json()
        assert client.get(f"/login_Nutricionist/{nutri['email']}/errada").status_code == 401
        assert client.get("/login_Nutricionist/ninguem@example.test/x").status_code == 404


class TestLinkUserNutricionist:
    def test_link_unlink_and_list(self, client, make_user, make_nutricionist, db):
        user, nutri = make_user(), make_nutricionist()
        response = client.post("/link_user_nutricionist", params={"user_id": user["id"], "nutricionist_id": nutri["id"]})
        assert response.status_code == 200
        assert response.json()["data"] == {"user_id": user["id"], "nutricionist_id": nutri["id"]}
        assert db.get(User, user["id"]).nutricionist_id == nutri["id"]

        listing = client.get(f"/list_user_data_by_nutricionist/{nutri['id']}")
        assert listing.status_code == 200
        assert [u["id"] for u in listing.json()] == [user["id"]]
        assert all("password" not in u for u in listing.json())

        response = client.patch(f"/unlink_user_nutricionist/{user['id']}")
        assert response.status_code == 200
        assert response.json()["data"]["nutricionist_id"] is None
        db.expunge_all()
        assert db.get(User, user["id"]).nutricionist_id is None
        assert client.get(f"/list_user_data_by_nutricionist/{nutri['id']}").json() == []

    def test_link_errors(self, client, make_user, make_nutricionist):
        user, nutri = make_user(), make_nutricionist()
        assert client.post("/link_user_nutricionist", params={"user_id": 999999, "nutricionist_id": nutri["id"]}).status_code == 404
        assert client.post("/link_user_nutricionist", params={"user_id": user["id"], "nutricionist_id": 999999}).status_code == 404
        assert client.post("/link_user_nutricionist", params={"user_id": user["id"]}).status_code == 422
        assert client.patch("/unlink_user_nutricionist/999999").status_code == 404
