"""Food search and meal management endpoints."""

from datetime import datetime
import os
from typing import Annotated, Any, Dict, List, Optional, Union
from unicodedata import normalize

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from shared.database import get_db
from application.models.application_models import CreatedFood, Nutrient, Food, Brand, Category, Meal, User, Allergen, FoodNutrientAssociation, AllergenFoodAssociation, MealFoodAssociation, UserAllergenAssociation, MealFoodAssociation, CreatedFoodNutrientAssociation, CreatedFoodAllergenAssociation
from application.models.return_model import ReturnModel, ReturnException


router = APIRouter(tags=["food search"])

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")  # Default to localhost if not set

# region Schemas

class NutrientAmount(BaseModel):
    """TypedDict for nutrient amount input, allowing flexible formats."""
    id: int
    amount: float


class PostCreatedFoodBodyRequest(BaseModel):
    """Base model for food creation."""

    model_config = ConfigDict(extra="forbid")

    name: str
    category_id: Optional[int] = None
    brand_id: Optional[int] = None
    nutrients: List[NutrientAmount] = Field(default_factory=list)
    allergen_ids: List[int] = Field(default_factory=list)


class PostCreateBrandBodyRequest(BaseModel):
    """Base model for brand creation."""
    name: str


class PostCreateMealBodyRequest(BaseModel):
    """Base model for meal creation."""
    model_config = ConfigDict(extra="forbid")

    name: str
    consumed_at: datetime
    # calories: float = 0.0
    # weight_g: float
    list_foods_ids: List[int] = Field(default_factory=list)
    list_foods_weights: List[float] = Field(default_factory=list)
    saved_meal: bool = False

    @field_validator("consumed_at")
    def parse_consumed_at(cls, value):
        """Ensure consumed_at is a datetime object."""
        if isinstance(value, str):
            try:
                return datetime.strptime(value, "%H:%M")
            except ValueError:
                raise ValueError("consumed_at must be in H:M format")
        return value

# region Setup

DbDependency = Annotated[Session, Depends(get_db)]

# region Helpers

def normalize_text(value: str) -> str:
    """Normalize text for consistent comparisons."""
    return normalize("NFKD", value.strip().lower()).encode("ascii", "ignore").decode("ascii")


def get_nutrient_by_identifier(db: Session, nutrient_identifier: Union[int, str]):
    """Fetch a nutrient by its ID or name. If a string is provided, it will be normalized for comparison."""
    if isinstance(nutrient_identifier, int):
        return db.query(Nutrient).filter(Nutrient.id == nutrient_identifier).first()

    if isinstance(nutrient_identifier, str) and nutrient_identifier.isdigit():
        return db.query(Nutrient).filter(Nutrient.id == int(nutrient_identifier)).first()

    normalized_identifier = normalize_text(nutrient_identifier)
    nutrients = db.query(Nutrient).all()
    return next(
        (n for n in nutrients if normalize_text(n.name) == normalized_identifier),
        None,
    )


def parse_nutrient_amount(value: Any, nutrient: Nutrient) -> float:
    """Parse nutrient amount from various formats, ensuring it returns a float."""
    if value is None:
        return 0.0

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        try:
            return float(value.replace(",", "."))
        except ValueError:
            return 0.0

    if isinstance(value, dict):
        possible_keys = (
            str(nutrient.id),
            nutrient.name,
            normalize_text(nutrient.name),
            "amount",
            "value",
        )
        for key in possible_keys:
            if key in value:
                return parse_nutrient_amount(value[key], nutrient)
        return 0.0

    if isinstance(value, list):
        if len(value) == 1:
            return parse_nutrient_amount(value[0], nutrient)
        return 0.0

    return 0.0


def get_food_nutrients_by_weight(db: Session, food_id: int, weight: float):
    """Fetches the nutrients and their amounts for a given food item, adjusted for a specific weight."""
    food_nutrient = FoodNutrientAssociation.__table__

    # join Nutrient with the association table and return (Nutrient, amount)
    nutrients_with_amounts = (
        db.query(
            Nutrient,
            food_nutrient.c.amount,
        )
        .join(
            food_nutrient,
            Nutrient.id == food_nutrient.c.nutrient_id,
        )
        .filter(food_nutrient.c.food_id == food_id)
        .all()
    )

    # Adjust amounts based on the provided weight
    adjusted_nutrients = []
    for nutrient, amount in nutrients_with_amounts:
        adjusted_amount = (amount * weight) / 100.0  # Assuming the original amount is per 100g
        adjusted_nutrients.append((nutrient, adjusted_amount))

    return {
        "nutrients": [
            {
                "nutrient_id": nutrient.id,
                "name": nutrient.name,
                "amount": adjusted_amount,
                "unit": nutrient.unit
            }
            for nutrient, adjusted_amount in adjusted_nutrients
        ]
    }


