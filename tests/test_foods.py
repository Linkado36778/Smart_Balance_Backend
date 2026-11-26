"""Alimentos, alimentos criados, marcas, categorias e nutrientes (food_controller)."""

import uuid

from application.models.application_models import (
    AllergenFoodAssociation,
    Brand,
    Food,
    FoodNutrientAssociation,
)
from shared.database import DEFAULT_CATEGORIES


def created_food_payload(**overrides):
    payload = {
        "name": f"Alimento-{uuid.uuid4().hex[:8]}",
        "category_id": 2,
        "brand_id": None,
        "nutrients": [{"id": 1, "amount": 10.5}, {"id": 2, "amount": 30.0}],
        "allergen_ids": [1],
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------- GET /foods

class TestListFoods:
    def test_success_structure(self, client, make_user, db):
        user = make_user()
        response = client.get("/foods", params={"user_id": user["id"]})
        assert response.status_code == 200
        foods = response.json()
        assert len(foods) == 25
        assert [f["id"] for f in foods] == sorted(f["id"] for f in foods)
        assert all(f["created_by_user"] is False for f in foods)
        rice = next(f for f in foods if f["id"] == 1)
        assert set(rice) == {"id", "name", "category_id", "brand_id", "nutrients", "image", "user_allergic", "description",
                             "model_label", "created_by_user"}
        assert rice["name"] == "Arroz tipo 1, cozido"
        assert rice["image"].endswith("/images/alimentos/arroz-tipo-1-cozido.jpg")
        db_amounts = {a.nutrient_id: a.amount for a in db.query(FoodNutrientAssociation).filter_by(food_id=1)}
        assert {n["id"]: n["amount"] for n in rice["nutrients"]} == db_amounts
        assert all(set(n) == {"id", "name", "amount", "unit", "calories_per_unit"} for n in rice["nutrients"])
        assert all(f["user_allergic"] is False for f in foods)

    def test_name_filter(self, client, make_user):
        user = make_user()
        foods = client.get("/foods", params={"user_id": user["id"], "name": "frango"}).json()
        assert foods and all("frango" in f["name"].lower() for f in foods)
        assert client.get("/foods", params={"user_id": user["id"], "name": "inexistente-xyz"}).json() == []

    def test_user_allergic_flag_uses_food_allergens(self, client, make_user, db):
        """Usuario alergico a um alergeno do alimento deve ver user_allergic=True naquele alimento."""
        user = make_user()
        assoc = db.query(AllergenFoodAssociation).filter_by(food_id=8).first()
        assert assoc is not None
        assert client.post("/add_allergen_to_user", json={"user_id": user["id"], "allergen_id": assoc.allergen_id}).status_code == 200
        foods = client.get("/foods", params={"user_id": user["id"]}).json()
        expected = {a.food_id for a in db.query(AllergenFoodAssociation).filter_by(allergen_id=assoc.allergen_id)}
        assert {f["id"] for f in foods if f["user_allergic"]} == expected

    def test_errors(self, client):
        assert client.get("/foods", params={"user_id": 999999}).status_code == 404
        assert client.get("/foods").status_code == 422
        assert client.get("/foods", params={"user_id": "abc"}).status_code == 422


# ------------------------------------------------------- Created foods CRUD
# Alimentos criados pelo usuario ficam na propria tabela Food (user_id preenchido).

def food_nutrients(db, food_id):
    return {a.nutrient_id: a.amount for a in db.query(FoodNutrientAssociation).filter_by(food_id=food_id)}


def food_allergens(db, food_id):
    return sorted(a.allergen_id for a in db.query(AllergenFoodAssociation).filter_by(food_id=food_id))


class TestCreatedFoods:
    def test_create_persists_with_associations(self, client, make_user, db):
        user = make_user()
        payload = created_food_payload()
        response = client.post("/foods", params={"user_id": user["id"]}, json=payload)
        assert response.status_code == 200, response.text
        assert response.json() == {"message": "Food created successfully", "success": True, "data": None}
        row = db.query(Food).filter_by(name=payload["name"]).one()
        assert row.user_id == user["id"] and row.category_id == 2
        assert row.id > max(f.id for f in db.query(Food).filter(Food.user_id.is_(None)))  # depois dos globais
        assert food_nutrients(db, row.id) == {1: 10.5, 2: 30.0}
        assert food_allergens(db, row.id) == [1]

    def test_create_errors_do_not_persist(self, client, make_user, db):
        user = make_user()
        for bad in (
            created_food_payload(allergen_ids=[999999]),
            created_food_payload(nutrients=[{"id": 999999, "amount": 1}]),
            created_food_payload(nutrients=[{"id": 1, "amount": 1}, {"id": 1, "amount": 2}]),
        ):
            response = client.post("/foods", params={"user_id": user["id"]}, json=bad)
            assert response.status_code == 400
            assert db.query(Food).filter_by(name=bad["name"]).count() == 0
        assert client.post("/foods", params={"user_id": user["id"]}, json={**created_food_payload(), "extra": 1}).status_code == 422
        assert client.post("/foods", params={"user_id": user["id"]}, json={}).status_code == 422
        assert client.post("/foods", json=created_food_payload()).status_code == 422

    def test_create_duplicate_name_is_per_user(self, client, make_user):
        user, other = make_user(), make_user()
        payload = created_food_payload()
        assert client.post("/foods", params={"user_id": user["id"]}, json=payload).status_code == 200
        dup = client.post("/foods", params={"user_id": user["id"]}, json={**payload, "name": payload["name"].upper()})
        assert dup.status_code == 400
        # outro usuario pode ter um alimento com o mesmo nome
        assert client.post("/foods", params={"user_id": other["id"]}, json=payload).status_code == 200

    def test_create_for_nonexistent_user_is_404(self, client, db):
        payload = created_food_payload()
        response = client.post("/foods", params={"user_id": 999999}, json=payload)
        assert response.status_code == 404, response.text
        assert db.query(Food).filter_by(name=payload["name"]).count() == 0

    def _create(self, client, db, user_id, **overrides):
        payload = created_food_payload(**overrides)
        assert client.post("/foods", params={"user_id": user_id}, json=payload).status_code == 200
        return db.query(Food).filter_by(name=payload["name"], user_id=user_id).one().id

    def test_list_created_foods_only_returns_the_users_foods(self, client, make_user, db):
        owner, other = make_user(), make_user()
        first = self._create(client, db, owner["id"])
        second = self._create(client, db, owner["id"], nutrients=[{"id": 3, "amount": 7.0}], allergen_ids=[])
        other_food = self._create(client, db, other["id"])

        response = client.get("/foods/created", params={"user_id": owner["id"]})
        assert response.status_code == 200, response.text
        body = response.json()
        assert [f["id"] for f in body] == [first, second]
        assert all(f["created_by_user"] is True for f in body)
        assert [(n["id"], n["amount"]) for n in body[1]["nutrients"]] == [(3, 7.0)]

        assert [f["id"] for f in client.get("/foods/created", params={"user_id": other["id"]}).json()] == [other_food]
        assert client.get("/foods/created", params={"user_id": 999999}).status_code == 404

    def test_list_foods_shows_globals_then_own_foods(self, client, make_user, db):
        owner, other = make_user(), make_user()
        own = self._create(client, db, owner["id"])
        foreign = self._create(client, db, other["id"])

        foods = client.get("/foods", params={"user_id": owner["id"]}).json()
        ids = [f["id"] for f in foods]
        assert own in ids and foreign not in ids
        assert ids[-1] == own  # alimentos do usuario por ultimo
        assert [f["created_by_user"] for f in foods] == [False] * (len(foods) - 1) + [True]

    def test_created_food_allergic_flag(self, client, make_user, db):
        user = make_user()
        food_id = self._create(client, db, user["id"], allergen_ids=[3])

        def flag():
            foods = client.get("/foods/created", params={"user_id": user["id"]}).json()
            return next(f for f in foods if f["id"] == food_id)["user_allergic"]

        assert flag() is False
        client.post("/add_allergen_to_user", json={"user_id": user["id"], "allergen_id": 3})
        assert flag() is True

    def test_update(self, client, make_user, db):
        user = make_user()
        food_id = self._create(client, db, user["id"])
        payload = created_food_payload(name=f"Atualizado-{uuid.uuid4().hex[:6]}", nutrients=[{"id": 4, "amount": 2.0}], allergen_ids=[2])
        response = client.patch(f"/foods/{food_id}", params={"user_id": user["id"]}, json=payload)
        assert response.status_code == 200
        assert response.json()["data"]["name"] == payload["name"]
        db.expunge_all()
        assert db.get(Food, food_id).name == payload["name"]
        assert food_nutrients(db, food_id) == {4: 2.0}
        assert food_allergens(db, food_id) == [2]

    def test_update_authorization_and_not_found(self, client, make_user, db):
        owner, other = make_user(), make_user()
        food_id = self._create(client, db, owner["id"])
        forbidden = client.patch(f"/foods/{food_id}", params={"user_id": other["id"]}, json=created_food_payload())
        assert forbidden.status_code == 403, forbidden.text
        missing = client.patch("/foods/999999", params={"user_id": owner["id"]}, json=created_food_payload())
        assert missing.status_code == 404, missing.text

    def test_global_foods_cannot_be_changed(self, client, make_user, db):
        user = make_user()
        before = food_nutrients(db, 1)
        assert client.patch("/foods/1", params={"user_id": user["id"]}, json=created_food_payload()).status_code == 403
        assert client.delete("/foods/1", params={"user_id": user["id"]}).status_code == 403
        db.expunge_all()
        assert db.get(Food, 1).name == "Arroz tipo 1, cozido" and food_nutrients(db, 1) == before

    def test_update_invalid_allergen_keeps_previous_state(self, client, make_user, db):
        user = make_user()
        payload = created_food_payload()
        food_id = self._create(client, db, user["id"], name=payload["name"])
        bad = client.patch(f"/foods/{food_id}", params={"user_id": user["id"]}, json=created_food_payload(allergen_ids=[999999]))
        assert bad.status_code == 400
        db.expunge_all()
        assert db.get(Food, food_id).name == payload["name"]
        assert len(food_nutrients(db, food_id)) == 2

    def test_delete(self, client, make_user, db):
        owner, other = make_user(), make_user()
        food_id = self._create(client, db, owner["id"])
        forbidden = client.delete(f"/foods/{food_id}", params={"user_id": other["id"]})
        assert forbidden.status_code == 403, forbidden.text
        assert client.delete("/foods/999999", params={"user_id": owner["id"]}).status_code == 404
        response = client.delete(f"/foods/{food_id}", params={"user_id": owner["id"]})
        assert response.status_code == 200
        db.expunge_all()
        assert db.get(Food, food_id) is None
        assert food_nutrients(db, food_id) == {} and food_allergens(db, food_id) == []

    def test_delete_food_used_in_meal_is_conflict(self, client, make_user, db):
        user = make_user()
        food_id = self._create(client, db, user["id"])
        meal = client.post("/meals", params={"user_id": user["id"]}, json={
            "name": "Lanche", "consumed_at": "2026-11-21 16:00:00",
            "list_foods_ids": [food_id], "list_foods_weights": [100], "saved_meal": True,
        })
        assert meal.status_code == 200, meal.text
        response = client.delete(f"/foods/{food_id}", params={"user_id": user["id"]})
        assert response.status_code == 409, response.text
        db.expunge_all()
        assert db.get(Food, food_id) is not None


# ------------------------------------------------------------------ Brands

class TestBrands:
    def test_create_search_update_delete(self, client, db):
        name = f"Marca-{uuid.uuid4().hex[:8]}"
        response = client.post("/brands", json={"name": name})
        assert response.status_code == 200
        brand = db.query(Brand).filter_by(name=name).one()

        search = client.get("/brands", params={"query_brand_name": name[:10]})
        assert search.status_code == 200
        assert {"id": brand.id, "name": name} in search.json()["data"]

        upd = client.patch(f"/brands/{brand.id}", json={"name": name + "-v2"})
        assert upd.status_code == 200 and upd.json()["name"] == name + "-v2"
        db.expunge_all()
        assert db.get(Brand, brand.id).name == name + "-v2"

        assert client.delete(f"/brands/{brand.id}").status_code == 200
        db.expunge_all()
        assert db.get(Brand, brand.id) is None

    def test_duplicate_is_rejected_case_insensitive(self, client):
        name = f"Marca-{uuid.uuid4().hex[:8]}"
        assert client.post("/brands", json={"name": name}).status_code == 200
        assert client.post("/brands", json={"name": name.upper()}).status_code == 400

    def test_name_contained_in_existing_brand_is_not_duplicate(self, client, db):
        base = f"Marca-{uuid.uuid4().hex[:8]}"
        assert client.post("/brands", json={"name": base + " Premium"}).status_code == 200
        response = client.post("/brands", json={"name": base})
        assert response.status_code == 200, response.text
        assert db.query(Brand).filter_by(name=base).count() == 1

    def test_search_no_match_and_validation(self, client):
        response = client.get("/brands", params={"query_brand_name": "nao-existe-" + uuid.uuid4().hex})
        assert response.status_code == 200 and response.json()["data"] == []
        assert client.get("/brands").status_code == 422
        assert client.post("/brands", json={}).status_code == 422

    def test_not_found(self, client):
        assert client.patch("/brands/999999", json={"name": "x"}).status_code == 404
        assert client.delete("/brands/999999").status_code == 404

    def test_delete_brand_in_use_is_conflict_not_500(self, client, make_user, db):
        name = f"Marca-{uuid.uuid4().hex[:8]}"
        client.post("/brands", json={"name": name})
        brand = db.query(Brand).filter_by(name=name).one()
        user = make_user()
        assert client.post("/foods", params={"user_id": user["id"]}, json=created_food_payload(brand_id=brand.id)).status_code == 200
        response = client.delete(f"/brands/{brand.id}")
        assert response.status_code == 409, response.text
        db.expunge_all()
        assert db.get(Brand, brand.id) is not None


# ---------------------------------------------------- Categories/Nutrients

def test_list_categories(client):
    response = client.get("/categories")
    assert response.status_code == 200
    data = response.json()["data"]
    assert [c["name"] for c in data] == DEFAULT_CATEGORIES
    assert [c["id"] for c in data] == list(range(1, len(DEFAULT_CATEGORIES) + 1))


def test_list_nutrients(client):
    response = client.get("/nutrients")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data and all(set(n) == {"id", "name", "unit", "calories_per_unit"} for n in data)
    by_id = {n["id"]: n for n in data}
    assert by_id[1]["name"] == "Proteinas" and by_id[1]["calories_per_unit"] == 4.0
    assert by_id[3]["name"] == "Gorduras" and by_id[3]["calories_per_unit"] == 9.0


def test_list_micronutrients_by_food(client, db):
    response = client.get("/nutrients/1")
    assert response.status_code == 200
    items = response.json()
    macro_ids = {1, 2, 3, 10, 11, 12}
    expected = {a.nutrient_id for a in db.query(FoodNutrientAssociation).filter_by(food_id=1)} - macro_ids
    assert {i["nutrient_id"] for i in items} == expected
    assert all(i["food_id"] == 1 for i in items)
    assert client.get("/nutrients/999999").json() == []
    assert client.get("/nutrients/abc").status_code == 422


def test_every_reference_food_exists(db):
    assert db.query(Food).filter(Food.user_id.is_(None)).count() == 25
