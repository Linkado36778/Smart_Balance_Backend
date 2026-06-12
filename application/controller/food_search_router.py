"""Food search and meal management endpoints."""

from datetime import datetime
from typing import Annotated, Any, Dict, List, Optional, Union
from unicodedata import normalize

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from shared.database import get_db
from application.models.application_models import Nutrient, Food, Brand, Category, Meal, User, Allergen, FoodNutrientAssociation, AllergenFoodAssociation, MealFoodAssociation
from application.models.return_models import ReturnModel, ReturnException

router = APIRouter(tags=["food search"])

# region Schemas

class NutrientAmount(BaseModel):
    """TypedDict for nutrient amount input, allowing flexible formats."""
    id: int
    amount: float

class PostCreateFoodBodyRequest(BaseModel):
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
    user_id: int
    consumed_at: datetime
    calories: float = 0.0
    weight_g: float = 0.0
    list_foods_ids: List[int] = Field(default_factory=list)

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

# region Foods

@router.get("/foods")
def list_foods(db: DbDependency, name: Optional[str] = None, food_id: Optional[int] = None):
    """Lista todos os alimentos. Filtra por nome (parcial) ou por food_id."""
    query = db.query(Food)

    if food_id is not None:
        food = query.filter(Food.id == food_id).first()
        if not food:
            raise HTTPException(status_code=404, detail="Food not found")
        return food

    if name:
        query = query.filter(Food.name.ilike(f"%{name}%"))

    return query.order_by(Food.id).all()


@router.post("/foods")
def create_food(food: PostCreateFoodBodyRequest, db: DbDependency):
    """Cadastra um novo alimento com seus nutrientes."""
    try:
        existing = db.query(Food).filter(Food.name.ilike(f"{food.name}")).first()

        if existing is not None:
            raise HTTPException(status_code=400, detail="Food already exists")

        # Create food with only column fields
        new_food = Food(
            name=food.name,
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

            assoc = AllergenFoodAssociation(
                allergen_id=allergen.id,
                food_id=new_food.id,
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

            assoc = FoodNutrientAssociation(
                food_id=new_food.id,
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

# region Brands

@router.get("/brands")
def search_brands(brand_name: str, db: DbDependency):
    """Busca marcas pelo nome (parcial)."""
    brands = db.query(Brand).filter(Brand.name.ilike(f"%{brand_name}%")).all()
    if not brands:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brands


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
def list_nutrients(db: DbDependency):
    """Lista todos os nutrientes disponíveis."""
    return db.query(Nutrient).order_by(Nutrient.id).all()


# region Meals

@router.get("/meals")
def list_user_meals(user_id: int, db: DbDependency):
    """Busca uma refeição pelo ID do usuário."""
    db_meal = db.query(Meal).filter(Meal.user_id == user_id).all()
    if not db_meal:
        raise HTTPException(status_code=404, detail="Meal not found")
    return db_meal


@router.post(
    "/meals",
    responses={
        200: {"model": Meal, "description": "Meal created successfully"},
    }
)
def create_meal(meal: PostCreateMealBodyRequest, db: DbDependency):
    """Calcula calorias/nutrientes e cadastra uma refeição."""

    if not meal.list_foods_ids:
        raise HTTPException(status_code=400, detail="At least one food ID must be provided")

    user = db.query(User).filter(User.id == meal.user_id).first()

    if user is None:
        raise HTTPException(status_code=400, detail=f"User_id: {meal.user_id} dont exist")

    total_calories = 0.0
    total_nutrients: Dict[str, float] = {}
    foods: List[Food] = []

    for food_id in meal.list_foods_ids:
        food = db.query(Food).filter(Food.id == food_id).first()

        if food is None:
            raise HTTPException(status_code=400, detail=f"Food_id: {food_id} dont exist")
        
        foods.append(food)

        item_calories = 0.0
        for nutrient, nutrient_amount in get_food_nutrients(db, food.id):
            amount_per_100g = parse_nutrient_amount(nutrient_amount, nutrient)
            total_nutrients[nutrient.name] = total_nutrients.get(nutrient.name, 0.0) + amount_per_100g
            item_calories += amount_per_100g * (nutrient.calories_per_unit or 0.0)

        total_calories += item_calories

    new_meal = Meal(
        name = meal.name,
        user_id = meal.user_id,
        consumed_at = meal.consumed_at,
        calories = total_calories,
        weight_g = meal.weight_g
    )
    db.add(new_meal)
    db.flush()

    for food in foods:
        assoc = MealFoodAssociation(
            meal_id=new_meal.id,
            food_id=food.id,
        )
        db.add(assoc)

    db.commit()
    db.refresh(new_meal)
    return new_meal