def get_food_nutrients(db: Session, food_id: int) -> List[Any]:
    """Fetches the nutrients and their amounts for a given food item from the association table."""
    food_nutrient = FoodNutrientAssociation.__table__

    # join Nutrient with the association table and return (Nutrient, amount)
    return (
        db.query(
            Nutrient,
            food_nutrient.c.amount,
        )
        .join(
            food_nutrient,
            Nutrient.id == food_nutrient.c.nutrient_id,
        )
        .filter(food_nutrient.c.food_id == food_id)
        .all()
    )


def calculate_meal_totals(db: Session, meal: "PostCreateMealBodyRequest"):
    """Validates the meal foods/weights and returns (foods, total_calories, total_nutrients),
    scaling each food's per-100g nutrient amounts to its consumed weight."""

    if not meal.list_foods_ids:
        raise HTTPException(status_code=400, detail="At least one food ID must be provided")

    if len(meal.list_foods_weights) != len(meal.list_foods_ids):
        raise HTTPException(
            status_code=400,
            detail="list_foods_weights must have the same length as list_foods_ids"
        )

    if any(weight <= 0 for weight in meal.list_foods_weights):
        raise HTTPException(status_code=400, detail="All food weights must be greater than zero")

    total_calories = 0.0
    total_nutrients: Dict[str, float] = {}
    foods: List[Food] = []

    for food_id, food_weight in zip(meal.list_foods_ids, meal.list_foods_weights):
        food = db.query(Food).filter(Food.id == food_id).first()

        if food is None:
            raise HTTPException(status_code=400, detail=f"Food_id: {food_id} dont exist")

        foods.append(food)

        for nutrient, nutrient_amount in get_food_nutrients(db, food.id):
            amount_per_100g = parse_nutrient_amount(nutrient_amount, nutrient)
            # Nutrient amounts are stored per 100g; scale them to the consumed weight
            adjusted_amount = amount_per_100g * food_weight / 100.0
            total_nutrients[nutrient.name] = total_nutrients.get(nutrient.name, 0.0) + adjusted_amount
            total_calories += adjusted_amount * (nutrient.calories_per_unit or 0.0)

    return foods, total_calories, total_nutrients

# Função integrada no list_foods para buscar os alérgenos do usuário para um alimento específico
# def get_user_allergens_by_food(user_id: int, food_id: int, db: DbDependency):
#     """Retrieve a user's allergens by their ID and a specific food ID."""
#     db_user = db.query(User).filter(User.id == user_id).first()
#     if db_user is None:
#         raise HTTPException(status_code=404, detail="User not found")

#     # Assuming you have a relationship set up between User and Allergen
#     allergens = (
#     db.query(Allergen)
#     .join(UserAllergenAssociation, UserAllergenAssociation.allergen_id == Allergen.id)
#     .join(AllergenFoodAssociation, AllergenFoodAssociation.allergen_id == Allergen.id)
#     .filter(UserAllergenAssociation.user_id == user_id)
#     .filter(AllergenFoodAssociation.food_id == food_id)
#     .all()
# )
#     return allergens

# region Foods

@router.get("/foods")
def list_foods(db: DbDependency, user_id: int, name: Optional[str] = None):
    """Lista alimentos e informa se o usuario e alergico a cada um."""

    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    query = db.query(Food)
    if name:
        query = query.filter(Food.name.ilike(f"%{name}%"))

    foods = query.order_by(Food.id).all()

    allergic_food_ids = {
        food_id
        for (food_id,) in (
            db.query(CreatedFoodAllergenAssociation.created_food_id)
            .join(
                UserAllergenAssociation,
                UserAllergenAssociation.allergen_id == CreatedFoodAllergenAssociation.allergen_id,
            )
            .filter(UserAllergenAssociation.user_id == user_id)
            .all()
        )
    }

    return [
        {
            "id": food.id,
            "name": food.name,
            "category_id": food.category_id,
            "brand_id": food.brand_id,
            "nutrients": [
                {
                    "id": nutrient.id,
                    "name": nutrient.name,
                    "amount": assoc.amount,
                    "unit": nutrient.unit,
                    "calories_per_unit": nutrient.calories_per_unit,
                }
                for nutrient, assoc in (
                    db.query(Nutrient, FoodNutrientAssociation)
                    .join(FoodNutrientAssociation, FoodNutrientAssociation.nutrient_id == Nutrient.id)
                    .filter(FoodNutrientAssociation.food_id == food.id)
                    .all()
                )
            ],
            "image": f"{BASE_URL}/images/alimentos/{food.image_url}" if food.image_url else None,
            "user_allergic": food.id in allergic_food_ids,
            "description": food.description
        }
        for food in foods
    ]


