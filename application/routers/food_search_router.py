from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from ..models import application_models as models
from typing import Annotated, Dict, List
from shared.database import engine, get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix="/food_search", tags=["food_search"])

class FoodBase(BaseModel):
    food_name: str
    category_name: str
    brand_id_FK: int
    food_nutrient_type: List[str]
    food_nutrient_amount: List[float]
    food_calories: float
    food_weight_g_ml: float

class BrandBase(BaseModel): 
    brand_name: str

class MealBase(BaseModel):
    meal_name: str
    user_id_FK2: int
    meal_items: List[str]
    meal_calories: float = 0.0
    meal_nutrients: Dict[str, float] = Field(default_factory=dict)
    consumed_at: str

models.Base.metadata.create_all(bind=engine)

db_dependency = Annotated[Session, Depends(get_db)]

@router.get("/search")
def search_food(food_name: str, db: db_dependency):
    db_food_search = db.query(models.Food).filter(models.Food.food_name.ilike(f"%{food_name}%")).all()

    if not db_food_search:
        raise HTTPException(status_code=404, detail="Food not found")
    
    return db_food_search


@router.post("/add_food")
# def food_nutrient_association(db: db_dependency, food: FoodBase):
#     db_food = db.query(models.Food).filter(models.Food.food_name.ilike(f"%{food.food_name}%")).first()

#     if db_food is not None:
#         for item in food.food_nutrient_type:
            # db_nutrient = db.query(models.Nutrient).filter(models.Nutrient.nutrient_name.ilike(f"%{item}%")).first()
            # if db_nutrient:
            #     db_food.food_nutrient_rl.append(db_nutrient)


def add_food(food: FoodBase, db: db_dependency):
    db_food = models.Food(
        food_name = food.food_name,
        category_name = food.category_name,
        brand_id_FK = food.brand_id_FK,
        food_nutrient_type = food.food_nutrient_type,
        food_nutrient_amount = food.food_nutrient_amount,
        food_calories = food.food_calories,
        food_weight_g_ml = food.food_weight_g_ml
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

    for item in meal.meal_items:
        db_food = db.query(models.Food).filter(models.Food.food_name.ilike(f"%{item}%")).first()
        if db_food:
            total_calories += db_food.food_calories or 0.0

            nutrient_types = db_food.food_nutrient_type or []
            nutrient_amounts = db_food.food_nutrient_amount or []

            for nutrient_type, nutrient_amount in zip(nutrient_types, nutrient_amounts):
                total_nutrients[nutrient_type] = (
                    total_nutrients.get(nutrient_type, 0.0) + (nutrient_amount or 0.0)
                )

    meal.meal_calories = total_calories
    meal.meal_nutrients = total_nutrients

    return add_meal(meal, db)


def add_meal(meal: MealBase, db: db_dependency, ):
    db_meal = models.Meal(
        meal_name = meal.meal_name,
        user_id_FK2 = meal.user_id_FK2,
        meal_items = meal.meal_items,
        meal_calories = meal.meal_calories,
        meal_nutrients = meal.meal_nutrients,
        consumed_at = meal.consumed_at
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
