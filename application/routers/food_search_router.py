from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from ..models import application_models as models
from typing import Annotated, Dict, List, Optional, Union
from shared.database import get_db, initialize_database
from sqlalchemy.orm import Session
from datetime import datetime
from unicodedata import normalize

router = APIRouter(prefix="/", tags=["food_search"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class FoodBase(BaseModel):
    food_name: str
    category_id_FK: Optional[int] = None
    brand_id_FK: Optional[int] = None
    food_nutrient_type: List[Union[int, str]]
    food_nutrient_amount: List[float]


class BrandBase(BaseModel):
    brand_name: str


class MealBase(BaseModel):
    meal_name: str
    user_id_FK2: int
    meal_items: List[str]
    meal_items_weight_g: List[float]
    consumed_at_date: str
    consumed_at_time: str = Field(default_factory=lambda: datetime.now().strftime("%H:%M"))
    meal_items_calories: List[float] = Field(default_factory=list)
    meal_items_nutrients: List[List[str]] = Field(default_factory=list)
    meal_items_nutrient_amounts: List[Dict[str, float]] = Field(default_factory=list)
    meal_calories: float = 0.0
    meal_nutrients: Dict[str, float] = Field(default_factory=dict)


# ── Setup ─────────────────────────────────────────────────────────────────────

initialize_database()

db_dependency = Annotated[Session, Depends(get_db)]


# ── Helpers ───────────────────────────────────────────────────────────────────

def normalize_text(value: str) -> str:
    return normalize("NFKD", value.strip().lower()).encode("ascii", "ignore").decode("ascii")


def get_nutrient_by_identifier(db: Session, nutrient_identifier: Union[int, str]):
    if isinstance(nutrient_identifier, int):
        return db.query(models.Nutrient).filter(models.Nutrient.nutrient_id == nutrient_identifier).first()

    if isinstance(nutrient_identifier, str) and nutrient_identifier.isdigit():
        return db.query(models.Nutrient).filter(models.Nutrient.nutrient_id == int(nutrient_identifier)).first()

    normalized_identifier = normalize_text(nutrient_identifier)
    nutrients = db.query(models.Nutrient).all()
    return next(
        (n for n in nutrients if normalize_text(n.nutrient_name) == normalized_identifier),
        None,
    )


# ── Foods ─────────────────────────────────────────────────────────────────────

@router.get("/foods")
def get_foods(name: Optional[str] = None, food_id: Optional[int] = None, db: db_dependency = None):
    """Lista todos os alimentos. Filtra por nome (parcial) ou por food_id."""
    query = db.query(models.Food)

    if food_id is not None:
        food = query.filter(models.Food.food_id == food_id).first()
        if not food:
            raise HTTPException(status_code=404, detail="Food not found")
        return food

    if name:
        query = query.filter(models.Food.food_name.ilike(f"%{name}%"))

    return query.order_by(models.Food.food_id).all()


@router.post("/foods")
def add_food(food: FoodBase, db: db_dependency):
    """Cadastra um novo alimento com seus nutrientes."""
    if len(food.food_nutrient_type) != len(food.food_nutrient_amount):
        raise HTTPException(
            status_code=400,
            detail="food_nutrient_type e food_nutrient_amount devem ter o mesmo tamanho",
        )

    nutrients = []
    nutrient_ids = []
    for nutrient_identifier in food.food_nutrient_type:
        nutrient = get_nutrient_by_identifier(db, nutrient_identifier)
        if not nutrient:
            raise HTTPException(
                status_code=400,
                detail=f"Nutriente '{nutrient_identifier}' nao encontrado",
            )
        nutrients.append(nutrient)
        nutrient_ids.append(nutrient.nutrient_id)

    existing = db.query(models.Food).filter(models.Food.food_name.ilike(f"%{food.food_name}%")).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail="Food already exists")

    db_food = models.Food(
        food_name=food.food_name,
        category_id_FK=food.category_id_FK,
        brand_id_FK=food.brand_id_FK,
        food_nutrient_type=nutrient_ids,
        food_nutrient_amount=food.food_nutrient_amount,
    )
    db_food.food_nutrient_rl = nutrients

    db.add(db_food)
    db.commit()
    db.refresh(db_food)
    return db_food


# ── Brands ────────────────────────────────────────────────────────────────────

@router.get("/brands")
def get_brands(brand_name: str, db: db_dependency):
    """Busca marcas pelo nome (parcial)."""
    brands = db.query(models.Brand).filter(models.Brand.brand_name.ilike(f"%{brand_name}%")).all()
    if not brands:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brands


@router.post("/brands")
def add_brand(brand: BrandBase, db: db_dependency):
    """Cadastra uma nova marca."""
    existing = db.query(models.Brand).filter(models.Brand.brand_name.ilike(f"%{brand.brand_name}%")).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail="Brand already exists")

    db_brand = models.Brand(brand_name=brand.brand_name)
    db.add(db_brand)
    db.commit()
    db.refresh(db_brand)
    return db_brand