@router.get("/foods/{food_id}")
def list_created_foods(db: DbDependency, user_id: int):
    """Lista alimentos criados pelo usuário e informa se o usuario e alergico a cada um."""

    db_user = db.query(User).filter(User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    created_food = db.query(CreatedFood).filter(CreatedFood.user_id == user_id).first()
    if created_food is None:
        raise HTTPException(status_code=404, detail="Created food not found")

    allergic_food_ids = {
        food_id
        for (food_id,) in (
            db.query(CreatedFoodAllergenAssociation.created_food_id)
            .join(
                UserAllergenAssociation,
                UserAllergenAssociation.allergen_id == CreatedFoodAllergenAssociation.allergen_id,
            )
            .filter(UserAllergenAssociation.user_id == user_id)
            .all()
        )
    }

    return {
        "id": created_food.id,
        "name": created_food.name,
        "category_id": created_food.category_id,
        "brand_id": created_food.brand_id,
        "nutrients": [
            {
                "id": nutrient.id,
                "name": nutrient.name,
                "amount": assoc.amount,
                "unit": nutrient.unit,
                "calories_per_unit": nutrient.calories_per_unit,
            }
            for nutrient, assoc in (
                db.query(Nutrient, CreatedFoodNutrientAssociation)
                .join(CreatedFoodNutrientAssociation, CreatedFoodNutrientAssociation.nutrient_id == Nutrient.id)
                .filter(CreatedFoodNutrientAssociation.created_food_id == created_food.id)
                .all()
            )
        ],
        "image": f"{BASE_URL}/images/alimentos/{created_food.image_url}" if created_food.image_url else None,
        "user_allergic": created_food.id in allergic_food_ids,
        "description": created_food.description
    }


@router.post("/foods")
def create_food(food: PostCreatedFoodBodyRequest, db: DbDependency, user_id: int):
    """Cadastra um novo alimento com seus nutrientes."""
    try:
        existing = db.query(CreatedFood).filter(CreatedFood.name.ilike(f"{food.name}")).first()

        if existing is not None:
            raise HTTPException(status_code=400, detail="Food already exists")

        # Create food with only column fields
        new_food = CreatedFood(
            name=food.name,
            user_id=user_id,
            category_id=food.category_id,
            brand_id=food.brand_id,
        )

        db.add(new_food)
        db.flush()

        for allergen_id in food.allergen_ids:
            allergen = db.query(Allergen).filter(Allergen.id == allergen_id).first()

            if allergen is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Allergen with id '{allergen_id}' not found",
                )

            assoc = CreatedFoodAllergenAssociation(
                allergen_id=allergen.id,
                created_food_id=new_food.id,
            )
            db.add(assoc)

        # create association mapped instances
        for nutrient_item in food.nutrients:
            nutrient = get_nutrient_by_identifier(db, nutrient_item.id)

            if nutrient is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Nutrient '{nutrient_item.id}' not found",
                )

            assoc = CreatedFoodNutrientAssociation(
                created_food_id=new_food.id,
                nutrient_id=nutrient.id,
                amount=nutrient_item.amount,
            )
            db.add(assoc)

        db.commit()
        db.refresh(new_food)

        return ReturnModel(
            message="Food created successfully",
            data=new_food,
            success=True
        )

    except Exception as err:
        db.rollback()
        raise ReturnException(
            message=str(err),
            success=False,
        ) from err


