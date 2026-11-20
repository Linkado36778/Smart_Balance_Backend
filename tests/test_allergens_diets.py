"""Alergenos e dietas (user_controller)."""

import uuid

from application.models.application_models import Allergen, Diet, DietFoodAssociation, UserAllergenAssociation


# --------------------------------------------------------------- Allergens

class TestAllergenCatalog:
    def test_add_and_list(self, client, db):
        name = f"Alergeno-{uuid.uuid4().hex[:6]}"
        response = client.post("/add_allergen", json={"name": name})
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["name"] == name and isinstance(data["id"], int)
        assert db.get(Allergen, data["id"]).name == name

        listing = client.get("/list_allergens")
        assert listing.status_code == 200
        items = listing.json()
        assert all(set(i) == {"allergens_id", "allergens_name"} for i in items)
        assert {"allergens_id": data["id"], "allergens_name": name} in items

    def test_add_validation(self, client):
        assert client.post("/add_allergen", json={}).status_code == 422
        assert client.post("/add_allergen", json={"name": 123}).status_code == 422


class TestUserAllergens:
    def test_add_list_remove(self, client, make_user, db):
        user = make_user()
        response = client.post("/add_allergen_to_user", json={"user_id": user["id"], "allergen_id": 1})
        assert response.status_code == 200
        assert response.json() == {"allergen_id": 1, "user_id": user["id"]}
        assert db.get(UserAllergenAssociation, (1, user["id"])) is not None

        listing = client.get(f"/list_allergens_by_user/{user['id']}")
        assert listing.status_code == 200
        assert [a["id"] for a in listing.json()] == [1]

        removed = client.delete("/remove_allergen_from_user", params={"user_id": user["id"], "allergen_id": 1})
        assert removed.status_code == 200
        assert removed.json()["data"] == {"user_id": user["id"], "allergen_id": 1}
        db.expunge_all()
        assert db.get(UserAllergenAssociation, (1, user["id"])) is None
        assert client.get(f"/list_allergens_by_user/{user['id']}").json() == []

    def test_add_to_nonexistent_user_or_allergen(self, client, make_user):
        user = make_user()
        r1 = client.post("/add_allergen_to_user", json={"user_id": 999999, "allergen_id": 1})
        r2 = client.post("/add_allergen_to_user", json={"user_id": user["id"], "allergen_id": 999999})
        assert r1.status_code == 404, r1.text
        assert r2.status_code == 404, r2.text

    def test_add_duplicate_is_client_error(self, client, make_user, db):
        user = make_user()
        assert client.post("/add_allergen_to_user", json={"user_id": user["id"], "allergen_id": 2}).status_code == 200
        dup = client.post("/add_allergen_to_user", json={"user_id": user["id"], "allergen_id": 2})
        assert dup.status_code in (400, 409), dup.text
        assert db.query(UserAllergenAssociation).filter_by(user_id=user["id"]).count() == 1

    def test_errors(self, client):
        assert client.get("/list_allergens_by_user/999999").status_code == 404
        assert client.delete("/remove_allergen_from_user", params={"user_id": 999999, "allergen_id": 1}).status_code == 404
        assert client.delete("/remove_allergen_from_user", params={"user_id": 1}).status_code == 422
        assert client.post("/add_allergen_to_user", json={"user_id": "x", "allergen_id": 1}).status_code == 422


# ------------------------------------------------------------------- Diets

def diet_payload(user_id, nutri_id, **overrides):
    payload = {
        "name": "Dieta hipocalorica",
        "user_id": user_id,
        "nutricionist_id": nutri_id,
        "list_foods_ids": [1, 3],
        "kcal_goal": 1800.0,
        "fat_goal": 50.0,
        "carb_goal": 200.0,
        "protein_goal": 120.0,
    }
    payload.update(overrides)
    return payload


class TestDiets:
    def test_create_list_update(self, client, make_user, make_nutricionist, db):
        user, nutri = make_user(), make_nutricionist()
        response = client.post(f"/create_diet/{nutri['id']}/{user['id']}", json=diet_payload(user["id"], nutri["id"]))
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["user_id"] == user["id"] and data["nutricionist_id"] == nutri["id"]
        diet_id = data["diet_id"]
        row = db.get(Diet, diet_id)
        assert row.kcal_goal == 1800.0 and row.protein_goal == 120.0
        assert sorted(a.food_id for a in db.query(DietFoodAssociation).filter_by(diet_id=diet_id)) == [1, 3]

        listing = client.get(f"/list_diets_by_user/{user['id']}")
        assert listing.status_code == 200
        assert [d["id"] for d in listing.json()] == [diet_id]

        upd = client.patch(f"/update_diet/{diet_id}", json=diet_payload(user["id"], nutri["id"], name="Nova", list_foods_ids=[2], kcal_goal=2000.0))
        assert upd.status_code == 200
        assert upd.json()["data"]["diet_name"] == "Nova"
        db.expunge_all()
        assert db.get(Diet, diet_id).kcal_goal == 2000.0
        assert [a.food_id for a in db.query(DietFoodAssociation).filter_by(diet_id=diet_id)] == [2]

    def test_create_errors_do_not_persist(self, client, make_user, make_nutricionist, db):
        user, nutri = make_user(), make_nutricionist()
        assert client.post(f"/create_diet/{nutri['id']}/999999", json=diet_payload(999999, nutri["id"])).status_code == 404
        assert client.post(f"/create_diet/999999/{user['id']}", json=diet_payload(user["id"], 999999)).status_code == 404
        bad_food = client.post(f"/create_diet/{nutri['id']}/{user['id']}", json=diet_payload(user["id"], nutri["id"], list_foods_ids=[1, 999999]))
        assert bad_food.status_code == 400
        assert db.query(Diet).filter_by(user_id=user["id"]).count() == 0
        assert client.post(f"/create_diet/{nutri['id']}/{user['id']}", json={"name": "x"}).status_code == 422

    def test_create_body_ids_must_match_path(self, client, make_user, make_nutricionist, db):
        """A dieta nao pode ser atribuida a um usuario diferente do validado na rota."""
        user, other, nutri = make_user(), make_user(), make_nutricionist()
        response = client.post(f"/create_diet/{nutri['id']}/{user['id']}", json=diet_payload(other["id"], nutri["id"]))
        assert response.status_code == 400, response.text
        assert db.query(Diet).filter(Diet.user_id.in_([user["id"], other["id"]])).count() == 0

    def test_update_errors_keep_previous_state(self, client, make_user, make_nutricionist, db):
        user, nutri = make_user(), make_nutricionist()
        diet_id = client.post(f"/create_diet/{nutri['id']}/{user['id']}", json=diet_payload(user["id"], nutri["id"])).json()["data"]["diet_id"]
        bad = client.patch(f"/update_diet/{diet_id}", json=diet_payload(user["id"], nutri["id"], name="X", list_foods_ids=[999999]))
        assert bad.status_code == 400
        db.expunge_all()
        assert db.get(Diet, diet_id).name == "Dieta hipocalorica"
        assert db.query(DietFoodAssociation).filter_by(diet_id=diet_id).count() == 2
        assert client.patch("/update_diet/999999", json=diet_payload(user["id"], nutri["id"])).status_code == 404
        assert client.get("/list_diets_by_user/999999").status_code == 404
