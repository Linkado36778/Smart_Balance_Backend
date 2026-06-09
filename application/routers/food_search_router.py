from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from ..models import application_models as models
from typing import Annotated, Dict, List, Optional
from shared.database import engine, get_db
from sqlalchemy.orm import Session
from datetime import datetime
from unicodedata import normalize

router = APIRouter(prefix="/food_search", tags=["food_search"])

class FoodBase(BaseModel):
    food_name: str
    category_name: str
    brand_id_FK: Optional[int] = None
    food_nutrient_type: List[str]
    food_nutrient_amount: List[float]

class BrandBase(BaseModel): 
    brand_name: str

class MealBase(BaseModel):
    meal_name: str
    user_id_FK2: int
    meal_items: List[str]
    meal_items_weight_g: List[float]
    meal_items_calories: List[float] = Field(default_factory=list)
    meal_items_nutrients: List[List[str]] = Field(default_factory=list)
    meal_items_nutrient_amounts: List[Dict[str, float]] = Field(default_factory=list)
    meal_calories: float = 0.0
    meal_nutrients: Dict[str, float] = Field(default_factory=dict)
    consumed_at: str

models.Base.metadata.create_all(bind=engine)

db_dependency = Annotated[Session, Depends(get_db)]

@router.get("/search_food")
def search_food(food_name: str, db: db_dependency):
    db_food_search = db.query(models.Food).filter(models.Food.food_name.ilike(f"%{food_name}%")).all()

    if not db_food_search:
        raise HTTPException(status_code=404, detail="Food not found")
    
    return db_food_search


@router.post("/add_food")
def add_food(food: FoodBase, db: db_dependency):
    db_food = models.Food(
        food_name = food.food_name,
        category_name = food.category_name,
        brand_id_FK = food.brand_id_FK,
        food_nutrient_type = food.food_nutrient_type,
        food_nutrient_amount = food.food_nutrient_amount,
    )

    db_food_create = db.query(models.Food).filter(models.Food.food_name.ilike(f"%{food.food_name}%")).first()

    if db_food_create is not None:
        raise HTTPException(status_code=400, detail="Food already exists")
    
    else:
        db.add(db_food)
        db.commit()
        db.refresh(db_food)

    return db_food


@router.get("/search_brand")
def search_brand(brand_name: str, db: db_dependency):
    db_brand_search = db.query(models.Brand).filter(models.Brand.brand_name.ilike(f"%{brand_name}%")).all()

    if not db_brand_search:
        raise HTTPException(status_code=404, detail="Brand not found")
    
    return db_brand_search
    

@router.post("/add_brand")
def add_brand(brand: BrandBase, db: db_dependency):
    db_brand = models.Brand(
        brand_name = brand.brand_name
    )

    db_brand_create = db.query(models.Brand).filter(models.Brand.brand_name.ilike(f"%{brand.brand_name}%")).first()

    if db_brand_create is not None:
        raise HTTPException(status_code=400, detail="Brand already exists")
    
    else:
        db.add(db_brand)
        db.commit()
        db.refresh(db_brand)

    return db_brand


@router.post("/add_meal")
def meal_calories_nutrient_calculator(meal: MealBase, db: db_dependency):
    total_calories = 0.0
    total_nutrients: Dict[str, float] = {}
    meal_items_calories = []
    meal_items_nutrients = []
    meal_items_nutrient_amounts = []

    calories_by_nutrient = {
        "carboidrato": 4.0,
        "carboidratos": 4.0,
        "carbohydrate": 4.0,
        "carbohydrates": 4.0,
        "proteina": 4.0,
        "proteinas": 4.0,
        "protein": 4.0,
        "proteins": 4.0,
        "gordura": 9.0,
        "gorduras": 9.0,
        "lipidio": 9.0,
        "lipidios": 9.0,
        "fat": 9.0,
        "fats": 9.0,
    }

    if len(meal.meal_items) != len(meal.meal_items_weight_g):
        raise HTTPException(
            status_code=400,
            detail="meal_items e meal_items_weight_g devem ter o mesmo tamanho"
        )

    for item, item_weight_g in zip(meal.meal_items, meal.meal_items_weight_g):
        db_food = db.query(models.Food).filter(models.Food.food_name.ilike(f"%{item}%")).first()
        if db_food:
            nutrient_types = db_food.food_nutrient_type or []
            nutrient_amounts = db_food.food_nutrient_amount or []
            item_nutrients = []
            item_nutrient_amounts: Dict[str, float] = {}
            item_calories = 0.0
            weight_ratio = item_weight_g / 100

            for nutrient_type, nutrient_amount in zip(nutrient_types, nutrient_amounts):
                consumed_amount = (nutrient_amount or 0.0) * weight_ratio
                item_nutrients.append(nutrient_type)
                item_nutrient_amounts[nutrient_type] = consumed_amount
                total_nutrients[nutrient_type] = total_nutrients.get(nutrient_type, 0.0) + consumed_amount

                nutrient_key = normalize("NFKD", nutrient_type.strip().lower()).encode("ascii", "ignore").decode("ascii")
                item_calories += consumed_amount * calories_by_nutrient.get(nutrient_key, 0.0)

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

    return add_meal(meal, db)


def add_meal(meal: MealBase, db: db_dependency, ):
    consumed_at = datetime.strptime(meal.consumed_at, "%d/%m/%Y").date()

    db_meal = models.Meal(
        meal_name = meal.meal_name,
        user_id_FK2 = meal.user_id_FK2,
        meal_items = meal.meal_items,
        consumed_at = consumed_at,
        meal_items_calories = meal.meal_items_calories,
        meal_items_nutrients = meal.meal_items_nutrients,
        meal_calories = meal.meal_calories,
        meal_nutrients = meal.meal_nutrients,
        meal_items_nutrient_amounts = meal.meal_items_nutrient_amounts,
        meal_items_weight_g = meal.meal_items_weight_g,
        weight_g = sum(meal.meal_items_weight_g),
        
    )

    db.add(db_meal)
    db.commit()
    db.refresh(db_meal)

    return db_meal


@router.get("/get_meal")
def get_meal(meal_id: int, db: db_dependency):
    db_meal = db.query(models.Meal).filter(models.Meal.meal_id == meal_id).first()

    if not db_meal:
        raise HTTPException(status_code=404, detail="Meal not found")

    return db_meal