@router.patch("/foods/{food_id}")
def update_food(food_id: int, food: PostCreatedFoodBodyRequest, db: DbDependency, user_id: int):
    """Atualiza um alimento existente com seus nutrientes."""
    try:
        existing_food = db.query(CreatedFood).filter(CreatedFood.id == food_id).first()

        if existing_food is None:
            raise HTTPException(status_code=404, detail="Food not found")

        if existing_food.user_id != user_id:
            raise HTTPException(status_code=403, detail="You do not have permission to update this food")

        # Update food fields
        existing_food.name = food.name
        existing_food.category_id = food.category_id
        existing_food.brand_id = food.brand_id

        # Clear existing associations
        db.query(CreatedFoodNutrientAssociation).filter(
            CreatedFoodNutrientAssociation.created_food_id == food_id
        ).delete()

        db.query(CreatedFoodAllergenAssociation).filter(
            CreatedFoodAllergenAssociation.created_food_id == food_id
        ).delete()

        # Create new associations for allergens
        for allergen_id in food.allergen_ids:
            allergen = db.query(Allergen).filter(Allergen.id == allergen_id).first()

            if allergen is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Allergen with id '{allergen_id}' not found",
                )

            assoc = CreatedFoodAllergenAssociation(
                allergen_id=allergen.id,
                created_food_id=existing_food.id,
            )
            db.add(assoc)

        # Create new associations for nutrients
        for nutrient_item in food.nutrients:
            nutrient = get_nutrient_by_identifier(db, nutrient_item.id)

            if nutrient is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Nutrient '{nutrient_item.id}' not found",
                )

            assoc = CreatedFoodNutrientAssociation(
                created_food_id=existing_food.id,
                nutrient_id=nutrient.id,
                amount=nutrient_item.amount,
            )
            db.add(assoc)

        db.commit()
        db.refresh(existing_food)

        return ReturnModel(
            message="Food updated successfully",
            data=existing_food,
            success=True
        )

    except Exception as err:
        db.rollback()
        raise ReturnException(
            message=str(err),
            success=False,
        ) from err


@router.delete("/foods/{food_id}")
def delete_food(food_id: int, db: DbDependency, user_id: int):
    """Deleta um alimento existente."""
    try:
        existing_food = db.query(CreatedFood).filter(CreatedFood.id == food_id).first()

        if existing_food is None:
            raise HTTPException(status_code=404, detail="Food not found")

        if existing_food.user_id != user_id:
            raise HTTPException(status_code=403, detail="You do not have permission to delete this food")

        # Delete associations first
        db.query(CreatedFoodNutrientAssociation).filter(
            CreatedFoodNutrientAssociation.created_food_id == food_id
        ).delete()

        db.query(CreatedFoodAllergenAssociation).filter(
            CreatedFoodAllergenAssociation.created_food_id == food_id
        ).delete()

        # Delete the food itself
        db.delete(existing_food)
        db.commit()

        return ReturnModel(
            message="Food deleted successfully",
            success=True
        )

    except Exception as err:
        db.rollback()
        raise ReturnException(
            message=str(err),
            success=False,
        ) from err

# region Brands

@router.get("/brands")
def search_brands(brand_name: str, db: DbDependency):
    """Busca marcas pelo nome (parcial)."""
    brands = db.query(Brand).filter(Brand.name.ilike(f"%{brand_name}%")).all()
    if not brands:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brands

@router.patch("/brands/{brand_id}")
def update_brand(brand_id: int, brand: PostCreateBrandBodyRequest, db: DbDependency):
    """Atualiza uma marca existente."""
    existing_brand = db.query(Brand).filter(Brand.id == brand_id).first()
    if existing_brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")

    existing_brand.name = brand.name
    db.commit()
    db.refresh(existing_brand)
    return existing_brand

@router.delete("/brands/{brand_id}")
def delete_brand(brand_id: int, db: DbDependency):
    """Deleta uma marca existente."""
    existing_brand = db.query(Brand).filter(Brand.id == brand_id).first()
    if existing_brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")

    db.delete(existing_brand)
    db.commit()
    return {"message": "Brand deleted successfully"}

@router.post("/brands")
def create_brand(brand: PostCreateBrandBodyRequest, db: DbDependency):
    """Cadastra uma nova marca."""
    existing = db.query(Brand).filter(Brand.name.ilike(f"%{brand.name}%")).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail="Brand already exists")

    new_brand = Brand(
        name = brand.name
    )

    db.add(new_brand)
    db.commit()
    db.refresh(new_brand)
    return new_brand


# region Categories

@router.get("/categories")
def list_categories(db: DbDependency):
    """Lista todas as categorias de alimentos."""
    return db.query(Category).order_by(Category.id).all()


# region Nutrients

@router.get("/nutrients")
def list_all_nutrients(db: DbDependency):
    """Lista todos os nutrientes disponíveis."""
    return db.query(Nutrient).order_by(Nutrient.id).all()


@router.get("/nutrients/{food_id}")
def list_micro_nutrients(food_id: int, db: DbDependency):
    """Lista todos os nutrientes disponíveis."""
    return db.query(FoodNutrientAssociation).join(Nutrient).filter(
        (Nutrient.name != "Proteinas") &
        (Nutrient.name != "Carboidratos") &
        (Nutrient.name != "Gorduras")
    ).filter(
        FoodNutrientAssociation.food_id == food_id
    ).all()

# region Meals