# ── Categories ────────────────────────────────────────────────────────────────

@router.get("/categories")
def get_categories(db: db_dependency):
    """Lista todas as categorias de alimentos."""
    return db.query(models.Category).order_by(models.Category.category_id).all()


# ── Nutrients ─────────────────────────────────────────────────────────────────

@router.get("/nutrients")
def get_nutrients(db: db_dependency):
    """Lista todos os nutrientes disponíveis."""
    return db.query(models.Nutrient).order_by(models.Nutrient.nutrient_id).all()


# ── Meals ─────────────────────────────────────────────────────────────────────

@router.get("/meals")
def get_meal(user_id_FK2: int, db: db_dependency):
    """Busca uma refeição pelo ID do usuário."""
    db_meal = db.query(models.Meal).filter(models.Meal.user_id_FK2 == user_id_FK2).all()
    if not db_meal:
        raise HTTPException(status_code=404, detail="Meal not found")
    return db_meal


@router.post("/meals")
def add_meal(meal: MealBase, db: db_dependency):
    """Calcula calorias/nutrientes e cadastra uma refeição."""
    if len(meal.meal_items) != len(meal.meal_items_weight_g):
        raise HTTPException(
            status_code=400,
            detail="meal_items e meal_items_weight_g devem ter o mesmo tamanho",
        )

    total_calories = 0.0
    total_nutrients: Dict[str, float] = {}
    meal_items_calories = []
    meal_items_nutrients = []
    meal_items_nutrient_amounts = []

    for item, item_weight_g in zip(meal.meal_items, meal.meal_items_weight_g):
        db_food = db.query(models.Food).filter(models.Food.food_name.ilike(f"%{item}%")).first()
        if db_food:
            nutrient_ids = db_food.food_nutrient_type or []
            nutrient_amounts = db_food.food_nutrient_amount or []
            item_nutrients = []
            item_nutrient_amounts: Dict[str, float] = {}
            item_calories = 0.0
            weight_ratio = item_weight_g / 100

            for nutrient_id, nutrient_amount in zip(nutrient_ids, nutrient_amounts):
                nutrient = get_nutrient_by_identifier(db, nutrient_id)
                if not nutrient:
                    continue
                nutrient_name = nutrient.nutrient_name
                consumed_amount = (nutrient_amount or 0.0) * weight_ratio
                item_nutrients.append(nutrient_name)
                item_nutrient_amounts[nutrient_name] = consumed_amount
                total_nutrients[nutrient_name] = total_nutrients.get(nutrient_name, 0.0) + consumed_amount
                item_calories += consumed_amount * (nutrient.nutrient_calories_per_unit or 0.0)

            meal_items_calories.append(item_calories)
            meal_items_nutrients.append(item_nutrients)
            meal_items_nutrient_amounts.append(item_nutrient_amounts)
            total_calories += item_calories
        else:
            meal_items_calories.append(0.0)
            meal_items_nutrients.append([])
            meal_items_nutrient_amounts.append({})

    meal.meal_calories = total_calories
    meal.meal_nutrients = total_nutrients
    meal.meal_items_calories = meal_items_calories
    meal.meal_items_nutrients = meal_items_nutrients
    meal.meal_items_nutrient_amounts = meal_items_nutrient_amounts

    db_meal = models.Meal(
        meal_name=meal.meal_name,
        user_id_FK2=meal.user_id_FK2,
        meal_items=meal.meal_items,
        consumed_at_date=datetime.strptime(meal.consumed_at_date, "%d/%m/%Y").date(),
        consumed_at_time=meal.consumed_at_time,
        meal_items_calories=meal.meal_items_calories,
        meal_items_nutrients=meal.meal_items_nutrients,
        meal_calories=meal.meal_calories,
        meal_nutrients=meal.meal_nutrients,
        meal_items_nutrient_amounts=meal.meal_items_nutrient_amounts,
        meal_items_weight_g=meal.meal_items_weight_g,
        weight_g=sum(meal.meal_items_weight_g),
    )

    db.add(db_meal)
    db.commit()
    db.refresh(db_meal)
    return db_meal