@router.get("/meals")
def list_user_meals(user_id: int, db: DbDependency):
    """Busca uma refeição pelo ID do usuário."""
    meals = db.query(Meal).filter(Meal.user_id == user_id).all()
    if not meals:
        raise HTTPException(status_code=404, detail="Meal not found")
    result = []
    for meal in meals:
        foods = (
            db.query(Food)
            .join(MealFoodAssociation, MealFoodAssociation.food_id == Food.id)
            .filter(MealFoodAssociation.meal_id == meal.id)
            .all()
        )

        for weight in db.query(MealFoodAssociation.food_weight_g).filter(MealFoodAssociation.meal_id == meal.id).all():
            weight_value = weight[0]

        result.append({
            "id": meal.id,
            "name": meal.name,
            "calories": meal.calories,
            "weight_g": meal.weight_g,
            "consumed_at": meal.consumed_at,
            "user_id": meal.user_id,
            "foods": [
                {
                    "id": food.id,
                    "name": food.name,
                    "category_id": food.category_id,
                    "brand_id": food.brand_id,
                    "weight_g": weight_value,
                    "image": f"{BASE_URL}/images/alimentos/{food.image_url}" if food.image_url else None,
                }
                for food in foods
            ],
        })
    return result


@router.post(
    "/meals",
    responses={
        200: {"model": Meal, "description": "Meal created successfully"},
    }
)
def create_meal(meal: PostCreateMealBodyRequest, db: DbDependency, user_id: int):
    """Calcula calorias/nutrientes e cadastra uma refeição."""

    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        raise HTTPException(status_code=400, detail=f"User_id: {user_id} dont exist")

    foods, total_calories, _ = calculate_meal_totals(db, meal)

    total_weight = sum(meal.list_foods_weights)

    new_meal = Meal(
        name = meal.name,
        user_id = user.id,
        consumed_at = meal.consumed_at,
        calories = total_calories,
        weight_g = total_weight,
        saved_meal = meal.saved_meal
    )

    if new_meal.weight_g <= 0:
        raise HTTPException(status_code=400, detail="Invalid meal weight")

    if new_meal.saved_meal == True:
        db.add(new_meal)
        db.flush()

        for weight, food in zip(meal.list_foods_weights, foods):
            assoc = MealFoodAssociation(
                meal_id=new_meal.id,
                food_id=food.id,
                food_weight_g=weight
            )
            db.add(assoc)

        db.commit()
        db.refresh(new_meal)

    return new_meal


@router.patch("/meals/{meal_id}/{user_id}", responses={200: {"model": Meal, "description": "Meal updated successfully"}})
def update_meal(meal_id: int, user_id: int, meal: PostCreateMealBodyRequest, db: DbDependency):
    """Atualiza uma refeição existente."""

    updated_meal = db.query(Meal).filter(Meal.id == meal_id).filter(Meal.user_id == user_id).first()

    if not updated_meal:
        raise HTTPException(status_code=404, detail="Meal not found")

    total_weight = sum(meal.list_foods_weights)
    if total_weight <= 0:
        raise HTTPException(status_code=400, detail="Invalid meal weight")

    # Validate and recalculate before touching the database
    foods, total_calories, _ = calculate_meal_totals(db, meal)

    updated_meal.name = meal.name
    updated_meal.consumed_at = meal.consumed_at
    updated_meal.calories = total_calories
    updated_meal.weight_g = total_weight
    updated_meal.saved_meal = meal.saved_meal

    db.query(MealFoodAssociation).filter(MealFoodAssociation.meal_id == updated_meal.id).delete()

    for food, food_weight in zip(foods, meal.list_foods_weights):
        db.add(MealFoodAssociation(
            meal_id=updated_meal.id,
            food_id=food.id,
            food_weight_g=food_weight
        ))

    db.commit()
    db.refresh(updated_meal)
    return updated_meal

@router.delete("/meals/{meal_id}/{user_id}", responses={200: {"model": Meal, "description": "Meal deleted successfully"}})
def delete_meal(meal_id: int, user_id: int, db: DbDependency):
    """Deleta uma refeição existente."""

    meal_to_delete = db.query(Meal).filter(Meal.id == meal_id).filter(Meal.user_id == user_id).first()

    if not meal_to_delete:
        raise HTTPException(status_code=404, detail="Meal not found")

    deleted_associations = db.query(MealFoodAssociation).filter(MealFoodAssociation.meal_id == meal_to_delete.id).all()
    for assoc in deleted_associations:
        db.delete(assoc)

    db.delete(meal_to_delete)
    db.commit()
    return {"message": "Meal deleted successfully"}